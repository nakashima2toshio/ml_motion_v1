"""PyTorch デバイス選択ユーティリティ。

M2 Mac では CUDA が使えないため MPS（Metal Performance Shaders）を優先する。
CUDA 環境（クラウド GPU）でも動くよう、優先順位は mps > cuda > cpu とせず、
「利用可能なアクセラレータ（mps または cuda）> cpu」で解決する。
"""

from __future__ import annotations


def get_device() -> str:
    """利用可能な最良のデバイス文字列を返す（"mps" / "cuda" / "cpu"）。"""
    try:
        import torch
    except ImportError:  # torch 未導入でも import 時に落ちないようにする
        return "cpu"

    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def describe_device() -> dict[str, object]:
    """デバイス・torch のバージョン情報をまとめて返す（UI / 起動ログ用）。"""
    info: dict[str, object] = {"device": "cpu", "torch": None, "mps_available": False, "cuda_available": False}
    try:
        import torch
    except ImportError:
        return info

    info["torch"] = torch.__version__
    info["mps_available"] = bool(torch.backends.mps.is_available())
    info["cuda_available"] = bool(torch.cuda.is_available())
    info["device"] = get_device()
    return info
