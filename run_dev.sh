#!/usr/bin/env bash
# 開発サーバ一括起動: backend(FastAPI :8000) + frontend(Vite :5173)。
#
#   ./run_dev.sh
#
# 停止は Ctrl-C（両方まとめて落とす）。
# 前提: uv pip install -e . 済み、frontend/ で npm install 済み。
# Streamlit 版は別物として `streamlit run app/Home.py` で従来どおり起動できる。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PORT="${BACKEND_PORT:-8000}"

if [ ! -d "frontend/node_modules" ]; then
  echo "frontend の依存が未インストールです。先に実行してください:"
  echo "  cd frontend && npm install"
  exit 1
fi

pids=()
cleanup() {
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

echo "▶ backend  http://localhost:${BACKEND_PORT}  (docs: /docs)"
uvicorn backend.app.main:app --reload --port "$BACKEND_PORT" &
pids+=($!)

echo "▶ frontend http://localhost:5173"
(cd frontend && npm run dev) &
pids+=($!)

wait
