"""1 フレーム処理器（Phase 3）。

検出（＋任意でセグ・ByteTrack 追跡）と注釈描画を 1 フレーム単位で行う。
バッチ処理（video.py）とリアルタイム（カメラ/webrtc）で共通利用する。
supervision は重い依存のため生成時に遅延 import。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline.detections import DetectionRecord
from pipeline.detector import Detector
from pipeline.tracking import Tracker


@dataclass
class FrameResult:
    """1 フレームの処理結果。"""

    annotated: object  # BGR ndarray
    records: list[DetectionRecord] = field(default_factory=list)
    tracks_norm: list[tuple[int, float, float]] = field(default_factory=list)  # (tid, nx, ny)

    @property
    def n_detections(self) -> int:
        return len(self.records)


class FrameProcessor:
    """検出器・トラッカー・各アノテーターを保持し、1 フレームを処理する。"""

    def __init__(
        self,
        detector: Detector,
        *,
        enable_masks: bool = False,
        enable_tracking: bool = True,
        trace_length: int = 30,
    ) -> None:
        import supervision as sv  # 遅延 import

        self._sv = sv
        self.detector = detector
        self.names = detector.names
        self._box = sv.BoxAnnotator()
        self._label = sv.LabelAnnotator()
        self._mask = sv.MaskAnnotator() if enable_masks else None
        self._trace = sv.TraceAnnotator(trace_length=trace_length) if enable_tracking else None
        self._tracker = Tracker() if enable_tracking else None

    def reset(self) -> None:
        """新しいストリーム/動画の開始時にトラッカー状態をリセットする。"""
        if self._tracker is not None:
            self._tracker.reset()

    def process(self, frame, frame_idx: int = 0, time_sec: float = 0.0) -> FrameResult:
        """BGR フレームを処理し、注釈付きフレームと検出レコードを返す。"""
        sv = self._sv
        height, width = frame.shape[:2]

        result = self.detector.predict(frame)
        detections = sv.Detections.from_ultralytics(result)
        if self._tracker is not None:
            detections = self._tracker.update(detections)

        tracker_ids = (
            detections.tracker_id
            if getattr(detections, "tracker_id", None) is not None
            else [None] * len(detections)
        )
        anchors = detections.get_anchors_coordinates(sv.Position.BOTTOM_CENTER) if len(detections) else []

        records: list[DetectionRecord] = []
        tracks_norm: list[tuple[int, float, float]] = []
        labels: list[str] = []
        for i in range(len(detections)):
            class_id = int(detections.class_id[i])
            conf = float(detections.confidence[i])
            tid = None if tracker_ids[i] is None else int(tracker_ids[i])
            class_name = self.names.get(class_id, str(class_id))
            x1, y1, x2, y2 = (float(v) for v in detections.xyxy[i])
            records.append(
                DetectionRecord(
                    frame=frame_idx,
                    time_sec=round(time_sec, 3),
                    class_id=class_id,
                    class_name=class_name,
                    confidence=round(conf, 4),
                    x1=round(x1, 1), y1=round(y1, 1), x2=round(x2, 1), y2=round(y2, 1),
                    tracker_id=tid,
                )
            )
            labels.append(f"{class_name} {conf:.2f}" if tid is None else f"#{tid} {class_name} {conf:.2f}")
            if tid is not None and len(anchors):
                nx = float(anchors[i][0]) / width if width else 0.0
                ny = float(anchors[i][1]) / height if height else 0.0
                tracks_norm.append((tid, nx, ny))

        annotated = frame.copy()
        if self._mask is not None:
            annotated = self._mask.annotate(annotated, detections)
        annotated = self._box.annotate(annotated, detections)
        if self._trace is not None:
            annotated = self._trace.annotate(annotated, detections)
        annotated = self._label.annotate(annotated, detections, labels=labels)

        return FrameResult(annotated=annotated, records=records, tracks_norm=tracks_norm)
