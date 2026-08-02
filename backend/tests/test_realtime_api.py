"""リアルタイム API のテスト。

実カメラも実 YOLO も使わず、`open_camera` と `FrameProcessor` をスタブに
差し替えて、**MJPEG の配信・カメラ解放・排他・WebSocket の往復**を確認する。

⚠️ この経路は JPEG のエンコード/デコードに cv2 を使うため、**cv2/numpy が
入っている環境でのみ**実行する（CI の軽量セットでは自動スキップ）。
依存なしで検証できる設定解決・排他・MJPEG フレーミングは
`test_realtime_session.py` が担当する。
"""

from __future__ import annotations

import pytest

np = pytest.importorskip("numpy", reason="リアルタイム API のテストは numpy/cv2 が必要")
pytest.importorskip("cv2", reason="リアルタイム API のテストは numpy/cv2 が必要")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.core.realtime_session import camera_lock  # noqa: E402
from backend.app.main import app  # noqa: E402

# 小さな黒画像（cv2 で JPEG にして使う）。
_BLACK = np.zeros((8, 8, 3), dtype=np.uint8)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def release_camera():
    """テスト間でカメラロックを持ち越さない。"""
    yield
    camera_lock.stats.running = False
    if camera_lock.busy:
        camera_lock.release()


class _FakeCap:
    """`cv2.VideoCapture` 互換の最小スタブ。"""

    def __init__(self, frames: int = 3, fail_after: int | None = None) -> None:
        self.index = 0
        self.frames = frames
        self.fail_after = fail_after
        self.released = False

    def read(self):
        if self.fail_after is not None and self.index >= self.fail_after:
            return False, None
        if self.index >= self.frames:
            return False, None
        self.index += 1
        return True, _BLACK.copy()

    def release(self):
        self.released = True


class _FakeProcessor:
    """`FrameProcessor` 互換の最小スタブ。"""

    def __init__(self) -> None:
        self.reset_called = 0

    def reset(self):
        self.reset_called += 1

    def process(self, frame, frame_idx: int = 0, time_sec: float = 0.0):
        class _Result:
            annotated = frame
            n_detections = 2

        return _Result()


@pytest.fixture
def stub_camera(monkeypatch: pytest.MonkeyPatch) -> dict:
    """カメラとモデルをスタブに差し替える。"""
    state: dict = {"cap": _FakeCap(), "processor": _FakeProcessor(), "opened_with": None}

    import pipeline.camera

    def fake_open(index=0, size=None):
        state["opened_with"] = {"index": index, "size": size}
        return state["cap"]

    monkeypatch.setattr(pipeline.camera, "open_camera", fake_open)
    monkeypatch.setattr(
        "backend.app.api.realtime.get_processor",
        lambda *args, **kwargs: state["processor"],
    )
    return state


# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------


def test_settings_reports_auto_switch(client: TestClient) -> None:
    body = client.get("/api/realtime/settings?model_name=yolo11m.pt&auto_light=true").json()
    assert body["model_name"] == "yolo11s.pt"
    assert body["auto_switched"] is True
    assert body["notes"] == ["⚡ 自動切替: yolo11m.pt → yolo11s.pt"]
    assert body["width"] == 640 and body["height"] == 360


def test_settings_rejects_invalid_resolution(client: TestClient) -> None:
    res = client.get("/api/realtime/settings?resolution=99x99")
    assert res.status_code == 400
    assert "未知の解像度" in res.json()["detail"]


def test_settings_reports_camera_busy(client: TestClient) -> None:
    camera_lock.acquire("test")
    try:
        assert client.get("/api/realtime/settings").json()["camera_busy"] is True
    finally:
        camera_lock.release()


# ---------------------------------------------------------------------------
# MJPEG（経路1）
# ---------------------------------------------------------------------------


def test_mjpeg_streams_multipart_jpeg_and_releases_camera(client: TestClient, stub_camera: dict) -> None:
    with client.stream("GET", "/api/realtime/mjpeg?camera_index=1&resolution=960x540") as res:
        assert res.status_code == 200
        assert res.headers["content-type"] == "multipart/x-mixed-replace; boundary=mlmotionframe"
        body = b"".join(res.iter_bytes())

    parts = [p for p in body.split(b"--mlmotionframe") if b"image/jpeg" in p]
    assert len(parts) == 3, "スタブが返した 3 フレームぶん配信される"
    # 本文が JPEG であること。
    payload = parts[0].split(b"\r\n\r\n", 1)[1]
    assert payload.startswith(b"\xff\xd8\xff")

    assert stub_camera["cap"].released is True, "配信終了でカメラを解放する"
    assert camera_lock.busy is False
    assert stub_camera["opened_with"] == {"index": 1, "size": (960, 540)}


def test_mjpeg_resets_tracker_at_stream_start(client: TestClient, stub_camera: dict) -> None:
    with client.stream("GET", "/api/realtime/mjpeg") as res:
        b"".join(res.iter_bytes())
    assert stub_camera["processor"].reset_called == 1


def test_mjpeg_is_exclusive(client: TestClient, stub_camera: dict) -> None:
    """カメラは 1 本しか開けないので、2 本目は 409。"""
    camera_lock.acquire("already-streaming")
    try:
        res = client.get("/api/realtime/mjpeg")
        assert res.status_code == 409
        assert "既に使用中" in res.json()["detail"]
    finally:
        camera_lock.release()


def test_mjpeg_rejects_invalid_settings_before_opening_camera(client: TestClient, stub_camera: dict) -> None:
    res = client.get("/api/realtime/mjpeg?resolution=99x99")
    assert res.status_code == 400
    assert stub_camera["opened_with"] is None, "検証前にカメラを開かない"
    assert camera_lock.busy is False, "失敗時にロックを残さない"


def test_mjpeg_reports_camera_open_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import pipeline.camera

    def boom(index=0, size=None):
        raise RuntimeError("カメラを開けませんでした (index=9)。デバイス接続/権限を確認してください。")

    monkeypatch.setattr(pipeline.camera, "open_camera", boom)
    monkeypatch.setattr("backend.app.api.realtime.get_processor", lambda *a, **k: _FakeProcessor())

    res = client.get("/api/realtime/mjpeg?camera_index=9")
    assert res.status_code == 400
    assert "カメラを開けませんでした" in res.json()["detail"]
    assert camera_lock.busy is False, "失敗時にロックを残さない"


def test_mjpeg_stops_after_repeated_read_failures(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """フレームが取れなくなったら諦めて解放する（無限ループにしない）。"""
    cap = _FakeCap(frames=100, fail_after=0)

    import pipeline.camera

    monkeypatch.setattr(pipeline.camera, "open_camera", lambda index=0, size=None: cap)
    monkeypatch.setattr("backend.app.api.realtime.get_processor", lambda *a, **k: _FakeProcessor())

    with client.stream("GET", "/api/realtime/mjpeg") as res:
        body = b"".join(res.iter_bytes())

    assert body == b"", "1 フレームも配信しない"
    assert cap.released is True
    assert camera_lock.busy is False


# ---------------------------------------------------------------------------
# 統計・停止
# ---------------------------------------------------------------------------


def test_stats_are_updated_during_streaming(client: TestClient, stub_camera: dict) -> None:
    with client.stream("GET", "/api/realtime/mjpeg") as res:
        b"".join(res.iter_bytes())

    stats = client.get("/api/realtime/stats").json()
    assert stats["running"] is False
    assert stats["frame_index"] == 2, "0-origin で 3 フレーム目まで進む"
    assert stats["n_detections"] == 2


def test_stop_marks_stream_as_stopped(client: TestClient) -> None:
    camera_lock.acquire("test")
    try:
        assert client.post("/api/realtime/stop").json()["stopped"] is True
        assert camera_lock.stats.running is False
    finally:
        camera_lock.release()


def test_stop_when_not_running(client: TestClient) -> None:
    assert client.post("/api/realtime/stop").json()["stopped"] is False


# ---------------------------------------------------------------------------
# WebSocket（経路2 / streamlit-webrtc の置き換え）
# ---------------------------------------------------------------------------


def _jpeg_bytes() -> bytes:
    import cv2

    ok, buf = cv2.imencode(".jpg", _BLACK)
    assert ok
    return buf.tobytes()


def test_websocket_returns_annotated_frame_and_stats(client: TestClient, stub_camera: dict) -> None:
    jpeg = _jpeg_bytes()
    with client.websocket_connect("/api/realtime/ws?model_name=yolo11n.pt") as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        assert ready["model_name"] == "yolo11n.pt"

        ws.send_bytes(jpeg)
        annotated = ws.receive_bytes()
        stats = ws.receive_json()

    assert annotated.startswith(b"\xff\xd8\xff"), "JPEG が返る"
    assert stats["type"] == "stats"
    assert stats["n_detections"] == 2
    assert stats["frame_index"] == 0


def test_websocket_does_not_use_the_server_camera(client: TestClient, stub_camera: dict) -> None:
    """ブラウザ経路はサーバ側カメラを使わない（排他ロックを取らない）。"""
    with client.websocket_connect("/api/realtime/ws") as ws:
        ws.receive_json()
        assert camera_lock.busy is False
    assert stub_camera["opened_with"] is None


def test_websocket_reports_undecodable_frame(client: TestClient, stub_camera: dict) -> None:
    with client.websocket_connect("/api/realtime/ws") as ws:
        ws.receive_json()
        ws.send_bytes(b"not-a-jpeg")
        message = ws.receive_json()

    assert message["type"] == "error"
    assert "復号できませんでした" in message["message"]


def test_websocket_rejects_invalid_settings(client: TestClient, stub_camera: dict) -> None:
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/realtime/ws?resolution=99x99") as ws:
            ws.receive_json()


def test_websocket_honours_frame_skip(client: TestClient, stub_camera: dict) -> None:
    """frame_skip=2 では 1 枚おきにしか推論しない。"""
    jpeg = _jpeg_bytes()
    detections = []
    with client.websocket_connect("/api/realtime/ws?frame_skip=2") as ws:
        ws.receive_json()
        for _ in range(4):
            ws.send_bytes(jpeg)
            ws.receive_bytes()
            detections.append(ws.receive_json()["n_detections"])

    assert detections == [2, 0, 2, 0], "推論したフレームだけ検出数が入る"
