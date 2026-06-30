"""モデル変換・最適化（Phase 5）。

YOLO11 を ONNX / CoreML / TorchScript / TensorRT へ変換し、量子化（FP16/INT8）を行う。
書式の検証は依存なしで単体テスト可能。実変換は ultralytics を要するため遅延 import。

M2 Mac（仕様書 §1.2/§7）では CoreML 変換が MPS 実行や iOS 配備に有効。
"""

from __future__ import annotations

# ultralytics がサポートする主な書式（本プロジェクトで扱う範囲）。
EXPORT_FORMATS: tuple[str, ...] = ("onnx", "coreml", "torchscript", "engine")

_FORMAT_ALIASES = {
    "onnx": "onnx",
    "coreml": "coreml",
    "mlmodel": "coreml",
    "torchscript": "torchscript",
    "ts": "torchscript",
    "engine": "engine",
    "tensorrt": "engine",
    "trt": "engine",
}


def normalize_format(fmt: str) -> str:
    """書式名の表記ゆれを ultralytics の format 値へ正規化する（不正値は ValueError）。"""
    key = fmt.strip().lower()
    if key not in _FORMAT_ALIASES:
        raise ValueError(f"未対応の書式: {fmt!r}（許可: {', '.join(EXPORT_FORMATS)}）")
    return _FORMAT_ALIASES[key]


def quantization_label(half: bool, int8: bool) -> str:
    """量子化設定の表示ラベルを返す（依存なし）。"""
    if int8:
        return "INT8"
    if half:
        return "FP16"
    return "FP32"


def export_model(weights: str, fmt: str, *, half: bool = False, int8: bool = False, imgsz: int = 640) -> str:
    """重みを指定書式へ変換し、出力パスを返す（ultralytics 遅延 import）。"""
    from ultralytics import YOLO

    target = normalize_format(fmt)
    model = YOLO(weights)
    out = model.export(format=target, half=half, int8=int8, imgsz=imgsz)
    # ultralytics は出力パス（str/Path）を返す。
    return str(out)
