"""pipeline.zones の点-多角形判定・滞留/侵入集計の単体テスト（依存なしで実行可能）。"""

from __future__ import annotations

from pipeline.zones import Zone, ZoneAnalyzer, point_in_polygon

# 正規化座標で中央付近の正方形ゾーン。
SQUARE = [(0.3, 0.3), (0.7, 0.3), (0.7, 0.7), (0.3, 0.7)]


def test_point_in_polygon_inside_outside():
    assert point_in_polygon(0.5, 0.5, SQUARE) is True
    assert point_in_polygon(0.1, 0.1, SQUARE) is False
    assert point_in_polygon(0.8, 0.5, SQUARE) is False


def test_point_in_polygon_degenerate():
    assert point_in_polygon(0.5, 0.5, [(0.0, 0.0), (1.0, 1.0)]) is False


def test_dwell_accumulation_single_track():
    # fps=10, stride=1 → 1フレーム=0.1秒。3フレーム在 → 0.3秒。
    za = ZoneAnalyzer([Zone("A", SQUARE)], fps=10.0, stride=1)
    for f in range(3):
        za.update(f, f * 0.1, [(1, 0.5, 0.5)])
    summary = za.summary()
    assert summary["A"]["unique_tracks"] == 1
    assert summary["A"]["intrusions"] == 1  # 1回だけ進入
    assert abs(summary["A"]["total_dwell_sec"] - 0.3) < 1e-6


def test_intrusion_reentry_counts_twice():
    # 在→不在→在 で侵入イベントは2回。
    za = ZoneAnalyzer([Zone("A", SQUARE)], fps=10.0, stride=1)
    za.update(0, 0.0, [(1, 0.5, 0.5)])   # 進入(1)
    za.update(1, 0.1, [(1, 0.1, 0.1)])   # 退出
    za.update(2, 0.2, [(1, 0.5, 0.5)])   # 再進入(2)
    summary = za.summary()
    assert summary["A"]["intrusions"] == 2
    assert summary["A"]["unique_tracks"] == 1


def test_max_occupancy_and_per_track():
    za = ZoneAnalyzer([Zone("A", SQUARE)], fps=10.0, stride=1)
    za.update(0, 0.0, [(1, 0.5, 0.5), (2, 0.4, 0.4)])  # 2人同時
    za.update(1, 0.1, [(1, 0.5, 0.5)])                 # 1人
    summary = za.summary()
    assert summary["A"]["max_occupancy"] == 2
    rows = za.per_track_dwell()
    assert len(rows) == 2
    assert {r["tracker_id"] for r in rows} == {1, 2}


def test_stride_scales_frame_duration():
    # stride=2, fps=10 → 1処理フレーム=0.2秒。
    za = ZoneAnalyzer([Zone("A", SQUARE)], fps=10.0, stride=2)
    za.update(0, 0.0, [(1, 0.5, 0.5)])
    assert abs(za.summary()["A"]["total_dwell_sec"] - 0.2) < 1e-6
