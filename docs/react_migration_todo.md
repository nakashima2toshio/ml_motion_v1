# Streamlit → React 移行 TODO（Video ML Analytics Studio）

`app/Home.py` を起点とする Streamlit マルチページ UI を、**機能はそのまま**に
**Vite + React 18 + TypeScript** の SPA へ置き換えるための調査結果と作業計画。

- 対象: `app/Home.py` + `app/views/*.py`（解析 / リアルタイム / 実験管理 / 本番・最適化 / アノテQA）
- 非対象: `pipeline/` の推論・解析ロジック（**一切変更しない**。API から呼ぶだけ）
- 参照実装: `grace_v2`（FastAPI `backend/app/` + Vite/React/TS `frontend/` + SSE ジョブ基盤）

---

## 1. 現状の調査結果

### 1.1 現行 UI の構造

| ファイル | 行数 | 役割 |
|---|---|---|
| `app/Home.py` | 35 | `st.set_page_config` ＋ `st.navigation` / `st.Page` によるナビだけ。**画面ロジックは持たない** |
| `app/views/analyze.py` | 231 | mp4 アップロード → 検出/セグ/追跡/ゾーン → 動画プレビュー・統計・テーブル・CSV/JSON/mp4 DL・Claude NL要約 |
| `app/views/realtime.py` | 160 | 経路1: Continuity Camera（サーバ側 OpenCV ループ）／経路2: `streamlit-webrtc`（ブラウザカメラ） |
| `app/views/experiments.py` | 101 | MLflow Run 一覧・最良 Run、転移学習ジョブ起動、`data.yaml` 生成、Model Registry 説明 |
| `app/views/production.py` | 88 | バッチ推論、モデル変換/量子化、レイテンシ計測（説明のみ）、Registry URI 表示 |
| `app/views/annotation_qa.py` | 38 | 画像アップロード → Claude Vision でアノテーション妥当性レビュー |

**重要**: `Home.py` 単体を React 化しても意味はない（ナビの器でしかない）。
「Home.py の React 化」＝**5 画面ぶんの Streamlit ランタイムを剥がし、React シェル＋ページに置き換える**こと。

### 1.2 Streamlit に強く依存している点（＝移行の設計論点）

| # | 依存 | 現行の実装 | React 化での扱い |
|---|---|---|---|
| A | 実行モデル | 「操作のたびにスクリプト全体を再実行」 | クライアント state ＋ REST/SSE の明示的呼び出しへ |
| B | サーバ状態 | `st.session_state["p2_result"]`（`DetectionRecord` オブジェクトをそのまま保持） | サーバ側ジョブ結果（job_id で参照）＋ JSON シリアライズ |
| C | モデルキャッシュ | `@st.cache_resource` で `Detector` / `FrameProcessor` を保持 | バックエンドのプロセス内 LRU キャッシュ（キー: model/device/conf/classes） |
| D | 進捗表示 | `st.progress` ＋ `progress_cb(cur, total)` | ジョブ＋**SSE** で `progress` イベント配信 |
| E | ファイル入出力 | `st.file_uploader` / `st.download_button`（bytes 直渡し） | multipart upload ＋ ダウンロード用エンドポイント |
| F | 動画プレビュー | `st.video(path)` | `<video>` ＋ Range 対応の静的配信（`StaticFiles`） |
| G | リアルタイム | `while st.session_state[...]` の**サーバ側 while ループ**で `st.image` を差し替え | MJPEG（`multipart/x-mixed-replace`）または WebSocket 配信へ置換 |
| H | ブラウザカメラ | `streamlit-webrtc`（Streamlit 専用） | `getUserMedia` ＋ WebSocket でフレーム往復（`streamlit-webrtc`/`av` 依存は不要になる） |
| I | 表示部品 | `st.dataframe` / `st.metric` / `st.form` / `st.expander` | 自前の React コンポーネント（表・メトリクス・アコーディオン） |

### 1.3 使える資産

- `pipeline/` は**遅延 import 設計**で、集計・エクスポート・ゾーン・プロンプト構築は依存ゼロの純 Python。
  → **API 層から素直に呼べる**。`to_csv_bytes` / `to_json_bytes` / `summarize` / `format_runs_table` はそのまま再利用。
- `progress_cb(cur, total)` が `process_tracking_video` / `run_batch` に既にある → SSE 進捗にそのまま接続できる。
- `grace_v2` に FastAPI ＋ SSE ジョブ基盤（`backend/app/core/jobs.py`）と React クライアント（`frontend/src/api/client.ts`, `state/jobReducer.ts`）の実績あり。**構成・命名を踏襲**する。
- 画面ごとの操作マニュアル `docs/manual/01〜05` が**そのまま受け入れ基準**として使える。

### 1.4 現状の欠落

- HTTP API・フロントエンドのビルド基盤が**まったく無い**（`fastapi` / `uvicorn` / `npm` の痕跡ゼロ）。
- `pyproject.toml` の依存に `streamlit` はあるが Web API 系は無し。`packages = ["pipeline"]`。
- CI ワークフローは未設定（lint/pytest はローカル実行）。フロント用ゲートも当然無い。

---

## 2. 目標アーキテクチャ

```
ブラウザ ── React SPA (Vite, :5173)
              │  REST(JSON) / multipart / SSE / WebSocket
              ▼
        FastAPI (backend/app, :8000)
              │  直接呼び出し（変更しない）
              ▼
        pipeline/  (detector, video, zones, realtime, batch, experiments, registry, claude_vision)
```

```
backend/
  app/
    main.py            # FastAPI アプリ・CORS(5173)・ルータ登録
    schemas.py         # Pydantic モデル（リクエスト/レスポンス）
    api/
      meta.py          # デバイス・モデル一覧・クラス一覧・定数
      analyze.py       # アップロード・解析ジョブ・SSE・結果・DL・NL要約
      realtime.py      # カメラ列挙・MJPEG ストリーム・WS 推論
      experiments.py   # MLflow Run・学習ジョブ・data.yaml
      production.py    # バッチ・変換/量子化・Registry URI
      annotation.py    # Claude Vision レビュー
    core/
      jobs.py          # インメモリ・ジョブ管理＋SSE イベント（grace_v2 踏襲）
      detector_cache.py# @st.cache_resource 代替
      storage.py       # 作業ディレクトリ・成果物パス管理
  tests/               # 重い依存なしで通る pytest
frontend/
  src/
    App.tsx            # ← 旧 app/Home.py（ナビ・タイトル・レイアウト）
    pages/AnalyzePage.tsx / RealtimePage.tsx / ExperimentsPage.tsx /
          ProductionPage.tsx / AnnotationQaPage.tsx
    components/        # DataTable, Metric, DeviceBar, ProgressBar, ZoneEditor ...
    api/client.ts      # fetch ラッパ・SSE 購読
    state/             # jobReducer 等（テスト対象）
    types.ts           # バックエンド schemas と 1:1
```

### API 一覧（案）

| メソッド | パス | 対応する現行 UI |
|---|---|---|
| GET | `/api/meta/device` | 各画面上部の Device / torch / MPS / CUDA メトリクス |
| GET | `/api/meta/options` | `AVAILABLE_MODELS` / `SEG_MODELS` / `COCO_COMMON` / `RESOLUTION_PRESETS` / `EXPORT_FORMATS` / `STAGES` |
| POST | `/api/analyze/upload` | `st.file_uploader`（mp4/mov/avi） |
| POST | `/api/analyze/run` | 「▶ Run 解析」→ 202 + job_id |
| GET | `/api/analyze/stream/{job_id}` | `st.progress`（SSE: progress / done / error） |
| GET | `/api/analyze/result/{job_id}` | 結果ペイン・ゾーン解析・検出テーブル |
| GET | `/api/analyze/download/{job_id}/{kind}` | ⬇ CSV / ⬇ JSON / ⬇ 注釈付き動画 |
| GET | `/media/{job_id}/annotated.mp4` | `st.video`（Range 対応の静的配信） |
| POST | `/api/analyze/summary/{job_id}` | 📝 NL要約（Claude） |
| GET | `/api/realtime/mjpeg` | 経路1: Continuity Camera のライブ表示 |
| WS | `/api/realtime/ws` | 経路2: ブラウザカメラ（`streamlit-webrtc` 置換） |
| GET | `/api/experiments/runs` | 🔄 MLflow から取得・最良 Run |
| POST | `/api/experiments/train` | ▶ 学習を開始（ジョブ化） |
| POST | `/api/experiments/dataset-yaml` | data.yaml 生成 |
| POST | `/api/production/discover` | 📁 入力ディレクトリを確認 |
| POST | `/api/production/batch` | ▶ バッチ実行（ジョブ化＋SSE） |
| POST | `/api/production/export` | 🛠 変換を実行 |
| GET | `/api/production/registry-uri` | Registry URI 表示 |
| POST | `/api/annotation/review` | 🔍 Claude でレビュー（画像 multipart） |

---

## 3. TODO（フェーズ別）

### R0. 基盤（バックエンド骨組み＋React シェル）✅ 完了
- [x] `pyproject.toml` に `fastapi` / `uvicorn[standard]` / `python-multipart` を追加、`packages` に `backend` を追加
- [x] `backend/app/main.py`：FastAPI 生成・CORS（`http://localhost:5173`）・`load_dotenv()`・ルータ登録・`GET /api/health`
- [x] `backend/app/core/jobs.py`：`grace_v2` の JobManager を移植（スレッド実行・イベント蓄積・リプレイ可能な SSE・完了ジョブ上限）
      ／ `Job.progress(cur, total)` が `pipeline` の `progress_cb` にそのまま渡せる
- [x] `backend/app/core/detector_cache.py`：`(model_name, device, conf, classes)` キーの `Detector` / `FrameProcessor` キャッシュ（`@st.cache_resource` 代替・LRU 2 件）
- [x] `backend/app/api/meta.py`：`/device`・`/options`（`describe_device()` と各定数をそのまま返す）
- [x] `frontend/` scaffold：Vite + React 18 + TS（`dev` / `build` / `lint`(tsc --noEmit) / `test`(vitest)）＋ `/api`・`/media` の dev プロキシ
- [x] `frontend/src/App.tsx` ＋ `src/nav.ts`：**旧 `app/Home.py` 相当**（タイトル・5 ページのナビ・既定は「解析」）
- [x] `frontend/src/api/client.ts` / `types.ts` / `components/DeviceBar.tsx` / `components/PagePlaceholder.tsx`
- [x] `run_dev.sh`：backend(:8000) ＋ frontend(:5173) 同時起動
- [x] テスト：`backend/tests/`（meta API・ジョブ基盤・Detector キャッシュ）＋ `frontend`（nav・エラー整形）
- [x] CI に `frontend`（tsc + vitest + build）ジョブを追加し、`auto-merge` を `[build, frontend]` に依存させる

> R0 時点では 5 画面すべてがプレースホルダ。**実機能は Streamlit 版（`streamlit run app/Home.py`）が引き続き担当**する。

### R1. 解析画面（`views/analyze.py` → `AnalyzePage.tsx`）✅ 完了
- [x] `POST /api/analyze/upload`：mp4/mov/avi をストリーミング保存し `upload_id` を返す（拡張子・サイズ上限・ファイル名サニタイズ）
- [x] `POST /api/analyze/run`：`enable_seg` / `enable_track` / `enable_zone` / `model_name` / `conf` / `classes` / `frame_stride` / `trace_length` / `zones` を受け、`process_tracking_video` をジョブ実行
- [x] `progress_cb` → SSE `progress {current,total}`、完了時 `done`、例外は `error`（現行のエラーメッセージ文言を踏襲）
- [x] `GET /api/analyze/result/{job_id}`：`summarize()`・`zone_summary`・`per_track_dwell`・`frames_processed/total`（**検出レコードは含めない**）
- [x] `GET /api/analyze/detections/{job_id}`：検出結果テーブルを 1000 件ずつページング（全件は CSV/JSON へ誘導）
- [x] ダウンロード 3 種（`to_csv_bytes` / `to_json_bytes` / 注釈付き mp4）＋ `Content-Disposition` のファイル名を現行と一致させる
- [x] 注釈付き動画の Range 対応配信（`/media/{run_id}/{filename}`）＋ 再生不可時の DL 誘導キャプション
- [x] `POST /api/analyze/summary/{job_id}`：`summarize_session()`（`ANTHROPIC_API_KEY` 未設定時のエラー文言を踏襲）
- [x] React 側：設定パネル — **セグ ON でモデル一覧を `-seg` に切替**、**追跡 OFF でゾーン解析を disabled**、**全クラス ON でクラス選択を disabled** の連動を再現（`state/analyzeSettings.ts`）
- [x] React 側：ゾーン定義エディタ（JSON テキスト＋クライアント側バリデーション）
- [x] React 側：メトリクス（総検出数 / ユニークID数 / 処理フレーム）・クラス別表・ゾーン解析表・ID別滞留表・検出結果テーブル（ページング）
- [x] 受け入れ基準：`docs/manual/01_analyze.md` の「操作手順」「出力・結果の見方」を実動画（YOLO11n）で確認

> 検出結果テーブルは既定 1000 件ずつのページング。全件はブラウザを固めるため
> **CSV / JSON のダウンロードへ誘導**する（`DEFAULT_PAGE_SIZE` / `MAX_PAGE_SIZE`）。

### R2. アノテーションQA（`views/annotation_qa.py` → `AnnotationQaPage.tsx`）✅ 完了
- [x] `POST /api/annotation/review`：画像 multipart ＋ `labels`（カンマ区切り）→ `review_annotation()` の Markdown を返す
      （画像は保存せずメモリで処理。拡張子・サイズ上限 5 MB・ラベル正規化を検証）
- [x] `GET /api/meta/options` に `claude_model` を追加（実行前にモデル名を表示するため）
- [x] React 側：画像プレビュー・ラベル入力・レビュー実行・Markdown レンダリング
      （`grace_v2` の `markdown/parseMarkdown.ts` + `components/Markdown.tsx` を移植）
- [x] 受け入れ基準：`docs/manual/05_annotation_qa.md`（成功時の Markdown 描画・`ANTHROPIC_API_KEY` 未設定時の案内をブラウザで確認）

### R3. 実験管理（`views/experiments.py` → `ExperimentsPage.tsx`）✅ 完了
- [x] `GET /api/experiments/config`：Tracking URI・既定実験名
- [x] `GET /api/experiments/runs?experiment=`：`list_runs` / `format_runs_table` / `best_run`、MLflow 未起動時は 503 ＋ docker-compose 起動案内
- [x] **MLflow への疎通確認（`core/mlflow_probe.py`）**：MLflow クライアントは接続失敗時に約 4 分リトライするため、
      先に 3 秒で疎通を確認して落ちていれば即 503 を返す（実測 4分6秒 → 0.016 秒）
- [x] `POST /api/experiments/train`：`TrainConfig` → ジョブ実行（長時間・高負荷の警告文言は API/UI 双方に残す）＋ SSE
- [x] `POST /api/experiments/dataset-yaml`：`build_dataset_yaml`（コードブロック表示・クラス順＝クラス ID）
- [x] React 側：Run 表・最良 Run バッジ・学習フォーム・`data.yaml` 生成・Registry 説明（「Claude自動レビュー(P6)」は現行どおり disabled）
- [x] 受け入れ基準：`docs/manual/03_experiments.md`（実 MLflow サーバに実 Run を登録して確認）

> ℹ️ 移行中に見つかった `pipeline/` 側の不具合（MLflow のメトリクス名に括弧が使えず
> mAP 列が常に 0.0 になる）は**修正済み**。詳細は `docs/known_issues.md` #1。

### R4. 本番/最適化（`views/production.py` → `ProductionPage.tsx`）✅ 完了
- [x] **`core/paths.py`（パストラバーサル対策）**：ユーザー入力のパスを**リポジトリルート配下に限定**し、
      外を指したら 400。シンボリックリンク経由の抜け道も実パスで判定して塞ぐ。
      リポジトリ外を使いたい場合は環境変数 `ML_MOTION_ALLOWED_ROOTS`（`os.pathsep` 区切り）で追加できる
- [x] `POST /api/production/discover`：`discover_media`（結果はリポジトリ相対で返す＝絶対パスを画面に出さない）
- [x] `POST /api/production/batch`：`run_batch` をジョブ実行＋SSE 進捗（ファイル単位）、完了時 `build_manifest`
- [x] `POST /api/production/export`：`export_model`（fmt / FP32・FP16・INT8）
- [x] `GET /api/production/registry-uri`：`model_uri(name, stage)`（ステージ名の正規化はサーバ側に集約）
- [x] React 側：入出力ディレクトリ・モデル/信頼度/間引き・マニフェスト表・変換フォーム・計測の説明ブロック
- [x] 受け入れ基準：`docs/manual/04_production.md`（実 YOLO11n で動画 2 本のバッチ推論を通して確認）

### R5. リアルタイム（`views/realtime.py` → `RealtimePage.tsx`）✅ 完了
- [x] 経路1（Continuity Camera）：`GET /api/realtime/mjpeg?...` で `open_camera` → `FrameProcessor.process` → JPEG エンコード → `multipart/x-mixed-replace` 配信。`<img src>` で表示
  - [x] 開始/停止（配信終了・`POST /stop` でカメラ解放。**多重オープンは 409 で排他**）
  - [x] `frame_skip` / 解像度プリセット / 軽量モデル自動切替（`recommend_realtime_model`）の再現
  - [x] FPS・検出数は `GET /api/realtime/stats` を 1 秒ごとにポーリングして表示（`FpsMeter` はサーバ側）
  - [x] 「バックエンドを動かしている Mac のカメラを使う」という制約表示を維持
  - [x] フレームが取れなくなったら諦めて解放する（無限ループにしない）
- [x] 経路2（ブラウザカメラ）：`getUserMedia` → canvas で JPEG 化 → WebSocket 送信 → サーバ推論 → 注釈フレーム返却
  - [x] 送信レート制御（**応答を受け取ってから次を送る＝in-flight 1 枚**）で遅延を溜めない
  - [x] Vite の dev プロキシは `ws: true` が必須（無いと WebSocket が中継されない）
- [x] 受け入れ基準：`docs/manual/02_realtime.md`

> `streamlit-webrtc` / `av`（`[realtime]` extra）は **React 版では不要**。ただし Streamlit 版
> `app/views/realtime.py` がまだ使っているため、Streamlit を退役させるまでは残す。

### R6. 仕上げ
- [ ] `backend/tests/`：各 API のスキーマ・ゾーン JSON パース・パス検証を R1〜R5 の実装に合わせて追加
- [ ] `frontend/src/**/*.test.ts(x)`：`jobReducer`・設定連動ロジック（セグ→モデル一覧、追跡→ゾーン可否）を vitest で
- [x] `ruff check .`（line-length 120 / py312）を backend にも通す
- [x] CI ワークフロー：`ruff` / `pytest`（tests + backend/tests）/ `frontend(tsc + vitest + build)`
- [ ] ドキュメント更新：`docs/manual/*` の「起動方法」を React 版へ、`frontend/docs/<Component>.md`・`backend/docs/` を規約に沿って追加、`README.md` の起動手順
- [ ] Streamlit 版の去就を決定：**全画面パリティ達成までは併存**（`app/` は残す）→ 達成後に削除 or `legacy_streamlit/` へ退避（削除は要ユーザ確認）

---

## 4. 設計判断（要確認ポイント）

| # | 論点 | 推奨 | 理由 |
|---|---|---|---|
| 1 | 段階移行か一括か | **段階**（R1→R2→R3→R4→R5、Streamlit と併存） | 5 画面同時は検証不能。1 画面ずつマニュアルで受け入れ確認できる |
| 2 | ルーティング | `react-router-dom` を追加 | 5 ページ・URL 共有あり。`grace_v2` は 1 ページなので自前 state で足りていた |
| 3 | UI ライブラリ | **入れない**（自前 CSS） | `grace_v2` が react/react-dom のみで完結。依存とビルド時間を増やさない |
| 4 | 表コンポーネント | 自前 `DataTable` ＋ 大量行はページング | `st.dataframe` 相当。検出テーブルは数万行になりうる |
| 5 | ジョブ永続化 | しない（インメモリ・単一プロセス） | 現行 Streamlit も `session_state` 揮発。ローカル開発用途 |
| 6 | 認証 | 無し（localhost 限定 CORS） | 現行と同水準。ただし**任意パス受け取り API はルート制限必須** |
| 7 | リアルタイム経路1 | MJPEG | サーバ側カメラという現行の性質を保ったまま最小実装。WebRTC は過剰 |

## 5. リスク

| リスク | 影響 | 緩和 |
|---|---|---|
| リアルタイムのレイテンシ悪化 | R5 が実用外に | frame_skip・解像度・軽量モデル自動切替を維持し、`pipeline/benchmark.py` で移行前後を比較 |
| 大きな mp4 のアップロード | メモリ/タイムアウト | ストリーミング保存・サイズ上限・一時ディレクトリの掃除 |
| ディレクトリパス受け取り（バッチ/重み/`data.yaml`） | 任意ファイル読み取り | 許可ルート配下へ正規化・検証。Streamlit 時代より露出が広がる点に注意 |
| 検出テーブルの巨大 JSON | ブラウザ固まる | 件数上限＋ページング、全件は CSV/JSON DL へ誘導 |
| 二重メンテ（Streamlit と React） | 修正漏れ | パリティ達成を短期で切り上げ、Streamlit を退役させる |
