"""ゾーン解析ロジック（Phase 2）。

多角形ゾーンに対する「在/不在」判定・滞留時間・侵入イベントを集計する。
描画は supervision に任せ、ここは重い依存を持たない純粋ロジックとして単体テスト可能にする
（仕様書 §2: "supervision + Shapely ベース自前ロジック" の自前ロジック部分）。

座標は **正規化座標（0.0〜1.0）** を基本とし、フレーム解像度に依存しないようにする。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Zone:
    """名前付きの多角形ゾーン。polygon は (x, y) の正規化座標（0〜1）のリスト。"""

    name: str
    polygon: list[tuple[float, float]]


@dataclass
class IntrusionEvent:
    """トラックがゾーンへ進入した（外→内）イベント。"""

    zone: str
    tracker_id: int
    frame: int
    time_sec: float


def point_in_polygon(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
    """レイキャスティング法による点-多角形内外判定。境界上は概ね内側に倒す。"""
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        # 辺 (i, j) が水平線 y と交差し、交点が x より右にあるか。
        intersects = (yi > y) != (yj > y)
        if intersects:
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


@dataclass
class ZoneAnalyzer:
    """フレームごとの更新で滞留時間・侵入イベント・占有数を蓄積する。

    使い方:
        za = ZoneAnalyzer(zones, fps=30.0, stride=1)
        za.update(frame_idx, time_sec, [(tracker_id, x, y), ...])  # x,y は正規化アンカー座標
        ...
        summary = za.summary()
    """

    zones: list[Zone]
    fps: float = 30.0
    stride: int = 1
    # 内部状態
    dwell: dict[tuple[str, int], float] = field(default_factory=dict)
    events: list[IntrusionEvent] = field(default_factory=list)
    _inside_prev: dict[str, set[int]] = field(default_factory=dict)
    _seen: dict[str, set[int]] = field(default_factory=dict)
    _max_occupancy: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for z in self.zones:
            self._inside_prev.setdefault(z.name, set())
            self._seen.setdefault(z.name, set())
            self._max_occupancy.setdefault(z.name, 0)

    @property
    def _frame_dt(self) -> float:
        return (self.stride / self.fps) if self.fps else 0.0

    def update(self, frame: int, time_sec: float, tracks: list[tuple[int, float, float]]) -> None:
        """1（処理）フレーム分の更新。tracks=[(tracker_id, x, y)]、x,y は正規化座標。"""
        dt = self._frame_dt
        for z in self.zones:
            inside_now = {tid for tid, x, y in tracks if point_in_polygon(x, y, z.polygon)}

            # 滞留時間（在のトラックにフレーム時間を加算）。
            for tid in inside_now:
                self.dwell[(z.name, tid)] = self.dwell.get((z.name, tid), 0.0) + dt

            # 侵入イベント（前フレーム不在 → 今フレーム在）。
            for tid in inside_now - self._inside_prev[z.name]:
                self.events.append(IntrusionEvent(zone=z.name, tracker_id=tid, frame=frame, time_sec=time_sec))

            self._seen[z.name] |= inside_now
            if len(inside_now) > self._max_occupancy[z.name]:
                self._max_occupancy[z.name] = len(inside_now)
            self._inside_prev[z.name] = inside_now

    def summary(self) -> dict[str, dict[str, object]]:
        """ゾーン別サマリ: ユニーク通過数・侵入回数・最大同時数・合計/最大滞留秒。"""
        out: dict[str, dict[str, object]] = {}
        for z in self.zones:
            dwells = [v for (zone, _tid), v in self.dwell.items() if zone == z.name]
            intrusions = sum(1 for e in self.events if e.zone == z.name)
            out[z.name] = {
                "unique_tracks": len(self._seen[z.name]),
                "intrusions": intrusions,
                "max_occupancy": self._max_occupancy[z.name],
                "total_dwell_sec": round(sum(dwells), 2),
                "max_dwell_sec": round(max(dwells), 2) if dwells else 0.0,
            }
        return out

    def per_track_dwell(self) -> list[dict[str, object]]:
        """(ゾーン, tracker_id) ごとの滞留秒のリスト（テーブル表示用）。"""
        return [
            {"zone": zone, "tracker_id": tid, "dwell_sec": round(sec, 2)}
            for (zone, tid), sec in sorted(self.dwell.items())
        ]
