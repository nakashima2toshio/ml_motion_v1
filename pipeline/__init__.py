"""推論パイプライン パッケージ。

Phase 0: デバイス選択ユーティリティ。
Phase 1: YOLO11 検出器・mp4 処理・検出レコード/エクスポート。
Phase 2: セグメンテーション・ByteTrack トラッキング・ゾーン解析。

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
from pipeline.camera import (
    LIGHTWEIGHT_MODELS,
    RESOLUTION_PRESETS,
    FpsMeter,
    is_lightweight,
    open_camera,
    recommend_realtime_model,
)
from pipeline.dataset import DatasetSpec, build_dataset_yaml, train_val_split
from pipeline.detector import AVAILABLE_MODELS, SEG_MODELS, Detector
from pipeline.device import describe_device, get_device
from pipeline.experiments import (
    DEFAULT_EXPERIMENT,
    best_run,
    format_runs_table,
    list_runs,
    tracking_uri,
)
from pipeline.realtime import FrameProcessor, FrameResult
from pipeline.registry import STAGES, normalize_stage, register_model, transition_stage
from pipeline.training import TrainConfig, TrainResult, train
from pipeline.tracking import Tracker
from pipeline.video import TrackingResult, VideoResult, process_tracking_video, process_video
from pipeline.zones import IntrusionEvent, Zone, ZoneAnalyzer, point_in_polygon

__all__ = [
    "get_device",
    "describe_device",
    "Detector",
    "AVAILABLE_MODELS",
    "SEG_MODELS",
    "DetectionRecord",
    "COCO_COMMON",
    "summarize",
    "to_csv_bytes",
    "to_json_bytes",
    "process_video",
    "process_tracking_video",
    "VideoResult",
    "TrackingResult",
    "Tracker",
    "Zone",
    "ZoneAnalyzer",
    "IntrusionEvent",
    "point_in_polygon",
    "FrameProcessor",
    "FrameResult",
    "FpsMeter",
    "RESOLUTION_PRESETS",
    "LIGHTWEIGHT_MODELS",
    "is_lightweight",
    "recommend_realtime_model",
    "open_camera",
    "DatasetSpec",
    "build_dataset_yaml",
    "train_val_split",
    "DEFAULT_EXPERIMENT",
    "tracking_uri",
    "list_runs",
    "format_runs_table",
    "best_run",
    "STAGES",
    "normalize_stage",
    "register_model",
    "transition_stage",
    "TrainConfig",
    "TrainResult",
    "train",
]
