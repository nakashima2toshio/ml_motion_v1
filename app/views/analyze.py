"""メイン解析ビュー（Phase 0 雛形 / 仕様書 §4.1）。

Phase 1 で mp4 アップロード → YOLO11 検出 → 注釈付き動画/CSV 出力を実装する。
ここではレイアウト骨格とデバイス状態の表示のみ。
"""

from __future__ import annotations

import streamlit as st

from pipeline.device import describe_device

st.title("🎥 Video ML Analytics Studio")
st.caption("メイン解析画面（Phase 0 雛形）")

info = describe_device()
cols = st.columns(4)
cols[0].metric("Device", str(info["device"]).upper())
cols[1].metric("torch", str(info["torch"] or "未導入"))
cols[2].metric("MPS", "✅" if info["mps_available"] else "—")
cols[3].metric("CUDA", "✅" if info["cuda_available"] else "—")

left, center, right = st.columns([1, 3, 1.2])

with left:
    st.subheader("入力ソース")
    st.radio("ソース", ["mp4", "iPhone (Continuity Camera)"], key="source", disabled=True)
    st.subheader("タスク")
    st.checkbox("検出", value=True, disabled=True)
    st.checkbox("セグメンテーション", disabled=True)
    st.checkbox("トラッキング", disabled=True)
    st.subheader("モデル")
    st.selectbox("モデル", ["yolo11n", "yolo11s", "yolo11m"], index=1, disabled=True)
    st.slider("信頼度しきい値", 0.0, 1.0, 0.25, disabled=True)

with center:
    st.subheader("映像プレビュー")
    st.info("Phase 1 で mp4 アップロードと検出結果の描画を実装します。", icon="🚧")
    st.empty()

with right:
    st.subheader("結果ペイン")
    st.write("検出統計 / 軌跡・ID / NL要約（Claude）をここに表示予定。")
    st.button("📝 NL要約（Claude）", disabled=True)
