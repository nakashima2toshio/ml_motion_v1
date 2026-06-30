"""転移学習 / Fine-tuning ラッパー（Phase 4）。

COCO 事前学習済み YOLO11 から転移学習し、ハイパラ・メトリクス・成果物を MLflow へ記録する。
ultralytics / mlflow は重い依存のため関数内で遅延 import。

M2 Mac の制約（仕様書 §1.2）: 本格学習は MPS で低速/未対応のことがあるため、
軽量モデルの短時間転移学習はローカル、重い学習はクラウド GPU を推奨。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline.device import get_device
from pipeline.experiments import DEFAULT_EXPERIMENT, tracking_uri


@dataclass
class TrainConfig:
    """学習設定。"""

    data_yaml: str
    base_model: str = "yolo11s.pt"
    epochs: int = 50
    imgsz: int = 640
    batch: int = 16
    device: str | None = None
    experiment: str = DEFAULT_EXPERIMENT
    run_name: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class TrainResult:
    """学習結果サマリ。"""

    run_id: str
    best_weights: str
    metrics: dict


def train(config: TrainConfig) -> TrainResult:
    """転移学習を実行し MLflow に記録して結果を返す。

    ※ 実行には ultralytics / mlflow と学習データ（data.yaml）が必要。
    """
    import mlflow
    from ultralytics import YOLO

    device = config.device or get_device()
    mlflow.set_tracking_uri(tracking_uri())
    mlflow.set_experiment(config.experiment)

    with mlflow.start_run(run_name=config.run_name) as run:
        params = {
            "base_model": config.base_model,
            "epochs": config.epochs,
            "imgsz": config.imgsz,
            "batch": config.batch,
            "device": device,
            "data": config.data_yaml,
            **config.extra,
        }
        mlflow.log_params(params)

        model = YOLO(config.base_model)
        results = model.train(
            data=config.data_yaml,
            epochs=config.epochs,
            imgsz=config.imgsz,
            batch=config.batch,
            device=device,
            **config.extra,
        )

        metrics = _extract_metrics(results)
        if metrics:
            mlflow.log_metrics(metrics)

        best_weights = _best_weights_path(model, results)
        if best_weights:
            mlflow.log_artifact(best_weights, artifact_path="weights")

        return TrainResult(run_id=run.info.run_id, best_weights=best_weights, metrics=metrics)


def _extract_metrics(results) -> dict:
    """ultralytics の学習結果から float 化できるスカラーメトリクスを取り出す。"""
    metrics: dict = {}
    results_dict = getattr(results, "results_dict", None)
    if isinstance(results_dict, dict):
        for k, v in results_dict.items():
            try:
                metrics[k] = float(v)
            except (TypeError, ValueError):
                continue
    return metrics


def _best_weights_path(model, results) -> str:
    """学習済みベスト重み(best.pt)のパスを推定する。"""
    save_dir = getattr(getattr(model, "trainer", None), "save_dir", None)
    if save_dir:
        return f"{save_dir}/weights/best.pt"
    return ""
