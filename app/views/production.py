"""本番化・最適化ビュー（Phase 5 / 仕様書 §5）。

ディレクトリ一括のバッチ推論、モデル変換（ONNX/CoreML/量子化）、
レイテンシ・スループットのモニタリングを行う。
"""

from __future__ import annotations

import streamlit as st

from pipeline.batch import build_manifest, discover_media, run_batch
from pipeline.detector import AVAILABLE_MODELS, SEG_MODELS
from pipeline.device import describe_device
from pipeline.export_model import EXPORT_FORMATS, quantization_label
from pipeline.registry import STAGES, model_uri

st.title("⚙️ 本番化・最適化")
st.caption("バッチ推論 / モデル変換・量子化 / レイテンシ計測 — Phase 5")

info = describe_device()
st.caption(f"Device: **{str(info['device']).upper()}** / torch: {info['torch'] or '未導入'}")

# ----- バッチ推論 -----
st.subheader("バッチ推論（ディレクトリ一括）")
c1, c2 = st.columns(2)
in_dir = c1.text_input("入力ディレクトリ", value="data/incoming")
out_dir = c2.text_input("出力ディレクトリ", value="output_batch")
bc1, bc2, bc3 = st.columns(3)
b_model = bc1.selectbox("モデル", list(AVAILABLE_MODELS) + list(SEG_MODELS), index=1)
b_conf = bc2.slider("信頼度", 0.0, 1.0, 0.25, 0.05)
b_stride = bc3.slider("フレーム間引き", 1, 10, 2)

if st.button("📁 入力ディレクトリを確認"):
    found = discover_media(in_dir)
    st.write(f"{len(found)} 件の動画を検出:")
    st.write(found or "（動画が見つかりません）")

if st.button("▶ バッチ実行", type="primary"):
    progress = st.progress(0.0, text="バッチ処理中…")

    def _cb(cur: int, total: int) -> None:
        progress.progress(min(1.0, cur / total) if total else 1.0, text=f"処理中… {cur}/{total} ファイル")

    try:
        result = run_batch(
            in_dir, out_dir, model_name=b_model, conf=b_conf,
            enable_tracking=True, frame_stride=b_stride, progress_cb=_cb,
        )
        progress.empty()
        st.success(f"完了: 成功 {result.succeeded} / 失敗 {result.failed} / 総検出 {result.total_detections}")
        st.dataframe(build_manifest(result), use_container_width=True, hide_index=True)
    except Exception as e:  # noqa: BLE001
        progress.empty()
        st.error(f"バッチ処理に失敗しました: {e}")

# ----- モデル変換・量子化 -----
st.subheader("モデル変換・量子化")
e1, e2, e3 = st.columns(3)
weights = e1.text_input("重みパス", value="yolo11s.pt")
fmt = e2.selectbox("書式", list(EXPORT_FORMATS), index=0)
quant = e3.selectbox("量子化", ["FP32", "FP16", "INT8"], index=0)
half, int8 = quant == "FP16", quant == "INT8"
st.caption(f"設定: {fmt} / {quantization_label(half, int8)}")
if st.button("🛠 変換を実行"):
    try:
        from pipeline.export_model import export_model

        with st.spinner("変換中…（初回は時間がかかります）"):
            out = export_model(weights, fmt, half=half, int8=int8)
        st.success(f"変換完了: {out}")
    except Exception as e:  # noqa: BLE001
        st.error(f"変換に失敗しました: {e}")

# ----- レイテンシ計測 -----
st.subheader("レイテンシ・スループット計測")
st.write(
    "`pipeline.benchmark.benchmark_processor()` で FrameProcessor を一連フレームに対し実行し、"
    "mean/p50/p95/fps を計測します（warmup 除外）。MPS/CoreML/ONNX/量子化の前後比較に使用。"
)
st.info("実計測は実機（M2 Mac）で `streamlit run` 中に実行してください。", icon="⏱")

# ----- Registry からのモデル取得 -----
st.subheader("Model Registry からの取得・差し替え")
r1, r2 = st.columns(2)
reg_name = r1.text_input("モデル名", value="ml_motion_detector")
reg_stage = r2.selectbox("ステージ", [s for s in STAGES if s != "None"], index=1)
st.code(model_uri(reg_name, reg_stage), language="text")
st.caption("`download_model()` で上記 URI の成果物を取得し、バッチ/リアルタイムのモデルを差し替えます。")
