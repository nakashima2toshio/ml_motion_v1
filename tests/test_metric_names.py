"""MLflow のメトリクス名の扱い（`docs/known_issues.md` #1 の回帰テスト）。

背景:
    ultralytics の `results_dict` のキーは `metrics/mAP50(B)` のように**括弧つき**だが、
    MLflow Tracking サーバはメトリクス名に括弧を許さない（`INVALID_PARAMETER_VALUE`）。
    ultralytics の MLflow コールバックは括弧を除去して `metrics/mAP50B` の形で記録する。

    このため `pipeline/experiments.py` が括弧つきキーだけを見ていると、
    実際に記録された Run の mAP が読めず、常に 0.0 になっていた。

ここでは「括弧なしで記録された Run を読めること」と
「記録前にキーを正規化すること」を固定する。
"""

from __future__ import annotations

import pytest

from pipeline.experiments import best_run, format_runs_table, metric_value, sanitize_metric_name
from pipeline.training import _extract_metrics


class _Results:
    """ultralytics の学習結果（`results_dict` を持つ）の最小スタブ。"""

    def __init__(self, results_dict: dict) -> None:
        self.results_dict = results_dict


# ---------------------------------------------------------------------------
# 名前の正規化
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("metrics/mAP50(B)", "metrics/mAP50B"),
        ("metrics/mAP50-95(B)", "metrics/mAP50-95B"),
        ("metrics/precision(M)", "metrics/precisionM"),
        ("metrics/mAP50B", "metrics/mAP50B"),  # 既に正規化済みなら変えない
        ("fitness", "fitness"),
    ],
)
def test_sanitize_metric_name(raw: str, expected: str) -> None:
    """ultralytics の MLflow コールバックと同じ正規化（括弧の除去）。"""
    assert sanitize_metric_name(raw) == expected


def test_sanitized_names_are_accepted_by_mlflow() -> None:
    """MLflow が許す文字（英数・`_ - . / : スペース`）だけになること。"""
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-./: ")
    assert set(sanitize_metric_name("metrics/mAP50-95(B)")) <= allowed


# ---------------------------------------------------------------------------
# 読み出し（記録済み Run → 表示）
# ---------------------------------------------------------------------------


def test_metric_value_reads_sanitized_key() -> None:
    """MLflow に実際に入っている形（括弧なし）を、括弧つきキーで引ける。"""
    metrics = {"metrics/mAP50B": 0.83, "metrics/mAP50-95B": 0.64}
    assert metric_value(metrics, "metrics/mAP50(B)") == 0.83
    assert metric_value(metrics, "metrics/mAP50-95(B)") == 0.64


def test_metric_value_prefers_exact_key() -> None:
    """括弧つきで入っている（ローカルの file ストア等）場合はそちらを優先する。"""
    metrics = {"metrics/mAP50(B)": 0.9, "metrics/mAP50B": 0.1}
    assert metric_value(metrics, "metrics/mAP50(B)") == 0.9


def test_metric_value_defaults_when_missing() -> None:
    assert metric_value({}, "metrics/mAP50(B)") == 0.0
    assert metric_value({}, "metrics/mAP50(B)", default=-1.0) == -1.0


def test_format_runs_table_reads_runs_logged_by_ultralytics() -> None:
    """⚠️ 回帰テスト: 修正前はこの mAP が 0.0 になっていた。"""
    runs = [
        {
            "run_name": "tuned",
            "status": "FINISHED",
            "metrics": {"metrics/mAP50B": 0.834, "metrics/mAP50-95B": 0.6412},
        }
    ]
    assert format_runs_table(runs)[0] == {
        "run": "tuned",
        "status": "FINISHED",
        "mAP50": 0.834,
        "mAP50-95": 0.6412,
    }


def test_best_run_reads_runs_logged_by_ultralytics() -> None:
    """⚠️ 回帰テスト: 修正前は候補ゼロで None になっていた。"""
    runs = [
        {"run_name": "baseline", "status": "FINISHED", "metrics": {"metrics/mAP50-95B": 0.51}},
        {"run_name": "tuned", "status": "FINISHED", "metrics": {"metrics/mAP50-95B": 0.64}},
    ]
    top = best_run(runs)
    assert top is not None
    assert top["run_name"] == "tuned"


def test_best_run_mixes_both_key_forms() -> None:
    """括弧あり Run と括弧なし Run が混在しても比較できる。"""
    runs = [
        {"run_name": "old", "status": "FINISHED", "metrics": {"metrics/mAP50-95(B)": 0.70}},
        {"run_name": "new", "status": "FINISHED", "metrics": {"metrics/mAP50-95B": 0.64}},
    ]
    assert best_run(runs)["run_name"] == "old"


# ---------------------------------------------------------------------------
# 書き込み（学習結果 → MLflow）
# ---------------------------------------------------------------------------


def test_extract_metrics_sanitizes_keys_before_logging() -> None:
    """⚠️ 回帰テスト: 修正前は括弧つきのまま `log_metrics()` に渡していたため、
    Tracking サーバ利用時に INVALID_PARAMETER_VALUE で失敗しうる。"""
    results = _Results({"metrics/mAP50(B)": 0.8, "metrics/mAP50-95(B)": 0.6, "fitness": 0.62})
    metrics = _extract_metrics(results)

    assert set(metrics) == {"metrics/mAP50B", "metrics/mAP50-95B", "fitness"}
    assert all("(" not in key and ")" not in key for key in metrics)
    assert metrics["metrics/mAP50B"] == 0.8


def test_extract_metrics_skips_non_numeric_values() -> None:
    results = _Results({"metrics/mAP50(B)": 0.8, "speed": "fast", "obj": object()})
    assert _extract_metrics(results) == {"metrics/mAP50B": 0.8}


def test_extract_metrics_without_results_dict() -> None:
    assert _extract_metrics(object()) == {}


def test_round_trip_extract_then_read() -> None:
    """学習で記録した値を、そのまま実験管理画面で読めること。"""
    results = _Results({"metrics/mAP50(B)": 0.834, "metrics/mAP50-95(B)": 0.6412})
    logged = _extract_metrics(results)

    rows = format_runs_table([{"run_name": "r", "status": "FINISHED", "metrics": logged}])
    assert rows[0]["mAP50"] == 0.834
    assert rows[0]["mAP50-95"] == 0.6412
