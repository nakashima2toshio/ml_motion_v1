# 📊 実験管理画面 操作マニュアル

**画面**: 左ナビ「実験管理」（`app/views/experiments.py`）。

## 目的
MLflow の **Run 一覧・メトリクス比較**、**転移学習ジョブの起動**、**data.yaml 生成**、**Model Registry** の確認を行う。

## 事前準備
- MLflow Tracking サーバを起動：
  ```zsh
  docker-compose -f docker-compose/docker-compose.yml up -d   # http://localhost:5000
  ```
- 接続先は `MLFLOW_TRACKING_URI`（既定 `http://localhost:5000`、`.env` の `MLFLOW_PORT` で変更可）。
- 学習には `data.yaml` と画像/ラベル（YOLO 形式）が必要。

## 画面の構成
| セクション | 項目 | 種類 | 既定 | 説明 |
|---|---|---|---|---|
| （上部） | MLflow Tracking URI | 表示 | — | 現在の接続先 |
| （上部） | 実験名 | 入力 | ml_motion_detection | 対象 experiment |
| Run 一覧・比較 | 🔄 MLflow から取得 | ボタン | — | Run 一覧を取得して表示 |
| 新規学習ジョブ | data.yaml パス | 入力 | data/datasets/custom/data.yaml | 学習データ定義 |
| 〃 | ベースモデル | 選択 | yolo11s | 検出/seg から選択 |
| 〃 | epochs | 数値 | 50 | 学習エポック |
| 〃 | Run 名（任意） | 入力 | 空 | MLflow の Run 名 |
| 〃 | ▶ 学習を開始 | ボタン | — | 転移学習を実行（重い） |
| データセット data.yaml 生成 | データセット名 / クラス / 生成 | 展開 | custom / person,car,… | data.yaml の雛形を表示 |
| Model Registry | （説明） | 表示 | — | ステージ None/Staging/Production/Archived |

## 操作手順

### A. Run を比較する
1. MLflow を起動しておく。
2. 実験名を確認（既定 `ml_motion_detection`）。
3. **🔄 MLflow から取得** を押す。
4. 表（run名 / status / mAP50 / mAP50-95）と **最良 Run** が表示される。

### B. 学習ジョブを実行する
1. 「データセット data.yaml 生成」を開き、クラスを入れて **data.yaml を生成** → 内容を確認し、実データに合わせて配置。
2. 「新規学習ジョブ」で **data.yaml パス / ベースモデル / epochs / Run名** を設定。
3. **▶ 学習を開始**。完了で `run_id` とメトリクス(JSON)が表示され、MLflow に記録される。

## 出力・結果の見方
- Run 表：各 Run の mAP50 / mAP50-95。複数回学習して**mAP の改善**を比較できる。
- 学習完了：`run_id` と検証メトリクス。詳細は MLflow UI（http://localhost:5000）でも確認。

## つまずきやすい点（トラブルシュート）
| 症状 | 対処 |
|---|---|
| 「MLflow へ接続できませんでした」 | `docker-compose ... up -d` で起動、URI/ポート（`MLFLOW_PORT`）を確認 |
| 「Run がありません」 | まず学習ジョブを実行するか、実験名を正しく指定 |
| 学習が極端に遅い/落ちる | M2 は軽量・短時間に留め、本格学習はクラウド GPU（仕様書 §1.2） |
| 学習エラー | `data.yaml` のパス・画像/ラベル配置（YOLO 形式）を確認 |
| ポート 5000 が別アプリと競合 | `.env` に `MLFLOW_PORT=5001` 等、`MLFLOW_TRACKING_URI` も更新（仕様書 §10） |
