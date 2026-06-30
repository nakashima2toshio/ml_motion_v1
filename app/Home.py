"""Video ML Analytics Studio — Streamlit マルチページ エントリポイント（Phase 0 雛形）。

起動:
    streamlit run app/Home.py

st.navigation / st.Page を使い、ファイル名に依存せず日本語のナビゲーション名を付ける。
各ページの中身は Phase 1 以降で実装する（現状はプレースホルダ）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# リポジトリルートを import パスに追加（`pipeline` パッケージを解決するため）。
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="Video ML Analytics Studio",
    page_icon="🎥",
    layout="wide",
)

analyze = st.Page("views/analyze.py", title="解析", icon="🎥", default=True)
experiments = st.Page("views/experiments.py", title="実験管理", icon="📊")
annotation_qa = st.Page("views/annotation_qa.py", title="アノテーションQA", icon="🏷")

pg = st.navigation([analyze, experiments, annotation_qa])
pg.run()
