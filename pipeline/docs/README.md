# pipeline パッケージ モジュール別ドキュメント

**Version 1.0** | 最終更新: 2026-07-01

`pipeline/` パッケージ（Video ML Analytics Studio の推論・学習コア）の各モジュールを
IPO（Input-Process-Output）形式で解説したドキュメント集。フォーマット仕様は
`.claude/skills/ml-motion-docs/a_class_method_md_format.md` に準拠する。

> **遅延 import 設計**: 重い依存（`torch` / `cv2` / `ultralytics` / `supervision` /
> `mlflow` / `anthropic`）はすべて関数・メソッド内で import する。したがって
> `import pipeline` 自体はこれらが未導入でも成功する。依存ゼロのロジック層
> （`detections` / `zones` / `camera` / `dataset` / `benchmark` / `batch`(filter/manifest) /
> `export_model`(format) / `claude_vision`(prompt) / `active_learning` / `registry`(stage)）は
> 単体テスト可能。

---

## モジュール一覧

### Phase 0 — デバイス

| モジュール | ドキュメント | 概要 | 主なエクスポート |
|-----------|------------|------|----------------|
| `device.py` | [device.md](./device.md) | PyTorch デバイス選択（MPS>CUDA>CPU） | `get_device` / `describe_device` |

### Phase 1 — 検出・動画処理・エクスポート

| モジュール | ドキュメント | 概要 | 主なエクスポート |
|-----------|------------|------|----------------|
| `detector.py` | [detector.md](./detector.md) | YOLO11 検出器ラッパー | `Detector` / `AVAILABLE_MODELS` / `SEG_MODELS` |
| `detections.py` | [detections.md](./detections.md) | 検出結果のデータ構造と CSV/JSON エクスポート | `DetectionRecord` / `COCO_COMMON` / `summarize` / `to_csv_bytes` / `to_json_bytes` |
| `video.py` | [video.md](./video.md) | mp4 バッチ動画処理 | `process_video` / `process_tracking_video` / `VideoResult` / `TrackingResult` |

### Phase 2 — セグメンテーション・トラッキング・ゾーン解析

| モジュール | ドキュメント | 概要 | 主なエクスポート |
|-----------|------------|------|----------------|
| `tracking.py` | [tracking.md](./tracking.md) | supervision ByteTrack ラッパー | `Tracker` |
| `zones.py` | [zones.md](./zones.md) | ゾーン滞留・侵入解析（依存ゼロ） | `Zone` / `ZoneAnalyzer` / `IntrusionEvent` / `point_in_polygon` |

### Phase 3 — リアルタイム・カメラ

| モジュール | ドキュメント | 概要 | 主なエクスポート |
|-----------|------------|------|----------------|
| `realtime.py` | [realtime.md](./realtime.md) | 1 フレーム処理器（検出→追跡→描画） | `FrameProcessor` / `FrameResult` |
| `camera.py` | [camera.md](./camera.md) | カメラ取り込みユーティリティ | `FpsMeter` / `RESOLUTION_PRESETS` / `LIGHTWEIGHT_MODELS` / `is_lightweight` / `recommend_realtime_model` / `open_camera` |

### Phase 4 — 学習・実験管理・データセット

| モジュール | ドキュメント | 概要 | 主なエクスポート |
|-----------|------------|------|----------------|
| `dataset.py` | [dataset.md](./dataset.md) | データセット設計（data.yaml 生成・分割） | `DatasetSpec` / `build_dataset_yaml` / `train_val_split` |
| `training.py` | [training.md](./training.md) | 転移学習 / Fine-tuning（MLflow 記録） | `TrainConfig` / `TrainResult` / `train` |
| `experiments.py` | [experiments.md](./experiments.md) | MLflow 実験トラッキング照会 | `DEFAULT_EXPERIMENT` / `tracking_uri` / `list_runs` / `format_runs_table` / `best_run` |
| `registry.py` | [registry.md](./registry.md) | MLflow Model Registry（None/Staging/Production/Archived） | `STAGES` / `normalize_stage` / `register_model` / `transition_stage` / `model_uri` / `download_model` |

### Phase 5 — 本番・最適化

| モジュール | ドキュメント | 概要 | 主なエクスポート |
|-----------|------------|------|----------------|
| `batch.py` | [batch.md](./batch.md) | バッチ推論ジョブ（ディレクトリ一括処理） | `filter_media` / `discover_media` / `build_manifest` / `run_batch` / `BatchResult` / `BatchItemResult` |
| `export_model.py` | [export_model.md](./export_model.md) | モデル変換・量子化（ONNX/CoreML/TorchScript/TensorRT） | `EXPORT_FORMATS` / `normalize_format` / `quantization_label` / `export_model` |
| `benchmark.py` | [benchmark.md](./benchmark.md) | 推論レイテンシ／スループット計測 | `LatencyStats` / `benchmark_processor` |

### Phase 6 — Active Learning・Claude 連携

| モジュール | ドキュメント | 概要 | 主なエクスポート |
|-----------|------------|------|----------------|
| `active_learning.py` | [active_learning.md](./active_learning.md) | 低信頼フレーム抽出（アノテ候補選定） | `select_low_confidence` / `FrameUncertainty` |
| `claude_vision.py` | [claude_vision.md](./claude_vision.md) | Claude 連携（サマリ・Vision レビュー・NL クエリ） | `DEFAULT_MODEL` / `build_summary_prompt` / `build_review_prompt` / `summarize_session` / `review_annotation` / `nl_query_frames` |

---

## 技術スタック

| 用途 | 採用技術 | 既定 |
|------|---------|------|
| 検出 / セグメンテーション | `ultralytics`（YOLO11 / YOLO11-seg） | `yolo11s` / `yolo11s-seg` |
| 追跡 / 描画 | `supervision`（`ByteTrack` / `BoxAnnotator` / `LabelAnnotator` / `MaskAnnotator` / `TraceAnnotator`） | — |
| デバイス | PyTorch **MPS**（M2 Mac、CUDA 非対応） | `get_device()` が `mps>cuda>cpu` を解決 |
| 実験管理 | `mlflow`（docker-compose） | `http://localhost:5000`（`MLFLOW_PORT` で可変） |
| LLM / VLM | **Anthropic Claude** | `claude-opus-4-8`（`ANTHROPIC_MODEL` で上書き、鍵 `ANTHROPIC_API_KEY`） |
| Python | 3.12（`requires-python = ">=3.12,<3.13"`） | — |

---

## 関連ドキュメント

- 横断仕様（クラス別・アーキテクチャ）: [`../../docs/ml_motion_spec.md`](../../docs/ml_motion_spec.md)
- 設計リファレンス: [`../../docs/ml_motion_detection_spec.md`](../../docs/ml_motion_detection_spec.md)
- 画面操作マニュアル: [`../../docs/manual/`](../../docs/manual/)

---

## 変更履歴

| バージョン | 変更内容 |
|-----------|---------|
| 1.0 | 初版作成（pipeline/*.py 全 17 モジュールの IPO ドキュメント整備） |
