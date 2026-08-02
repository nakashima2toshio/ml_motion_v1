"""`detector_cache` のキー正規化・LRU のテスト。

実モデルのロード（ultralytics）は単体テストの対象外なので、`Detector` /
`FrameProcessor` をスタブに差し替えて「何回生成されたか」で検証する。
"""

from __future__ import annotations

import pytest

from backend.app.core import detector_cache


class _StubDetector:
    instances = 0

    def __init__(self, model_name: str, device: str, conf: float, classes: list[int] | None = None) -> None:
        type(self).instances += 1
        self.model_name = model_name
        self.device = device
        self.conf = conf
        self.classes = classes


class _StubProcessor:
    instances = 0

    def __init__(self, detector, enable_masks: bool = False, enable_tracking: bool = True) -> None:
        type(self).instances += 1
        self.detector = detector
        self.enable_masks = enable_masks
        self.enable_tracking = enable_tracking


@pytest.fixture(autouse=True)
def stub_models(monkeypatch: pytest.MonkeyPatch) -> None:
    _StubDetector.instances = 0
    _StubProcessor.instances = 0
    monkeypatch.setattr(detector_cache, "Detector", _StubDetector)
    monkeypatch.setattr(detector_cache, "FrameProcessor", _StubProcessor)
    detector_cache.clear()
    yield
    detector_cache.clear()


def test_same_settings_reuse_one_detector() -> None:
    first = detector_cache.get_detector("yolo11s.pt", "cpu", 0.25, [0, 2])
    second = detector_cache.get_detector("yolo11s.pt", "cpu", 0.25, [0, 2])
    assert first is second
    assert _StubDetector.instances == 1


def test_class_order_does_not_change_the_key() -> None:
    """UI のマルチセレクトは選択順が変わりうる。順序でキャッシュを外さない。"""
    first = detector_cache.get_detector("yolo11s.pt", "cpu", 0.25, [2, 0])
    second = detector_cache.get_detector("yolo11s.pt", "cpu", 0.25, [0, 2])
    assert first is second
    assert _StubDetector.instances == 1


def test_all_classes_none_differs_from_explicit_classes() -> None:
    """「全クラス」(None) と明示クラス指定は別物として扱う。"""
    detector_cache.get_detector("yolo11s.pt", "cpu", 0.25, None)
    detector_cache.get_detector("yolo11s.pt", "cpu", 0.25, [0])
    assert _StubDetector.instances == 2


def test_conf_change_creates_new_detector() -> None:
    detector_cache.get_detector("yolo11s.pt", "cpu", 0.25, None)
    detector_cache.get_detector("yolo11s.pt", "cpu", 0.50, None)
    assert _StubDetector.instances == 2


def test_lru_evicts_beyond_max_cached() -> None:
    for name in ("yolo11n.pt", "yolo11s.pt", "yolo11m.pt"):
        detector_cache.get_detector(name, "cpu", 0.25, None)
    assert detector_cache.stats()["detectors"] == detector_cache.MAX_CACHED

    # 最初に入れたものは追い出されているので、再取得で生成が走る。
    detector_cache.get_detector("yolo11n.pt", "cpu", 0.25, None)
    assert _StubDetector.instances == 4


def test_detector_receives_a_copy_of_classes() -> None:
    """呼び出し側のリストを後から変更されても検出器の設定が壊れないこと。"""
    classes = [0, 2]
    detector = detector_cache.get_detector("yolo11s.pt", "cpu", 0.25, classes)
    classes.append(7)
    assert detector.classes == [0, 2]


def test_processor_reuses_detector_and_respects_task_flags() -> None:
    processor = detector_cache.get_processor("yolo11n.pt", "cpu", 0.25, enable_masks=True, enable_tracking=False)
    same = detector_cache.get_processor("yolo11n.pt", "cpu", 0.25, enable_masks=True, enable_tracking=False)
    assert processor is same
    assert _StubProcessor.instances == 1
    assert _StubDetector.instances == 1
    assert processor.enable_masks is True
    assert processor.enable_tracking is False

    detector_cache.get_processor("yolo11n.pt", "cpu", 0.25, enable_masks=False, enable_tracking=True)
    assert _StubProcessor.instances == 2
    assert _StubDetector.instances == 1, "同じ設定の Detector は共有する"


def test_clear_empties_cache() -> None:
    detector_cache.get_detector("yolo11s.pt", "cpu", 0.25, None)
    detector_cache.clear()
    assert detector_cache.stats()["detectors"] == 0
