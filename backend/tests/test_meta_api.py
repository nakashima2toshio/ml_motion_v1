"""メタ情報 API のテスト。

`pipeline` の定数と API のレスポンスがずれていないことを確認する（React 側は
この API だけを見るため、ここがずれると UI の選択肢が黙って古くなる）。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from pipeline.camera import RESOLUTION_PRESETS
from pipeline.detections import COCO_COMMON, FIELDS
from pipeline.detector import AVAILABLE_MODELS, SEG_MODELS
from pipeline.export_model import EXPORT_FORMATS
from pipeline.registry import STAGES


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_device_info_works_without_torch(client: TestClient) -> None:
    """torch 未導入の環境でも 200 と既定値（cpu）を返す。"""
    res = client.get("/api/meta/device")
    assert res.status_code == 200
    body = res.json()
    assert body["device"] in {"cpu", "mps", "cuda"}
    assert set(body) == {"device", "torch", "mps_available", "cuda_available"}


def test_options_mirror_pipeline_constants(client: TestClient) -> None:
    res = client.get("/api/meta/options")
    assert res.status_code == 200
    body = res.json()

    assert body["models"] == list(AVAILABLE_MODELS)
    assert body["seg_models"] == list(SEG_MODELS)
    assert body["coco_common"] == dict(COCO_COMMON)
    assert body["export_formats"] == list(EXPORT_FORMATS)
    assert body["registry_stages"] == list(STAGES)
    assert body["detection_fields"] == list(FIELDS)


def test_options_resolution_presets_are_json_pairs(client: TestClient) -> None:
    """tuple は JSON で配列になる。UI が [w, h] として読める形か確認する。"""
    presets = client.get("/api/meta/options").json()["resolution_presets"]
    assert set(presets) == set(RESOLUTION_PRESETS)
    for key, (width, height) in RESOLUTION_PRESETS.items():
        assert presets[key] == [width, height]


def test_options_lightweight_models_are_sorted(client: TestClient) -> None:
    """frozenset の反復順は不定なので、API は必ずソート済みで返す。"""
    lightweight = client.get("/api/meta/options").json()["lightweight_models"]
    assert lightweight == sorted(lightweight)
