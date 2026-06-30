"""pipeline.claude_vision._first_text の単体テスト（疑似レスポンスで依存ゼロ）。

anthropic SDK は遅延 import のため、レスポンス整形ロジックは疑似オブジェクトで検証できる。
"""

from __future__ import annotations

from dataclasses import dataclass

from pipeline.claude_vision import _first_text


@dataclass
class _Block:
    type: str
    text: str = ""


@dataclass
class _Resp:
    content: list


def test_first_text_returns_first_text_block():
    resp = _Resp(content=[_Block("thinking", "..."), _Block("text", "要約本文"), _Block("text", "2つ目")])
    assert _first_text(resp) == "要約本文"


def test_first_text_empty_when_no_text_block():
    resp = _Resp(content=[_Block("tool_use", ""), _Block("image", "")])
    assert _first_text(resp) == ""


def test_first_text_empty_content():
    assert _first_text(_Resp(content=[])) == ""
