"""API のリクエスト/レスポンススキーマ。

`frontend/src/types.ts` と 1:1 で対応させる。片方だけ変えないこと。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """`GET /api/health`。"""

    status: str = "ok"
    version: str


class DeviceInfo(BaseModel):
    """`GET /api/meta/device`。

    Streamlit 版で各画面の上部に出していたデバイス表示（Device / torch / MPS / CUDA）。
    `pipeline.device.describe_device()` の戻りをそのまま写す。
    """

    device: str = Field(description='実行デバイス（"mps" / "cuda" / "cpu"）')
    torch: str | None = Field(default=None, description="torch のバージョン。未導入なら None")
    mps_available: bool = False
    cuda_available: bool = False


class OptionsResponse(BaseModel):
    """`GET /api/meta/options`。

    Streamlit 版では各ビューが `pipeline` の定数を直接 import していた。React 版では
    UI が同じ選択肢を持てるよう、この 1 本にまとめて配信する（定数の二重管理を避ける）。
    """

    models: list[str] = Field(description="検出モデル（AVAILABLE_MODELS）")
    seg_models: list[str] = Field(description="セグメンテーションモデル（SEG_MODELS）")
    lightweight_models: list[str] = Field(description="リアルタイム向き軽量モデル")
    coco_common: dict[str, int] = Field(description="COCO 代表クラス名 → クラス ID")
    resolution_presets: dict[str, list[int]] = Field(description="リアルタイム解像度プリセット")
    export_formats: list[str] = Field(description="モデル変換の書式")
    registry_stages: list[str] = Field(description="Model Registry のステージ")
    default_experiment: str = Field(description="MLflow の既定実験名")
    detection_fields: list[str] = Field(description="検出結果テーブルの列順")


class JobAccepted(BaseModel):
    """ジョブ起動（202）の共通レスポンス。"""

    job_id: str


class JobStatusResponse(BaseModel):
    """ジョブの状態と結果。"""

    job_id: str
    kind: str
    status: str = Field(description="running / completed / failed")
    result: dict | None = None
    error: str | None = None
