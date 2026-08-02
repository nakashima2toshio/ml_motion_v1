# 既知の不具合

移行作業中に見つかった、**移行前から存在する**（React 化とは無関係の）問題を記録する。
いずれも Streamlit 版・React 版の両方に影響する。

| # | 内容 | 状態 |
|---|---|---|
| 1 | MLflow のメトリクス名に括弧が使えず、mAP 列が常に 0.0 | ✅ **修正済み** |
| 2 | 注釈付き動画がブラウザで再生できないことがある（コーデック依存） | 未修正 |

---

## 1. MLflow のメトリクス名に括弧が使えず、mAP 列が常に 0.0 になる ✅ 修正済み

**影響**: 実験管理画面の Run 一覧で `mAP50` / `mAP50-95` が常に `0`、最良 Run も表示されない。
`pipeline.training.train()` は MLflow Tracking サーバへのメトリクス記録で例外になる可能性がある。

**該当**: `pipeline/experiments.py`（`KEY_METRICS` / `format_runs_table` / `best_run`）、
`pipeline/training.py`（`_extract_metrics`）

**原因**:

1. `pipeline/experiments.py` はメトリクスを **`metrics/mAP50(B)` / `metrics/mAP50-95(B)`** というキーで引く。
2. しかし MLflow Tracking サーバは**メトリクス名に括弧を許さない**。

   ```
   INVALID_PARAMETER_VALUE: Invalid value "metrics/mAP50-95(B)" for parameter 'metrics[0].name'
   supplied: Names may only contain alphanumerics, underscores (_), dashes (-), periods (.),
   spaces ( ), colon(:) and slashes (/).
   ```

   （MLflow 2.22.5 のサーバへ実際に記録を試して確認）

3. ultralytics の MLflow コールバックは、記録前に括弧を除去している:

   ```python
   # ultralytics/utils/callbacks/mlflow.py
   SANITIZE = lambda x: {k.replace("(", "").replace(")", ""): float(v) for k, v in x.items()}
   ```

   したがって実際に保存されるキーは **`metrics/mAP50B` / `metrics/mAP50-95B`**。

4. 結果として `format_runs_table` の `metrics.get("metrics/mAP50(B)", 0.0)` は必ず既定値 `0.0` を返し、
   `best_run` も候補ゼロで `None` を返す。

5. さらに `pipeline/training.py::_extract_metrics` は ultralytics の `results_dict` のキーを
   **そのまま**（括弧つきで）`mlflow.log_metrics()` に渡すため、Tracking サーバ利用時は
   上記の `INVALID_PARAMETER_VALUE` で失敗しうる。

**再現**（MLflow サーバ起動後）:

```python
import mlflow
mlflow.set_tracking_uri("http://localhost:5000")
mlflow.set_experiment("ml_motion_detection")
with mlflow.start_run(run_name="paren-test"):
    mlflow.log_metrics({"metrics/mAP50-95(B)": 0.5})   # → INVALID_PARAMETER_VALUE
```

**修正内容**:

- `pipeline/experiments.py` に `sanitize_metric_name()` / `metric_value()` / `has_metric()` を追加。
  `format_runs_table` と `best_run` は `metric_value()` 経由で読むようにし、
  **括弧あり・括弧なしの両方**に対応した（過去 Run とも互換）。
- `pipeline/training.py::_extract_metrics` はキーを正規化してから返すようにした。
  これで `mlflow.log_metrics()` が Tracking サーバでも成功する。
- `backend/app/api/experiments.py` の `best_metric` も `metric_value()` 経由に統一した。

**回帰テスト**: `tests/test_metric_names.py`（修正前のコードでは
`format_runs_table` が 0.0、`best_run` が None、`_extract_metrics` が括弧つきを返すことを確認済み）。
実 MLflow サーバ（2.22.5）へ記録 → 読み出しの往復も確認した。

---

## 2. 注釈付き動画がブラウザで再生できないことがある（コーデック依存）

**影響**: 解析画面の動画プレビューが黒いまま再生できない。ダウンロードすれば再生できる。

**該当**: `pipeline/video.py::_open_writer`

**原因**: 書き出しは `avc1`（H.264）を優先し、使えない環境では `mp4v`（MPEG-4 Part 2）へ
フォールバックする。`mp4v` はブラウザ（Chromium/Safari）が再生できない。
macOS では通常 `avc1` が通るため顕在化しにくいが、`avc1` が無い環境（Linux コンテナ等）では
必ず `mp4v` になる。

**現状の扱い**: Streamlit 版・React 版とも「ブラウザで再生できない場合は
『⬇ 注釈付き動画』からDLしてください（コーデック依存）」と案内している。

**想定される修正方針**（未着手）: 書き出しを H.264 に固定する（ffmpeg 経由）か、
配信時にトランスコードする。いずれも `pipeline/` またはインフラ側の変更を伴う。
