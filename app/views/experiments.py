"""実験管理・モデル管理ビュー（Phase 0 雛形 / 仕様書 §4.2）。

Phase 4 で MLflow/W&B の Run 一覧・メトリクス比較・Model Registry 連携を実装する。
ここでは MLflow Tracking サーバへの接続先表示とプレースホルダ表のみ。
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

st.title("📊 Experiments & Models")
st.caption("実験管理・モデル管理画面（Phase 0 雛形）")

tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
st.write(f"MLflow Tracking URI: `{tracking_uri}`")
st.info("docker-compose で MLflow を起動後、Phase 4 で Run の同期・比較を実装します。", icon="🚧")

# レイアウト確認用のダミー Run 表（実データは Phase 4 で MLflow から取得）。
demo = pd.DataFrame(
    [
        {"Run名": "ft_v3_aug", "mAP50": 0.87, "mAP50-95": 0.61, "推論ms": 18, "ステータス": "✅完了"},
        {"Run名": "ft_v2", "mAP50": 0.81, "mAP50-95": 0.55, "推論ms": 17, "ステータス": "✅完了"},
        {"Run名": "baseline", "mAP50": 0.74, "mAP50-95": 0.49, "推論ms": 16, "ステータス": "✅完了"},
    ]
)
st.dataframe(demo, use_container_width=True)

cols = st.columns(3)
cols[0].button("新規学習ジョブ", disabled=True)
cols[1].button("データセット品質レポート", disabled=True)
cols[2].button("Claude自動レビュー", disabled=True)
