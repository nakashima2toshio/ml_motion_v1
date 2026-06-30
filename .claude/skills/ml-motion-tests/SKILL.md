---
name: ml-motion-tests
description: >-
  Add and maintain the pytest suite AND author test documentation in the
  ml_motion_v1 repo (Video ML Analytics Studio). Use when `pytest` reports
  collection errors/failures, when adding tests for the dependency-free logic
  layer (detections/zones/camera/dataset/benchmark/batch/export/claude_vision/
  active_learning/registry), or when writing/updating test-spec docs that follow
  `a_test_md_format.md` (SAE format). Encodes the lazy-import test strategy, what
  is and isn't unit-testable, and the SAE test-doc format.
---

# ml_motion_v1 テスト保守スキル

`pytest tests/` の追加・保守と、テスト仕様書（`a_test_md_format.md`・SAE形式）作成の知見。

## テスト戦略（このプロジェクトの肝）
- 重い依存（torch/cv2/ultralytics/supervision/mlflow/anthropic）は**遅延 import**設計のため、
  **依存ゼロのロジック層だけを単体テスト対象**にする。これにより torch 等が無い環境でもテストが緑になる。
- 単体テスト可能（＝テスト必須）な層と代表ファイル:

| 対象モジュール | テスト対象ロジック | テストファイル |
|---|---|---|
| `pipeline/detections.py` | `to_csv_bytes`/`to_json_bytes`/`summarize`/`DetectionRecord` | `tests/test_detections.py` |
| `pipeline/zones.py` | `point_in_polygon`/`ZoneAnalyzer`（滞留・侵入・最大同時） | `tests/test_zones.py` |
| `pipeline/camera.py` | `FpsMeter`/`RESOLUTION_PRESETS`/`recommend_realtime_model` | `tests/test_camera.py` |
| `pipeline/dataset.py`/`experiments.py`/`registry.py` | `build_dataset_yaml`/`train_val_split`/`format_runs_table`/`best_run`/`normalize_stage` | `tests/test_phase4.py` |
| `pipeline/batch.py`/`benchmark.py`/`export_model.py` | `filter_media`/`build_manifest`/`LatencyStats`/`_percentile`/`normalize_format`/`quantization_label` | `tests/test_phase5.py` |
| `pipeline/claude_vision.py`/`active_learning.py` | `build_*_prompt`/`media_type_for`/`select_low_confidence` | `tests/test_phase6.py` |

- **単体テストに含めない**（実機・実 API・サーバ依存。実機確認に回す）:
  - `Detector`/`Tracker`/`FrameProcessor`/`process_tracking_video`（torch・cv2・supervision・YOLO 重み）
  - `run_batch`（cv2・実動画）、`export_model`/`train`（ultralytics・mlflow）
  - `summarize_session`/`review_annotation`/`nl_query_frames` の実呼び出し（`ANTHROPIC_API_KEY` 必須）
  - `experiments.list_runs`/`registry.*` の MLflow I/O（稼働中サーバ必須）

## 実行・検証
- `pytest tests/ -q`。ruff はゲート → 触ったファイルは `ruff check <file>` を通す。
- pytest 未導入の検証環境では、対象関数を直接 import して assert を回す簡易ランナーで代替確認できる（`pytest.raises` を使うテストは try/except に読み替える）。
- 新規テストは**依存ゼロで完結**させる。重い依存が要るならテストにせず、実機手順としてドキュメント化する。

## よくある追加・修正パターン
1. **新しいロジック関数を足したら同じ依存ゼロ方針でテストを追加**（`tests/test_phaseN.py` 慣習）。
2. **`DetectionRecord` のフィールド追加**（例: `tracker_id` を後方互換の既定 `None` で追加した）→ `FIELDS`/CSV ヘッダ期待値とテストを同時更新。
3. **決定的であること**: `train_val_split` 等は乱数非依存。テストも固定入力→固定出力で書く。
4. **境界・異常系を入れる**: 空入力（`summarize([])`/`select_low_confidence([])`）、しきい値境界、不正値（`normalize_stage("bogus")`→`ValueError`）。

## テスト仕様書の作成（`a_test_md_format.md`・SAE形式）
テストファイル（`tests/test_*.py`）のドキュメントを書く/最新化するときは、スキル同梱
`.claude/skills/ml-motion-tests/a_test_md_format.md` に従う。モジュール仕様（IPO）とは**観点・構成が異なる**ので混同しない。
- 中心構造は **SAE（Setup-Action-Expected）**＝「準備→実行→検証」。IPO 詳細・戻り値例・使用例ワークフローは**使わない**。
- タイトル: `# test_<module>.py - <対象説明> 単体テスト ドキュメント` → `**Version X.X** | 最終更新: YYYY-MM-DD`。
- 必須セクション順: 目次 → 概要（テーブル＋テスト方針）→ テスト対象の責務と境界 → テスト構成図(Mermaid)→ モック・フィクスチャ設計 → テストケース一覧（＋カバレッジマトリクス）→ テストケース詳細（SAEテーブル、`> 📝 **根拠**: <file> L番号`）→ 実行方法 → 変更履歴。
- フレームワークは `pytest`（このプロジェクトは重い依存を避けるため `unittest.mock` は基本不要。必要時のみ）。
- Mermaid は本リポジトリ共通の**黒背景・白文字**（`classDef default fill:#000,stroke:#fff,color:#fff` を末尾、全ノードに `class ... default`、全サブグラフに `style ... fill:#1a1a1a`）。sequenceDiagram は先頭に `%%{ init: ... }%%`。
- 所在: `docs/` 配下（既存配置に従う）。
- 整合: **実テストコードを読んで**、テストケース名・件数・カバレッジを突合する（数を盛らない）。
