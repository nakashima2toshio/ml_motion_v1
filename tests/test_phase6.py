"""Phase 6 の依存なしロジック（Claude プロンプト構築 / Active Learning 選択）の単体テスト。

anthropic SDK は遅延 import なので、プロンプト構築・選択ロジックは API なしで検証できる。
"""

from __future__ import annotations

from pipeline.active_learning import select_low_confidence
from pipeline.claude_vision import (
    build_nl_query_prompt,
    build_review_prompt,
    build_summary_prompt,
    media_type_for,
)
from pipeline.detections import DetectionRecord


# ---- Claude プロンプト構築 ----
def test_default_model_fallback_is_opus_48():
    """ANTHROPIC_MODEL 未設定時の既定モデルが claude-opus-4-8 であること。

    DEFAULT_MODEL は os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8") で環境変数により
    上書き可能なため、env を外して再読込し「フォールバック既定」を検証する（env 依存にしない）。
    """
    import importlib
    import os

    import pipeline.claude_vision as cv

    original = os.environ.pop("ANTHROPIC_MODEL", None)
    try:
        importlib.reload(cv)
        assert cv.DEFAULT_MODEL == "claude-opus-4-8"
    finally:
        if original is not None:
            os.environ["ANTHROPIC_MODEL"] = original
        importlib.reload(cv)  # 元の環境ベースの値へ戻す


def test_media_type_for():
    assert media_type_for("frame.png") == "image/png"
    assert media_type_for("a.JPG") == "image/jpeg"
    assert media_type_for("x.webp") == "image/webp"
    assert media_type_for("noext") == "image/jpeg"


def test_build_summary_prompt_includes_stats():
    stats = {"person": {"total": 3, "max_in_frame": 2}}
    zones = {"ゾーンA": {"unique_tracks": 1, "intrusions": 1, "max_occupancy": 1,
                        "total_dwell_sec": 0.3, "max_dwell_sec": 0.3}}
    prompt = build_summary_prompt(stats, zones)
    assert "person" in prompt and "ゾーンA" in prompt
    assert "要約" in prompt


def test_build_summary_prompt_empty():
    prompt = build_summary_prompt({}, {})
    assert "検出なし" in prompt and "ゾーン未定義" in prompt


def test_build_review_prompt_lists_labels():
    assert "person" in build_review_prompt(["person", "car"])
    assert "ラベルなし" in build_review_prompt([])


def test_build_nl_query_prompt():
    p = build_nl_query_prompt("赤い服の人", ["0: 人が2人", "5: 車が1台"])
    assert "赤い服の人" in p and "0: 人が2人" in p
    assert "JSON" in p


# ---- Active Learning ----
def _recs():
    return [
        DetectionRecord(0, 0.0, 0, "person", 0.95, 0, 0, 1, 1),   # frame0: 高確信のみ
        DetectionRecord(1, 0.1, 0, "person", 0.30, 0, 0, 1, 1),   # frame1: 低確信
        DetectionRecord(1, 0.1, 2, "car", 0.40, 0, 0, 1, 1),
        DetectionRecord(2, 0.2, 0, "person", 0.45, 0, 0, 1, 1),   # frame2: 低確信(やや高)
    ]


def test_select_low_confidence_filters_and_orders():
    out = select_low_confidence(_recs(), conf_threshold=0.5, top_k=10)
    frames = [f.frame for f in out]
    assert 0 not in frames                 # 高確信フレームは除外
    assert frames == [1, 2]                # 平均confidence昇順（1=0.35 < 2=0.45）


def test_select_low_confidence_top_k():
    out = select_low_confidence(_recs(), conf_threshold=0.5, top_k=1)
    assert len(out) == 1 and out[0].frame == 1


def test_select_low_confidence_none_below_threshold():
    out = select_low_confidence(_recs(), conf_threshold=0.2, top_k=10)
    assert out == []
