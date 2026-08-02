"""`Detector` / `FrameProcessor` のプロセス内キャッシュ。

Streamlit 版は `@st.cache_resource` でモデルを保持していた（`views/analyze.py`
`load_detector` / `views/realtime.py` `make_processor`）。React 版ではその役目を
このモジュールが担う。同じ設定なら重みのロードをやり直さない。

`pipeline.detector` / `pipeline.realtime` は ultralytics を遅延 import するため、
このモジュールを import するだけでは重い依存を要求しない。
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any

from pipeline.detector import Detector
from pipeline.realtime import FrameProcessor

# 同時に保持するモデル数の上限。M2 Mac のメモリを考慮して小さく保つ。
MAX_CACHED = 2

CacheKey = tuple[Any, ...]

_lock = threading.Lock()
_detectors: OrderedDict[CacheKey, Detector] = OrderedDict()
_processors: OrderedDict[CacheKey, FrameProcessor] = OrderedDict()


def detector_key(model_name: str, device: str, conf: float, classes: list[int] | None) -> CacheKey:
    """キャッシュキー。`classes` は順序差でキーがぶれないようソートして正規化する。"""
    return (model_name, device, round(float(conf), 4), tuple(sorted(classes)) if classes else None)


def get_detector(model_name: str, device: str, conf: float, classes: list[int] | None = None) -> Detector:
    """設定が同じなら同一の `Detector` を返す（無ければ生成してキャッシュ）。"""
    key = detector_key(model_name, device, conf, classes)
    with _lock:
        cached = _detectors.get(key)
        if cached is not None:
            _detectors.move_to_end(key)
            return cached

    # ロード（重い）はロック外で行い、他リクエストのキャッシュ参照を止めない。
    detector = Detector(model_name=model_name, device=device, conf=conf, classes=list(classes) if classes else None)

    with _lock:
        # 競合して二重ロードした場合は先勝ちに揃える（重複インスタンスを残さない）。
        existing = _detectors.get(key)
        if existing is not None:
            _detectors.move_to_end(key)
            return existing
        _detectors[key] = detector
        _evict_locked(_detectors)
    return detector


def get_processor(
    model_name: str,
    device: str,
    conf: float,
    enable_masks: bool = False,
    enable_tracking: bool = True,
) -> FrameProcessor:
    """リアルタイム用の `FrameProcessor` を返す（設定が同じなら使い回す）。"""
    key = (model_name, device, round(float(conf), 4), bool(enable_masks), bool(enable_tracking))
    with _lock:
        cached = _processors.get(key)
        if cached is not None:
            _processors.move_to_end(key)
            return cached

    detector = get_detector(model_name, device, conf, None)
    processor = FrameProcessor(detector, enable_masks=enable_masks, enable_tracking=enable_tracking)

    with _lock:
        existing = _processors.get(key)
        if existing is not None:
            _processors.move_to_end(key)
            return existing
        _processors[key] = processor
        _evict_locked(_processors)
    return processor


def _evict_locked(cache: OrderedDict[CacheKey, Any]) -> None:
    """LRU で上限まで縮める（呼び出し側で lock 保持）。"""
    while len(cache) > MAX_CACHED:
        cache.popitem(last=False)


def clear() -> None:
    """キャッシュを空にする（テスト・モデル差し替え用）。"""
    with _lock:
        _detectors.clear()
        _processors.clear()


def stats() -> dict[str, int]:
    """キャッシュ状況（デバッグ用）。"""
    with _lock:
        return {"detectors": len(_detectors), "processors": len(_processors), "max_cached": MAX_CACHED}
