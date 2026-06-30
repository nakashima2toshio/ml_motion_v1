"""pipeline.camera の FPS 計測・軽量モデル切替・解像度プリセットの単体テスト（依存なし）。"""

from __future__ import annotations

from pipeline.camera import (
    LIGHTWEIGHT_MODELS,
    RESOLUTION_PRESETS,
    FpsMeter,
    is_lightweight,
    recommend_realtime_model,
)


def test_resolution_presets():
    assert RESOLUTION_PRESETS["640x360"] == (640, 360)
    assert RESOLUTION_PRESETS["1280x720"] == (1280, 720)


def test_is_lightweight():
    assert is_lightweight("yolo11n.pt") is True
    assert is_lightweight("yolo11s-seg.pt") is True
    assert is_lightweight("yolo11m.pt") is False


def test_recommend_realtime_model_keeps_light():
    for m in LIGHTWEIGHT_MODELS:
        assert recommend_realtime_model(m) == m


def test_recommend_realtime_model_downgrades_heavy():
    assert recommend_realtime_model("yolo11m.pt") == "yolo11s.pt"
    assert recommend_realtime_model("yolo11m-seg.pt") == "yolo11s-seg.pt"


def test_fps_meter_empty_and_single():
    m = FpsMeter()
    assert m.fps == 0.0
    m.tick(1.0)
    assert m.fps == 0.0  # 1 サンプルでは算出不可


def test_fps_meter_constant_interval():
    m = FpsMeter(window=10)
    # 0.1 秒間隔 → 10 fps
    for i in range(5):
        m.tick(i * 0.1)
    assert abs(m.fps - 10.0) < 1e-6


def test_fps_meter_window_eviction():
    m = FpsMeter(window=3)
    for i in range(10):
        m.tick(i * 0.5)  # 0.5秒間隔 → 2 fps
    assert abs(m.fps - 2.0) < 1e-6


def test_fps_meter_reset():
    m = FpsMeter()
    m.tick(0.0)
    m.tick(0.1)
    m.reset()
    assert m.fps == 0.0
