"""実験管理 API（Streamlit 版 `app/views/experiments.py` に対応）。

    GET  /api/experiments/config        Tracking URI・既定実験名
    GET  /api/experiments/runs          Run 一覧・最良 Run（MLflow 未起動なら 503）
    POST /api/experiments/train         転移学習ジョブの起動（202 + job_id）
    GET  /api/experiments/stream/{id}   学習ジョブの進捗（SSE）
    GET  /api/experiments/result/{id}   学習ジョブの結果
    POST /api/experiments/dataset-yaml  data.yaml の生成

MLflow は重い依存なので、ルータ import 時には読み込まない（`pipeline` 側が遅延 import）。
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.app.core.jobs import Job, job_manager, sse_stream
from backend.app.core.mlflow_probe import is_mlflow_reachable
from backend.app.core.training_runner import TrainParams, run_training
from backend.app.schemas import (
    DatasetYamlRequest,
    DatasetYamlResponse,
    ExperimentsConfig,
    JobAccepted,
    JobStatusResponse,
    RunsResponse,
    TrainRequest,
)
from pipeline.detector import AVAILABLE_MODELS, SEG_MODELS
from pipeline.experiments import DEFAULT_EXPERIMENT, KEY_METRICS, tracking_uri

router = APIRouter(prefix="/api/experiments", tags=["experiments"])

# MLflow へ繋がらないときの案内（Streamlit 版と同じ文言）。
MLFLOW_HINT = "`docker-compose -f docker-compose/docker-compose.yml up -d` で起動してください。"



@router.get("/config", response_model=ExperimentsConfig)
def get_config() -> ExperimentsConfig:
    """Tracking URI と既定の実験名。画面上部の表示に使う。"""
    return ExperimentsConfig(
        tracking_uri=tracking_uri(),
        default_experiment=DEFAULT_EXPERIMENT,
        key_metrics=list(KEY_METRICS),
    )


@router.get("/runs", response_model=RunsResponse)
def get_runs(experiment: str = Query(default=DEFAULT_EXPERIMENT)) -> RunsResponse:
    """Run 一覧と最良 Run。MLflow へ繋がらないときは 503 に起動案内を載せる。"""
    # 遅延 import（mlflow）
    from pipeline.experiments import best_run, format_runs_table, list_runs, metric_value

    uri = tracking_uri()
    if not is_mlflow_reachable(uri):
        raise HTTPException(status_code=503, detail=f"MLflow へ接続できませんでした: {uri}\n\n{MLFLOW_HINT}")

    try:
        runs = list_runs(experiment)
    except Exception as e:  # noqa: BLE001 — MLflow 未起動が主な原因
        raise HTTPException(
            status_code=503, detail=f"MLflow へ接続できませんでした: {e}\n\n{MLFLOW_HINT}"
        ) from e

    top = best_run(runs)
    best_metric = None
    if top is not None:
        # ⚠️ 直接 `.get()` しない。MLflow に保存された名前は括弧が落ちているため
        # （docs/known_issues.md #1）、`metric_value` で両方の形に対応する。
        best_metric = round(metric_value(top["metrics"], "metrics/mAP50-95(B)"), 4)

    return RunsResponse(
        experiment=experiment,
        rows=format_runs_table(runs),
        best_run_name=top["run_name"] if top else None,
        best_metric=best_metric,
    )


@router.post("/train", response_model=JobAccepted, status_code=202)
def start_training(request: TrainRequest) -> JobAccepted:
    """転移学習ジョブを起動する。

    学習は長時間・高負荷なので、Streamlit 版と同じくジョブとして投げっぱなしにし、
    進捗は MLflow UI / コンソールでも確認できる。
    """
    allowed = tuple(AVAILABLE_MODELS) + tuple(SEG_MODELS)
    if request.base_model not in allowed:
        raise HTTPException(
            status_code=400, detail=f"未知のベースモデルです: {request.base_model}（候補: {', '.join(allowed)}）"
        )

    params = TrainParams(
        data_yaml=request.data_yaml,
        base_model=request.base_model,
        epochs=request.epochs,
        experiment=request.experiment or DEFAULT_EXPERIMENT,
        run_name=request.run_name or None,
    )
    job = job_manager.start(params, run_training, kind="train")
    return JobAccepted(job_id=job.job_id)


@router.get("/stream/{job_id}")
def stream_training(job_id: str) -> StreamingResponse:
    """学習ジョブの進捗（SSE）。"""
    job = _get_job(job_id)

    def events() -> Iterator[str]:
        yield from sse_stream(job)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/result/{job_id}", response_model=JobStatusResponse)
def get_training_result(job_id: str) -> JobStatusResponse:
    """学習ジョブの結果（run_id とメトリクス）。"""
    job = _get_job(job_id)
    return JobStatusResponse(
        job_id=job.job_id, kind=job.kind, status=job.status, result=job.result, error=job.error
    )


@router.post("/dataset-yaml", response_model=DatasetYamlResponse)
def generate_dataset_yaml(request: DatasetYamlRequest) -> DatasetYamlResponse:
    """`data.yaml` の雛形を生成する。"""
    from pipeline.dataset import DatasetSpec, build_dataset_yaml  # PyYAML のみ

    classes = parse_classes(request.classes)
    if not classes:
        raise HTTPException(status_code=400, detail="クラスを1つ以上入力してください（カンマ区切り）。")

    spec = DatasetSpec(name=request.name, classes=classes)
    return DatasetYamlResponse(yaml=build_dataset_yaml(spec), classes=classes)


def parse_classes(text: str) -> list[str]:
    """カンマ区切りのクラス名を正規化する（空白除去・空要素除去・重複排除）。

    クラス ID は並び順で決まるため、**入力順を保持**する（並べ替えない）。
    """
    classes: list[str] = []
    for chunk in text.split(","):
        name = chunk.strip()
        if name and name not in classes:
            classes.append(name)
    return classes


def _get_job(job_id: str) -> Job:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません（サーバ再起動で失われた可能性）")
    return job
