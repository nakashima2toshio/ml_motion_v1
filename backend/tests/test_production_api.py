"""本番化・最適化 API のテスト。

実処理（`run_batch` / `export_model`）はスタブに差し替え、
**パスの制限**と引き渡しの正しさを確認する。
"""

from __future__ import annotations

import sys

import pytest
from fastapi.testclient import TestClient

from backend.app.core.jobs import job_manager
from backend.app.core.paths import repo_root
from backend.app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _wait(job_id: str, timeout: float = 10.0):
    job = job_manager.get(job_id)
    assert job is not None
    with job.cond:
        while not job.done:
            if not job.cond.wait(timeout=timeout):
                break
    assert job.done, "ジョブが完了しなかった"
    return job


# ---------------------------------------------------------------------------
# パス制限（この画面の要）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("outside", ["../../etc", "/etc", "/tmp", "~", "data/../../.."])
def test_discover_rejects_paths_outside_repo(client: TestClient, outside: str) -> None:
    res = client.post("/api/production/discover", json={"input_dir": outside})
    assert res.status_code == 400
    assert "リポジトリ外" in res.json()["detail"]


@pytest.mark.parametrize("field", ["input_dir", "output_dir"])
def test_batch_rejects_paths_outside_repo(client: TestClient, field: str) -> None:
    body = {"input_dir": "data", "output_dir": "output_batch", field: "/etc"}
    res = client.post("/api/production/batch", json=body)
    assert res.status_code == 400
    assert "リポジトリ外" in res.json()["detail"]


def test_export_rejects_weights_outside_repo(client: TestClient) -> None:
    res = client.post("/api/production/export", json={"weights": "/etc/passwd", "fmt": "onnx"})
    assert res.status_code == 400
    assert "リポジトリ外" in res.json()["detail"]


def test_batch_rejects_missing_input_dir(client: TestClient) -> None:
    res = client.post("/api/production/batch", json={"input_dir": "no/such/dir", "output_dir": "out"})
    assert res.status_code == 400
    assert "存在しない" in res.json()["detail"]


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------


def test_discover_lists_media_with_relative_paths(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import pipeline.batch

    root = repo_root()
    monkeypatch.setattr(
        pipeline.batch,
        "discover_media",
        lambda directory: [str(root / "data" / "a.mp4"), str(root / "data" / "b.mov")],
    )

    body = client.post("/api/production/discover", json={"input_dir": "data"}).json()
    assert body["files"] == ["data/a.mp4", "data/b.mov"], "絶対パスを画面に出さない"
    assert body["input_dir"] == "data"


def test_discover_on_empty_directory(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import pipeline.batch

    monkeypatch.setattr(pipeline.batch, "discover_media", lambda directory: [])
    body = client.post("/api/production/discover", json={"input_dir": "data"}).json()
    assert body["files"] == []


# ---------------------------------------------------------------------------
# バッチ実行
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_batch(monkeypatch: pytest.MonkeyPatch) -> dict:
    """`run_batch` と `discover_media` を差し替える。"""
    calls: dict = {}

    class _Item:
        def __init__(self, ok: bool, error: str = "") -> None:
            self.input_path = str(repo_root() / "data" / "a.mp4")
            self.output_path = str(repo_root() / "output_batch" / "annotated_a.mp4") if ok else ""
            self.frames_processed = 30
            self.n_detections = 12
            self.ok = ok
            self.error = error

    class _Result:
        def __init__(self) -> None:
            self.items = [_Item(True), _Item(False, "動画を開けませんでした")]

        @property
        def total_detections(self):
            return sum(i.n_detections for i in self.items)

        @property
        def succeeded(self):
            return sum(1 for i in self.items if i.ok)

        @property
        def failed(self):
            return sum(1 for i in self.items if not i.ok)

    def fake_run_batch(input_dir, output_dir, **kwargs):
        calls["input_dir"] = input_dir
        calls["output_dir"] = output_dir
        calls.update(kwargs)
        cb = kwargs.get("progress_cb")
        if cb:
            cb(1, 2)
            cb(2, 2)
        return _Result()

    import pipeline.batch

    monkeypatch.setattr(pipeline.batch, "discover_media", lambda directory: ["a.mp4", "b.mp4"])
    monkeypatch.setattr(pipeline.batch, "run_batch", fake_run_batch)
    return calls


def test_batch_passes_settings_and_absolute_paths(client: TestClient, stub_batch: dict) -> None:
    res = client.post(
        "/api/production/batch",
        json={
            "input_dir": "data",
            "output_dir": "output_batch",
            "model_name": "yolo11m.pt",
            "conf": 0.4,
            "frame_stride": 5,
        },
    )
    assert res.status_code == 202
    _wait(res.json()["job_id"])

    assert stub_batch["input_dir"] == str(repo_root() / "data")
    assert stub_batch["output_dir"] == str(repo_root() / "output_batch")
    assert stub_batch["model_name"] == "yolo11m.pt"
    assert stub_batch["conf"] == 0.4
    assert stub_batch["frame_stride"] == 5


def test_batch_result_manifest_uses_relative_paths(client: TestClient, stub_batch: dict) -> None:
    job_id = client.post("/api/production/batch", json={"input_dir": "data", "output_dir": "out"}).json()[
        "job_id"
    ]
    _wait(job_id)

    result = client.get(f"/api/production/result/{job_id}").json()["result"]
    assert result["succeeded"] == 1
    assert result["failed"] == 1
    assert result["total_detections"] == 24
    assert result["manifest"][0]["input"] == "data/a.mp4"
    assert result["manifest"][0]["output"] == "output_batch/annotated_a.mp4"
    assert result["manifest"][1]["status"].startswith("error:")


def test_batch_reports_no_media_found(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import pipeline.batch

    monkeypatch.setattr(pipeline.batch, "discover_media", lambda directory: [])

    job_id = client.post("/api/production/batch", json={"input_dir": "data", "output_dir": "out"}).json()[
        "job_id"
    ]
    _wait(job_id)

    body = client.get(f"/api/production/result/{job_id}").json()
    assert body["status"] == "failed"
    assert "動画が見つかりません" in body["error"]


def test_batch_progress_is_streamed_per_file(client: TestClient, stub_batch: dict) -> None:
    job_id = client.post("/api/production/batch", json={"input_dir": "data", "output_dir": "out"}).json()[
        "job_id"
    ]
    _wait(job_id)

    with client.stream("GET", f"/api/production/stream/{job_id}") as res:
        body = "".join(res.iter_text())
    assert "event: progress" in body
    assert '"current": 2' in body
    assert "event: done" in body


def test_batch_rejects_unknown_model(client: TestClient) -> None:
    res = client.post("/api/production/batch", json={"input_dir": "data", "model_name": "yolov5s.pt"})
    assert res.status_code == 400
    assert "未知のモデル" in res.json()["detail"]


def test_batch_failure_reports_streamlit_message(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import pipeline.batch

    monkeypatch.setattr(pipeline.batch, "discover_media", lambda directory: ["a.mp4"])

    def boom(*args, **kwargs):
        raise RuntimeError("モデルの読み込みに失敗")

    monkeypatch.setattr(pipeline.batch, "run_batch", boom)

    job_id = client.post("/api/production/batch", json={"input_dir": "data", "output_dir": "out"}).json()[
        "job_id"
    ]
    _wait(job_id)
    assert "バッチ処理に失敗しました" in client.get(f"/api/production/result/{job_id}").json()["error"]


# ---------------------------------------------------------------------------
# 変換・Registry
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_export(monkeypatch: pytest.MonkeyPatch) -> dict:
    calls: dict = {}

    def fake_export(weights, fmt, *, half=False, int8=False, imgsz=640):
        calls.update({"weights": weights, "fmt": fmt, "half": half, "int8": int8})
        return str(repo_root() / "models" / "yolo11s.onnx")

    # ⚠️ `pipeline/__init__.py` が `export_model` 関数を再エクスポートしており、
    # 属性 `pipeline.export_model` は**モジュールではなく関数**になる。
    # モジュールは sys.modules から取る。
    monkeypatch.setattr(sys.modules["pipeline.export_model"], "export_model", fake_export)
    return calls


@pytest.mark.parametrize(
    "quantization,half,int8",
    [("FP32", False, False), ("FP16", True, False), ("INT8", False, True)],
)
def test_export_maps_quantization_flags(
    client: TestClient, stub_export: dict, quantization: str, half: bool, int8: bool
) -> None:
    res = client.post(
        "/api/production/export",
        json={"weights": "pyproject.toml", "fmt": "onnx", "quantization": quantization},
    )
    assert res.status_code == 200
    assert stub_export["half"] is half
    assert stub_export["int8"] is int8
    assert res.json()["quantization"] == quantization
    assert res.json()["output_path"] == "models/yolo11s.onnx"


def test_export_normalizes_format_alias(client: TestClient, stub_export: dict) -> None:
    """`tensorrt` → `engine` のような別名を受け付ける（pipeline 側の正規化）。"""
    res = client.post("/api/production/export", json={"weights": "pyproject.toml", "fmt": "tensorrt"})
    assert res.status_code == 200
    assert stub_export["fmt"] == "engine"


def test_export_rejects_unknown_format(client: TestClient) -> None:
    res = client.post("/api/production/export", json={"weights": "pyproject.toml", "fmt": "zzz"})
    assert res.status_code == 400
    assert "未対応の書式" in res.json()["detail"]


def test_export_rejects_invalid_quantization(client: TestClient) -> None:
    res = client.post(
        "/api/production/export", json={"weights": "pyproject.toml", "fmt": "onnx", "quantization": "FP8"}
    )
    assert res.status_code == 422


def test_export_failure_reports_streamlit_message(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("onnx が未導入")

    monkeypatch.setattr(sys.modules["pipeline.export_model"], "export_model", boom)

    res = client.post("/api/production/export", json={"weights": "pyproject.toml", "fmt": "onnx"})
    assert res.status_code == 500
    assert "変換に失敗しました" in res.json()["detail"]


def test_registry_uri(client: TestClient) -> None:
    body = client.get("/api/production/registry-uri?name=ml_motion_detector&stage=Production").json()
    assert body["uri"] == "models:/ml_motion_detector/Production"
    assert "Staging" in body["stages"]
    assert "onnx" in body["formats"]


def test_registry_uri_normalizes_stage_alias(client: TestClient) -> None:
    assert client.get("/api/production/registry-uri?stage=prod").json()["uri"].endswith("/Production")


def test_registry_uri_rejects_unknown_stage(client: TestClient) -> None:
    res = client.get("/api/production/registry-uri?stage=Nope")
    assert res.status_code == 400
    assert "未知のステージ" in res.json()["detail"]
