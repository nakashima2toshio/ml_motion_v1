"""mp4 → フレーム抽出 → YOLO11 検出 → 注釈付き動画書き出し（Phase 1）。

cv2 / supervision は重い依存のため、関数内で遅延 import する。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from pipeline.detections import DetectionRecord
from pipeline.detector import Detector
from pipeline.tracking import Tracker
from pipeline.zones import Zone, ZoneAnalyzer

ProgressCallback = Callable[[int, int], None]


@dataclass
class VideoResult:
    """動画処理の結果サマリ。"""

    records: list[DetectionRecord] = field(default_factory=list)
    output_path: str = ""
    frames_total: int = 0
    frames_processed: int = 0
    fps: float = 0.0
    width: int = 0
    height: int = 0

    @property
    def duration_sec(self) -> float:
        return self.frames_total / self.fps if self.fps else 0.0


def _open_writer(cv2, path: str, fps: float, size: tuple[int, int]):
    """ブラウザ再生しやすい H.264(avc1) を優先し、不可なら mp4v にフォールバックする。"""
    for fourcc_name in ("avc1", "mp4v"):
        fourcc = cv2.VideoWriter_fourcc(*fourcc_name)
        writer = cv2.VideoWriter(path, fourcc, fps, size)
        if writer.isOpened():
            return writer
        writer.release()
    raise RuntimeError(f"VideoWriter を初期化できませんでした: {path}")


def process_video(
    input_path: str,
    output_path: str,
    detector: Detector,
    frame_stride: int = 1,
    progress_cb: ProgressCallback | None = None,
) -> VideoResult:
    """input_path の mp4 を検出し、注釈付き動画を output_path に書き出す。

    frame_stride > 1 の場合は N フレームごとに検出・書き出しを行い、
    出力 fps を 1/stride に下げる（軽量化）。検出レコードの time_sec は元動画の実時刻。
    """
    import cv2
    import supervision as sv

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise RuntimeError(f"動画を開けませんでした: {input_path}")

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frames_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    stride = max(1, int(frame_stride))
    out_fps = max(1.0, src_fps / stride)
    writer = _open_writer(cv2, output_path, out_fps, (width, height))

    box_annotator = sv.BoxAnnotator()
    label_annotator = sv.LabelAnnotator()
    names = detector.names

    records: list[DetectionRecord] = []
    frame_idx = 0
    processed = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % stride == 0:
                result = detector.predict(frame)
                detections = sv.Detections.from_ultralytics(result)
                time_sec = frame_idx / src_fps if src_fps else 0.0

                labels: list[str] = []
                for xyxy, conf, class_id in zip(
                    detections.xyxy, detections.confidence, detections.class_id
                ):
                    class_name = names.get(int(class_id), str(int(class_id)))
                    x1, y1, x2, y2 = (float(v) for v in xyxy)
                    records.append(
                        DetectionRecord(
                            frame=frame_idx,
                            time_sec=round(time_sec, 3),
                            class_id=int(class_id),
                            class_name=class_name,
                            confidence=round(float(conf), 4),
                            x1=round(x1, 1),
                            y1=round(y1, 1),
                            x2=round(x2, 1),
                            y2=round(y2, 1),
                        )
                    )
                    labels.append(f"{class_name} {float(conf):.2f}")

                annotated = box_annotator.annotate(frame.copy(), detections)
                annotated = label_annotator.annotate(annotated, detections, labels=labels)
                writer.write(annotated)
                processed += 1
                if progress_cb is not None and frames_total > 0:
                    progress_cb(frame_idx + 1, frames_total)
            frame_idx += 1
    finally:
        cap.release()
        writer.release()

    return VideoResult(
        records=records,
        output_path=output_path,
        frames_total=frames_total,
        frames_processed=processed,
        fps=src_fps,
        width=width,
        height=height,
    )


@dataclass
class TrackingResult(VideoResult):
    """Phase 2 の結果（検出 + セグ + 追跡 + ゾーン）。"""

    zone_summary: dict = field(default_factory=dict)
    per_track_dwell: list = field(default_factory=list)


def _draw_zones(cv2, frame, zones: list[Zone], width: int, height: int) -> None:
    """正規化ゾーン多角形をピクセル座標に変換して枠線＋名前を描画する。"""
    import numpy as np

    for z in zones:
        pts = np.array([[int(x * width), int(y * height)] for x, y in z.polygon], dtype=np.int32)
        cv2.polylines(frame, [pts], isClosed=True, color=(0, 255, 255), thickness=2)
        if len(pts) > 0:
            cv2.putText(
                frame, z.name, (int(pts[0][0]), max(0, int(pts[0][1]) - 8)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2,
            )


def process_tracking_video(
    input_path: str,
    output_path: str,
    detector: Detector,
    *,
    enable_masks: bool = False,
    enable_tracking: bool = True,
    zones: list[Zone] | None = None,
    frame_stride: int = 1,
    trace_length: int = 30,
    progress_cb: ProgressCallback | None = None,
) -> TrackingResult:
    """検出 + （任意で）セグメンテーション・ByteTrack・ゾーン解析を行い注釈動画を書き出す。

    zones（正規化座標）が与えられた場合は ByteTrack で付与した tracker_id を使って
    ゾーン別の滞留時間・侵入イベントを集計する（ゾーン解析にはトラッキングが必要）。
    """
    import cv2
    import supervision as sv

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise RuntimeError(f"動画を開けませんでした: {input_path}")

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frames_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    stride = max(1, int(frame_stride))
    out_fps = max(1.0, src_fps / stride)
    writer = _open_writer(cv2, output_path, out_fps, (width, height))

    box_annotator = sv.BoxAnnotator()
    label_annotator = sv.LabelAnnotator()
    mask_annotator = sv.MaskAnnotator() if enable_masks else None
    trace_annotator = sv.TraceAnnotator(trace_length=trace_length) if enable_tracking else None

    tracker = Tracker() if enable_tracking else None
    zones = zones or []
    analyzer = ZoneAnalyzer(zones, fps=src_fps, stride=stride) if zones else None
    names = detector.names

    records: list[DetectionRecord] = []
    frame_idx = 0
    processed = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % stride == 0:
                result = detector.predict(frame)
                detections = sv.Detections.from_ultralytics(result)
                if tracker is not None:
                    detections = tracker.update(detections)
                time_sec = frame_idx / src_fps if src_fps else 0.0

                tracker_ids = (
                    detections.tracker_id
                    if getattr(detections, "tracker_id", None) is not None
                    else [None] * len(detections)
                )

                labels: list[str] = []
                tracks_for_zone: list[tuple[int, float, float]] = []
                anchors = (
                    detections.get_anchors_coordinates(sv.Position.BOTTOM_CENTER)
                    if len(detections) else []
                )
                for i in range(len(detections)):
                    class_id = int(detections.class_id[i])
                    conf = float(detections.confidence[i])
                    tid = None if tracker_ids[i] is None else int(tracker_ids[i])
                    class_name = names.get(class_id, str(class_id))
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
                    label = f"{class_name} {conf:.2f}" if tid is None else f"#{tid} {class_name} {conf:.2f}"
                    labels.append(label)
                    if tid is not None and len(anchors):
                        ax, ay = float(anchors[i][0]), float(anchors[i][1])
                        nx = ax / width if width else 0.0
                        ny = ay / height if height else 0.0
                        tracks_for_zone.append((tid, nx, ny))

                if analyzer is not None:
                    analyzer.update(frame_idx, round(time_sec, 3), tracks_for_zone)

                annotated = frame.copy()
                if mask_annotator is not None:
                    annotated = mask_annotator.annotate(annotated, detections)
                annotated = box_annotator.annotate(annotated, detections)
                if trace_annotator is not None:
                    annotated = trace_annotator.annotate(annotated, detections)
                annotated = label_annotator.annotate(annotated, detections, labels=labels)
                if zones:
                    _draw_zones(cv2, annotated, zones, width, height)

                writer.write(annotated)
                processed += 1
                if progress_cb is not None and frames_total > 0:
                    progress_cb(frame_idx + 1, frames_total)
            frame_idx += 1
    finally:
        cap.release()
        writer.release()

    return TrackingResult(
        records=records,
        output_path=output_path,
        frames_total=frames_total,
        frames_processed=processed,
        fps=src_fps,
        width=width,
        height=height,
        zone_summary=analyzer.summary() if analyzer is not None else {},
        per_track_dwell=analyzer.per_track_dwell() if analyzer is not None else [],
    )
