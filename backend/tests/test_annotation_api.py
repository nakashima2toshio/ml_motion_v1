"""アノテーション QA API のテスト。

実際の Claude 呼び出しは行わず、`review_annotation` をスタブに差し替えて
「検証 → Claude へ渡す値 → 応答の形」を確認する。
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from backend.app.api.annotation import parse_labels
from backend.app.core import storage
from backend.app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def stub_claude(monkeypatch: pytest.MonkeyPatch) -> dict:
    """`pipeline.claude_vision.review_annotation` を差し替えて呼び出し引数を記録する。"""
    calls: dict = {}

    def fake_review(image_bytes, filename, proposed_labels, model=None):
        calls["image_bytes"] = image_bytes
        calls["filename"] = filename
        calls["labels"] = proposed_labels
        return "## 検出された問題\n\n- person の bbox が広すぎます"

    import pipeline.claude_vision

    monkeypatch.setattr(pipeline.claude_vision, "review_annotation", fake_review)
    return calls


def _post(client: TestClient, name: str = "frame.jpg", data: bytes = b"image-bytes", labels: str = "person,car"):
    return client.post(
        "/api/annotation/review",
        files={"file": (name, io.BytesIO(data), "image/jpeg")},
        data={"labels": labels},
    )


# ---------------------------------------------------------------------------
# ラベルの正規化
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("person,car", ["person", "car"]),
        (" person , car ", ["person", "car"]),  # 前後の空白を落とす
        ("person,,car,", ["person", "car"]),  # 空要素を落とす
        ("person,car,person", ["person", "car"]),  # 重複は入力順で 1 つに
        ("", []),
        ("   ", []),
        (",,,", []),
    ],
)
def test_parse_labels(raw: str, expected: list[str]) -> None:
    assert parse_labels(raw) == expected


# ---------------------------------------------------------------------------
# 入力検証
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["frame.jpg", "frame.jpeg", "frame.PNG", "frame.webp"])
def test_accepts_supported_image_types(client: TestClient, stub_claude: dict, name: str) -> None:
    assert _post(client, name=name).status_code == 200


@pytest.mark.parametrize("name", ["frame.gif", "frame.bmp", "frame.mp4", "frame"])
def test_rejects_unsupported_image_types(client: TestClient, stub_claude: dict, name: str) -> None:
    res = _post(client, name=name)
    assert res.status_code == 400
    assert "未対応の画像形式" in res.json()["detail"]


def test_rejects_empty_labels(client: TestClient, stub_claude: dict) -> None:
    res = _post(client, labels="  ,  ")
    assert res.status_code == 400
    assert "提案ラベルを1つ以上" in res.json()["detail"]


def test_rejects_empty_image(client: TestClient, stub_claude: dict) -> None:
    res = _post(client, data=b"")
    assert res.status_code == 400
    assert "空のファイル" in res.json()["detail"]


def test_rejects_oversized_image(client: TestClient, stub_claude: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage, "MAX_IMAGE_BYTES", 16)
    res = _post(client, data=b"x" * 100)
    assert res.status_code == 400
    assert "大きすぎます" in res.json()["detail"]


# ---------------------------------------------------------------------------
# レビュー
# ---------------------------------------------------------------------------


def test_review_passes_image_and_labels_to_claude(client: TestClient, stub_claude: dict) -> None:
    res = _post(client, data=b"jpeg-data", labels=" person , car , person ")
    assert res.status_code == 200

    assert stub_claude["image_bytes"] == b"jpeg-data"
    assert stub_claude["filename"] == "frame.jpg"
    assert stub_claude["labels"] == ["person", "car"]


def test_review_returns_markdown_model_and_labels(client: TestClient, stub_claude: dict) -> None:
    body = _post(client).json()
    assert body["review"].startswith("## 検出された問題")
    assert body["labels"] == ["person", "car"]
    assert body["model"], "使用モデルを返す（画面に出すため）"


def test_review_failure_reports_api_key_hint(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """`ANTHROPIC_API_KEY` 未設定時の案内を Streamlit 版と揃える。"""

    def boom(*args, **kwargs):
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    import pipeline.claude_vision

    monkeypatch.setattr(pipeline.claude_vision, "review_annotation", boom)

    res = _post(client)
    assert res.status_code == 502
    detail = res.json()["detail"]
    assert "レビューに失敗しました" in detail
    assert "ANTHROPIC_API_KEY" in detail


def test_options_expose_claude_model(client: TestClient) -> None:
    """画面はレビュー実行前にモデル名を表示する。"""
    from pipeline.claude_vision import DEFAULT_MODEL

    assert client.get("/api/meta/options").json()["claude_model"] == DEFAULT_MODEL
