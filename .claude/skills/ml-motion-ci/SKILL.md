---
name: ml-motion-ci
description: >-
  Work with branching, PR workflow, lint, and the dev environment in the
  ml_motion_v1 repo (Video ML Analytics Studio). Use when editing
  docker-compose, when ruff/lint blocks a change, when creating branches/PRs via
  the GitHub MCP tools, or when running the project locally. Encodes the ruff
  config, the lazy-import test/lint design, the docker-compose naming/port
  conventions, and the remote-environment/PR conventions.
---

# ml_motion_v1 CI・PR運用・環境スキル

Video ML Analytics Studio（`ml_motion_v1`）の lint / ブランチ・PR 運用 / ローカル実行のための知見。

## lint・コンパイル・テスト
- **lint**: `ruff check .`（`pyproject.toml` `[tool.ruff]` line-length=120 / target-version=`py312`）。触ったファイルは必ず緑にする。
- **compile**: `python -m py_compile pipeline/*.py app/Home.py app/views/*.py scripts/*.py main.py tests/*.py`。
- **import スモーク**: `python -c "import pipeline"`。重い依存（torch/cv2/ultralytics/supervision/mlflow/anthropic）が未導入の環境でも**成功するのが正**（全て遅延 import のため）。失敗したらモジュール先頭で重い import をしていないか疑う。
- **テスト**: `pytest tests/ -q`。依存ゼロのロジック層（`detections`/`zones`/`camera`/`dataset`/`benchmark`/`batch`/`export_model`/`claude_vision`/`active_learning`/`registry`）のみを対象にしており、torch 等が無くても通る。実映像・実 API・MLflow を要する処理は単体テストに含めない（実機確認）。
- pytest 未導入の検証環境では、テスト対象関数を直接 import してアサーションを回す簡易ランナーで代替確認できる（過去の作業実績）。

## 設計上の不変条件（壊さない）
- **遅延 import**: 重い依存はクラス生成時／関数内で import する。モジュール先頭 import に格上げしない。
- **依存ゼロ層を保つ**: エクスポート/集計/プロンプト構築/書式正規化/統計などのロジックは純 Python（標準ライブラリ＋既存の軽量依存）で実装し、テスト可能に保つ。重い処理（cv2 描画・YOLO 推論・mlflow I/O）と分離する。

## ブランチ・PR 運用
- 開発は指定の `claude/<topic>` ブランチ。**ドラフト PR で作成**し、確認後に Ready 化 → master へマージ（このリポジトリは auto-merge CI ワークフローは未設定なので、マージは明示操作）。
- 既にマージ済みのブランチに積み増さない。フォローアップは最新 master から作り直す（未マージの独自コミットがあれば rebase で温存）。
- GitHub 操作は **`mcp__github__*` MCP ツール**（`gh` CLI 不可）。ToolSearch で都度ロード。
- commit メッセージ末尾・PR 本文末尾に session リンクを付与（ハーネス規約）。PR は作成後ドラフトで、ユーザ確認不要。
- リモート Git プロキシは ref 削除を拒否することがある → ブランチ削除は GitHub UI かユーザのローカルで。

## docker-compose（MLflow）の衝突対策
- `docker-compose/docker-compose.yml` は **MLflow Tracking サーバ**のみ。Compose はディレクトリ名を既定プロジェクト名にするため、別アプリの `docker-compose/` と衝突する。回避策は実装済み:
  - top-level `name: ml_motion_v1`（v1 では `-p ml_motion_v1` か `COMPOSE_PROJECT_NAME`）。
  - `container_name: ml_motion_v1_mlflow`。
  - ホストポート `"${MLFLOW_PORT:-5000}:5000"`（`.env` の `MLFLOW_PORT` で変更、`MLFLOW_TRACKING_URI` も合わせる）。
- 詳細は `docs/ml_motion_detection_spec.md` §10。

## ローカル実行・リモート環境
- セットアップ: `uv venv --python 3.12 && uv pip install -e .`（ブラウザ webrtc は `.[realtime]`）。
- 起動: `streamlit run app/Home.py`（解析/リアルタイム/実験管理/本番・最適化/アノテQA）。MLflow は `docker-compose -f docker-compose/docker-compose.yml up -d`。
- リモート実行コンテナは ephemeral・起動時 fresh clone。**コミット＆プッシュしないと消える**。`data/*.mp4` 等の生成物・サンプルは Git 管理外（`scripts/fetch_sample_videos.sh` で取得）。

## PR アクティビティ購読
- `subscribe_pr_activity` で CI 失敗・レビューコメントを受信。CI 成功・新 push・コンフリクト遷移は webhook で来ないため、必要なら自己チェックインを再アーム（このサンドボックスでは `send_later` 不在のことが多く、`ScheduleWakeup` 等で代替）。
