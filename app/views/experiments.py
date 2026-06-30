"""実験管理・モデル管理ビュー（Phase 4 / 仕様書 §4.2）。

MLflow Tracking サーバから Run 一覧・メトリクス比較を取得し、Model Registry の
ステージ管理と転移学習ジョブの起動を行う。MLflow 未起動でも UI は表示する。
"""

from __future__ import annotations

import streamlit as st

from pipeline.dataset import DatasetSpec, build_dataset_yaml
from pipeline.detector import AVAILABLE_MODELS, SEG_MODELS
from pipeline.experiments import (
    DEFAULT_EXPERIMENT,
    best_run,
    format_runs_table,
    list_runs,
    tracking_uri,
)
from pipeline.registry import STAGES

st.title("📊 Experiments & Models")
st.caption("実験管理・モデル管理画面 — Phase 4（MLflow / Model Registry）")

uri = tracking_uri()
st.write(f"MLflow Tracking URI: `{uri}`")

experiment = st.text_input("実験名", value=DEFAULT_EXPERIMENT)

# ----- Run 一覧・比較 -----
st.subheader("Run 一覧・比較")
if st.button("🔄 MLflow から取得", type="primary"):
    try:
        st.session_state["mlflow_runs"] = list_runs(experiment)
    except Exception as e:  # noqa: BLE001
        st.session_state["mlflow_runs"] = None
        st.error(
            f"MLflow へ接続できませんでした: {e}\n\n"
            "`docker-compose -f docker-compose/docker-compose.yml up -d` で起動してください。"
        )

runs = st.session_state.get("mlflow_runs")
if runs is None:
    st.info("「MLflow から取得」を押すと Run 一覧を表示します。", icon="📡")
elif not runs:
    st.warning(f"実験 '{experiment}' に Run がありません。学習ジョブを実行してください。")
else:
    st.dataframe(format_runs_table(runs), use_container_width=True, hide_index=True)
    top = best_run(runs)
    if top:
        m = top["metrics"].get("metrics/mAP50-95(B)", 0.0)
        st.success(f"最良 Run: **{top['run_name']}**（mAP50-95 = {m:.4f}）")

# ----- 転移学習ジョブ -----
st.subheader("新規学習ジョブ（転移学習 / Fine-tuning）")
with st.form("train_job"):
    c1, c2, c3 = st.columns(3)
    data_yaml = c1.text_input("data.yaml パス", value="data/datasets/custom/data.yaml")
    base_model = c2.selectbox("ベースモデル", list(AVAILABLE_MODELS) + list(SEG_MODELS), index=1)
    epochs = c3.number_input("epochs", min_value=1, max_value=1000, value=50)
    run_name = st.text_input("Run 名（任意）", value="")
    submitted = st.form_submit_button("▶ 学習を開始")
    if submitted:
        st.info(
            "学習は ultralytics + MLflow を要し、長時間かつ高負荷です。"
            "M2 Mac では軽量・短時間に留め、本格学習はクラウド GPU を推奨します（仕様書 §1.2）。",
            icon="⚙️",
        )
        try:
            from pipeline.training import TrainConfig, train

            cfg = TrainConfig(
                data_yaml=data_yaml,
                base_model=base_model,
                epochs=int(epochs),
                experiment=experiment,
                run_name=run_name or None,
            )
            with st.spinner("学習中…（進捗は MLflow UI / コンソールで確認）"):
                result = train(cfg)
            st.success(f"学習完了: run_id={result.run_id}")
            st.json(result.metrics)
        except Exception as e:  # noqa: BLE001
            st.error(f"学習の実行に失敗しました: {e}")

# ----- データセット雛形生成 -----
with st.expander("データセット data.yaml 生成"):
    ds_name = st.text_input("データセット名", value="custom")
    ds_classes = st.text_input("クラス（カンマ区切り）", value="person,car,truck,bus,bicycle,motorcycle")
    if st.button("data.yaml を生成"):
        spec = DatasetSpec(name=ds_name, classes=[c.strip() for c in ds_classes.split(",") if c.strip()])
        st.code(build_dataset_yaml(spec), language="yaml")

# ----- Model Registry -----
st.subheader("Model Registry")
st.caption(f"ステージ: {' / '.join(STAGES)}")
st.write(
    "学習済みベスト重みを `register_model()` で登録し、`transition_stage()` で "
    "Staging→Production→Archived を管理します（仕様書 §4.2）。"
)
st.button("Claude自動レビュー（P6）", disabled=True)
