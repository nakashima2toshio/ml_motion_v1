"""pipeline.experiments の依存ゼロ部分（tracking_uri / 定数）の単体テスト。"""

from __future__ import annotations

from pipeline.experiments import DEFAULT_EXPERIMENT, KEY_METRICS, tracking_uri


def test_tracking_uri_default(monkeypatch):
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    assert tracking_uri() == "http://localhost:5000"


def test_tracking_uri_env_override(monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://example:5001")
    assert tracking_uri() == "http://example:5001"


def test_default_experiment():
    assert DEFAULT_EXPERIMENT == "ml_motion_detection"


def test_key_metrics():
    assert "metrics/mAP50(B)" in KEY_METRICS
    assert "metrics/mAP50-95(B)" in KEY_METRICS
