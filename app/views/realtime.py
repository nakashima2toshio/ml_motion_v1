"""リアルタイム解析ビュー（Phase 3 / 仕様書 §1.3, §5）。

iPhone 映像を 2 経路で取り込み、検出（＋追跡）を準リアルタイムに行う:
  1) Continuity Camera を OpenCV のカメラデバイスとして取り込む（最推奨・ローカル実行）
  2) streamlit-webrtc によるブラウザカメラ経路（代替）

フレームスキップ・解像度調整・軽量モデル自動切替でスループットを確保する。
"""

from __future__ import annotations

import time

import streamlit as st

from pipeline.camera import (
    RESOLUTION_PRESETS,
    FpsMeter,
    is_lightweight,
    open_camera,
    recommend_realtime_model,
)
from pipeline.detector import AVAILABLE_MODELS, SEG_MODELS, Detector
from pipeline.device import describe_device
from pipeline.realtime import FrameProcessor

st.title("📡 リアルタイム解析")
st.caption("iPhone 映像（Continuity Camera / ブラウザ）での準リアルタイム検出 — Phase 3")

info = describe_device()
st.caption(f"Device: **{str(info['device']).upper()}** / torch: {info['torch'] or '未導入'}")

# ----- サイドバー設定 -----
with st.sidebar:
    st.subheader("取り込み経路")
    route = st.radio("経路", ["Continuity Camera (OpenCV)", "ブラウザ (streamlit-webrtc)"], index=0)

    st.subheader("タスク")
    enable_seg = st.checkbox("セグメンテーション", value=False)
    enable_track = st.checkbox("トラッキング（ByteTrack）", value=True)

    st.subheader("モデル")
    base_list = SEG_MODELS if enable_seg else AVAILABLE_MODELS
    requested_model = st.selectbox("YOLO11 モデル", list(base_list), index=0)
    auto_light = st.checkbox("リアルタイム用に軽量モデルへ自動切替", value=True)
    model_name = recommend_realtime_model(requested_model) if auto_light else requested_model
    if model_name != requested_model:
        st.caption(f"⚡ 自動切替: {requested_model} → **{model_name}**")
    elif not is_lightweight(model_name):
        st.caption("⚠️ 重いモデルです。fps が出ない場合は n/s 系へ。")

    conf = st.slider("信頼度しきい値", 0.0, 1.0, 0.25, 0.05)

    st.subheader("スループット最適化")
    res_key = st.selectbox("解像度", list(RESOLUTION_PRESETS.keys()), index=0)
    frame_skip = st.slider("フレームスキップ（N フレームに1回推論）", 1, 5, 1)

size = RESOLUTION_PRESETS[res_key]


@st.cache_resource(show_spinner="モデルを読み込み中…")
def make_processor(model_name: str, device: str, conf: float, seg: bool, track: bool) -> FrameProcessor:
    detector = Detector(model_name=model_name, device=device, conf=conf)
    return FrameProcessor(detector, enable_masks=seg, enable_tracking=track)


# =========================================================
# 経路 1: Continuity Camera（OpenCV）
# =========================================================
if route.startswith("Continuity"):
    st.info(
        "iPhone を Mac の近くに置き、Continuity Camera を有効化してください。"
        "OpenCV のカメラ一覧に iPhone が現れます（macOS Ventura+ / iPhone XR+）。"
        "※ この経路はローカル実行（Mac 上の `streamlit run`）でのみ動作します。",
        icon="📱",
    )
    cam_index = st.number_input("カメラ index（0=内蔵、1〜=外部/iPhone）", min_value=0, max_value=10, value=0)
    running = st.toggle("▶ 開始 / ⏹ 停止", value=False, key="rt_running")
    frame_slot = st.empty()
    metrics_slot = st.empty()

    if running:
        try:
            processor = make_processor(model_name, str(info["device"]), conf, enable_seg, enable_track)
            processor.reset()
        except Exception as e:  # noqa: BLE001
            st.error(f"モデルの読み込みに失敗しました: {e}")
            st.stop()

        try:
            cap = open_camera(int(cam_index), size=size)
        except Exception as e:  # noqa: BLE001
            st.error(str(e))
            st.stop()

        import cv2  # 表示用の色変換のみ

        meter = FpsMeter(window=30)
        idx = 0
        try:
            # st.session_state["rt_running"] が False になる（トグル操作→再実行）まで回す。
            while st.session_state.get("rt_running", False):
                ok, frame = cap.read()
                if not ok:
                    st.warning("フレームを取得できませんでした。カメラ index を確認してください。")
                    break
                meter.tick(time.monotonic())
                if idx % frame_skip == 0:
                    fr = processor.process(frame, frame_idx=idx, time_sec=idx)
                    annotated = fr.annotated
                    n = fr.n_detections
                else:
                    annotated = frame
                    n = 0
                frame_slot.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), channels="RGB")
                metrics_slot.caption(f"FPS: **{meter.fps:.1f}** / 検出数: {n} / frame {idx}")
                idx += 1
        finally:
            cap.release()
    else:
        st.caption("「開始」を押すとカメラ取り込みを開始します。")

# =========================================================
# 経路 2: streamlit-webrtc（ブラウザカメラ）
# =========================================================
else:
    try:
        import av  # noqa: F401
        from streamlit_webrtc import VideoProcessorBase, webrtc_streamer
    except ImportError:
        st.warning(
            "ブラウザ経路には追加依存が必要です。`uv pip install -e '.[realtime]'`"
            "（streamlit-webrtc, av）を実行してください。",
            icon="📦",
        )
        st.stop()

    processor = make_processor(model_name, str(info["device"]), conf, enable_seg, enable_track)

    class _VideoProcessor(VideoProcessorBase):
        def __init__(self) -> None:
            self.frame_skip = frame_skip
            self._idx = 0

        def recv(self, frame):
            import av as _av

            img = frame.to_ndarray(format="bgr24")
            if self._idx % self.frame_skip == 0:
                fr = processor.process(img, frame_idx=self._idx, time_sec=self._idx)
                img = fr.annotated
            self._idx += 1
            return _av.VideoFrame.from_ndarray(img, format="bgr24")

    st.info("ブラウザのカメラ許可ダイアログで iPhone/Web カメラを選択してください。", icon="🌐")
    webrtc_streamer(
        key="rt-webrtc",
        video_processor_factory=_VideoProcessor,
        media_stream_constraints={"video": True, "audio": False},
    )
