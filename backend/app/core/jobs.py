"""長時間ジョブの管理とイベント配信（インメモリ・スレッドセーフ）。

Streamlit 版では `st.progress` と `progress_cb(cur, total)` で進捗を出していたが、
React 版ではリクエストとレスポンスが分離するため「ジョブ + SSE」で置き換える。

    POST /api/xxx/run      -> 202 {"job_id": ...}   （ワーカースレッドで実行開始）
    GET  /api/xxx/stream/{job_id}  -> text/event-stream（progress/done/error）
    GET  /api/xxx/result/{job_id}  -> 最終結果 JSON

1 リクエスト = 1 ジョブ。イベントは Job に蓄積し、購読者は先頭から追いかけるため、
途中購読・再接続でも全イベントをリプレイできる。ローカル開発のシングルプロセス
前提で永続化はしない（Streamlit の `st.session_state` も揮発だったため同水準）。

重い依存（torch/cv2/ultralytics）には一切触れないので、このモジュールは単体で
テストできる。実際の実行関数（runner）は各 API ルータが注入する。
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# 完了済みジョブをメモリに保持する上限（超えたら古い完了ジョブから破棄）。
MAX_FINISHED_JOBS = 20

# 進捗を通知するコールバック。`pipeline` 側の ProgressCallback と同じ形。
EmitFn = Callable[["JobEvent"], None]

# ジョブの実行関数。戻り dict がそのまま `Job.result` になる。
JobRunner = Callable[[Any, EmitFn], dict[str, Any]]


@dataclass
class JobEvent:
    """SSE で配信する 1 イベント。

    type:
        started  … 実行開始
        progress … 進捗（data: {"current": int, "total": int}）
        done     … 正常終了
        error    … 失敗（message にユーザ向け文言）
    """

    type: str
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Job:
    """実行中/完了のジョブ。イベント列と最終結果を保持する。"""

    job_id: str
    params: Any
    kind: str = "job"
    status: str = "running"  # running / completed / failed
    events: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    cond: threading.Condition = field(default_factory=threading.Condition)

    @property
    def done(self) -> bool:
        return self.status != "running"

    def emit(self, event: JobEvent) -> None:
        """進捗イベントを蓄積し、SSE 購読者を起こす。"""
        record = {"seq": len(self.events), "ts": time.time(), **asdict(event)}
        with self.cond:
            self.events.append(record)
            self.cond.notify_all()

    def progress(self, current: int, total: int) -> None:
        """`pipeline` 側の `progress_cb(cur, total)` をそのまま繋ぐためのアダプタ。"""
        self.emit(JobEvent(type="progress", data={"current": current, "total": total}))

    def finish(self, status: str, result: dict[str, Any] | None = None, error: str | None = None) -> None:
        with self.cond:
            self.status = status
            self.result = result
            self.error = error
            self.finished_at = time.time()
            self.cond.notify_all()

    def stream_events(self, poll_timeout: float = 15.0) -> Iterator[dict[str, Any] | None]:
        """イベントを先頭から順に返すブロッキングイテレータ。

        新イベントが `poll_timeout` 秒来ない場合は None を返す（SSE 側は
        keepalive コメントを送って接続を維持する）。ジョブ完了かつ全イベント
        配信済みで終了する。
        """
        index = 0
        while True:
            with self.cond:
                if index >= len(self.events) and not self.done:
                    self.cond.wait(timeout=poll_timeout)
                if index < len(self.events):
                    event = self.events[index]
                    index += 1
                else:
                    if self.done:
                        return
                    event = None  # タイムアウト → keepalive
            yield event


def format_sse(event: dict[str, Any] | None) -> str:
    """イベントを SSE のワイヤ形式へ変換する。None は keepalive コメント。"""
    if event is None:
        return ": keepalive\n\n"
    return f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


def sse_stream(job: Job, poll_timeout: float = 15.0) -> Iterator[str]:
    """`StreamingResponse` にそのまま渡せる SSE 文字列のイテレータ。"""
    for event in job.stream_events(poll_timeout=poll_timeout):
        yield format_sse(event)


class JobManager:
    """ジョブの生成・参照を担う（インメモリ・スレッドセーフ）。"""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def start(self, params: Any, runner: JobRunner, kind: str = "job") -> Job:
        """ワーカースレッドで runner を実行するジョブを起動する。"""
        job = Job(job_id=uuid.uuid4().hex[:12], params=params, kind=kind)
        with self._lock:
            self._gc_finished_locked()
            self._jobs[job.job_id] = job
        thread = threading.Thread(
            target=self._run, args=(job, runner), name=f"{kind}-job-{job.job_id}", daemon=True
        )
        thread.start()
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _run(self, job: Job, runner: JobRunner) -> None:
        job.emit(JobEvent(type="started"))
        try:
            result = runner(job.params, job.emit)
        except Exception as e:  # noqa: BLE001 — 失敗はイベントとして UI に返す
            logger.exception("%s job %s failed", job.kind, job.job_id)
            message = f"{type(e).__name__}: {e}"
            job.emit(JobEvent(type="error", message=message))
            job.finish("failed", error=message)
            return
        job.emit(JobEvent(type="done"))
        job.finish("completed", result=result)

    def _gc_finished_locked(self) -> None:
        """完了ジョブが増えすぎたら古い順に破棄する（呼び出し側で lock 保持）。"""
        finished = sorted((j for j in self._jobs.values() if j.done), key=lambda j: j.finished_at or 0.0)
        for job in finished[: max(0, len(finished) - MAX_FINISHED_JOBS)]:
            self._jobs.pop(job.job_id, None)


# アプリ全体で共有するジョブマネージャ（シングルプロセス前提）。
job_manager = JobManager()
