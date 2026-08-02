"""ジョブ基盤（`backend/app/core/jobs.py`）のテスト。

Streamlit の `st.progress` を置き換える経路なので、
「進捗が順に流れる」「失敗してもイベントとして届く」「途中購読でも全部読める」
の 3 点を押さえる。
"""

from __future__ import annotations

import json
import threading

import pytest

from backend.app.core.jobs import Job, JobEvent, JobManager, format_sse


def _drain(job: Job) -> list[dict]:
    """完了済みジョブのイベントを全部読む（keepalive は除く）。"""
    return [e for e in job.stream_events(poll_timeout=0.05) if e is not None]


def _wait(job: Job, timeout: float = 5.0) -> None:
    deadline = threading.Event()
    with job.cond:
        while not job.done:
            if not job.cond.wait(timeout=timeout):
                break
    assert job.done, "ジョブが時間内に完了しなかった"
    deadline.set()


def test_successful_job_emits_started_progress_done() -> None:
    manager = JobManager()

    def runner(params, emit):
        for i in range(1, 4):
            emit(JobEvent(type="progress", data={"current": i, "total": 3}))
        return {"frames": params["frames"]}

    job = manager.start({"frames": 3}, runner, kind="analyze")
    _wait(job)

    assert job.status == "completed"
    assert job.result == {"frames": 3}
    assert job.error is None

    types = [e["type"] for e in _drain(job)]
    assert types == ["started", "progress", "progress", "progress", "done"]


def test_progress_adapter_matches_pipeline_callback_shape() -> None:
    """`Job.progress` は pipeline の `progress_cb(cur, total)` にそのまま渡せる。"""
    job = Job(job_id="x", params=None)
    progress_cb = job.progress  # Callable[[int, int], None]
    progress_cb(2, 10)

    event = job.events[0]
    assert event["type"] == "progress"
    assert event["data"] == {"current": 2, "total": 10}


def test_failed_job_reports_error_event_and_status() -> None:
    manager = JobManager()

    def runner(params, emit):
        raise RuntimeError("動画処理に失敗しました")

    job = manager.start(None, runner, kind="analyze")
    _wait(job)

    assert job.status == "failed"
    assert job.result is None
    assert "動画処理に失敗しました" in (job.error or "")

    events = _drain(job)
    assert events[-1]["type"] == "error"
    assert "RuntimeError" in events[-1]["message"]


def test_late_subscriber_replays_all_events() -> None:
    """完了後に購読しても、最初のイベントから全部読める（再接続対応）。"""
    manager = JobManager()
    job = manager.start(None, lambda params, emit: {"ok": True}, kind="analyze")
    _wait(job)

    first_read = _drain(job)
    second_read = _drain(job)
    assert first_read == second_read
    assert [e["seq"] for e in first_read] == list(range(len(first_read)))


def test_manager_get_returns_none_for_unknown_job() -> None:
    assert JobManager().get("does-not-exist") is None


def test_finished_jobs_are_garbage_collected() -> None:
    manager = JobManager()
    jobs = []
    for _ in range(25):  # MAX_FINISHED_JOBS = 20
        job = manager.start(None, lambda params, emit: {"ok": True})
        _wait(job)
        jobs.append(job)

    alive = [j for j in jobs if manager.get(j.job_id) is not None]
    assert len(alive) <= 21  # 直近ジョブ + GC 上限
    assert manager.get(jobs[-1].job_id) is not None, "最新ジョブは残る"
    assert manager.get(jobs[0].job_id) is None, "最古の完了ジョブは破棄される"


@pytest.mark.parametrize(
    "event,expected_prefix",
    [
        (None, ": keepalive"),
        ({"seq": 0, "type": "progress", "data": {"current": 1}}, "event: progress"),
    ],
)
def test_format_sse(event, expected_prefix) -> None:
    wire = format_sse(event)
    assert wire.startswith(expected_prefix)
    assert wire.endswith("\n\n")


def test_format_sse_payload_is_json_and_keeps_japanese() -> None:
    wire = format_sse({"seq": 1, "type": "error", "message": "失敗しました", "data": {}})
    payload = wire.split("data: ", 1)[1].strip()
    assert json.loads(payload)["message"] == "失敗しました"
    assert "失敗しました" in wire, "ensure_ascii=False でそのまま読める形にする"
