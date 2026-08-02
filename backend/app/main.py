"""Video ML Analytics Studio Web API（FastAPI）。

Streamlit UI（`app/Home.py`）を React SPA へ置き換えるためのバックエンド。
**推論・解析のロジックは `pipeline/` のまま**で、ここはその薄い HTTP 層に徹する。

起動（リポジトリルートで）::

    uvicorn backend.app.main:app --reload --port 8000

フロントエンド（別ターミナル）::

    cd frontend && npm run dev      # http://localhost:5173

両方まとめて起動するなら `./run_dev.sh`。

ローカル開発専用（認証なし）。CORS は Vite dev サーバのみ許可する。
移行の計画は `docs/react_migration_todo.md` を参照。
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import analyze, annotation, experiments, media, meta, production
from backend.app.schemas import HealthResponse

# .env から ANTHROPIC_API_KEY 等を読み込む（未導入でも続行）。
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - python-dotenv 未導入環境
    pass

API_VERSION = "0.1.0"

app = FastAPI(
    title="Video ML Analytics Studio API",
    description=(
        "動画ML解析プラットフォームの Web API。"
        "検出/セグメンテーション/トラッキング/ゾーン解析・実験管理・本番化・"
        "アノテーション QA を React UI へ提供する。"
    ),
    version=API_VERSION,
)

# ローカル開発: Vite dev サーバ（既定 5173）からのアクセスを許可する。
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meta.router)
app.include_router(analyze.router)
app.include_router(annotation.router)
app.include_router(experiments.router)
app.include_router(production.router)
app.include_router(media.router)


@app.get("/api/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    """疎通確認。フロントの「バックエンド未起動」表示の判定に使う。"""
    return HealthResponse(status="ok", version=API_VERSION)
