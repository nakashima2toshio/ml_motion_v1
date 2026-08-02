"""リアルタイム設定の解決とセッション管理（`core/realtime_session.py`）のテスト。

Streamlit 版 `app/views/realtime.py` の挙動（軽量モデルへの自動切替、
フレームスキップ、カメラの排他）を固定する。
"""

from __future__ import annotations

import pytest

from backend.app.core.realtime_session import (
    MJPEG_BOUNDARY,
    CameraBusyError,
    CameraLock,
    RealtimeError,
    mjpeg_content_type,
    mjpeg_part,
    resolve_settings,
    should_infer,
)


def _resolve(**overrides):
    params = {
        "model_name": "yolo11n.pt",
        "enable_seg": False,
        "enable_track": True,
        "auto_light": True,
        "conf": 0.25,
        "resolution": "640x360",
        "frame_skip": 1,
    }
    params.update(overrides)
    return resolve_settings(**params)


# ---------------------------------------------------------------------------
# 軽量モデルへの自動切替（Streamlit 版のキャプションと同じ）
# ---------------------------------------------------------------------------


def test_lightweight_model_is_kept_as_is() -> None:
    resolved = _resolve(model_name="yolo11n.pt", auto_light=True)
    assert resolved.model_name == "yolo11n.pt"
    assert resolved.auto_switched is False
    assert resolved.notes == []


def test_heavy_model_is_switched_when_auto_light_is_on() -> None:
    resolved = _resolve(model_name="yolo11m.pt", auto_light=True)
    assert resolved.auto_switched is True
    assert resolved.notes == ["⚡ 自動切替: yolo11m.pt → yolo11s.pt"]


def test_heavy_model_warns_when_auto_light_is_off() -> None:
    resolved = _resolve(model_name="yolo11m.pt", auto_light=False)
    assert resolved.model_name == "yolo11m.pt"
    assert resolved.auto_switched is False
    assert "⚠️ 重いモデルです" in resolved.notes[0]


def test_seg_models_are_required_when_segmentation_is_on() -> None:
    with pytest.raises(RealtimeError, match="使えません"):
        _resolve(model_name="yolo11n.pt", enable_seg=True)

    resolved = _resolve(model_name="yolo11n-seg.pt", enable_seg=True)
    assert resolved.model_name == "yolo11n-seg.pt"


def test_seg_heavy_model_is_switched_to_seg_lightweight() -> None:
    resolved = _resolve(model_name="yolo11m-seg.pt", enable_seg=True, auto_light=True)
    assert resolved.model_name.endswith("-seg.pt"), "セグの自動切替でもセグモデルを保つ"
    assert resolved.auto_switched is True


# ---------------------------------------------------------------------------
# 入力検証
# ---------------------------------------------------------------------------


def test_resolution_preset_is_resolved_to_size() -> None:
    resolved = _resolve(resolution="1280x720")
    assert resolved.size == (1280, 720)


@pytest.mark.parametrize("resolution", ["99x99", "", "640x361"])
def test_unknown_resolution_is_rejected(resolution: str) -> None:
    with pytest.raises(RealtimeError, match="未知の解像度"):
        _resolve(resolution=resolution)


@pytest.mark.parametrize("conf", [-0.1, 1.5])
def test_out_of_range_conf_is_rejected(conf: float) -> None:
    with pytest.raises(RealtimeError, match="信頼度"):
        _resolve(conf=conf)


@pytest.mark.parametrize("skip", [0, 6, -1])
def test_out_of_range_frame_skip_is_rejected(skip: int) -> None:
    with pytest.raises(RealtimeError, match="フレームスキップ"):
        _resolve(frame_skip=skip)


@pytest.mark.parametrize("index", [-1, 11])
def test_out_of_range_camera_index_is_rejected(index: int) -> None:
    with pytest.raises(RealtimeError, match="カメラ index"):
        _resolve(camera_index=index)


# ---------------------------------------------------------------------------
# フレームスキップ
# ---------------------------------------------------------------------------


def test_should_infer_every_frame_when_skip_is_one() -> None:
    assert [should_infer(i, 1) for i in range(4)] == [True, True, True, True]


def test_should_infer_every_third_frame() -> None:
    assert [should_infer(i, 3) for i in range(6)] == [True, False, False, True, False, False]


def test_should_infer_treats_zero_as_one() -> None:
    assert should_infer(1, 0) is True


# ---------------------------------------------------------------------------
# MJPEG のフレーミング
# ---------------------------------------------------------------------------


def test_mjpeg_part_has_boundary_and_length() -> None:
    part = mjpeg_part(b"\xff\xd8\xff-jpeg-body")
    assert part.startswith(f"--{MJPEG_BOUNDARY}\r\n".encode())
    assert b"Content-Type: image/jpeg" in part
    assert b"Content-Length: 13" in part
    assert part.endswith(b"\r\n")
    # ヘッダと本文は空行で区切られ、本文はそのまま入る。
    assert part.split(b"\r\n\r\n", 1)[1] == b"\xff\xd8\xff-jpeg-body\r\n"


def test_mjpeg_content_type_declares_boundary() -> None:
    assert mjpeg_content_type() == f"multipart/x-mixed-replace; boundary={MJPEG_BOUNDARY}"


# ---------------------------------------------------------------------------
# カメラの排他
# ---------------------------------------------------------------------------


def test_camera_lock_allows_one_holder() -> None:
    lock = CameraLock()
    lock.acquire("first")
    assert lock.busy is True
    assert lock.stats.running is True

    with pytest.raises(CameraBusyError, match="既に使用中"):
        lock.acquire("second")

    lock.release()
    assert lock.busy is False
    assert lock.stats.running is False


def test_camera_lock_can_be_reacquired_after_release() -> None:
    lock = CameraLock()
    lock.acquire("first")
    lock.release()
    lock.acquire("second")  # 例外にならない
    lock.release()


def test_camera_lock_release_without_acquire_is_noop() -> None:
    CameraLock().release()  # 例外にならない


def test_camera_lock_stats_reset_on_acquire() -> None:
    lock = CameraLock()
    lock.acquire("first")
    lock.stats.fps = 12.3
    lock.stats.n_detections = 4
    lock.release()

    lock.acquire("second")
    assert lock.stats.fps == 0.0
    assert lock.stats.n_detections == 0
    lock.release()
