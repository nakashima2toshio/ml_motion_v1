"""MLflow 実験トラッキングの照会ヘルパー（Phase 4）。

mlflow は重い依存のため関数内で遅延 import する。
Run 整形（format_runs_table）と最良 Run 選択（best_run）は依存なしで単体テスト可能。
"""

from __future__ import annotations

import os

# 解析パイプラインの既定 MLflow 実験名。
DEFAULT_EXPERIMENT = "ml_motion_detection"

# 実験管理画面で表示する主要メトリクス（ultralytics の検証メトリクス名に対応）。
#
# ⚠️ ここは ultralytics の `results_dict` と同じ**括弧つき**の名前だが、MLflow に
# 保存されるときは括弧が落ちる（`sanitize_metric_name` を参照）。読み出しは
# `metric_value()` を使い、両方の形に対応すること。
KEY_METRICS: tuple[str, ...] = ("metrics/mAP50(B)", "metrics/mAP50-95(B)")


def tracking_uri() -> str:
    """環境変数 MLFLOW_TRACKING_URI（既定 http://localhost:5000）。"""
    return os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")


def sanitize_metric_name(name: str) -> str:
    """MLflow が受け付ける形へメトリクス名を正規化する（依存なし）。

    MLflow はメトリクス名に括弧を許さない::

        INVALID_PARAMETER_VALUE: Invalid value "metrics/mAP50-95(B)" for parameter
        'metrics[0].name' supplied: Names may only contain alphanumerics,
        underscores (_), dashes (-), periods (.), spaces ( ), colon(:) and slashes (/).

    ultralytics の MLflow コールバックも同じく括弧を除去して記録するため、
    実際に保存される名前は `metrics/mAP50B` / `metrics/mAP50-95B` になる。
    ここを合わせておかないと、記録した値を読み戻せない。
    """
    return name.replace("(", "").replace(")", "")


def metric_value(metrics: dict, key: str, default: float = 0.0) -> float:
    """メトリクスを取り出す。括弧つき・括弧なしのどちらで入っていても読める。

    - 括弧つきのまま入っている Run（ローカルの file ストア等）→ そのまま引く
    - MLflow サーバに入った Run（括弧が落ちている）→ 正規化した名前で引く
    """
    if key in metrics:
        return float(metrics[key])
    sanitized = sanitize_metric_name(key)
    if sanitized in metrics:
        return float(metrics[sanitized])
    return default


def has_metric(metrics: dict, key: str) -> bool:
    """`metric_value` と同じ規則で、そのメトリクスが存在するか。"""
    return key in metrics or sanitize_metric_name(key) in metrics


def format_runs_table(runs: list[dict]) -> list[dict]:
    """生の Run dict（run_name/status/metrics）を表示用の行へ整形する（依存なし）。

    入力: [{"run_name": str, "status": str, "metrics": {name: value}}, ...]
    出力: mAP50 / mAP50-95 を抜き出し小数を丸めた行のリスト。

    メトリクス名は括弧つき・括弧なしの両方に対応する（`metric_value` 参照）。
    """
    rows: list[dict] = []
    for r in runs:
        metrics = r.get("metrics", {})
        rows.append(
            {
                "run": r.get("run_name", ""),
                "status": r.get("status", ""),
                "mAP50": round(metric_value(metrics, "metrics/mAP50(B)"), 4),
                "mAP50-95": round(metric_value(metrics, "metrics/mAP50-95(B)"), 4),
            }
        )
    return rows


def best_run(runs: list[dict], metric: str = "metrics/mAP50-95(B)") -> dict | None:
    """指定メトリクスが最大の Run を返す（依存なし）。runs が空なら None。

    メトリクス名は括弧つき・括弧なしの両方に対応する（`metric_value` 参照）。
    """
    candidates = [r for r in runs if has_metric(r.get("metrics", {}), metric)]
    if not candidates:
        return None
    return max(candidates, key=lambda r: metric_value(r["metrics"], metric))


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
