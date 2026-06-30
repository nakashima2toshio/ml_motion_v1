"""MLflow 実験トラッキングの照会ヘルパー（Phase 4）。

mlflow は重い依存のため関数内で遅延 import する。
Run 整形（format_runs_table）と最良 Run 選択（best_run）は依存なしで単体テスト可能。
"""

from __future__ import annotations

import os

# 解析パイプラインの既定 MLflow 実験名。
DEFAULT_EXPERIMENT = "ml_motion_detection"

# 実験管理画面で表示する主要メトリクス（ultralytics の検証メトリクス名に対応）。
KEY_METRICS: tuple[str, ...] = ("metrics/mAP50(B)", "metrics/mAP50-95(B)")


def tracking_uri() -> str:
    """環境変数 MLFLOW_TRACKING_URI（既定 http://localhost:5000）。"""
    return os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")


def format_runs_table(runs: list[dict]) -> list[dict]:
    """生の Run dict（run_name/status/metrics）を表示用の行へ整形する（依存なし）。

    入力: [{"run_name": str, "status": str, "metrics": {name: value}}, ...]
    出力: mAP50 / mAP50-95 を抜き出し小数を丸めた行のリスト。
    """
    rows: list[dict] = []
    for r in runs:
        metrics = r.get("metrics", {})
        rows.append(
            {
                "run": r.get("run_name", ""),
                "status": r.get("status", ""),
                "mAP50": round(metrics.get("metrics/mAP50(B)", 0.0), 4),
                "mAP50-95": round(metrics.get("metrics/mAP50-95(B)", 0.0), 4),
            }
        )
    return rows


def best_run(runs: list[dict], metric: str = "metrics/mAP50-95(B)") -> dict | None:
    """指定メトリクスが最大の Run を返す（依存なし）。runs が空なら None。"""
    candidates = [r for r in runs if metric in r.get("metrics", {})]
    if not candidates:
        return None
    return max(candidates, key=lambda r: r["metrics"][metric])


def list_runs(experiment_name: str = DEFAULT_EXPERIMENT) -> list[dict]:
    """MLflow から Run 一覧を取得して dict のリストで返す（mlflow 遅延 import）。"""
    import mlflow
    from mlflow.tracking import MlflowClient

    mlflow.set_tracking_uri(tracking_uri())
    client = MlflowClient()
    exp = client.get_experiment_by_name(experiment_name)
    if exp is None:
        return []
    runs = client.search_runs(experiment_ids=[exp.experiment_id], max_results=200)
    return [
        {
            "run_id": run.info.run_id,
            "run_name": run.info.run_name or run.data.tags.get("mlflow.runName", run.info.run_id[:8]),
            "status": run.info.status,
            "metrics": dict(run.data.metrics),
            "params": dict(run.data.params),
        }
        for run in runs
    ]
