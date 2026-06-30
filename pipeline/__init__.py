"""推論パイプライン パッケージ。

Phase 1 以降でフレーム抽出・検出・セグメンテーション・トラッキング・ゾーン解析の
各モジュールをここに追加する。Phase 0 ではデバイス選択ユーティリティのみを提供する。
"""

from pipeline.device import get_device, describe_device

__all__ = ["get_device", "describe_device"]
