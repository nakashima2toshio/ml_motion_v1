---
name: ml-motion-docs
description: >-
  Author or update Japanese module/page documentation for the ml_motion_v1
  project (Video ML Analytics Studio). Use when writing or modernizing docs
  under docs/*.md, when documenting the pipeline/ package (Detector,
  FrameProcessor, Tracker, ZoneAnalyzer, batch/export/benchmark/training), or
  the Streamlit pages under app/views/, when asked to follow
  `a_class_method_md_format.md` (modules/classes, IPO) or `a_pages_md_format.md`
  (Streamlit UI pages), or when adding Mermaid diagrams. Encodes the IPO doc
  format, the Streamlit page format, the mandatory black-background Mermaid
  style, and this project's tech-stack terminology.
---

# ml_motion_v1 ドキュメント作成スキル

Video ML Analytics Studio（`ml_motion_v1`）のモジュール／画面ドキュメントを、
プロジェクト規約どおりに作成・最新化するための知見。

## 0. どのフォーマット仕様を使うか（必ず先に判定）

対象によって**使う仕様書が異なる**。いずれもスキル同梱で、書く前に該当仕様を**実際に読むこと**。

| 対象 | 使う仕様書 | 中心構造 | 主なドキュメント所在 |
|------|-----------|---------|------------------|
| コード・モジュール（クラス/関数） | `.claude/skills/ml-motion-docs/a_class_method_md_format.md` | IPO（Input-Process-Output） | `docs/<topic>.md`（例 `docs/ml_motion_spec.md`） |
| Streamlit 画面・ページ | `.claude/skills/ml-motion-docs/a_pages_md_format.md` | 画面レイアウト＋セッション状態＋操作フロー | `docs/<page>.md`（`app/views/<page>.py` 対応） |
| 単体テスト | `.claude/skills/ml-motion-tests/a_test_md_format.md` | SAE（Setup-Action-Expected） | ml-motion-tests スキル参照 |

> テスト仕様（SAE）は **ml-motion-tests** スキルが担当。本スキルはモジュール（IPO）と画面（ページ）を担当する。

## 1. モジュール仕様（`a_class_method_md_format.md`・IPO形式）— 必読
- 仕様書はスキル同梱 `.claude/skills/ml-motion-docs/a_class_method_md_format.md`（IPO形式）。**先に読むこと**。
- タイトル: `# <module>.py - <説明> ドキュメント` → 次行 `**Version X.X** | 最終更新: YYYY-MM-DD`。
- 必須セクション順: 目次 → 概要（責務・対応モジュール表・主要機能一覧表）→ アーキテクチャ構成図(Mermaid 3層)→ モジュール構成図(Mermaid)→ クラス・関数一覧表 → IPO詳細（各要素に 概要/シグネチャ/パラメータ表/IPO表/戻り値例/使用例）→ 設定・定数 → 使用例 → エクスポート(`__all__`) → 変更履歴 → 付録(依存関係図)。
- 本プロジェクトの中心は `pipeline/` パッケージ。横断仕様は IPO を各クラスに委ね、本文はアーキテクチャ＋データフロー＋一覧に徹してよい（例: `docs/ml_motion_spec.md`）。

## 1B. 画面・ページ仕様（`a_pages_md_format.md`・Streamlit UI）— 必読
`app/views/*.py`（`st.navigation` で束ねる 解析/リアルタイム/実験管理/本番・最適化/アノテQA の各ページ）と
エントリ `app/Home.py` は IPO ではなく**画面特化フォーマット**を使う。
- 概要 → 画面レイアウト図(Mermaid)→ UIコンポーネント詳細（`st.file_uploader`/`st.selectbox`/`st.slider` 等を表で）→ セッション状態管理（`st.session_state` のキー例: `p1_result`/`p2_result`/`rt_running`/`mlflow_runs`）→ 操作フロー → 関数一覧 → 依存関係 → イベント処理 → エラーハンドリング(`st.error`/`st.warning`/`st.info`)→ 変更履歴。
- 実装整合: `st.session_state` のキー・各 `st.*` 呼び出しを**実コードと突合**する。

## 2. Mermaid 黒背景・白文字（`a_class_method_md_format.md` §16.5）— 必須
- flowchart/graph はブロック末尾に必ず:
  - `classDef default fill:#000,stroke:#fff,color:#fff`
  - `classDef subgraphStyle fill:#1a1a1a,stroke:#fff,color:#fff`
  - 全ノード `class <id,...> default`
  - 各サブグラフ `style <Subgraph> fill:#1a1a1a,stroke:#fff,color:#fff`
- sequenceDiagram は先頭に `%%{ init: { "theme":"base", "themeVariables": { ...黒テーマ... } } }%%` を付け、`classDef`/`class` は使わない。Note も `noteBkgColor:#000000`（`noteBkg` ではない）。
- ノードラベルの特殊文字はダブルクォートで囲む。バッククォート禁止。`<br>` は可。
- 検証(grep): `flowchart|graph` の数 == `classDef default fill:#000` の数、`sequenceDiagram` の数 == `%%{ init` の数。

## 3. 技術スタック表記の統一（本プロジェクト）
- **検出/セグ/追跡**: `ultralytics`(YOLO11 / YOLO11-seg) ＋ `supervision`（`BoxAnnotator`/`LabelAnnotator`/`MaskAnnotator`/`TraceAnnotator`/`ByteTrack`）。
- **デバイス**: PyTorch **MPS**（M2 Mac、CUDA 非対応）。`pipeline.device.get_device()` が `mps>cuda>cpu` を解決。
- **LLM/VLM**: **Anthropic Claude**、既定モデル **`claude-opus-4-8`**（`ANTHROPIC_MODEL` で上書き、鍵 `ANTHROPIC_API_KEY`）。Vision は base64 image ブロック、構造化出力は `output_config.format`（`messages.parse` も可）。`temperature`/`top_p`/`budget_tokens` は Opus 4.8 で使わない。
- **実験管理**: `mlflow`（docker-compose、既定 `http://localhost:5000`、`MLFLOW_PORT` で可変）。Model Registry ステージは `None/Staging/Production/Archived`。
- **Python**: 3.12（`requires-python = ">=3.12,<3.13"`）。
- 旧 grace 系の用語（Gemini 埋め込み / Qdrant / RAG / `ModelConfig` / `helper_llm` / chunking / qa_qdrant）は**本プロジェクトには存在しない**ので書かない。

## 4. 実装との整合（重要）
- 書く前に**対応ソースを実際に読む**。シグネチャ・既定値・`__all__`（`pipeline/__init__.py`）を突合。
- **遅延 import 設計**: `torch`/`cv2`/`ultralytics`/`supervision`/`mlflow`/`anthropic` はすべて関数・メソッド内で import する。`import pipeline` 自体はこれら未導入でも成功する、と明記する。
- 依存ゼロのロジック層（`detections`/`zones`/`camera`/`dataset`/`benchmark`/`batch`(filter/manifest)/`export_model`(format)/`claude_vision`(prompt)/`active_learning`/`registry`(stage)）は単体テスト可能、という設計を踏まえる。

## 5. ドキュメントの所在
- モジュール仕様（IPO）・横断仕様: リポジトリ直下 `docs/*.md`（例 `docs/ml_motion_spec.md`、設計リファレンスは `docs/ml_motion_detection_spec.md`）。
- 画面・ページ仕様: `docs/*.md`（`app/views/` 各ページ対応）。

## 6. 進め方のコツ
- 複数ファイルを最新化するときは **ファイルごとにサブエージェントを並列起動**（各に「使うフォーマット仕様のパス＋対象ソース＋黒背景Mermaid規約＋スタック表記」を渡す）。
- 仕上げに mermaid 準拠を grep 検証し、版・最終更新日・変更履歴を更新する。
