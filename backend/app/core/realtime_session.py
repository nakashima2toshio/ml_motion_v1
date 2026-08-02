"""リアルタイム解析のセッション管理と設定解決。

Streamlit 版 `app/views/realtime.py` の 2 経路を React 版へ移す:

1. **Continuity Camera（サーバ側 OpenCV）** — サーバがカメラを開いて推論し、
   MJPEG（`multipart/x-mixed-replace`）で配信する。`<img>` で表示できる。
   Streamlit 版は `while` ループ内で `st.image` を差し替えていた部分に相当する。
2. **ブラウザカメラ** — ブラウザが `getUserMedia` で取得したフレームを
   WebSocket で送り、注釈付きフレームを受け取る（`streamlit-webrtc` の置き換え）。

⚠️ カメラデバイスは同時に 1 つしか開けないため、経路 1 は**排他**にする。

設定解決と MJPEG のフレーミングは重い依存を持たないので単体テストできる。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from pipeline.camera import RESOLUTION_PRESETS
from pipeline.detector import AVAILABLE_MODELS, SEG_MODELS

# MJPEG のパート境界。
MJPEG_BOUNDARY = "mlmotionframe"

# カメラからフレームを取得できないときに諦めるまでの連続失敗回数。
MAX_READ_FAILURES = 30


class RealtimeError(ValueError):
    """設定不正（呼び出し側で 400 にする）。"""


class CameraBusyError(RuntimeError):
    """カメラが既に使用中（呼び出し側で 409 にする）。"""


@dataclass
class ResolvedSettings:
    """検証・解決済みのリアルタイム設定。"""

    model_name: str
    requested_model: str
    size: tuple[int, int]
    resolution_key: str
    conf: float
    frame_skip: int
    enable_seg: bool
    enable_track: bool
    camera_index: int = 0
    # 画面に出す注意書き（Streamlit 版のキャプションに対応）。
    notes: list[str] = field(default_factory=list)

    @property
    def auto_switched(self) -> bool:
        return self.model_name != self.requested_model


def resolve_settings(
    *,
    model_name: str,
    enable_seg: bool,
    enable_track: bool,
    auto_light: bool,
    conf: float,
    resolution: str,
    frame_skip: int,
    camera_index: int = 0,
) -> ResolvedSettings:
    """リクエストの設定を検証し、軽量モデルへの自動切替まで解決する。

    Streamlit 版の挙動:
      - セグ ON なら SEG_MODELS から選ぶ
      - 「リアルタイム用に軽量モデルへ自動切替」ON なら `recommend_realtime_model`
      - 切替が起きたら「⚡ 自動切替: A → B」、重いままなら「⚠️ 重いモデルです」を出す
    """
    from pipeline.camera import is_lightweight, recommend_realtime_model

    allowed = SEG_MODELS if enable_seg else AVAILABLE_MODELS
    if model_name not in allowed:
        raise RealtimeError(f"モデル {model_name} は選択中のタスクに使えません（候補: {', '.join(allowed)}）")

    if resolution not in RESOLUTION_PRESETS:
        raise RealtimeError(f"未知の解像度です: {resolution}（候補: {', '.join(RESOLUTION_PRESETS)}）")

    if not 0.0 <= conf <= 1.0:
        raise RealtimeError(f"信頼度しきい値は 0〜1 です: {conf}")
    if not 1 <= frame_skip <= 5:
        raise RealtimeError(f"フレームスキップは 1〜5 です: {frame_skip}")
    if not 0 <= camera_index <= 10:
        raise RealtimeError(f"カメラ index は 0〜10 です: {camera_index}")

    resolved = recommend_realtime_model(model_name) if auto_light else model_name

    notes: list[str] = []
    if resolved != model_name:
        notes.append(f"⚡ 自動切替: {model_name} → {resolved}")
    elif not is_lightweight(resolved):
        notes.append("⚠️ 重いモデルです。fps が出ない場合は n/s 系へ。")

    return ResolvedSettings(
        model_name=resolved,
        requested_model=model_name,
        size=RESOLUTION_PRESETS[resolution],
        resolution_key=resolution,
        conf=conf,
        frame_skip=frame_skip,
        enable_seg=enable_seg,
        enable_track=enable_track,
        camera_index=camera_index,
        notes=notes,
    )


def should_infer(frame_index: int, frame_skip: int) -> bool:
    """このフレームで推論するか（`N フレームに1回`）。"""
    return frame_index % max(1, frame_skip) == 0


def mjpeg_part(jpeg: bytes, boundary: str = MJPEG_BOUNDARY) -> bytes:
    """MJPEG（`multipart/x-mixed-replace`）の 1 パートを組み立てる。"""
    header = (
        f"--{boundary}\r\n"
        f"Content-Type: image/jpeg\r\n"
        f"Content-Length: {len(jpeg)}\r\n\r\n"
    ).encode()
    return header + jpeg + b"\r\n"


def mjpeg_content_type(boundary: str = MJPEG_BOUNDARY) -> str:
    return f"multipart/x-mixed-replace; boundary={boundary}"


@dataclass
class StreamStats:
    """配信中のライブ統計（画面の FPS / 検出数表示用）。"""

    fps: float = 0.0
    n_detections: int = 0
    frame_index: int = 0
    model_name: str = ""
    running: bool = False
    started_at: float | None = None

    @property
    def elapsed_sec(self) -> float:
        return time.monotonic() - self.started_at if self.started_at else 0.0


class CameraLock:
    """サーバ側カメラの排他ロック。

    カメラデバイスは同時に 1 つしか開けないので、MJPEG 配信は 1 本に限る。
    2 本目の要求は `CameraBusyError`（409）で断る。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._holder: str | None = None
        self.stats = StreamStats()

    def acquire(self, holder: str) -> None:
        if not self._lock.acquire(blocking=False):
            raise CameraBusyError(
                f"カメラは既に使用中です（{self._holder}）。先に停止してください。"
            )
        self._holder = holder
        self.stats = StreamStats(running=True, started_at=time.monotonic())

    def release(self) -> None:
        if self._holder is None:
            return
        self._holder = None
        self.stats.running = False
        self._lock.release()

    @property
    def busy(self) -> bool:
        return self._holder is not None


# サーバ側カメラの共有ロック（シングルプロセス前提）。
camera_lock = CameraLock()
