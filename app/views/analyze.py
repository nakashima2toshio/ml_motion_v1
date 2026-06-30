"""メイン解析ビュー（Phase 1 / 仕様書 §4.1）。

mp4 アップロード → OpenCV フレーム抽出 → YOLO11 検出 → 注釈付き動画書き出し →
検出結果テーブルと CSV/JSON エクスポート。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from pipeline.detections import COCO_COMMON, summarize, to_csv_bytes, to_json_bytes
from pipeline.detector import AVAILABLE_MODELS, Detector
from pipeline.device import describe_device
from pipeline.video import process_video

st.title("🎥 Video ML Analytics Studio")
st.caption("メイン解析画面 — Phase 1（mp4 検出 MVP）")

info = describe_device()
cols = st.columns(4)
cols[0].metric("Device", str(info["device"]).upper())
cols[1].metric("torch", str(info["torch"] or "未導入"))
cols[2].metric("MPS", "✅" if info["mps_available"] else "—")
cols[3].metric("CUDA", "✅" if info["cuda_available"] else "—")


@st.cache_resource(show_spinner="モデルを読み込み中…")
def load_detector(model_name: str, device: str, conf: float, classes_key: tuple[int, ...] | None) -> Detector:
    """モデルをキャッシュ。conf/classes は predict 時に上書きするので識別キーに含める。"""
    classes = list(classes_key) if classes_key else None
    return Detector(model_name=model_name, device=device, conf=conf, classes=classes)


# ----- サイドバー設定 -----
with st.sidebar:
    st.subheader("入力ソース")
    st.radio("ソース", ["mp4", "iPhone (Continuity Camera) — P3"], index=0, key="source")

    st.subheader("モデル")
    model_name = st.selectbox("YOLO11 モデル", list(AVAILABLE_MODELS), index=1)
    conf = st.slider("信頼度しきい値", 0.0, 1.0, 0.25, 0.05)

    st.subheader("対象クラス")
    all_classes = st.checkbox("全クラス（COCO 80）", value=False)
    selected_names = st.multiselect(
        "クラス（COCO 代表）",
        options=list(COCO_COMMON.keys()),
        default=list(COCO_COMMON.keys()),
        disabled=all_classes,
    )

    st.subheader("処理設定")
    frame_stride = st.slider("フレーム間引き（N フレームに1回）", 1, 10, 1)

class_ids = None if all_classes else tuple(COCO_COMMON[n] for n in selected_names)

# ----- メイン -----
center, right = st.columns([3, 1.3])

with center:
    st.subheader("映像プレビュー")
    uploaded = st.file_uploader("mp4 をアップロード", type=["mp4", "mov", "avi"])
    run = st.button("▶ Run 検出", type="primary", disabled=uploaded is None)

if run and uploaded is not None:
    if not all_classes and not selected_names:
        st.warning("対象クラスを1つ以上選ぶか「全クラス」を有効にしてください。")
        st.stop()

    workdir = Path(tempfile.mkdtemp(prefix="mlmotion_"))
    in_path = workdir / uploaded.name
    in_path.write_bytes(uploaded.getbuffer())
    out_path = workdir / f"annotated_{Path(uploaded.name).stem}.mp4"

    try:
        detector = load_detector(model_name, str(info["device"]), conf, class_ids)
    except Exception as e:  # noqa: BLE001 — UI へ集約表示
        st.error(f"モデルの読み込みに失敗しました: {e}")
        st.stop()

    progress = st.progress(0.0, text="検出中…")

    def _cb(cur: int, total: int) -> None:
        progress.progress(min(1.0, cur / total), text=f"検出中… {cur}/{total} フレーム")

    try:
        result = process_video(str(in_path), str(out_path), detector, frame_stride=frame_stride, progress_cb=_cb)
    except Exception as e:  # noqa: BLE001
        st.error(f"動画処理に失敗しました: {e}")
        st.stop()
    finally:
        progress.empty()

    # 結果をセッションに保持（再実行せずにダウンロード可能にする）。
    st.session_state["p1_result"] = {
        "records": result.records,
        "output_path": result.output_path,
        "frames_processed": result.frames_processed,
        "frames_total": result.frames_total,
        "fps": result.fps,
        "stem": Path(uploaded.name).stem,
    }

# ----- 結果表示 -----
res = st.session_state.get("p1_result")

with center:
    if res:
        out_path = res["output_path"]
        if Path(out_path).exists():
            st.video(out_path)
            st.caption(
                "ブラウザで再生できない場合は下の「注釈付き動画」からダウンロードしてください"
                "（コーデック依存）。"
            )

with right:
    st.subheader("結果ペイン")
    if not res:
        st.info("mp4 をアップロードして Run すると、検出統計とエクスポートが表示されます。", icon="📤")
    else:
        records = res["records"]
        st.metric("総検出数", len(records))
        st.metric("処理フレーム", f"{res['frames_processed']} / {res['frames_total']}")

        st.markdown("**クラス別（延べ / 最大同時）**")
        stats = summarize(records)
        if stats:
            st.dataframe(
                [{"クラス": k, "延べ": v["total"], "最大同時": v["max_in_frame"]} for k, v in stats.items()],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.write("検出ゼロ")

        st.download_button(
            "⬇ CSV", data=to_csv_bytes(records), file_name=f"{res['stem']}_detections.csv", mime="text/csv"
        )
        st.download_button(
            "⬇ JSON",
            data=to_json_bytes(records),
            file_name=f"{res['stem']}_detections.json",
            mime="application/json",
        )
        if Path(res["output_path"]).exists():
            st.download_button(
                "⬇ 注釈付き動画",
                data=Path(res["output_path"]).read_bytes(),
                file_name=f"{res['stem']}_annotated.mp4",
                mime="video/mp4",
            )
        st.button("📝 NL要約（Claude）— P6", disabled=True)

if res:
    with center:
        st.subheader("検出結果テーブル")
        rows = [r.to_dict() for r in res["records"]]
        st.dataframe(rows, use_container_width=True, hide_index=True)
