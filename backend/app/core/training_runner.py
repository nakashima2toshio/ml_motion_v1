"""転移学習ジョブの実行関数（`app/views/experiments.py` の「▶ 学習を開始」相当）。

学習は長時間・高負荷（仕様書 §1.2: M2 Mac では軽量・短時間に留め、本格学習は
クラウド GPU を推奨）。ここではワーカースレッドで `pipeline.training.train()` を
呼び、開始と完了をイベントで知らせる。細かい進捗は ultralytics /  MLflow UI 側で確認する。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app.core.jobs import EmitFn, JobEvent


@dataclass
class TrainParams:
    """学習ジョブのパラメータ（API の `TrainRequest` を解決したもの）。"""

    data_yaml: str
    base_model: str
    epochs: int
    experiment: str
    run_name: str | None = None


def run_training(params: TrainParams, emit: EmitFn) -> dict[str, Any]:
    """転移学習を実行して結果（run_id・メトリクス）を返す。"""
    # 遅延 import: ultralytics / mlflow をここで初めて読み込む。
    from pipeline.training import TrainConfig, train

    emit(
        JobEvent(
            type="progress",
            message=(
                "学習中…（進捗は MLflow UI / コンソールで確認）"
                "学習は長時間かつ高負荷です。M2 Mac では軽量・短時間に留めてください。"
            ),
        )
    )

    config = TrainConfig(
        data_yaml=params.data_yaml,
        base_model=params.base_model,
        epochs=params.epochs,
        experiment=params.experiment,
        run_name=params.run_name,
    )
    try:
        result = train(config)
    except Exception as e:  # noqa: BLE001 — Streamlit 版と同じ文言でユーザに返す
        raise RuntimeError(f"学習の実行に失敗しました: {e}") from e

    return {
        "run_id": result.run_id,
        "best_weights": result.best_weights,
        "metrics": result.metrics,
        "experiment": params.experiment,
    }
