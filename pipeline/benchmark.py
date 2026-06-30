"""推論レイテンシ／スループット計測（Phase 5）。

レイテンシ統計（mean / p50 / p95 / fps）は依存なしで単体テスト可能。
実モデルのベンチ（benchmark_processor）は cv2/torch を要するため遅延 import。
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field


def _percentile(sorted_vals: list[float], p: float) -> float:
    """線形補間によるパーセンタイル（p は 0〜100）。"""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return sorted_vals[int(k)]
    return sorted_vals[lo] * (hi - k) + sorted_vals[hi] * (k - lo)


@dataclass
class LatencyStats:
    """フレーム毎のレイテンシ（ミリ秒）から各種統計を計算する。"""

    samples_ms: list[float] = field(default_factory=list)

    def add(self, ms: float) -> None:
        self.samples_ms.append(ms)

    @property
    def count(self) -> int:
        return len(self.samples_ms)

    @property
    def mean_ms(self) -> float:
        return sum(self.samples_ms) / len(self.samples_ms) if self.samples_ms else 0.0

    def percentile_ms(self, p: float) -> float:
        return _percentile(sorted(self.samples_ms), p)

    @property
    def fps(self) -> float:
        """平均レイテンシから求めるスループット（frames/sec）。"""
        m = self.mean_ms
        return 1000.0 / m if m > 0 else 0.0

    def summary(self) -> dict[str, float]:
        return {
            "count": self.count,
            "mean_ms": round(self.mean_ms, 2),
            "p50_ms": round(self.percentile_ms(50), 2),
            "p95_ms": round(self.percentile_ms(95), 2),
            "fps": round(self.fps, 2),
        }


def benchmark_processor(processor, frames: list, warmup: int = 3) -> LatencyStats:
    """FrameProcessor を一連のフレームで実行しレイテンシを計測する。

    warmup フレームは（MPS/CUDA の初回コンパイル等を除くため）計測から除外する。
    """
    stats = LatencyStats()
    for i, frame in enumerate(frames):
        t0 = time.perf_counter()
        processor.process(frame, frame_idx=i)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        if i >= warmup:
            stats.add(dt_ms)
    return stats
