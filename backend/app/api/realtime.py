"""リアルタイム解析 API（Streamlit 版 `app/views/realtime.py` に対応）。

    GET  /api/realtime/settings   設定の解決結果（自動切替の注意書きなど）
    GET  /api/realtime/mjpeg      経路1: サーバ側カメラ → MJPEG 配信
    GET  /api/realtime/stats      配信中の FPS / 検出数
    POST /api/realtime/stop       配信の停止（カメラ解放）
    WS   /api/realtime/ws         経路2: ブラウザカメラ ↔ 注釈付きフレーム

経路1は Streamlit 版の `while` ループ ＋ `st.image` 差し替えに相当し、
経路2は `streamlit-webrtc` の置き換え（`streamlit-webrtc` / `av` は不要になる）。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from backend.app.core.detector_cache import get_processor
from backend.app.core.realtime_session import (
    MAX_READ_FAILURES,
    CameraBusyError,
    RealtimeError,
    ResolvedSettings,
    camera_lock,
    mjpeg_content_type,
    mjpeg_part,
    resolve_settings,
    should_infer,
)
from backend.app.schemas import RealtimeSettingsResponse, RealtimeStatsResponse, StopResponse
from pipeline.device import get_device

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/realtime", tags=["realtime"])

# JPEG エンコード品質（帯域とのトレードオフ）。
JPEG_QUALITY = 80


def _settings(
    model_name: str,
    enable_seg: bool,
    enable_track: bool,
    auto_light: bool,
    conf: float,
    resolution: str,
    frame_skip: int,
    camera_index: int = 0,
) -> ResolvedSettings:
    try:
        return resolve_settings(
            model_name=model_name,
            enable_seg=enable_seg,
            enable_track=enable_track,
            auto_light=auto_light,
            conf=conf,
            resolution=resolution,
            frame_skip=frame_skip,
            camera_index=camera_index,
        )
    except RealtimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/settings", response_model=RealtimeSettingsResponse)
def get_settings(
    model_name: str = Query(default="yolo11n.pt"),
    enable_seg: bool = Query(default=False),
    enable_track: bool = Query(default=True),
    auto_light: bool = Query(default=True),
    conf: float = Query(default=0.25),
    resolution: str = Query(default="640x360"),
    frame_skip: int = Query(default=1),
) -> RealtimeSettingsResponse:
    """設定を解決して返す（配信を始める前に注意書きを表示するため）。"""
    resolved = _settings(model_name, enable_seg, enable_track, auto_light, conf, resolution, frame_skip)
    return RealtimeSettingsResponse(
        model_name=resolved.model_name,
        requested_model=resolved.requested_model,
        auto_switched=resolved.auto_switched,
        width=resolved.size[0],
        height=resolved.size[1],
        notes=resolved.notes,
        camera_busy=camera_lock.busy,
    )


@router.get("/mjpeg")
def mjpeg_stream(
    camera_index: int = Query(default=0, ge=0, le=10),
    model_name: str = Query(default="yolo11n.pt"),
    enable_seg: bool = Query(default=False),
    enable_track: bool = Query(default=True),
    auto_light: bool = Query(default=True),
    conf: float = Query(default=0.25),
    resolution: str = Query(default="640x360"),
    frame_skip: int = Query(default=1, ge=1, le=5),
) -> StreamingResponse:
    """サーバ側のカメラ（Continuity Camera 等）を推論しながら MJPEG で配信する。

    ⚠️ この経路は**サーバがカメラを持っている前提**（Streamlit 版と同じく、
    Mac 上でローカル実行したときだけ動く）。カメラは同時に 1 本しか開けないので、
    既に配信中なら 409 を返す。
    """
    resolved = _settings(
        model_name, enable_seg, enable_track, auto_light, conf, resolution, frame_skip, camera_index
    )

    try:
        camera_lock.acquire(holder=f"mjpeg(camera={camera_index})")
    except CameraBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    # ⚠️ モデル読み込みとカメラオープンは**レスポンスを返す前**に行う。
    # ジェネレータの中でやるとストリーム開始後の例外になり、HTTP ステータスで
    # 失敗を伝えられない（Starlette が "response already started" で落ちる）。
    from pipeline.camera import open_camera

    try:
        processor = get_processor(
            resolved.model_name,
            get_device(),
            resolved.conf,
            enable_masks=resolved.enable_seg,
            enable_tracking=resolved.enable_track,
        )
        processor.reset()
    except Exception as e:  # noqa: BLE001
        camera_lock.release()
        raise HTTPException(status_code=500, detail=f"モデルの読み込みに失敗しました: {e}") from e

    try:
        cap = open_camera(resolved.camera_index, size=resolved.size)
    except Exception as e:  # noqa: BLE001 — カメラ未接続・権限なし等
        camera_lock.release()
        raise HTTPException(status_code=400, detail=str(e)) from e

    return StreamingResponse(
        _camera_frames(cap, processor, resolved),
        media_type=mjpeg_content_type(),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _camera_frames(cap, processor, resolved: ResolvedSettings) -> Iterator[bytes]:
    """開いたカメラから読んで推論し、MJPEG のパートを産み続けるジェネレータ。

    クライアント切断（ジェネレータの close）や停止要求でカメラを必ず解放する。
    """
    import cv2

    from pipeline.camera import FpsMeter

    meter = FpsMeter(window=30)
    stats = camera_lock.stats
    stats.model_name = resolved.model_name

    index = 0
    failures = 0
    try:
        while camera_lock.stats.running:
            ok, frame = cap.read()
            if not ok:
                failures += 1
                if failures >= MAX_READ_FAILURES:
                    logger.warning("カメラからフレームを取得できません (index=%s)", resolved.camera_index)
                    break
                time.sleep(0.01)
                continue
            failures = 0
            meter.tick(time.monotonic())

            if should_infer(index, resolved.frame_skip):
                result = processor.process(frame, frame_idx=index, time_sec=index)
                annotated = result.annotated
                stats.n_detections = result.n_detections
            else:
                annotated = frame

            encoded, buffer = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
            if not encoded:
                continue

            stats.fps = meter.fps
            stats.frame_index = index
            index += 1
            yield mjpeg_part(buffer.tobytes())
    finally:
        cap.release()
        camera_lock.release()


@router.get("/stats", response_model=RealtimeStatsResponse)
def get_stats() -> RealtimeStatsResponse:
    """配信中の FPS・検出数（Streamlit 版のキャプション相当）。"""
    stats = camera_lock.stats
    return RealtimeStatsResponse(
        running=stats.running,
        fps=round(stats.fps, 1),
        n_detections=stats.n_detections,
        frame_index=stats.frame_index,
        model_name=stats.model_name,
        elapsed_sec=round(stats.elapsed_sec, 1),
    )


@router.post("/stop", response_model=StopResponse)
def stop_stream() -> StopResponse:
    """配信を止めてカメラを解放する（ブラウザ側の停止が届かない場合の保険）。"""
    was_running = camera_lock.stats.running
    # 生成ループは `stats.running` を見ているので、False にすれば次の周回で抜ける。
    camera_lock.stats.running = False
    return StopResponse(stopped=was_running)


@router.websocket("/ws")
async def browser_camera(websocket: WebSocket) -> None:
    """経路2: ブラウザカメラのフレームを受け取り、注釈付きフレームを返す。

    プロトコル（`streamlit-webrtc` の置き換え）:
        client → server : JPEG バイナリ 1 枚
        server → client : 注釈付き JPEG バイナリ 1 枚 ＋ 統計 JSON

    クライアントは**応答を受け取ってから次を送る**（in-flight 1 枚）ことで
    遅延の蓄積を防ぐ。サーバ側カメラは使わないので排他ロックは不要。
    """
    params = websocket.query_params
    try:
        resolved = resolve_settings(
            model_name=params.get("model_name", "yolo11n.pt"),
            enable_seg=params.get("enable_seg", "false").lower() == "true",
            enable_track=params.get("enable_track", "true").lower() == "true",
            auto_light=params.get("auto_light", "true").lower() == "true",
            conf=float(params.get("conf", "0.25")),
            resolution=params.get("resolution", "640x360"),
            frame_skip=int(params.get("frame_skip", "1")),
        )
    except (RealtimeError, ValueError) as e:
        await websocket.close(code=1008, reason=str(e)[:120])
        return

    await websocket.accept()

    import cv2
    import numpy as np

    from pipeline.camera import FpsMeter

    try:
        processor = get_processor(
            resolved.model_name,
            get_device(),
            resolved.conf,
            enable_masks=resolved.enable_seg,
            enable_tracking=resolved.enable_track,
        )
        processor.reset()
    except Exception as e:  # noqa: BLE001
        await websocket.send_json({"type": "error", "message": f"モデルの読み込みに失敗しました: {e}"})
        await websocket.close()
        return

    await websocket.send_json({"type": "ready", "model_name": resolved.model_name, "notes": resolved.notes})

    meter = FpsMeter(window=30)
    index = 0
    try:
        while True:
            data = await websocket.receive_bytes()
            meter.tick(time.monotonic())

            frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                await websocket.send_json({"type": "error", "message": "フレームを復号できませんでした"})
                continue

            n_detections = 0
            if should_infer(index, resolved.frame_skip):
                result = processor.process(frame, frame_idx=index, time_sec=index)
                frame = result.annotated
                n_detections = result.n_detections

            encoded, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
            if encoded:
                await websocket.send_bytes(buffer.tobytes())
            await websocket.send_json(
                {
                    "type": "stats",
                    "fps": round(meter.fps, 1),
                    "n_detections": n_detections,
                    "frame_index": index,
                }
            )
            index += 1
    except WebSocketDisconnect:
        logger.info("ブラウザカメラの WebSocket が切断されました（%s フレーム処理）", index)
