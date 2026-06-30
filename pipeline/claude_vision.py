"""Claude（Anthropic）連携 — 高度化機能（Phase 6 / 仕様書 §7）。

- 検出/ゾーン結果の自然言語サマリ
- フレーム画像の bbox/ラベル妥当性レビュー（Vision）
- 自然言語クエリ → 該当フレーム抽出

anthropic SDK は重い依存のため関数内で遅延 import する。
プロンプト構築・モデル解決は依存なしで単体テスト可能。
モデルは最新世代 Opus 4.8（`claude-opus-4-8`）を既定とする（仕様書 §7）。
"""

from __future__ import annotations

import base64
import os

DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")

_MEDIA_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


def media_type_for(filename: str) -> str:
    """拡張子から画像 media_type を返す（既定 image/jpeg）。"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _MEDIA_TYPES.get(ext, "image/jpeg")


def build_summary_prompt(class_stats: dict, zone_summary: dict) -> str:
    """検出・ゾーン集計から要約用プロンプトを組み立てる（依存なし）。"""
    lines = ["以下の動画解析結果を、日本語で簡潔に要約してください（3〜5文）。", "", "## クラス別検出数"]
    if class_stats:
        for name, s in class_stats.items():
            lines.append(f"- {name}: 延べ{s.get('total', 0)} / 最大同時{s.get('max_in_frame', 0)}")
    else:
        lines.append("- 検出なし")
    lines.append("")
    lines.append("## ゾーン解析")
    if zone_summary:
        for zone, s in zone_summary.items():
            lines.append(
                f"- {zone}: 通過{s.get('unique_tracks', 0)}件 / 侵入{s.get('intrusions', 0)}回 / "
                f"最大同時{s.get('max_occupancy', 0)} / 合計滞留{s.get('total_dwell_sec', 0)}秒"
            )
    else:
        lines.append("- ゾーン未定義")
    return "\n".join(lines)


def build_review_prompt(proposed_labels: list[str]) -> str:
    """アノテーション妥当性レビュー用プロンプト（依存なし）。"""
    labels = "、".join(proposed_labels) if proposed_labels else "（ラベルなし）"
    return (
        "この画像に付与された検出ラベルの妥当性を確認してください。\n"
        f"提案ラベル: {labels}\n\n"
        "各ラベルについて、(1) 妥当 / 要修正の判定、(2) 妥当なら短い理由、"
        "要修正なら正しいと思われるラベルとその理由を、日本語で箇条書きで返してください。"
    )


def build_nl_query_prompt(query: str, frame_summaries: list[str]) -> str:
    """自然言語クエリで該当フレームを選ばせるプロンプト（依存なし）。"""
    lines = [
        f'次の自然言語クエリに該当するフレーム番号を選んでください。クエリ: 「{query}」',
        "",
        "## フレーム一覧（番号: 内容）",
    ]
    lines.extend(frame_summaries)
    lines.append("")
    lines.append("該当するフレーム番号のみを JSON 配列で返してください（例: [0, 5, 12]）。")
    return "\n".join(lines)


def _client():
    import anthropic

    return anthropic.Anthropic()


def _first_text(response) -> str:
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


def summarize_session(class_stats: dict, zone_summary: dict, model: str | None = None) -> str:
    """検出・ゾーン結果を Claude で自然言語要約する（anthropic 遅延 import）。"""
    client = _client()
    resp = client.messages.create(
        model=model or DEFAULT_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": build_summary_prompt(class_stats, zone_summary)}],
    )
    return _first_text(resp)


def review_annotation(
    image_bytes: bytes, filename: str, proposed_labels: list[str], model: str | None = None
) -> str:
    """フレーム画像と提案ラベルを Claude Vision に渡して妥当性レビューを得る。"""
    client = _client()
    data = base64.standard_b64encode(image_bytes).decode("utf-8")
    resp = client.messages.create(
        model=model or DEFAULT_MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type_for(filename), "data": data},
                    },
                    {"type": "text", "text": build_review_prompt(proposed_labels)},
                ],
            }
        ],
    )
    return _first_text(resp)


def nl_query_frames(query: str, frame_summaries: list[str], model: str | None = None) -> list[int]:
    """自然言語クエリに該当するフレーム番号のリストを返す（構造化出力）。"""
    import json

    client = _client()
    resp = client.messages.create(
        model=model or DEFAULT_MODEL,
        max_tokens=1024,
        output_config={
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {"frames": {"type": "array", "items": {"type": "integer"}}},
                    "required": ["frames"],
                    "additionalProperties": False,
                },
            }
        },
        messages=[{"role": "user", "content": build_nl_query_prompt(query, frame_summaries)}],
    )
    text = _first_text(resp)
    try:
        return list(json.loads(text).get("frames", []))
    except (json.JSONDecodeError, AttributeError):
        return []
