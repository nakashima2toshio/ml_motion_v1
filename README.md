# Video ML Analytics Studio (ml_motion_v1)

動画ML解析プラットフォーム。mp4 / iPhone リアルタイム映像 → 物体検出・セグメンテーション・トラッキング → ゾーン解析 → Claude Vision による要約・アノテーション補助。MLflow で実験管理し、Fine-tuning したモデルをバージョン管理して本番推論パイプラインへ載せる。

- 設計の全体像・開発計画は [`docs/ml_motion_detection_spec.md`](docs/ml_motion_detection_spec.md) を参照。
- 対象: MacBook Air M2（MPS バックエンド）/ Python 3.12 / PyCharm Pro。

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
# 1. Python 3.12 環境を用意して依存をインストール（uv 推奨）
uv venv --python 3.12
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

> 別アプリでも `docker-compose/` を使っていてプロジェクト名やポート 5000 が衝突する場合は、
> 仕様書 [§10 docker-compose の名前/ポート衝突対策](docs/ml_motion_detection_spec.md) を参照
> （本リポジトリは `name: ml_motion_v1` 固定・`MLFLOW_PORT` で可変）。

### Phase 0 完了判定

| 項目 | 確認方法 |
|---|---|
| MPS 利用可能（M2 Mac） | `python scripts/check_mps.py` → `✅ Phase 0 完了判定: ... == True` |
| Streamlit 雛形起動 | `streamlit run app/Home.py` で3ページが表示される |
| MLflow UI 起動 | `docker-compose ... up -d` 後 http://localhost:5000 が開く |

> 注: MPS は Apple Silicon（M2 Mac）でのみ利用可能。CUDA / CPU 環境ではスクリプトは
> 選択デバイスで疎通確認のみ行い、Phase 0 の MPS 判定は M2 Mac 上で再実行する。

## Phase 1（検出 MVP / mp4）

mp4 をアップロードして YOLO11 で物体検出し、注釈付き動画と検出結果（CSV/JSON）を出力する。

```bash
streamlit run app/Home.py     # 「解析」ページで mp4 をアップロード → ▶ Run 検出
```

- サイドバー: モデル（yolo11n/s/m）、信頼度しきい値、対象クラス（COCO 代表 / 全クラス）、フレーム間引き。
- 出力: 注釈付き動画（bbox + ラベル）、クラス別集計、検出テーブル、CSV / JSON ダウンロード。
- 実装: `pipeline/detector.py`（YOLO11 ラッパー）、`pipeline/video.py`（フレーム抽出・描画・書き出し）、
  `pipeline/detections.py`（レコード・集計・エクスポート、依存ゼロでテスト可能）。

```bash
# 単体テスト（エクスポート/集計ロジック）
pytest tests/ -q
```

> 注: YOLO11 の重み（`yolo11s.pt` 等）は初回 `Detector` 生成時に ultralytics が自動ダウンロードする。
> 注釈付き動画はコーデック（avc1→mp4v フォールバック）依存でブラウザ再生できない場合があるため、
> ダウンロードボタンも用意している。

## Phase 2（セグメンテーション ＋ トラッキング ＋ ゾーン解析）

検出に加えてマスク描画・ID 付与（軌跡）・ゾーン別の滞留時間/侵入イベントを集計する。
「解析」ページのサイドバー「タスク」で有効化する。

- **セグメンテーション**: `YOLO11-seg`（`yolo11*-seg.pt`）でマスク生成・`MaskAnnotator` 描画。
- **トラッキング**: `ByteTrack`（supervision）で `tracker_id` 付与、`TraceAnnotator` で軌跡描画。
- **ゾーン解析**: 正規化座標(0〜1)の多角形を JSON で定義。ID ごとの滞留時間・侵入回数・最大同時数を集計。
- 実装: `pipeline/tracking.py`（ByteTrack ラッパー）、`pipeline/zones.py`（点-多角形判定・滞留/侵入、**依存ゼロでテスト可能**）、
  `pipeline/video.py` の `process_tracking_video()`。
- CSV/JSON には `tracker_id` 列を追加。完了判定（仕様書 §5）「人物に ID 付与＋ゾーン滞留時間が出る」に対応。

```bash
pytest tests/ -q     # detections + zones の単体テスト（計 11 件）
```

> ゾーン定義はサイドバーの JSON で編集（既定例つき）。GUI 描画(streamlit-drawable-canvas)は将来拡張。

## Phase 3（リアルタイム / iPhone・Continuity Camera）

「リアルタイム」ページで iPhone 映像を準リアルタイム検出する。取り込みは 2 経路。

1. **Continuity Camera（OpenCV / 最推奨）**: iPhone を Mac のカメラとして認識させ、カメラ index で取り込む。
   ローカル実行（Mac 上の `streamlit run`）でのみ動作。
2. **ブラウザ（streamlit-webrtc / 代替）**: ブラウザのカメラを使う。追加依存が必要。

```bash
uv pip install -e '.[realtime]'   # ブラウザ経路（streamlit-webrtc, av）を使う場合のみ
streamlit run app/Home.py          # 「リアルタイム」ページ
```

- **スループット最適化**: 解像度プリセット（640×360〜1280×720）、フレームスキップ、
  リアルタイム時の**軽量モデル自動切替**（重いモデル→`yolo11s`）。FPS をライブ表示。
- 実装: `pipeline/camera.py`（`FpsMeter`・解像度プリセット・モデル切替、**依存ゼロでテスト可能**）、
  `pipeline/realtime.py`（`FrameProcessor`：1 フレーム処理をバッチ/リアルタイムで共通化）。
- リファクタ: `video.py` の `process_tracking_video` も `FrameProcessor` を使う形に統一。
- 完了判定（仕様書 §5）「iPhone 映像で準リアルタイム検出（≥10fps）」に対応（実機計測は M2 Mac で）。

```bash
pytest tests/ -q     # detections + zones + camera の単体テスト（計 19 件）
```

## Phase 4（学習・実験管理 / MLflow・Model Registry）

COCO 事前学習からの転移学習・Fine-tuning を行い、ハイパラ/メトリクス/成果物を MLflow に記録、
Model Registry でステージ管理する。「実験管理」ページから操作する。

```bash
docker-compose -f docker-compose/docker-compose.yml up -d   # MLflow 起動（http://localhost:5000）
streamlit run app/Home.py                                    # 「実験管理」ページ
```

- **データセット設計**: `pipeline/dataset.py`（`DatasetSpec`・YOLO `data.yaml` 生成・決定的 train/val 分割）。
- **転移学習**: `pipeline/training.py`（`TrainConfig`/`train()`、ultralytics 学習＋MLflow ログ）。M2 は軽量・短時間、本格学習はクラウド GPU 推奨（仕様書 §1.2）。
- **実験照会**: `pipeline/experiments.py`（Run 一覧取得・mAP 比較・最良 Run 選択）。
- **Model Registry**: `pipeline/registry.py`（`register_model`/`transition_stage`、`None/Staging/Production/Archived`）。
- 依存ゼロのロジック（data.yaml 生成・分割・Run 整形・ステージ正規化）は単体テスト化。

```bash
pytest tests/ -q     # detections + zones + camera + phase4 の単体テスト（計 32 件）
```

> 完了判定（仕様書 §5）「自前データで mAP 改善を Run 比較で確認」→ 学習ジョブを複数回回し、実験管理ページの Run 比較で mAP 向上を確認。

## Phase 5（本番化・最適化）

ディレクトリ一括のバッチ推論、モデル変換（ONNX/CoreML/TorchScript）・量子化（FP16/INT8）、
レイテンシ/スループット計測、Registry からのモデル取得・差し替え。「本番/最適化」ページで操作する。

- **バッチ推論**: `pipeline/batch.py`（`discover_media`/`run_batch`/`build_manifest`、選別・整形は依存ゼロ）。
- **変換・量子化**: `pipeline/export_model.py`（`export_model`、`EXPORT_FORMATS`/`normalize_format` は依存ゼロ）。M2 は CoreML が有効。
- **レイテンシ計測**: `pipeline/benchmark.py`（`LatencyStats`：mean/p50/p95/fps、warmup 除外。依存ゼロでテスト可能）。
- **モデル差し替え**: `pipeline/registry.py` の `model_uri`/`download_model` で Registry のステージ別モデルを取得。

```bash
pytest tests/ -q     # detections + zones + camera + phase4 + phase5（計 44 件）
```

> 完了判定（仕様書 §5）「バッチ処理が回り、推論レイテンシ低減を計測」→ バッチ実行 + 変換前後を `LatencyStats` で比較。

## Phase 6（高度化 / Claude Vision）

Claude API（Opus 4.8, Vision）で差別化機能を提供する（仕様書 §7）。

- **NL サマリ**: 検出・ゾーン結果を自然言語要約（「解析」ページの「📝 NL要約」）。
- **アノテーション自動レビュー**: フレーム画像＋提案ラベルを Claude Vision に渡して妥当性チェック（「アノテーションQA」ページ）。
- **自然言語検索**: 「赤い服の人を探す」等のクエリ → 該当フレーム抽出（`nl_query_frames`、構造化出力）。
- **Active Learning**: 低確信フレームを抽出して再学習候補に（`select_low_confidence`）。
- 実装: `pipeline/claude_vision.py`（既定モデル `claude-opus-4-8`、`anthropic` 遅延 import、プロンプト構築は依存ゼロでテスト可能）、`pipeline/active_learning.py`。

```bash
cp .env.example .env   # ANTHROPIC_API_KEY を設定
pytest tests/ -q       # 全フェーズの単体テスト（計 57 件）
```

> 完了判定（仕様書 §5）「『赤い服の人を探す』等の NL クエリが動く」→ `nl_query_frames` がフレーム一覧に対し該当番号を返す。

## 実装済み Phase 一覧

| Phase | ゴール |
|---|---|
| ~~P0~~ | ~~基盤構築（MPS / Streamlit / MLflow / ディレクトリ）~~ ✅ |
| ~~P1~~ | ~~検出 MVP（mp4 → YOLO11 → 注釈付き動画/CSV）~~ ✅ |
| ~~P2~~ | ~~セグメンテーション ＋ トラッキング ＋ ゾーン解析~~ ✅ |
| ~~P3~~ | ~~リアルタイム（iPhone / Continuity Camera）~~ ✅ |
| ~~P4~~ | ~~学習・実験管理（Fine-tuning / MLflow / Model Registry）~~ ✅ |
| ~~P5~~ | ~~本番化・最適化（バッチ推論 / CoreML・ONNX / 量子化）~~ ✅ |
| ~~P6~~ | ~~高度化（Claude による NL 要約・検索・アノテ自動レビュー）~~ ✅ |
| P4 | 学習・実験管理（Fine-tuning / MLflow / Model Registry） |
| P5 | 本番化・最適化（バッチ推論 / CoreML・ONNX / 量子化） |
| P6 | 高度化（Claude による NL 要約・検索・アノテ自動レビュー） |

詳細な TODO は仕様書 §5 を参照。
