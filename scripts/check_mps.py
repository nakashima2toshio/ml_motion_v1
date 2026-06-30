#!/usr/bin/env python3
"""Phase 0 完了判定スクリプト: MPS（M2 Mac）動作確認。

完了判定（仕様書 §5）:
    torch.backends.mps.is_available() == True

実行:
    python scripts/check_mps.py

M2 Mac 以外（CUDA / CPU のみ）の環境でも落ちずに、検出したデバイスで
簡単なテンソル演算（行列積）を実行して数値が返ることを確認する。
"""

from __future__ import annotations

import sys


def main() -> int:
    try:
        import torch
    except ImportError:
        print("❌ torch が未導入です。`uv sync` または `pip install -e .` を実行してください。")
        return 1

    mps_available = torch.backends.mps.is_available()
    mps_built = torch.backends.mps.is_built()
    cuda_available = torch.cuda.is_available()

    print(f"torch version        : {torch.__version__}")
    print(f"MPS available        : {mps_available}")
    print(f"MPS built            : {mps_built}")
    print(f"CUDA available       : {cuda_available}")

    if mps_available:
        device = "mps"
    elif cuda_available:
        device = "cuda"
    else:
        device = "cpu"
    print(f"selected device      : {device}")

    # 選択デバイス上で簡単な行列積を実行して、実際に演算が通ることを確認する。
    a = torch.randn(512, 512, device=device)
    b = torch.randn(512, 512, device=device)
    c = (a @ b).sum().item()
    print(f"matmul sanity check  : ok (sum={c:.2f}, device={device})")

    # 完了判定: M2 Mac では MPS が True であることを期待する。
    if mps_available:
        print("\n✅ Phase 0 完了判定: torch.backends.mps.is_available() == True")
        return 0

    print(
        "\n⚠️ MPS は利用できません（このマシンは M2 Mac ではない可能性があります）。\n"
        f"   現在のデバイス '{device}' で演算自体は成功しています。\n"
        "   仕様書の Phase 0 完了判定は M2 Mac 上で再実行してください。"
    )
    # MPS 以外でも演算が通れば異常終了にはしない（CI / クラウド GPU 用）。
    return 0


if __name__ == "__main__":
    sys.exit(main())
