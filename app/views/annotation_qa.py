"""アノテーション品質ビュー（Phase 0 雛形 / 仕様書 §4.3）。

Phase 6 で Claude Vision による bbox/ラベルの下書き生成・妥当性レビューを実装する。
ここではレイアウト骨格のみ。
"""

from __future__ import annotations

import streamlit as st

st.title("🏷 Annotation QA")
st.caption("アノテーション品質画面（Phase 0 雛形）")

left, right = st.columns(2)

with left:
    st.subheader("画像")
    st.file_uploader("フレーム画像をアップロード", type=["jpg", "jpeg", "png"], disabled=True)
    st.empty()

with right:
    st.subheader("検出された問題（Claude Vision）")
    st.info("Phase 6 で Claude Vision によるラベル妥当性チェックを実装します。", icon="🚧")
    st.write("- ⚠ bbox が対象を内包しきれていない")
    st.write("- ⚠ ラベル不一致の可能性（例: 車 → 自転車）")
    st.write("- ✅ ラベル妥当")

cols = st.columns(4)
cols[0].button("自動下書き生成", disabled=True)
cols[1].button("人手で修正", disabled=True)
cols[2].button("承認", disabled=True)
cols[3].button("却下", disabled=True)
