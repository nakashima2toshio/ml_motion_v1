"""アノテーション品質ビュー（Phase 6 / 仕様書 §4.3）。

Claude Vision でフレーム画像の bbox/ラベル妥当性をレビューする。
"""

from __future__ import annotations

import streamlit as st

from pipeline.claude_vision import DEFAULT_MODEL, review_annotation

st.title("🏷 Annotation QA")
st.caption("アノテーション品質画面 — Phase 6（Claude Vision レビュー）")

st.caption(f"モデル: `{DEFAULT_MODEL}`（`ANTHROPIC_API_KEY` が必要）")

left, right = st.columns(2)

with left:
    st.subheader("画像")
    uploaded = st.file_uploader("フレーム画像をアップロード", type=["jpg", "jpeg", "png", "webp"])
    if uploaded is not None:
        st.image(uploaded, use_container_width=True)
    labels_text = st.text_input("提案ラベル（カンマ区切り）", value="person,car")
    review = st.button("🔍 Claude でレビュー", type="primary", disabled=uploaded is None)

with right:
    st.subheader("検出された問題（Claude Vision）")
    if not uploaded:
        st.info("画像をアップロードし、提案ラベルを入れてレビューを実行してください。", icon="🖼")
    elif review:
        labels = [s.strip() for s in labels_text.split(",") if s.strip()]
        try:
            with st.spinner("Claude がレビュー中…"):
                result = review_annotation(uploaded.getvalue(), uploaded.name, labels)
            st.markdown(result)
        except Exception as e:  # noqa: BLE001
            st.error(f"レビューに失敗しました: {e}\n\n`ANTHROPIC_API_KEY` の設定を確認してください。")
