"""実験管理 API のテスト。

MLflow（`list_runs`）と学習（`train`）はスタブに差し替え、
「接続失敗時の案内」「最良 Run の選択」「学習ジョブの引き渡し」を確認する。
"""

from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient

from backend.app.api.experiments import parse_classes
from backend.app.core.jobs import job_manager
from backend.app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _runs() -> list[dict]:
    return [
        {"run_id": "a", "run_name": "baseline", "status": "FINISHED",
         "metrics": {"metrics/mAP50(B)": 0.71, "metrics/mAP50-95(B)": 0.512345}, "params": {}},
        {"run_id": "b", "run_name": "tuned", "status": "FINISHED",
         "metrics": {"metrics/mAP50(B)": 0.83, "metrics/mAP50-95(B)": 0.612345}, "params": {}},
    ]


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
# 設定・Run 一覧
# ---------------------------------------------------------------------------


def test_config_reports_tracking_uri(client: TestClient) -> None:
    from pipeline.experiments import DEFAULT_EXPERIMENT, tracking_uri

    body = client.get("/api/experiments/config").json()
    assert body["tracking_uri"] == tracking_uri()
    assert body["default_experiment"] == DEFAULT_EXPERIMENT
    assert "metrics/mAP50-95(B)" in body["key_metrics"]


@pytest.fixture(autouse=True)
def reachable_mlflow(monkeypatch: pytest.MonkeyPatch) -> None:
    """既定では MLflow に疎通できることにする（疎通確認そのもののテストは個別に行う）。"""
    monkeypatch.setattr("backend.app.api.experiments.is_mlflow_reachable", lambda uri, timeout=3.0: True)


def test_runs_returns_rows_and_best_run(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import pipeline.experiments

    monkeypatch.setattr(pipeline.experiments, "list_runs", lambda experiment: _runs())

    body = client.get("/api/experiments/runs?experiment=exp1").json()
    assert body["experiment"] == "exp1"
    assert [row["run"] for row in body["rows"]] == ["baseline", "tuned"]
    # format_runs_table は 4 桁に丸める。
    assert body["rows"][1]["mAP50-95"] == 0.6123
    assert body["best_run_name"] == "tuned"
    assert body["best_metric"] == 0.6123


def test_runs_reads_metrics_logged_by_ultralytics(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """⚠️ 回帰テスト（docs/known_issues.md #1）。

    MLflow に保存されるメトリクス名は括弧が落ちる（`metrics/mAP50-95B`）。
    修正前は mAP 列が 0.0、`best_metric` も 0.0 になっていた。
    """
    import pipeline.experiments

    monkeypatch.setattr(
        pipeline.experiments,
        "list_runs",
        lambda experiment: [
            {"run_name": "baseline", "status": "FINISHED",
             "metrics": {"metrics/mAP50B": 0.71, "metrics/mAP50-95B": 0.512}},
            {"run_name": "tuned", "status": "FINISHED",
             "metrics": {"metrics/mAP50B": 0.834, "metrics/mAP50-95B": 0.6412}},
        ],
    )

    body = client.get("/api/experiments/runs").json()
    assert body["rows"][1]["mAP50"] == 0.834
    assert body["rows"][1]["mAP50-95"] == 0.6412
    assert body["best_run_name"] == "tuned"
    assert body["best_metric"] == 0.6412


def test_runs_passes_experiment_name_through(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}

    import pipeline.experiments

    def fake_list_runs(experiment):
        seen["experiment"] = experiment
        return []

    monkeypatch.setattr(pipeline.experiments, "list_runs", fake_list_runs)
    client.get("/api/experiments/runs?experiment=%E5%AE%9F%E9%A8%93A")
    assert seen["experiment"] == "実験A"


def test_runs_empty_experiment_returns_no_rows(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import pipeline.experiments

    monkeypatch.setattr(pipeline.experiments, "list_runs", lambda experiment: [])

    body = client.get("/api/experiments/runs").json()
    assert body["rows"] == []
    assert body["best_run_name"] is None


def test_runs_reports_mlflow_down_with_startup_hint(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """MLflow 未起動でも画面は出る。案内は Streamlit 版と同じ docker-compose コマンド。"""
    import pipeline.experiments

    def boom(experiment):
        raise ConnectionError("Connection refused")

    monkeypatch.setattr(pipeline.experiments, "list_runs", boom)

    res = client.get("/api/experiments/runs")
    assert res.status_code == 503
    detail = res.json()["detail"]
    assert "MLflow へ接続できませんでした" in detail
    assert "docker-compose" in detail


def test_unreachable_mlflow_fails_fast_without_calling_client(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """疎通確認で落ちていると分かったら、MLflow クライアントを呼ばずに 503 を返す。

    MLflow クライアントは接続失敗時に数分リトライするため、ここで止めないと
    ブラウザが待たされ、ワーカースレッドも占有される。
    """
    import pipeline.experiments

    called = {"list_runs": False}

    def should_not_be_called(experiment):
        called["list_runs"] = True
        return []

    monkeypatch.setattr(pipeline.experiments, "list_runs", should_not_be_called)
    monkeypatch.setattr("backend.app.api.experiments.is_mlflow_reachable", lambda uri, timeout=3.0: False)

    res = client.get("/api/experiments/runs")
    assert res.status_code == 503
    assert "docker-compose" in res.json()["detail"]
    assert called["list_runs"] is False, "疎通できないなら MLflow クライアントを呼ばない"


def test_is_mlflow_reachable_against_closed_port() -> None:
    """実際に閉じているポートへ短時間で False を返す。"""
    import socket
    import time

    from backend.app.core.mlflow_probe import is_mlflow_reachable

    # 空きポートを 1 つ確保してすぐ閉じる（誰も listen していない状態を作る）。
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    started = time.monotonic()
    assert is_mlflow_reachable(f"http://127.0.0.1:{port}", timeout=3.0) is False
    assert time.monotonic() - started < 5.0, "接続不可はすぐ返る"


def test_is_mlflow_reachable_skips_non_http_uri() -> None:
    """ローカルの file: ストアは疎通確認しない（確認しようがない）。"""
    from backend.app.core.mlflow_probe import is_mlflow_reachable

    assert is_mlflow_reachable("file:./mlruns") is True


# ---------------------------------------------------------------------------
# 学習ジョブ
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_train(monkeypatch: pytest.MonkeyPatch) -> dict:
    calls: dict = {}

    class _Result:
        run_id = "run-123"
        best_weights = "runs/detect/train/weights/best.pt"
        metrics = {"metrics/mAP50-95(B)": 0.42}

    def fake_train(config):
        calls["config"] = config
        return _Result()

    import pipeline.training

    monkeypatch.setattr(pipeline.training, "train", fake_train)
    return calls


def test_train_starts_job_and_passes_config(client: TestClient, stub_train: dict) -> None:
    res = client.post(
        "/api/experiments/train",
        json={
            "data_yaml": "data/datasets/custom/data.yaml",
            "base_model": "yolo11m.pt",
            "epochs": 3,
            "experiment": "exp1",
            "run_name": "試行1",
        },
    )
    assert res.status_code == 202
    job_id = res.json()["job_id"]
    _wait(job_id)

    config = stub_train["config"]
    assert config.data_yaml == "data/datasets/custom/data.yaml"
    assert config.base_model == "yolo11m.pt"
    assert config.epochs == 3
    assert config.experiment == "exp1"
    assert config.run_name == "試行1"

    body = client.get(f"/api/experiments/result/{job_id}").json()
    assert body["status"] == "completed"
    assert body["result"]["run_id"] == "run-123"
    assert body["result"]["metrics"] == {"metrics/mAP50-95(B)": 0.42}


def test_train_uses_default_experiment_when_omitted(client: TestClient, stub_train: dict) -> None:
    from pipeline.experiments import DEFAULT_EXPERIMENT

    job_id = client.post("/api/experiments/train", json={"experiment": None}).json()["job_id"]
    _wait(job_id)
    assert stub_train["config"].experiment == DEFAULT_EXPERIMENT


def test_train_rejects_unknown_base_model(client: TestClient) -> None:
    res = client.post("/api/experiments/train", json={"base_model": "yolov5s.pt"})
    assert res.status_code == 400
    assert "未知のベースモデル" in res.json()["detail"]


@pytest.mark.parametrize("epochs", [0, -1, 1001])
def test_train_rejects_out_of_range_epochs(client: TestClient, epochs: int) -> None:
    assert client.post("/api/experiments/train", json={"epochs": epochs}).status_code == 422


def test_train_seg_model_is_allowed(client: TestClient, stub_train: dict) -> None:
    """ベースモデルは検出・セグの両方から選べる（Streamlit 版と同じ）。"""
    res = client.post("/api/experiments/train", json={"base_model": "yolo11s-seg.pt"})
    assert res.status_code == 202
    _wait(res.json()["job_id"])
    assert stub_train["config"].base_model == "yolo11s-seg.pt"


def test_train_failure_reports_streamlit_message(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import pipeline.training

    def boom(config):
        raise RuntimeError("data.yaml が見つかりません")

    monkeypatch.setattr(pipeline.training, "train", boom)

    job_id = client.post("/api/experiments/train", json={}).json()["job_id"]
    _wait(job_id)

    body = client.get(f"/api/experiments/result/{job_id}").json()
    assert body["status"] == "failed"
    assert "学習の実行に失敗しました" in body["error"]


def test_train_progress_is_streamed(client: TestClient, stub_train: dict) -> None:
    job_id = client.post("/api/experiments/train", json={}).json()["job_id"]
    _wait(job_id)

    with client.stream("GET", f"/api/experiments/stream/{job_id}") as res:
        body = "".join(res.iter_text())
    assert "event: started" in body
    assert "event: done" in body
    assert "MLflow UI" in body, "長時間処理である旨の案内を流す"


def test_training_result_of_unknown_job_is_404(client: TestClient) -> None:
    assert client.get("/api/experiments/result/nope").status_code == 404


def test_running_training_job_reports_running(client: TestClient) -> None:
    blocker = threading.Event()
    job = job_manager.start(None, lambda params, emit: (blocker.wait(timeout=5), {"run_id": "x"})[1], kind="train")
    try:
        assert client.get(f"/api/experiments/result/{job.job_id}").json()["status"] == "running"
    finally:
        blocker.set()
        _wait(job.job_id)


# ---------------------------------------------------------------------------
# data.yaml 生成
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("person,car", ["person", "car"]),
        (" person , car ", ["person", "car"]),
        ("person,,car,", ["person", "car"]),
        ("person,car,person", ["person", "car"]),
        ("truck,person,car", ["truck", "person", "car"]),  # 並び順＝クラス ID なので保持
        ("", []),
    ],
)
def test_parse_classes(raw: str, expected: list[str]) -> None:
    assert parse_classes(raw) == expected


def test_dataset_yaml_contains_paths_and_class_map(client: TestClient) -> None:
    body = client.post(
        "/api/experiments/dataset-yaml", json={"name": "custom", "classes": "person,car"}
    ).json()

    assert body["classes"] == ["person", "car"]
    assert "data/datasets/custom" in body["yaml"]
    assert "images/train" in body["yaml"]
    assert "images/val" in body["yaml"]
    # クラス ID は入力順で振られる。
    assert "0: person" in body["yaml"]
    assert "1: car" in body["yaml"]


def test_dataset_yaml_rejects_empty_classes(client: TestClient) -> None:
    res = client.post("/api/experiments/dataset-yaml", json={"name": "custom", "classes": " , "})
    assert res.status_code == 400
    assert "クラスを1つ以上" in res.json()["detail"]


def test_dataset_yaml_keeps_japanese_class_names(client: TestClient) -> None:
    body = client.post("/api/experiments/dataset-yaml", json={"name": "jp", "classes": "人,車"}).json()
    assert body["classes"] == ["人", "車"]
    assert "人" in body["yaml"], "allow_unicode=True でそのまま読める形にする"
