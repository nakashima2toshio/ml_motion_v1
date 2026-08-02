"""解析ジョブの実行関数（`app/views/analyze.py` の Run 相当）。

Streamlit 版の処理順:
    アップロード保存 → Detector 読み込み → process_tracking_video（進捗コールバック）
    → session_state へ結果格納

React 版はこれをワーカースレッドで実行し、進捗を SSE で流す。**検証（クラス未選択・
ゾーンとトラッキングの依存）は API 層で先に行う**ので、ここは実行に専念する。

`pipeline` の重い依存はこのモジュールを import しただけでは読み込まれない
（`detector_cache` 経由の遅延 import）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.app.core import storage
from backend.app.core.detector_cache import get_detector
from backend.app.core.jobs import EmitFn, JobEvent


@dataclass
class AnalyzeParams:
    """解析ジョブのパラメータ（API の `AnalyzeRequest` を実行用に解決したもの）。"""

    input_path: Path
    output_dir: Path
    run_id: str
    stem: str
    model_name: str
    device: str
    conf: float
    classes: list[int] | None
    enable_seg: bool
    enable_track: bool
    frame_stride: int
    trace_length: int
    # 正規化座標の多角形。空ならゾーン解析なし。
    zones: list[tuple[str, list[tuple[float, float]]]] = field(default_factory=list)


def run_analyze(params: AnalyzeParams, emit: EmitFn) -> dict[str, Any]:
    """1 本の動画を解析し、結果 dict を返す。

    戻り dict は `Job.result` になる。`records` は数万件になりうるため、API は
    これを直接返さず、サマリ用の応答から除外してページングで配信する。
    """
    # 遅延 import: torch/cv2/ultralytics をここで初めて読み込む。
    from pipeline.detections import summarize, to_csv_bytes, to_json_bytes
    from pipeline.video import process_tracking_video
    from pipeline.zones import Zone

    # フレーム数を伴わない進捗（UI 側はメッセージだけを出す）。ここで current/total を
    # 入れると「解析中… 0/1 フレーム」と誤解を招くラベルになるので入れない。
    emit(JobEvent(type="progress", message="モデルを読み込み中…"))
    try:
        detector = get_detector(params.model_name, params.device, params.conf, params.classes)
    except Exception as e:  # noqa: BLE001 — Streamlit 版と同じ文言でユーザに返す
        raise RuntimeError(f"モデルの読み込みに失敗しました: {e}") from e

    zones = [Zone(name=name, polygon=polygon) for name, polygon in params.zones]
    output_path = params.output_dir / f"annotated_{params.stem}.mp4"

    def progress_cb(current: int, total: int) -> None:
        emit(JobEvent(type="progress", data={"current": current, "total": total}))

    try:
        result = process_tracking_video(
            str(params.input_path),
            str(output_path),
            detector,
            enable_masks=params.enable_seg,
            enable_tracking=params.enable_track,
            zones=zones,
            frame_stride=params.frame_stride,
            trace_length=params.trace_length,
            progress_cb=progress_cb,
        )
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"動画処理に失敗しました: {e}") from e

    records = result.records
    # ダウンロード用にこの場で書き出す（結果参照のたびに再生成しない）。
    (params.output_dir / "detections.csv").write_bytes(to_csv_bytes(records))
    (params.output_dir / "detections.json").write_bytes(to_json_bytes(records))

    tracker_ids = {r.tracker_id for r in records if r.tracker_id is not None}
    written = output_path.exists() and output_path.stat().st_size > 0

    return {
        "run_id": params.run_id,
        "stem": params.stem,
        "video_url": storage.media_url(params.run_id, output_path.name) if written else None,
        "output_path": str(output_path),
        "frames_processed": result.frames_processed,
        "frames_total": result.frames_total,
        "fps": round(result.fps, 3),
        "width": result.width,
        "height": result.height,
        "duration_sec": round(result.duration_sec, 2),
        "total_detections": len(records),
        "unique_track_ids": len(tracker_ids),
        "stats": summarize(records),
        "zone_summary": result.zone_summary or {},
        "per_track_dwell": result.per_track_dwell or [],
        "records": [r.to_dict() for r in records],
    }
