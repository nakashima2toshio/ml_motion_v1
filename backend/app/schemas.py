"""API のリクエスト/レスポンススキーマ。

`frontend/src/types.ts` と 1:1 で対応させる。片方だけ変えないこと。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


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


# =============================================================================
# 解析画面（app/views/analyze.py 相当）
# =============================================================================


class UploadResponse(BaseModel):
    """`POST /api/analyze/upload`（`st.file_uploader` 相当）。"""

    upload_id: str
    filename: str
    size: int


class ZoneInput(BaseModel):
    """ゾーン定義 1 件。座標は正規化（左上 0,0 / 右下 1,1）。"""

    name: str = Field(min_length=1)
    polygon: list[tuple[float, float]]

    @field_validator("polygon")
    @classmethod
    def _validate_polygon(cls, polygon: list[tuple[float, float]]) -> list[tuple[float, float]]:
        if len(polygon) < 3:
            raise ValueError("polygon には 3 点以上必要です")
        for x, y in polygon:
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise ValueError(f"polygon の座標は 0〜1 の正規化座標です: ({x}, {y})")
        return polygon


class AnalyzeRequest(BaseModel):
    """`POST /api/analyze/run`（サイドバー設定 + ▶ Run 解析）。"""

    upload_id: str
    enable_seg: bool = False
    enable_track: bool = True
    enable_zone: bool = False
    model_name: str = "yolo11s.pt"
    conf: float = Field(default=0.25, ge=0.0, le=1.0)
    # None は「全クラス（COCO 80）」。空リストは選択漏れとして 400 にする。
    classes: list[int] | None = None
    frame_stride: int = Field(default=1, ge=1, le=10)
    trace_length: int = Field(default=30, ge=5, le=120)
    zones: list[ZoneInput] = Field(default_factory=list)


class AnalyzeSummary(BaseModel):
    """解析結果のうち、検出レコードを除いた部分。

    検出レコードは数万件になりうるため、この応答には含めない
    （`GET /api/analyze/detections/{job_id}` でページングして取得する）。
    """

    run_id: str
    stem: str
    video_url: str | None = Field(default=None, description="注釈付き動画の URL（書き出し失敗時は None）")
    frames_processed: int
    frames_total: int
    fps: float
    width: int
    height: int
    duration_sec: float
    total_detections: int
    unique_track_ids: int
    stats: dict[str, dict[str, int]] = Field(description="クラス別 {total, max_in_frame}")
    zone_summary: dict[str, dict[str, Any]] = Field(default_factory=dict)
    per_track_dwell: list[dict[str, Any]] = Field(default_factory=list)


class DetectionPage(BaseModel):
    """`GET /api/analyze/detections/{job_id}`（検出結果テーブルのページング）。"""

    total: int
    offset: int
    limit: int
    records: list[dict[str, Any]]


class SummaryResponse(BaseModel):
    """`POST /api/analyze/summary/{job_id}`（📝 NL要約）。"""

    summary: str
