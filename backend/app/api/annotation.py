"""アノテーション QA API（Streamlit 版 `app/views/annotation_qa.py` に対応）。

    POST /api/annotation/review   画像 + 提案ラベル → Claude Vision のレビュー（Markdown）

画像は保存せず、その場で Claude に渡して結果だけを返す（Streamlit 版と同じ）。
`ANTHROPIC_API_KEY` が要る処理なので、失敗時は同じ案内文言を返す。
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.app.core import storage
from backend.app.schemas import AnnotationReviewResponse

router = APIRouter(prefix="/api/annotation", tags=["annotation"])


def parse_labels(text: str) -> list[str]:
    """カンマ区切りの提案ラベルを正規化する（空白除去・空要素の除去・重複排除）。

    Streamlit 版は `[s.strip() for s in labels_text.split(",") if s.strip()]` 相当。
    重複排除は入力順を保つ。
    """
    labels: list[str] = []
    for chunk in text.split(","):
        label = chunk.strip()
        if label and label not in labels:
            labels.append(label)
    return labels


@router.post("/review", response_model=AnnotationReviewResponse)
async def review(
    file: UploadFile = File(...),
    labels: str = Form(default=""),
) -> AnnotationReviewResponse:
    """フレーム画像の bbox/ラベル妥当性を Claude Vision でレビューする。"""
    try:
        image_bytes = storage.read_image_upload(file.file, file.filename or "frame.jpg")
    except storage.StorageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    proposed = parse_labels(labels)
    if not proposed:
        raise HTTPException(status_code=400, detail="提案ラベルを1つ以上入力してください（カンマ区切り）。")

    # 遅延 import（anthropic）。未導入・キー未設定はここで例外になる。
    from pipeline.claude_vision import DEFAULT_MODEL, review_annotation

    try:
        result = review_annotation(image_bytes, file.filename or "frame.jpg", proposed)
    except Exception as e:  # noqa: BLE001 — Streamlit 版と同じ案内を返す
        raise HTTPException(
            status_code=502,
            detail=f"レビューに失敗しました: {e}（`ANTHROPIC_API_KEY` の設定を確認してください）",
        ) from e

    return AnnotationReviewResponse(review=result, model=DEFAULT_MODEL, labels=proposed)
