"""推論パイプライン パッケージ。

Phase 0: デバイス選択ユーティリティ。
Phase 1: YOLO11 検出器・mp4 処理・検出レコード/エクスポート。

重い依存（torch/cv2/ultralytics/supervision）はいずれも関数・メソッド内で
遅延 import するため、本パッケージの import 自体はそれらが未導入でも成功する。
"""

from pipeline.detections import (
    COCO_COMMON,
    DetectionRecord,
    summarize,
    to_csv_bytes,
    to_json_bytes,
)
from pipeline.detector import AVAILABLE_MODELS, Detector
from pipeline.device import describe_device, get_device
from pipeline.video import VideoResult, process_video

__all__ = [
    "get_device",
    "describe_device",
    "Detector",
    "AVAILABLE_MODELS",
    "DetectionRecord",
    "COCO_COMMON",
    "summarize",
    "to_csv_bytes",
    "to_json_bytes",
    "process_video",
    "VideoResult",
]
