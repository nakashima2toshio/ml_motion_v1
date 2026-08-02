"""本番化・最適化 API（Streamlit 版 `app/views/production.py` に対応）。

    POST /api/production/discover       入力ディレクトリの動画を確認
    POST /api/production/batch          バッチ推論ジョブの起動（202 + job_id）
    GET  /api/production/stream/{id}    進捗（SSE）
    GET  /api/production/result/{id}    結果（マニフェスト）
    POST /api/production/export         モデル変換・量子化
    GET  /api/production/registry-uri   Model Registry の URI

⚠️ この画面はディレクトリや重みのパスを**ユーザー入力**で受け取る。
`core/paths.py` でリポジトリルート配下に限定し、外を指したら 400 を返す
（Streamlit 版はローカル実行専用で無制限だったが、HTTP API では露出が広がるため）。
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.app.core.batch_runner import BatchParams, run_batch_job
from backend.app.core.jobs import Job, job_manager, sse_stream
from backend.app.core.paths import PathNotAllowedError, resolve_user_path, to_display
from backend.app.schemas import (
    BatchRequest,
    DiscoverRequest,
    DiscoverResponse,
    ExportRequest,
    ExportResponse,
    JobAccepted,
    JobStatusResponse,
    RegistryUriResponse,
)
from pipeline.detector import AVAILABLE_MODELS, SEG_MODELS
from pipeline.export_model import EXPORT_FORMATS, quantization_label
from pipeline.registry import STAGES

router = APIRouter(prefix="/api/production", tags=["production"])


@router.post("/discover", response_model=DiscoverResponse)
def discover(request: DiscoverRequest) -> DiscoverResponse:
    """入力ディレクトリ直下の動画を列挙する（📁 入力ディレクトリを確認）。"""
    from pipeline.batch import discover_media  # 依存なし

    directory = _resolve(request.input_dir, must_be_dir=True)
    from pathlib import Path

    files = [to_display(Path(p)) for p in discover_media(str(directory))]
    return DiscoverResponse(input_dir=to_display(directory), files=files, exists=directory.is_dir())


@router.post("/batch", response_model=JobAccepted, status_code=202)
def start_batch(request: BatchRequest) -> JobAccepted:
    """バッチ推論ジョブを起動する。"""
    input_dir = _resolve(request.input_dir, must_exist=True, must_be_dir=True)
    # 出力先はこれから作るので存在チェックはしない（許可ルート内であることだけ確認）。
    output_dir = _resolve(request.output_dir, must_be_dir=True)

    allowed_models = tuple(AVAILABLE_MODELS) + tuple(SEG_MODELS)
    if request.model_name not in allowed_models:
        raise HTTPException(
            status_code=400, detail=f"未知のモデルです: {request.model_name}（候補: {', '.join(allowed_models)}）"
        )

    params = BatchParams(
        input_dir=input_dir,
        output_dir=output_dir,
        model_name=request.model_name,
        conf=request.conf,
        frame_stride=request.frame_stride,
    )
    job = job_manager.start(params, run_batch_job, kind="batch")
    return JobAccepted(job_id=job.job_id)


@router.get("/stream/{job_id}")
def stream_batch(job_id: str) -> StreamingResponse:
    """バッチ推論の進捗（SSE）。"""
    job = _get_job(job_id)

    def events() -> Iterator[str]:
        yield from sse_stream(job)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/result/{job_id}", response_model=JobStatusResponse)
def get_batch_result(job_id: str) -> JobStatusResponse:
    """バッチ推論の結果（成功/失敗件数とマニフェスト）。"""
    job = _get_job(job_id)
    return JobStatusResponse(
        job_id=job.job_id, kind=job.kind, status=job.status, result=job.result, error=job.error
    )


@router.post("/export", response_model=ExportResponse)
def export(request: ExportRequest) -> ExportResponse:
    """モデルを変換・量子化する（🛠 変換を実行）。

    変換は数分かかることがあるが、Streamlit 版と同じ同期呼び出しにしている
    （バッチと違い進捗イベントが取れないため、ジョブ化しても表示は変わらない）。
    """
    from pipeline.export_model import export_model, normalize_format

    weights = _resolve(request.weights, must_exist=True)
    try:
        fmt = normalize_format(request.fmt)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    half = request.quantization == "FP16"
    int8 = request.quantization == "INT8"

    try:
        output = export_model(str(weights), fmt, half=half, int8=int8)
    except Exception as e:  # noqa: BLE001 — Streamlit 版と同じ文言
        raise HTTPException(status_code=500, detail=f"変換に失敗しました: {e}") from e

    from pathlib import Path

    return ExportResponse(
        output_path=to_display(Path(output)),
        fmt=fmt,
        quantization=quantization_label(half, int8),
    )


@router.get("/registry-uri", response_model=RegistryUriResponse)
def registry_uri(
    name: str = Query(default="ml_motion_detector"),
    stage: str = Query(default="Production"),
) -> RegistryUriResponse:
    """Model Registry の URI を組み立てる。"""
    from pipeline.registry import model_uri

    try:
        uri = model_uri(name, stage)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return RegistryUriResponse(uri=uri, stages=list(STAGES), formats=list(EXPORT_FORMATS))


def _resolve(raw: str, *, must_exist: bool = False, must_be_dir: bool = False):
    """ユーザー入力パスを許可ルート内で解決する。外なら 400。"""
    try:
        return resolve_user_path(raw, must_exist=must_exist, must_be_dir=must_be_dir)
    except PathNotAllowedError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _get_job(job_id: str) -> Job:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません（サーバ再起動で失われた可能性）")
    return job
