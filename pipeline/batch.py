"""バッチ推論ジョブ（Phase 5）。

ディレクトリ内の動画を一括処理し、出力動画と検出マニフェストを生成する。
ファイル選別（filter_media）とマニフェスト整形（build_manifest）は依存なしで単体テスト可能。
実処理 run_batch は cv2/ultralytics を要するため遅延処理。
"""

from __future__ import annotations

from dataclasses import dataclass, field

MEDIA_EXTS: tuple[str, ...] = (".mp4", ".mov", ".avi", ".mkv")


def filter_media(names: list[str], exts: tuple[str, ...] = MEDIA_EXTS) -> list[str]:
    """拡張子で動画ファイル名を抽出してソートする（大文字小文字を無視、依存なし）。"""
    low = tuple(e.lower() for e in exts)
    return sorted(n for n in names if n.lower().endswith(low))


@dataclass
class BatchItemResult:
    """1 ファイルの処理結果。"""

    input_path: str
    output_path: str = ""
    frames_processed: int = 0
    n_detections: int = 0
    ok: bool = True
    error: str = ""


@dataclass
class BatchResult:
    """バッチ全体の結果。"""

    items: list[BatchItemResult] = field(default_factory=list)

    @property
    def total_detections(self) -> int:
        return sum(i.n_detections for i in self.items)

    @property
    def succeeded(self) -> int:
        return sum(1 for i in self.items if i.ok)

    @property
    def failed(self) -> int:
        return sum(1 for i in self.items if not i.ok)


def build_manifest(result: BatchResult) -> list[dict]:
    """バッチ結果を表示/保存用の行リストへ整形する（依存なし）。"""
    return [
        {
            "input": i.input_path,
            "output": i.output_path,
            "frames": i.frames_processed,
            "detections": i.n_detections,
            "status": "ok" if i.ok else f"error: {i.error}",
        }
        for i in result.items
    ]


def discover_media(directory: str, exts: tuple[str, ...] = MEDIA_EXTS) -> list[str]:
    """ディレクトリ直下の動画ファイルの絶対パス一覧を返す。"""
    from pathlib import Path

    root = Path(directory)
    if not root.is_dir():
        return []
    names = [p.name for p in root.iterdir() if p.is_file()]
    return [str(root / n) for n in filter_media(names, exts)]


def run_batch(
    input_dir: str,
    output_dir: str,
    *,
    model_name: str = "yolo11s.pt",
    conf: float = 0.25,
    classes: list[int] | None = None,
    enable_masks: bool = False,
    enable_tracking: bool = True,
    frame_stride: int = 1,
    progress_cb=None,
) -> BatchResult:
    """input_dir 内の動画を一括で検出処理し、output_dir に注釈付き動画を書き出す。"""
    from pathlib import Path

    from pipeline.detector import Detector
    from pipeline.video import process_tracking_video

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    detector = Detector(model_name=model_name, conf=conf, classes=classes)

    inputs = discover_media(input_dir)
    result = BatchResult()
    for idx, in_path in enumerate(inputs):
        stem = Path(in_path).stem
        out_path = str(Path(output_dir) / f"annotated_{stem}.mp4")
        try:
            vr = process_tracking_video(
                in_path, out_path, detector,
                enable_masks=enable_masks, enable_tracking=enable_tracking, frame_stride=frame_stride,
            )
            result.items.append(
                BatchItemResult(
                    input_path=in_path, output_path=out_path,
                    frames_processed=vr.frames_processed, n_detections=len(vr.records), ok=True,
                )
            )
        except Exception as e:  # noqa: BLE001 — 1 ファイルの失敗で全体を止めない
            result.items.append(BatchItemResult(input_path=in_path, ok=False, error=str(e)))
        if progress_cb is not None:
            progress_cb(idx + 1, len(inputs))
    return result
