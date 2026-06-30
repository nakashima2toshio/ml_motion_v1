"""YOLO11 検出器ラッパー（Phase 1）。

ultralytics は重い依存のため、import はクラス生成時に遅延させる。
これによりモデル未導入の環境でもこのモジュール自体は import できる。
"""

from __future__ import annotations

from pipeline.device import get_device

# 利用可能な検出モデル（軽量 → 高精度）。リアルタイム(P3)は n/s を既定にする。
AVAILABLE_MODELS: tuple[str, ...] = ("yolo11n.pt", "yolo11s.pt", "yolo11m.pt")


class Detector:
    """ultralytics YOLO11 をラップし、1 フレームの推論結果を返す。"""

    def __init__(
        self,
        model_name: str = "yolo11s.pt",
        device: str | None = None,
        conf: float = 0.25,
        classes: list[int] | None = None,
    ) -> None:
        from ultralytics import YOLO  # 遅延 import

        self.model_name = model_name
        self.device = device or get_device()
        self.conf = conf
        self.classes = classes  # None=全クラス
        self.model = YOLO(model_name)

    @property
    def names(self) -> dict[int, str]:
        """クラス ID → クラス名のマッピング。"""
        return self.model.names

    def predict(self, frame):
        """1 フレーム（BGR ndarray）を推論し ultralytics の Results を返す。"""
        results = self.model.predict(
            frame,
            device=self.device,
            conf=self.conf,
            classes=self.classes,
            verbose=False,
        )
        return results[0]
