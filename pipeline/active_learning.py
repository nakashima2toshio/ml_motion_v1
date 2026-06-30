"""Active Learning 用サンプル選択（Phase 6 / 仕様書 §5 P6）。

低確信（低 confidence）の検出を含むフレームを優先的に抽出し、再アノテーション・
再学習の候補とする。重い依存を持たず単体テスト可能。
"""

from __future__ import annotations

from dataclasses import dataclass

from pipeline.detections import DetectionRecord


@dataclass
class FrameUncertainty:
    """1 フレームの不確実性サマリ。"""

    frame: int
    min_confidence: float
    mean_confidence: float
    n_detections: int


def select_low_confidence(
    records: list[DetectionRecord], conf_threshold: float = 0.5, top_k: int = 20
) -> list[FrameUncertainty]:
    """低確信の検出を含むフレームを不確実性の高い順に最大 top_k 件返す。

    フレーム内に conf_threshold 未満の検出が1つでもあれば候補とし、
    平均 confidence の昇順（=不確実な順）に並べる。
    """
    by_frame: dict[int, list[float]] = {}
    for r in records:
        by_frame.setdefault(r.frame, []).append(r.confidence)

    candidates: list[FrameUncertainty] = []
    for frame, confs in by_frame.items():
        if any(c < conf_threshold for c in confs):
            candidates.append(
                FrameUncertainty(
                    frame=frame,
                    min_confidence=round(min(confs), 4),
                    mean_confidence=round(sum(confs) / len(confs), 4),
                    n_detections=len(confs),
                )
            )

    candidates.sort(key=lambda f: (f.mean_confidence, f.min_confidence))
    return candidates[: max(0, top_k)]
