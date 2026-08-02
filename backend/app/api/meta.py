"""メタ情報 API（デバイス・選択肢）。

Streamlit 版では各ビューが `describe_device()` や `AVAILABLE_MODELS` を直接
参照していた。React 版はブラウザ側からは Python 定数を見られないため、ここで
まとめて配信する。**定数の定義元は `pipeline` のまま**（ここでは写すだけ）。
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.schemas import DeviceInfo, OptionsResponse
from pipeline.camera import LIGHTWEIGHT_MODELS, RESOLUTION_PRESETS
from pipeline.claude_vision import DEFAULT_MODEL as CLAUDE_MODEL
from pipeline.detections import COCO_COMMON, FIELDS
from pipeline.detector import AVAILABLE_MODELS, SEG_MODELS
from pipeline.device import describe_device
from pipeline.experiments import DEFAULT_EXPERIMENT
from pipeline.export_model import EXPORT_FORMATS
from pipeline.registry import STAGES

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/device", response_model=DeviceInfo)
def get_device_info() -> DeviceInfo:
    """実行デバイスと torch の導入状況。torch 未導入でも 200 を返す。"""
    info = describe_device()
    return DeviceInfo(
        device=str(info["device"]),
        torch=str(info["torch"]) if info["torch"] else None,
        mps_available=bool(info["mps_available"]),
        cuda_available=bool(info["cuda_available"]),
    )


@router.get("/options", response_model=OptionsResponse)
def get_options() -> OptionsResponse:
    """UI の選択肢（モデル・クラス・解像度・書式・ステージ）をまとめて返す。"""
    return OptionsResponse(
        models=list(AVAILABLE_MODELS),
        seg_models=list(SEG_MODELS),
        # frozenset は順不同なので、UI が安定して表示できるようソートして返す。
        lightweight_models=sorted(LIGHTWEIGHT_MODELS),
        coco_common=dict(COCO_COMMON),
        resolution_presets={k: [v[0], v[1]] for k, v in RESOLUTION_PRESETS.items()},
        export_formats=list(EXPORT_FORMATS),
        registry_stages=list(STAGES),
        default_experiment=DEFAULT_EXPERIMENT,
        detection_fields=list(FIELDS),
        claude_model=CLAUDE_MODEL,
    )
