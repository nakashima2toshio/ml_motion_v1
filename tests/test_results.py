"""dataclass のプロパティ・既定値の単体テスト（依存ゼロ）。

対象: FrameResult / VideoResult / TrackingResult / TrainConfig / FrameUncertainty。
いずれも重い依存を import せずに構築できる。
"""

from __future__ import annotations

from pipeline.active_learning import FrameUncertainty
from pipeline.detections import DetectionRecord
from pipeline.realtime import FrameResult
from pipeline.training import TrainConfig
from pipeline.video import TrackingResult, VideoResult


# ---- FrameResult ----
def test_frame_result_n_detections():
    recs = [DetectionRecord(0, 0.0, 0, "person", 0.9, 1, 2, 3, 4)]
    fr = FrameResult(annotated=None, records=recs, tracks_norm=[(1, 0.5, 0.5)])
    assert fr.n_detections == 1


def test_frame_result_defaults_empty():
    fr = FrameResult(annotated=None)
    assert fr.n_detections == 0
    assert fr.records == [] and fr.tracks_norm == []


# ---- VideoResult / TrackingResult ----
def test_video_result_duration():
    vr = VideoResult(frames_total=300, fps=30.0)
    assert vr.duration_sec == 10.0


def test_video_result_duration_zero_fps():
    vr = VideoResult(frames_total=300, fps=0.0)
    assert vr.duration_sec == 0.0


def test_tracking_result_defaults():
    tr = TrackingResult()
    assert tr.zone_summary == {}
    assert tr.per_track_dwell == []
    assert tr.records == [] and tr.frames_processed == 0


# ---- TrainConfig ----
def test_train_config_defaults():
    cfg = TrainConfig(data_yaml="data/datasets/custom/data.yaml")
    assert cfg.base_model == "yolo11s.pt"
    assert cfg.epochs == 50
    assert cfg.imgsz == 640
    assert cfg.batch == 16
    assert cfg.device is None
    assert cfg.experiment == "ml_motion_detection"
    assert cfg.run_name is None
    assert cfg.extra == {}


# ---- FrameUncertainty ----
def test_frame_uncertainty_fields():
    fu = FrameUncertainty(frame=3, min_confidence=0.2, mean_confidence=0.35, n_detections=2)
    assert fu.frame == 3 and fu.n_detections == 2
    assert fu.min_confidence == 0.2 and fu.mean_confidence == 0.35
