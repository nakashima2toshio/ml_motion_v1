# Video ML Analytics Studio (ml_motion_v1)

動画ML解析プラットフォーム。mp4 / iPhone リアルタイム映像 → 物体検出・セグメンテーション・トラッキング → ゾーン解析 → Claude Vision による要約・アノテーション補助。MLflow で実験管理し、Fine-tuning したモデルをバージョン管理して本番推論パイプラインへ載せる。

- 設計の全体像・開発計画は [`docs/ml_motion_detection_spec.md`](docs/ml_motion_detection_spec.md) を参照。
- 対象: MacBook Air M2（MPS バックエンド）/ Python 3.11 / PyCharm Pro。

## Phase 0（基盤構築）

環境とリポジトリ骨格を用意するフェーズ。完了判定は **`torch.backends.mps.is_available() == True`** と **MLflow UI の起動**。

### ディレクトリ構成

```
ml_motion_v1/
├── app/                  # Streamlit マルチページ UI
│   ├── Home.py           #   エントリポイント（st.navigation）
│   └── views/            #   解析 / 実験管理 / アノテQA の各ページ
├── pipeline/             # 推論パイプライン（Phase 0: デバイス選択ユーティリティ）
├── scripts/              # 補助スクリプト（check_mps.py 等）
├── models/               # モデル重み・変換成果物（git 管理外）
├── data/                 # サンプル動画・データセット（git 管理外）
├── experiments/          # MLflow の DB・アーティファクト（git 管理外）
├── docker-compose/       # MLflow Tracking サーバ
└── docs/                 # 仕様書
```

### セットアップ

```bash
# 1. Python 3.11 環境を用意して依存をインストール（uv 推奨）
uv venv --python 3.11
uv pip install -e .
# もしくは: pip install -e .

# 2. 環境変数を設定
cp .env.example .env
#   .env を編集して ANTHROPIC_API_KEY を設定

# 3. MPS 動作確認（Phase 0 完了判定）
python scripts/check_mps.py

# 4. Streamlit UI の起動（解析 / 実験管理 / アノテQA の3ページ雛形）
streamlit run app/Home.py

# 5. MLflow Tracking サーバの起動（http://localhost:5000）
docker-compose -f docker-compose/docker-compose.yml up -d
```

### Phase 0 完了判定

| 項目 | 確認方法 |
|---|---|
| MPS 利用可能（M2 Mac） | `python scripts/check_mps.py` → `✅ Phase 0 完了判定: ... == True` |
| Streamlit 雛形起動 | `streamlit run app/Home.py` で3ページが表示される |
| MLflow UI 起動 | `docker-compose ... up -d` 後 http://localhost:5000 が開く |

> 注: MPS は Apple Silicon（M2 Mac）でのみ利用可能。CUDA / CPU 環境ではスクリプトは
> 選択デバイスで疎通確認のみ行い、Phase 0 の MPS 判定は M2 Mac 上で再実行する。

## 以降の Phase

| Phase | ゴール |
|---|---|
| P1 | 検出 MVP（mp4 → YOLO11 → 注釈付き動画/CSV） |
| P2 | セグメンテーション ＋ トラッキング ＋ ゾーン解析 |
| P3 | リアルタイム（iPhone / Continuity Camera） |
| P4 | 学習・実験管理（Fine-tuning / MLflow / Model Registry） |
| P5 | 本番化・最適化（バッチ推論 / CoreML・ONNX / 量子化） |
| P6 | 高度化（Claude による NL 要約・検索・アノテ自動レビュー） |

詳細な TODO は仕様書 §5 を参照。
