#!/usr/bin/env bash
# Heimsted: FastAPI :8788 + Vite :5173 (loopback).
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$HERE/backend/.venv"
if [[ ! -x "$VENV/bin/uvicorn" ]]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -r "$HERE/backend/requirements.txt"
fi
export PYTHONPATH="$HERE/backend${PYTHONPATH:+:$PYTHONPATH}"
"$VENV/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8788 --reload --reload-dir "$HERE/backend" &
API=$!
trap 'kill $API 2>/dev/null || true' EXIT
cd "$HERE/web"
npm run dev
