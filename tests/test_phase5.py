"""Phase 5 の依存なしロジック（batch / benchmark / export 書式）の単体テスト。"""

from __future__ import annotations

import pytest

from pipeline.batch import BatchItemResult, BatchResult, build_manifest, filter_media
from pipeline.benchmark import LatencyStats, _percentile
from pipeline.export_model import EXPORT_FORMATS, normalize_format, quantization_label


# ---- batch ----
def test_filter_media_extension_and_sort():
    names = ["b.mp4", "a.MOV", "note.txt", "c.mkv", "img.png"]
    assert filter_media(names) == ["a.MOV", "b.mp4", "c.mkv"]


def test_filter_media_empty():
    assert filter_media(["a.txt", "b.csv"]) == []


def test_build_manifest_and_aggregates():
    res = BatchResult(items=[
        BatchItemResult("in1.mp4", "out1.mp4", frames_processed=100, n_detections=42, ok=True),
        BatchItemResult("in2.mp4", ok=False, error="boom"),
    ])
    assert res.total_detections == 42
    assert res.succeeded == 1
    assert res.failed == 1
    manifest = build_manifest(res)
    assert manifest[0]["status"] == "ok"
    assert manifest[1]["status"] == "error: boom"


# ---- benchmark ----
def test_percentile_basic():
    vals = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert _percentile(vals, 0) == 10.0
    assert _percentile(vals, 100) == 50.0
    assert _percentile(vals, 50) == 30.0


def test_percentile_empty_and_single():
    assert _percentile([], 95) == 0.0
    assert _percentile([7.0], 95) == 7.0


def test_latency_stats_summary():
    s = LatencyStats()
    for v in (10.0, 20.0, 30.0, 40.0):
        s.add(v)
    summary = s.summary()
    assert summary["count"] == 4
    assert summary["mean_ms"] == 25.0
    assert summary["fps"] == round(1000.0 / 25.0, 2)


def test_latency_stats_empty():
    s = LatencyStats()
    assert s.mean_ms == 0.0
    assert s.fps == 0.0


# ---- export 書式 ----
def test_normalize_format_aliases():
    assert normalize_format("ONNX") == "onnx"
    assert normalize_format("mlmodel") == "coreml"
    assert normalize_format("trt") == "engine"
    assert normalize_format("ts") == "torchscript"


def test_normalize_format_invalid():
    with pytest.raises(ValueError):
        normalize_format("bogus")


def test_quantization_label():
    assert quantization_label(False, False) == "FP32"
    assert quantization_label(True, False) == "FP16"
    assert quantization_label(False, True) == "INT8"
    assert quantization_label(True, True) == "INT8"  # int8 優先


def test_export_formats_constant():
    assert "onnx" in EXPORT_FORMATS and "coreml" in EXPORT_FORMATS
