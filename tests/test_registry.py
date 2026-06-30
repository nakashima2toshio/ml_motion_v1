"""pipeline.registry の依存ゼロ部分（model_uri / normalize_stage / STAGES）の単体テスト。"""

from __future__ import annotations

import pytest

from pipeline.registry import STAGES, model_uri, normalize_stage


def test_model_uri_default_production():
    assert model_uri("ml_motion_detector") == "models:/ml_motion_detector/Production"


def test_model_uri_normalizes_stage():
    assert model_uri("m", "staging") == "models:/m/Staging"
    assert model_uri("m", "prod") == "models:/m/Production"
    assert model_uri("m", "archive") == "models:/m/Archived"


def test_model_uri_invalid_stage_raises():
    with pytest.raises(ValueError):
        model_uri("m", "bogus")


def test_stages_constant():
    assert STAGES == ("None", "Staging", "Production", "Archived")


def test_normalize_stage_roundtrip_through_uri():
    # 正規化後のステージ名は STAGES に含まれる。
    for raw in ("none", "STAGING", " production ", "prod", "archived"):
        uri = model_uri("m", raw)
        stage = uri.rsplit("/", 1)[-1]
        assert stage in STAGES
        assert normalize_stage(raw) == stage
