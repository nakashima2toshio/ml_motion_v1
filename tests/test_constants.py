"""pipeline の公開定数の健全性テスト（依存ゼロ）。"""

from __future__ import annotations

from pipeline.batch import MEDIA_EXTS
from pipeline.camera import LIGHTWEIGHT_MODELS, RESOLUTION_PRESETS
from pipeline.detections import COCO_COMMON
from pipeline.detector import AVAILABLE_MODELS, SEG_MODELS
from pipeline.export_model import EXPORT_FORMATS
from pipeline.registry import STAGES


def test_available_models():
    assert AVAILABLE_MODELS == ("yolo11n.pt", "yolo11s.pt", "yolo11m.pt")
    assert all(m.endswith(".pt") for m in AVAILABLE_MODELS)


def test_seg_models():
    assert SEG_MODELS == ("yolo11n-seg.pt", "yolo11s-seg.pt", "yolo11m-seg.pt")
    assert all(m.endswith("-seg.pt") for m in SEG_MODELS)


def test_lightweight_subset_of_models():
    # 軽量モデルは検出/セグの n・s。m は含まない。
    assert "yolo11n.pt" in LIGHTWEIGHT_MODELS and "yolo11s.pt" in LIGHTWEIGHT_MODELS
    assert "yolo11m.pt" not in LIGHTWEIGHT_MODELS


def test_media_exts():
    assert set(MEDIA_EXTS) >= {".mp4", ".mov", ".avi", ".mkv"}
    assert all(e.startswith(".") for e in MEDIA_EXTS)


def test_export_formats():
    assert {"onnx", "coreml", "torchscript", "engine"} <= set(EXPORT_FORMATS)


def test_resolution_presets():
    assert RESOLUTION_PRESETS["640x360"] == (640, 360)
    assert all(isinstance(v, tuple) and len(v) == 2 for v in RESOLUTION_PRESETS.values())


def test_coco_common_ids():
    assert COCO_COMMON["person"] == 0 and COCO_COMMON["car"] == 2
    assert set(COCO_COMMON) >= {"person", "bicycle", "car", "motorcycle", "bus", "truck"}


def test_stages():
    assert STAGES == ("None", "Staging", "Production", "Archived")
