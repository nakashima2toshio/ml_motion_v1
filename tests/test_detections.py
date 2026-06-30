"""pipeline.detections のエクスポート・集計の単体テスト（重い依存なしで実行可能）。"""

from __future__ import annotations

import csv
import io
import json

from pipeline.detections import (
    COCO_COMMON,
    DetectionRecord,
    summarize,
    to_csv_bytes,
    to_json_bytes,
)


def _sample() -> list[DetectionRecord]:
    return [
        DetectionRecord(0, 0.0, 0, "person", 0.9, 1, 2, 3, 4),
        DetectionRecord(0, 0.0, 0, "person", 0.8, 5, 6, 7, 8),
        DetectionRecord(0, 0.0, 2, "car", 0.7, 9, 10, 11, 12),
        DetectionRecord(1, 0.04, 0, "person", 0.6, 1, 2, 3, 4),
    ]


def test_coco_common_ids():
    assert COCO_COMMON["person"] == 0
    assert COCO_COMMON["car"] == 2


def test_to_csv_bytes_roundtrip():
    data = to_csv_bytes(_sample())
    text = data.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 4
    assert rows[0]["class_name"] == "person"
    assert rows[2]["class_name"] == "car"
    assert set(rows[0].keys()) == {
        "frame", "time_sec", "class_id", "class_name", "confidence", "x1", "y1", "x2", "y2", "tracker_id",
    }


def test_to_json_bytes_roundtrip():
    payload = json.loads(to_json_bytes(_sample()).decode("utf-8"))
    assert len(payload) == 4
    assert payload[0]["confidence"] == 0.9


def test_summarize_counts():
    stats = summarize(_sample())
    # person: 延べ3（frame0 に2 + frame1 に1）、最大同時2（frame0）
    assert stats["person"]["total"] == 3
    assert stats["person"]["max_in_frame"] == 2
    # car: 延べ1、最大同時1
    assert stats["car"]["total"] == 1
    assert stats["car"]["max_in_frame"] == 1


def test_summarize_empty():
    assert summarize([]) == {}
