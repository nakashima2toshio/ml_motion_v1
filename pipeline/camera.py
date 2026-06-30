"""カメラ取り込みユーティリティ（Phase 3）。

Continuity Camera は macOS 上で通常のカメラデバイス（インデックス）として見えるため、
OpenCV の VideoCapture でそのまま扱える。FPS 計測・解像度プリセット・軽量モデル自動切替の
ロジックは重い依存を持たず単体テスト可能にする。cv2 を使う open_camera のみ遅延 import。
"""

from __future__ import annotations

from collections import deque

# リアルタイム時の解像度プリセット（軽い順）。スループットとのトレードオフ。
RESOLUTION_PRESETS: dict[str, tuple[int, int]] = {
    "640x360": (640, 360),
    "960x540": (960, 540),
    "1280x720": (1280, 720),
}

# リアルタイムで実用 fps を出しやすい軽量モデル（検出・セグ）。
LIGHTWEIGHT_MODELS: frozenset[str] = frozenset(
    {"yolo11n.pt", "yolo11s.pt", "yolo11n-seg.pt", "yolo11s-seg.pt"}
)


def is_lightweight(model_name: str) -> bool:
    """リアルタイム向きの軽量モデルか。"""
    return model_name in LIGHTWEIGHT_MODELS


def recommend_realtime_model(model_name: str) -> str:
    """リアルタイム用に軽量モデルへ自動切替する（重いモデルは s 相当へ）。

    既に軽量なら据え置き。セグ系は seg のまま s 相当へ落とす。
    """
    if is_lightweight(model_name):
        return model_name
    return "yolo11s-seg.pt" if model_name.endswith("-seg.pt") else "yolo11s.pt"


class FpsMeter:
    """直近 window フレームのタイムスタンプから移動平均 FPS を求める（依存なし）。"""

    def __init__(self, window: int = 30) -> None:
        self._ts: deque[float] = deque(maxlen=max(2, window))

    def tick(self, timestamp: float) -> None:
        """フレーム取得時刻（秒・単調増加）を記録する。"""
        self._ts.append(timestamp)

    @property
    def fps(self) -> float:
        if len(self._ts) < 2:
            return 0.0
        span = self._ts[-1] - self._ts[0]
        return (len(self._ts) - 1) / span if span > 0 else 0.0

    def reset(self) -> None:
        self._ts.clear()


def open_camera(index: int = 0, size: tuple[int, int] | None = None):
    """カメラ（Continuity Camera 含む）を開く。size=(w,h) で解像度を指定。"""
    import cv2

    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(f"カメラを開けませんでした (index={index})。デバイス接続/権限を確認してください。")
    if size is not None:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
    return cap
