"""バッチ推論ジョブの実行関数（`app/views/production.py` の「▶ バッチ実行」相当）。

`pipeline.batch.run_batch` をワーカースレッドで呼び、ファイル単位の進捗を SSE へ流す。
パスの検証は API 層で済ませてから渡す（ここには解決済みの絶対パスだけが来る）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.core.jobs import EmitFn, JobEvent
from backend.app.core.paths import to_display


@dataclass
class BatchParams:
    """バッチ推論ジョブのパラメータ（検証済み）。"""

    input_dir: Path
    output_dir: Path
    model_name: str
    conf: float
    frame_stride: int
    enable_tracking: bool = True


def run_batch_job(params: BatchParams, emit: EmitFn) -> dict[str, Any]:
    """ディレクトリ内の動画を一括処理し、マニフェストを返す。"""
    # 遅延 import: cv2/ultralytics をここで初めて読み込む。
    from pipeline.batch import build_manifest, discover_media, run_batch

    inputs = discover_media(str(params.input_dir))
    if not inputs:
        raise RuntimeError(f"動画が見つかりません: {to_display(params.input_dir)}")

    emit(JobEvent(type="progress", message=f"{len(inputs)} 件を処理します", data={"current": 0, "total": len(inputs)}))

    def progress_cb(current: int, total: int) -> None:
        emit(JobEvent(type="progress", data={"current": current, "total": total}))

    try:
        result = run_batch(
            str(params.input_dir),
            str(params.output_dir),
            model_name=params.model_name,
            conf=params.conf,
            enable_tracking=params.enable_tracking,
            frame_stride=params.frame_stride,
            progress_cb=progress_cb,
        )
    except Exception as e:  # noqa: BLE001 — Streamlit 版と同じ文言でユーザに返す
        raise RuntimeError(f"バッチ処理に失敗しました: {e}") from e

    # マニフェストのパスはリポジトリ相対にして、絶対パスを画面へ出さない。
    manifest = build_manifest(result)
    for row in manifest:
        row["input"] = to_display(Path(row["input"]))
        row["output"] = to_display(Path(row["output"])) if row["output"] else ""

    return {
        "input_dir": to_display(params.input_dir),
        "output_dir": to_display(params.output_dir),
        "succeeded": result.succeeded,
        "failed": result.failed,
        "total_detections": result.total_detections,
        "manifest": manifest,
    }
