"""メイン解析ビュー（Phase 1–2 / 仕様書 §4.1）。

mp4 アップロード → OpenCV フレーム抽出 → YOLO11 検出（＋セグ／ByteTrack 追跡） →
ゾーン解析（滞留時間・侵入） → 注釈付き動画書き出し → テーブルと CSV/JSON エクスポート。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import streamlit as st

from pipeline.detections import COCO_COMMON, summarize, to_csv_bytes, to_json_bytes
from pipeline.detector import AVAILABLE_MODELS, SEG_MODELS, Detector
from pipeline.device import describe_device
from pipeline.video import process_tracking_video
from pipeline.zones import Zone

st.title("🎥 Video ML Analytics Studio")
st.caption("メイン解析画面 — Phase 1–2（検出 / セグ / 追跡 / ゾーン）")

info = describe_device()
cols = st.columns(4)
cols[0].metric("Device", str(info["device"]).upper())
cols[1].metric("torch", str(info["torch"] or "未導入"))
cols[2].metric("MPS", "✅" if info["mps_available"] else "—")
cols[3].metric("CUDA", "✅" if info["cuda_available"] else "—")

DEFAULT_ZONES = json.dumps(
    [{"name": "ゾーンA", "polygon": [[0.3, 0.3], [0.7, 0.3], [0.7, 0.9], [0.3, 0.9]]}],
    ensure_ascii=False,
    indent=2,
)


@st.cache_resource(show_spinner="モデルを読み込み中…")
def load_detector(model_name: str, device: str, conf: float, classes_key: tuple[int, ...] | None) -> Detector:
    classes = list(classes_key) if classes_key else None
    return Detector(model_name=model_name, device=device, conf=conf, classes=classes)


def parse_zones(text: str) -> list[Zone]:
    """JSON テキストを Zone のリストに変換（正規化座標 0〜1）。"""
    data = json.loads(text)
    zones: list[Zone] = []
    for item in data:
        polygon = [(float(x), float(y)) for x, y in item["polygon"]]
        zones.append(Zone(name=str(item["name"]), polygon=polygon))
    return zones


# ----- サイドバー設定 -----
with st.sidebar:
    st.subheader("入力ソース")
    st.radio("ソース", ["mp4", "iPhone (Continuity Camera) — P3"], index=0, key="source")

    st.subheader("タスク")
    enable_seg = st.checkbox("セグメンテーション（YOLO11-seg）", value=False)
    enable_track = st.checkbox("トラッキング（ByteTrack / ID付与）", value=True)
    enable_zone = st.checkbox("ゾーン解析（滞留・侵入）", value=False, disabled=not enable_track)
    if enable_zone and not enable_track:
        st.caption("※ ゾーン解析にはトラッキングが必要です")

    st.subheader("モデル")
    model_list = SEG_MODELS if enable_seg else AVAILABLE_MODELS
    model_name = st.selectbox("YOLO11 モデル", list(model_list), index=1)
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
    trace_length = st.slider("軌跡の長さ（フレーム）", 5, 120, 30, disabled=not enable_track)

    zone_text = DEFAULT_ZONES
    if enable_zone:
        st.subheader("ゾーン定義（正規化 0〜1 / JSON）")
        zone_text = st.text_area("polygon", value=DEFAULT_ZONES, height=180)

class_ids = None if all_classes else tuple(COCO_COMMON[n] for n in selected_names)

# ----- メイン -----
center, right = st.columns([3, 1.4])

with center:
    st.subheader("映像プレビュー")
    uploaded = st.file_uploader("mp4 をアップロード", type=["mp4", "mov", "avi"])
    run = st.button("▶ Run 解析", type="primary", disabled=uploaded is None)

if run and uploaded is not None:
    if not all_classes and not selected_names:
        st.warning("対象クラスを1つ以上選ぶか「全クラス」を有効にしてください。")
        st.stop()

    zones: list[Zone] = []
    if enable_zone:
        try:
            zones = parse_zones(zone_text)
        except Exception as e:  # noqa: BLE001
            st.error(f"ゾーン定義(JSON)の解析に失敗しました: {e}")
            st.stop()

    workdir = Path(tempfile.mkdtemp(prefix="mlmotion_"))
    in_path = workdir / uploaded.name
    in_path.write_bytes(uploaded.getbuffer())
    out_path = workdir / f"annotated_{Path(uploaded.name).stem}.mp4"

    try:
        detector = load_detector(model_name, str(info["device"]), conf, class_ids)
    except Exception as e:  # noqa: BLE001
        st.error(f"モデルの読み込みに失敗しました: {e}")
        st.stop()

    progress = st.progress(0.0, text="解析中…")

    def _cb(cur: int, total: int) -> None:
        progress.progress(min(1.0, cur / total), text=f"解析中… {cur}/{total} フレーム")

    try:
        result = process_tracking_video(
            str(in_path),
            str(out_path),
            detector,
            enable_masks=enable_seg,
            enable_tracking=enable_track,
            zones=zones,
            frame_stride=frame_stride,
            trace_length=trace_length,
            progress_cb=_cb,
        )
    except Exception as e:  # noqa: BLE001
        st.error(f"動画処理に失敗しました: {e}")
        st.stop()
    finally:
        progress.empty()

    st.session_state["p2_result"] = {
        "records": result.records,
        "output_path": result.output_path,
        "frames_processed": result.frames_processed,
        "frames_total": result.frames_total,
        "zone_summary": result.zone_summary,
        "per_track_dwell": result.per_track_dwell,
        "stem": Path(uploaded.name).stem,
    }

# ----- 結果表示 -----
res = st.session_state.get("p2_result")

with center:
    if res and Path(res["output_path"]).exists():
        st.video(res["output_path"])
        st.caption("ブラウザで再生できない場合は右の「注釈付き動画」からDLしてください（コーデック依存）。")

with right:
    st.subheader("結果ペイン")
    if not res:
        st.info("mp4 をアップロードして Run すると、統計・ゾーン解析・エクスポートが出ます。", icon="📤")
    else:
        records = res["records"]
        ids = {r.tracker_id for r in records if r.tracker_id is not None}
        st.metric("総検出数", len(records))
        st.metric("ユニークID数", len(ids))
        st.metric("処理フレーム", f"{res['frames_processed']} / {res['frames_total']}")

        st.markdown("**クラス別（延べ / 最大同時）**")
        stats = summarize(records)
        if stats:
            st.dataframe(
                [{"クラス": k, "延べ": v["total"], "最大同時": v["max_in_frame"]} for k, v in stats.items()],
                use_container_width=True, hide_index=True,
            )
        else:
            st.write("検出ゼロ")

        st.download_button(
            "⬇ CSV", data=to_csv_bytes(records), file_name=f"{res['stem']}_detections.csv", mime="text/csv"
        )
        st.download_button(
            "⬇ JSON", data=to_json_bytes(records),
            file_name=f"{res['stem']}_detections.json", mime="application/json",
        )
        if Path(res["output_path"]).exists():
            st.download_button(
                "⬇ 注釈付き動画", data=Path(res["output_path"]).read_bytes(),
                file_name=f"{res['stem']}_annotated.mp4", mime="video/mp4",
            )
        st.button("📝 NL要約（Claude）— P6", disabled=True)

# ----- ゾーン解析・検出テーブル -----
if res:
    with center:
        zone_summary = res.get("zone_summary") or {}
        if zone_summary:
            st.subheader("ゾーン解析")
            st.dataframe(
                [
                    {
                        "ゾーン": name,
                        "通過ID数": s["unique_tracks"],
                        "侵入回数": s["intrusions"],
                        "最大同時": s["max_occupancy"],
                        "合計滞留(s)": s["total_dwell_sec"],
                        "最大滞留(s)": s["max_dwell_sec"],
                    }
                    for name, s in zone_summary.items()
                ],
                use_container_width=True, hide_index=True,
            )
            if res.get("per_track_dwell"):
                st.caption("ID別 滞留時間")
                st.dataframe(res["per_track_dwell"], use_container_width=True, hide_index=True)

        st.subheader("検出結果テーブル")
        st.dataframe([r.to_dict() for r in res["records"]], use_container_width=True, hide_index=True)
