"""解析 API（Streamlit 版 `app/views/analyze.py` に対応）。

    POST /api/analyze/upload            mp4 アップロード
    POST /api/analyze/run               ▶ Run 解析（202 + job_id）
    GET  /api/analyze/stream/{job_id}   進捗（SSE）
    GET  /api/analyze/result/{job_id}   結果サマリ（検出レコードは含めない）
    GET  /api/analyze/detections/{job_id}?offset=&limit=   検出結果テーブル（ページング）
    GET  /api/analyze/download/{job_id}/{kind}             CSV / JSON / 注釈付き動画
    POST /api/analyze/summary/{job_id}  📝 NL要約（Claude）

エラー文言は Streamlit 版の表示をそのまま踏襲する（マニュアル
`docs/manual/01_analyze.md` のトラブルシュート表と対応させるため）。
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from backend.app.core import storage
from backend.app.core.analyze_runner import AnalyzeParams, run_analyze
from backend.app.core.jobs import Job, job_manager, sse_stream
from backend.app.schemas import (
    AnalyzeRequest,
    AnalyzeSummary,
    DetectionPage,
    JobAccepted,
    JobStatusResponse,
    SummaryResponse,
    UploadResponse,
)
from pipeline.detector import AVAILABLE_MODELS, SEG_MODELS
from pipeline.device import get_device

router = APIRouter(prefix="/api/analyze", tags=["analyze"])

# 検出結果テーブル 1 ページの既定・上限。全件はブラウザが固まるので CSV/JSON へ誘導する。
DEFAULT_PAGE_SIZE = 1000
MAX_PAGE_SIZE = 5000

# ダウンロード種別 → (ファイル名, MIME)。動画のみ実ファイル名が可変。
_DOWNLOAD_KINDS = {
    "csv": ("detections.csv", "text/csv"),
    "json": ("detections.json", "application/json"),
}


@router.post("/upload", response_model=UploadResponse)
async def upload_video(file: UploadFile = File(...)) -> UploadResponse:
    """動画をアップロードする（mp4 / mov / avi）。"""
    try:
        ref = storage.save_upload(file.file, file.filename or "input.mp4")
    except storage.StorageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return UploadResponse(upload_id=ref.upload_id, filename=ref.filename, size=ref.size)


@router.post("/run", response_model=JobAccepted, status_code=202)
def run_analysis(request: AnalyzeRequest) -> JobAccepted:
    """解析ジョブを起動する。設定の妥当性はここで全て検証してから開始する。"""
    upload = storage.find_upload(request.upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="アップロードが見つかりません。もう一度アップロードしてください。")

    # --- Streamlit 版の警告と同じ検証 ---
    if request.classes is not None and not request.classes:
        raise HTTPException(
            status_code=400, detail="対象クラスを1つ以上選ぶか「全クラス」を有効にしてください。"
        )
    if request.enable_zone and not request.enable_track:
        raise HTTPException(status_code=400, detail="ゾーン解析にはトラッキングが必要です")
    if request.enable_zone and not request.zones:
        raise HTTPException(status_code=400, detail="ゾーン解析を有効にする場合はゾーンを1つ以上定義してください。")

    allowed_models = SEG_MODELS if request.enable_seg else AVAILABLE_MODELS
    if request.model_name not in allowed_models:
        raise HTTPException(
            status_code=400,
            detail=f"モデル {request.model_name} は選択中のタスクに使えません（候補: {', '.join(allowed_models)}）",
        )

    run_id, output_dir = storage.new_run_dir()
    params = AnalyzeParams(
        input_path=upload.path,
        output_dir=output_dir,
        run_id=run_id,
        stem=upload.stem,
        model_name=request.model_name,
        device=get_device(),
        conf=request.conf,
        classes=request.classes,
        enable_seg=request.enable_seg,
        enable_track=request.enable_track,
        frame_stride=request.frame_stride,
        trace_length=request.trace_length,
        # ゾーン解析 OFF のときは定義があっても使わない（Streamlit 版と同じ挙動）。
        zones=[(z.name, [(x, y) for x, y in z.polygon]) for z in request.zones] if request.enable_zone else [],
    )
    job = job_manager.start(params, run_analyze, kind="analyze")
    return JobAccepted(job_id=job.job_id)


@router.get("/stream/{job_id}")
def stream_progress(job_id: str) -> StreamingResponse:
    """進捗イベントを SSE で配信する（`st.progress` の置き換え）。"""
    job = _get_job(job_id)

    def events() -> Iterator[str]:
        yield from sse_stream(job)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/result/{job_id}", response_model=JobStatusResponse)
def get_result(job_id: str) -> JobStatusResponse:
    """結果サマリ。検出レコードは含めない（`/detections` でページング取得）。"""
    job = _get_job(job_id)
    result = None
    if job.result is not None:
        summary = AnalyzeSummary(**{k: v for k, v in job.result.items() if k in AnalyzeSummary.model_fields})
        result = summary.model_dump()
        result["total_records"] = len(job.result.get("records", []))
    return JobStatusResponse(job_id=job.job_id, kind=job.kind, status=job.status, result=result, error=job.error)


@router.get("/detections/{job_id}", response_model=DetectionPage)
def get_detections(
    job_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> DetectionPage:
    """検出結果テーブルの 1 ページ分。

    全件は数万行になりうるためページングする。全件が必要なときは CSV/JSON を
    ダウンロードしてもらう（`/download/{job_id}/csv`）。
    """
    records: list[dict[str, Any]] = _completed_result(job_id).get("records", [])
    return DetectionPage(total=len(records), offset=offset, limit=limit, records=records[offset : offset + limit])


@router.get("/download/{job_id}/{kind}")
def download(job_id: str, kind: str) -> FileResponse:
    """CSV / JSON / 注釈付き動画のダウンロード（`st.download_button` 相当）。"""
    result = _completed_result(job_id)
    stem = result["stem"]

    if kind in _DOWNLOAD_KINDS:
        name, media_type = _DOWNLOAD_KINDS[kind]
        path = Path(result["output_path"]).parent / name
        download_name = f"{stem}_{name}"
    elif kind == "video":
        path = Path(result["output_path"])
        media_type = "video/mp4"
        download_name = f"{stem}_annotated.mp4"
    else:
        raise HTTPException(status_code=404, detail=f"未対応のダウンロード種別です: {kind}")

    if not path.exists():
        raise HTTPException(status_code=404, detail="ファイルが見つかりません（作業ディレクトリが削除された可能性）")
    return FileResponse(path, media_type=media_type, filename=download_name)


@router.post("/summary/{job_id}", response_model=SummaryResponse)
def nl_summary(job_id: str) -> SummaryResponse:
    """検出・ゾーン結果を Claude で自然言語要約する（要 `ANTHROPIC_API_KEY`）。"""
    result = _completed_result(job_id)
    from pipeline.claude_vision import summarize_session  # 遅延 import（anthropic）

    try:
        summary = summarize_session(result.get("stats") or {}, result.get("zone_summary") or {})
    except Exception as e:  # noqa: BLE001 — Streamlit 版と同じ案内を返す
        raise HTTPException(
            status_code=502, detail=f"要約に失敗しました: {e}（`ANTHROPIC_API_KEY` を確認）"
        ) from e
    return SummaryResponse(summary=summary)


def _get_job(job_id: str) -> Job:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません（サーバ再起動で失われた可能性）")
    return job


def _completed_result(job_id: str) -> dict[str, Any]:
    """完了済みジョブの生の結果 dict を返す。未完了・失敗なら 409。"""
    job = _get_job(job_id)
    if job.result is None:
        raise HTTPException(status_code=409, detail=f"ジョブはまだ完了していません（status={job.status}）")
    return job.result
