"""解析 API のテスト。

実際の YOLO 推論（torch/ultralytics）は単体テストの対象外なので、
`process_tracking_video` をスタブに差し替えて **API の流れ**を検証する:
アップロード → 検証 → ジョブ → 進捗 → 結果 → ページング → ダウンロード。

エラー文言は Streamlit 版（`docs/manual/01_analyze.md` のトラブルシュート表）
と一致していることを確認する。
"""

from __future__ import annotations

import io
import threading
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from backend.app.core import detector_cache
from backend.app.core.jobs import Job, job_manager
from backend.app.main import app


@dataclass
class _StubRecord:
    frame: int
    time_sec: float
    class_id: int
    class_name: str
    confidence: float
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 1.0
    y2: float = 1.0
    tracker_id: int | None = None

    def to_dict(self) -> dict:
        return {
            "frame": self.frame,
            "time_sec": self.time_sec,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": self.confidence,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "tracker_id": self.tracker_id,
        }


@dataclass
class _StubResult:
    records: list
    output_path: str
    frames_total: int = 10
    frames_processed: int = 10
    fps: float = 30.0
    width: int = 640
    height: int = 360
    zone_summary: dict = field(default_factory=dict)
    per_track_dwell: list = field(default_factory=list)

    @property
    def duration_sec(self) -> float:
        return self.frames_total / self.fps


def _records(count: int = 3) -> list[_StubRecord]:
    return [
        _StubRecord(frame=i, time_sec=i / 30.0, class_id=0, class_name="person", confidence=0.9, tracker_id=i % 2)
        for i in range(count)
    ]


@pytest.fixture(autouse=True)
def isolated_workspace(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ML_MOTION_WORKDIR", str(tmp_path))
    detector_cache.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def stub_pipeline(monkeypatch: pytest.MonkeyPatch):
    """`Detector` と `process_tracking_video` を差し替え、呼ばれた引数を記録する。"""
    calls: dict = {}

    def fake_detector(model_name, device, conf, classes=None):
        calls["detector"] = {"model_name": model_name, "device": device, "conf": conf, "classes": classes}
        return object()

    def fake_process(input_path, output_path, detector, **kwargs):
        calls["process"] = {"input_path": input_path, "output_path": output_path, **kwargs}
        progress_cb = kwargs.get("progress_cb")
        if progress_cb:
            progress_cb(5, 10)
            progress_cb(10, 10)
        # 注釈付き動画の書き出しを模す。
        with open(output_path, "wb") as f:
            f.write(b"fake-mp4")
        return _StubResult(records=calls.get("records", _records()), output_path=output_path)

    import pipeline.video

    monkeypatch.setattr("backend.app.core.analyze_runner.get_detector", fake_detector)
    monkeypatch.setattr(pipeline.video, "process_tracking_video", fake_process)
    return calls


def _upload(client: TestClient, name: str = "clip.mp4", data: bytes = b"video") -> str:
    res = client.post("/api/analyze/upload", files={"file": (name, io.BytesIO(data), "video/mp4")})
    assert res.status_code == 200, res.text
    return res.json()["upload_id"]


def _wait(job_id: str, timeout: float = 10.0) -> Job:
    job = job_manager.get(job_id)
    assert job is not None
    with job.cond:
        while not job.done:
            if not job.cond.wait(timeout=timeout):
                break
    assert job.done, "ジョブが完了しなかった"
    return job


# ---------------------------------------------------------------------------
# アップロード
# ---------------------------------------------------------------------------


def test_upload_returns_id_and_size(client: TestClient) -> None:
    res = client.post("/api/analyze/upload", files={"file": ("clip.mp4", io.BytesIO(b"abc"), "video/mp4")})
    assert res.status_code == 200
    body = res.json()
    assert body["filename"] == "clip.mp4"
    assert body["size"] == 3


def test_upload_rejects_unsupported_extension(client: TestClient) -> None:
    res = client.post("/api/analyze/upload", files={"file": ("a.txt", io.BytesIO(b"abc"), "text/plain")})
    assert res.status_code == 400
    assert "未対応のファイル形式" in res.json()["detail"]


def test_upload_sanitizes_traversal_filename(client: TestClient) -> None:
    res = client.post("/api/analyze/upload", files={"file": ("../../evil.mp4", io.BytesIO(b"abc"), "video/mp4")})
    assert res.status_code == 200
    assert res.json()["filename"] == "evil.mp4"


# ---------------------------------------------------------------------------
# 実行前の検証（Streamlit 版の警告と同じ文言）
# ---------------------------------------------------------------------------


def test_run_rejects_empty_class_selection(client: TestClient) -> None:
    upload_id = _upload(client)
    res = client.post("/api/analyze/run", json={"upload_id": upload_id, "classes": []})
    assert res.status_code == 400
    assert res.json()["detail"] == "対象クラスを1つ以上選ぶか「全クラス」を有効にしてください。"


def test_run_rejects_zone_without_tracking(client: TestClient) -> None:
    upload_id = _upload(client)
    res = client.post(
        "/api/analyze/run", json={"upload_id": upload_id, "enable_zone": True, "enable_track": False}
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "ゾーン解析にはトラッキングが必要です"


def test_run_rejects_zone_without_definitions(client: TestClient) -> None:
    upload_id = _upload(client)
    res = client.post("/api/analyze/run", json={"upload_id": upload_id, "enable_zone": True, "zones": []})
    assert res.status_code == 400


def test_run_rejects_non_seg_model_when_seg_enabled(client: TestClient) -> None:
    upload_id = _upload(client)
    res = client.post(
        "/api/analyze/run", json={"upload_id": upload_id, "enable_seg": True, "model_name": "yolo11s.pt"}
    )
    assert res.status_code == 400


def test_run_rejects_unknown_upload(client: TestClient) -> None:
    assert client.post("/api/analyze/run", json={"upload_id": "0123456789ab"}).status_code == 404


@pytest.mark.parametrize(
    "polygon",
    [
        [[0.1, 0.1], [0.9, 0.1]],  # 3 点未満
        [[0.1, 0.1], [640, 0.1], [0.9, 0.9]],  # 正規化されていない
    ],
)
def test_run_rejects_invalid_polygon(client: TestClient, polygon: list) -> None:
    upload_id = _upload(client)
    res = client.post(
        "/api/analyze/run",
        json={"upload_id": upload_id, "enable_zone": True, "zones": [{"name": "z", "polygon": polygon}]},
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# 実行 → 結果
# ---------------------------------------------------------------------------


def test_run_passes_settings_through_to_pipeline(client: TestClient, stub_pipeline: dict) -> None:
    upload_id = _upload(client)
    res = client.post(
        "/api/analyze/run",
        json={
            "upload_id": upload_id,
            "enable_seg": False,
            "enable_track": True,
            "enable_zone": True,
            "model_name": "yolo11m.pt",
            "conf": 0.4,
            "classes": [0, 2],
            "frame_stride": 3,
            "trace_length": 60,
            "zones": [{"name": "ゾーンA", "polygon": [[0.3, 0.3], [0.7, 0.3], [0.7, 0.9]]}],
        },
    )
    assert res.status_code == 202
    _wait(res.json()["job_id"])

    assert stub_pipeline["detector"]["model_name"] == "yolo11m.pt"
    assert stub_pipeline["detector"]["conf"] == 0.4
    assert stub_pipeline["detector"]["classes"] == [0, 2]

    process = stub_pipeline["process"]
    assert process["enable_masks"] is False
    assert process["enable_tracking"] is True
    assert process["frame_stride"] == 3
    assert process["trace_length"] == 60
    assert len(process["zones"]) == 1
    assert process["zones"][0].name == "ゾーンA"


def test_zones_are_ignored_when_zone_analysis_is_off(client: TestClient, stub_pipeline: dict) -> None:
    """Streamlit 版と同じく、ゾーン解析 OFF なら定義が残っていても使わない。"""
    upload_id = _upload(client)
    res = client.post(
        "/api/analyze/run",
        json={
            "upload_id": upload_id,
            "enable_zone": False,
            "zones": [{"name": "ゾーンA", "polygon": [[0.3, 0.3], [0.7, 0.3], [0.7, 0.9]]}],
        },
    )
    _wait(res.json()["job_id"])
    assert stub_pipeline["process"]["zones"] == []


def test_result_excludes_records_but_reports_totals(client: TestClient, stub_pipeline: dict) -> None:
    upload_id = _upload(client)
    job_id = client.post("/api/analyze/run", json={"upload_id": upload_id}).json()["job_id"]
    _wait(job_id)

    body = client.get(f"/api/analyze/result/{job_id}").json()
    assert body["status"] == "completed"
    result = body["result"]
    assert "records" not in result, "巨大になりうる検出レコードはサマリに含めない"
    assert result["total_records"] == 3
    assert result["total_detections"] == 3
    assert result["unique_track_ids"] == 2
    assert result["stats"] == {"person": {"total": 3, "max_in_frame": 1}}
    assert result["video_url"].startswith("/media/")


def test_detections_are_paginated(client: TestClient, stub_pipeline: dict) -> None:
    stub_pipeline["records"] = _records(2500)
    upload_id = _upload(client)
    job_id = client.post("/api/analyze/run", json={"upload_id": upload_id}).json()["job_id"]
    _wait(job_id)

    first = client.get(f"/api/analyze/detections/{job_id}?offset=0&limit=1000").json()
    assert first["total"] == 2500
    assert len(first["records"]) == 1000
    assert first["records"][0]["frame"] == 0

    last = client.get(f"/api/analyze/detections/{job_id}?offset=2000&limit=1000").json()
    assert len(last["records"]) == 500
    assert last["records"][0]["frame"] == 2000


def test_detections_limit_is_capped(client: TestClient, stub_pipeline: dict) -> None:
    upload_id = _upload(client)
    job_id = client.post("/api/analyze/run", json={"upload_id": upload_id}).json()["job_id"]
    _wait(job_id)
    assert client.get(f"/api/analyze/detections/{job_id}?limit=99999").status_code == 422


@pytest.mark.parametrize(
    "kind,expected_name",
    [
        ("csv", "clip_detections.csv"),
        ("json", "clip_detections.json"),
        ("video", "clip_annotated.mp4"),
    ],
)
def test_downloads_use_streamlit_filenames(
    client: TestClient, stub_pipeline: dict, kind: str, expected_name: str
) -> None:
    upload_id = _upload(client)
    job_id = client.post("/api/analyze/run", json={"upload_id": upload_id}).json()["job_id"]
    _wait(job_id)

    res = client.get(f"/api/analyze/download/{job_id}/{kind}")
    assert res.status_code == 200
    assert expected_name in res.headers["content-disposition"]


def test_download_rejects_unknown_kind(client: TestClient, stub_pipeline: dict) -> None:
    upload_id = _upload(client)
    job_id = client.post("/api/analyze/run", json={"upload_id": upload_id}).json()["job_id"]
    _wait(job_id)
    assert client.get(f"/api/analyze/download/{job_id}/exe").status_code == 404


def test_annotated_video_is_served_over_media_mount(client: TestClient, stub_pipeline: dict) -> None:
    upload_id = _upload(client)
    job_id = client.post("/api/analyze/run", json={"upload_id": upload_id}).json()["job_id"]
    _wait(job_id)

    video_url = client.get(f"/api/analyze/result/{job_id}").json()["result"]["video_url"]
    res = client.get(video_url)
    assert res.status_code == 200
    assert res.content == b"fake-mp4"


def test_media_mount_supports_range_requests(client: TestClient, stub_pipeline: dict) -> None:
    """`<video>` のシークに Range 応答（206）が必要。"""
    upload_id = _upload(client)
    job_id = client.post("/api/analyze/run", json={"upload_id": upload_id}).json()["job_id"]
    _wait(job_id)

    video_url = client.get(f"/api/analyze/result/{job_id}").json()["result"]["video_url"]
    res = client.get(video_url, headers={"Range": "bytes=0-3"})
    assert res.status_code == 206
    assert res.content == b"fake"


def test_result_endpoints_reject_incomplete_job(client: TestClient) -> None:
    """未完了ジョブの結果・ダウンロードは 409。"""
    blocker = threading.Event()

    def slow_runner(params, emit):
        blocker.wait(timeout=5)
        return {"stem": "x", "records": [], "output_path": "", "run_id": "r"}

    job = job_manager.start(None, slow_runner, kind="analyze")
    try:
        assert client.get(f"/api/analyze/detections/{job.job_id}").status_code == 409
        assert client.get(f"/api/analyze/download/{job.job_id}/csv").status_code == 409
    finally:
        blocker.set()
        _wait(job.job_id)


def test_unknown_job_returns_404(client: TestClient) -> None:
    assert client.get("/api/analyze/result/unknownjob").status_code == 404
    assert client.get("/api/analyze/detections/unknownjob").status_code == 404


def test_progress_events_are_streamed_as_sse(client: TestClient, stub_pipeline: dict) -> None:
    upload_id = _upload(client)
    job_id = client.post("/api/analyze/run", json={"upload_id": upload_id}).json()["job_id"]
    _wait(job_id)

    with client.stream("GET", f"/api/analyze/stream/{job_id}") as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        body = "".join(res.iter_text())

    assert "event: started" in body
    assert "event: progress" in body
    assert "event: done" in body
    assert '"current": 10' in body


def test_failed_job_reports_streamlit_style_message(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("backend.app.core.analyze_runner.get_detector", boom)

    upload_id = _upload(client)
    job_id = client.post("/api/analyze/run", json={"upload_id": upload_id}).json()["job_id"]
    _wait(job_id)

    body = client.get(f"/api/analyze/result/{job_id}").json()
    assert body["status"] == "failed"
    assert "モデルの読み込みに失敗しました" in body["error"]
