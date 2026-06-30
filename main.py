"""Video ML Analytics Studio — 簡易ステータス エントリポイント。

依存導入後の素早い疎通確認用。詳細な MPS 動作確認は scripts/check_mps.py を使う。

    python main.py
"""

from __future__ import annotations

from pipeline.device import describe_device


def main() -> None:
    info = describe_device()
    print("Video ML Analytics Studio — Phase 0 環境ステータス")
    print(f"  torch          : {info['torch'] or '未導入'}")
    print(f"  selected device: {info['device']}")
    print(f"  MPS available  : {info['mps_available']}")
    print(f"  CUDA available : {info['cuda_available']}")
    print()
    print("次のステップ:")
    print("  - 詳細な MPS 確認 : python scripts/check_mps.py")
    print("  - UI 起動         : streamlit run app/Home.py")
    print("  - MLflow 起動     : docker-compose -f docker-compose/docker-compose.yml up -d")


if __name__ == "__main__":
    main()
