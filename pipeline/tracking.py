"""トラッキング ラッパー（Phase 2）。

supervision の ByteTrack を薄くラップし、検出に tracker_id を付与する。
supervision は重い依存のため import は生成時に遅延させる。
"""

from __future__ import annotations


class Tracker:
    """ByteTrack による ID 付与ラッパー。"""

    def __init__(self) -> None:
        import supervision as sv  # 遅延 import

        self._tracker = sv.ByteTrack()

    def update(self, detections):
        """sv.Detections を受け取り、tracker_id 付きの sv.Detections を返す。"""
        return self._tracker.update_with_detections(detections)

    def reset(self) -> None:
        """新しい動画の処理開始時に内部状態をリセットする。"""
        self._tracker.reset()
