# Video ML Analytics Studio 操作マニュアル

アプリの**画面単位**の操作手順書です。設計・仕様は [`docs/ml_motion_detection_spec.md`](../ml_motion_detection_spec.md)、
クラス仕様は [`docs/ml_motion_spec.md`](../ml_motion_spec.md) を参照してください。

## 起動方法

UI は **React 版（推奨）** と **Streamlit 版（従来）** の 2 種類があります。
機能は同じで、どちらも同じ `pipeline/` を使います。

```zsh
# 1. セットアップ（初回のみ）
uv venv --python 3.12 && source .venv/bin/activate && uv pip install -e .
cp .env.example .env          # ANTHROPIC_API_KEY を設定（アノテQA / NL要約で使用）
cd frontend && npm install && cd ..   # React 版のみ

# 2-A. React 版（推奨）: backend :8000 + frontend :5173 を同時起動
./run_dev.sh                  # ブラウザで http://localhost:5173

# 2-B. Streamlit 版（従来）
streamlit run app/Home.py     # ブラウザで http://localhost:8501 が開く
```

左サイドバーの**ページナビ**でページを切り替えて各機能を使います。

| ナビ | 画面 | 主な用途 | マニュアル |
|---|---|---|---|
| 🎥 解析 | メイン解析 | mp4 の検出／セグ／追跡／ゾーン解析・エクスポート | [01_analyze.md](01_analyze.md) |
| 📡 リアルタイム | リアルタイム | iPhone/カメラの準リアルタイム検出 | [02_realtime.md](02_realtime.md) |
| 📊 実験管理 | 実験・モデル管理 | MLflow Run 比較・学習ジョブ・Registry | [03_experiments.md](03_experiments.md) |
| ⚙️ 本番/最適化 | 本番化・最適化 | バッチ推論・変換/量子化・計測 | [04_production.md](04_production.md) |
| 🏷 アノテーションQA | アノテ品質 | Claude Vision でラベル妥当性レビュー | [05_annotation_qa.md](05_annotation_qa.md) |

React 版の API ドキュメント（自動生成）は http://localhost:8000/docs で見られます。
既知の不具合は [`docs/known_issues.md`](../known_issues.md) にまとめています。

## 共通の見方

- **どの画面にも上部にデバイス表示**があります（解析/リアルタイム/本番）。
  - `Device`: 実行デバイス（`MPS`/`CUDA`/`CPU`）。M2 Mac は `MPS`。
  - `torch` / `MPS` / `CUDA`: 導入状況（✅＝利用可）。
- 重い処理（検出・学習・変換）は**初回にモデル重み（例 `yolo11s.pt`）を自動ダウンロード**します（ネット接続が必要）。

## 事前準備チェックリスト

| 使う画面 | 必要なもの |
|---|---|
| 解析 / リアルタイム | 動画 or カメラ（動画は `./scripts/fetch_sample_videos.sh` 等で取得 → [`data/README.md`](../../data/README.md)） |
| 実験管理 | MLflow 起動：`docker-compose -f docker-compose/docker-compose.yml up -d`（http://localhost:5000） |
| アノテQA / 解析のNL要約 | `.env` の `ANTHROPIC_API_KEY` |
| リアルタイム（ブラウザ経路） | `uv pip install -e '.[realtime]'`（streamlit-webrtc / av） |
