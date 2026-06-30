"""pipeline.benchmark.benchmark_processor の単体テスト（ダミー processor で依存ゼロ）。"""

from __future__ import annotations

from pipeline.benchmark import LatencyStats, benchmark_processor


class _DummyProcessor:
    """process() を呼ばれた回数だけ記録するダミー（重い依存なし）。"""

    def __init__(self) -> None:
        self.calls = 0

    def process(self, frame, frame_idx: int = 0, time_sec: float = 0.0):
        self.calls += 1
        return frame


def test_benchmark_processor_warmup_excluded():
    proc = _DummyProcessor()
    frames = list(range(10))  # フレームの中身は問わない
    stats = benchmark_processor(proc, frames, warmup=3)
    assert isinstance(stats, LatencyStats)
    assert proc.calls == 10           # 全フレームで process は呼ばれる
    assert stats.count == 7           # warmup=3 を除外して計測


def test_benchmark_processor_no_warmup():
    proc = _DummyProcessor()
    stats = benchmark_processor(proc, list(range(4)), warmup=0)
    assert stats.count == 4
    assert stats.mean_ms >= 0.0


def test_benchmark_processor_all_warmup():
    proc = _DummyProcessor()
    stats = benchmark_processor(proc, list(range(3)), warmup=5)
    assert stats.count == 0           # 全て warmup → 計測ゼロ
    assert stats.fps == 0.0
