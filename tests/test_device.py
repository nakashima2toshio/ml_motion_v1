"""pipeline.device の単体テスト（torch 未導入でも成立する依存ゼロ層）。"""

from __future__ import annotations

import importlib.util

from pipeline.device import describe_device, get_device

_HAS_TORCH = importlib.util.find_spec("torch") is not None


def test_get_device_returns_valid_value():
    assert get_device() in {"mps", "cuda", "cpu"}


def test_get_device_cpu_without_torch():
    # torch 未導入環境では必ず "cpu"。
    if not _HAS_TORCH:
        assert get_device() == "cpu"


def test_describe_device_keys():
    info = describe_device()
    assert set(info.keys()) == {"device", "torch", "mps_available", "cuda_available"}
    assert info["device"] in {"mps", "cuda", "cpu"}
    assert isinstance(info["mps_available"], bool)
    assert isinstance(info["cuda_available"], bool)


def test_describe_device_without_torch():
    if not _HAS_TORCH:
        info = describe_device()
        assert info == {"device": "cpu", "torch": None, "mps_available": False, "cuda_available": False}


def test_describe_device_consistent_with_get_device():
    assert describe_device()["device"] == get_device()
