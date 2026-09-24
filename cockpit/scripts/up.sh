#!/usr/bin/env bash
# Start the local cockpit stack: memory (loopback) + FastAPI :8788 + Vite :5173.
# Hiroshima is the drawer in the UI, not :8787. Optional: sudo kalived-ctl api
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
COMPOSE="$HERE/memory/compose.yml"
VENV="$HERE/backend/.venv"
LOG="${KALIVED_UP_LOG:-/tmp/kalived-ui}"
mkdir -p "$LOG"

ok() { printf '  ok  %s\n' "$*"; }
warn() { printf '  !!  %s\n' "$*" >&2; }
have() { curl -sf --max-time 1 "$1" >/dev/null 2>&1; }

echo "== kalived up (loopback) =="

if [[ ! -S /var/run/docker.sock ]]; then
  if sudo -n systemctl start docker.socket docker.service 2>/dev/null; then
    ok "docker startet (sudo -n)"
    sleep 1
  else
    warn "docker nede — minne (qdrant/redis/minio) hopper over. sudo systemctl start docker"
  fi
fi
if [[ -S /var/run/docker.sock && -f "$COMPOSE" ]]; then
  if docker compose -f "$COMPOSE" up -d; then
    ok "memory-compose :6333 :6379 :9100"
  else
    warn "compose feilet"
  fi
fi

if [[ ! -x "$VENV/bin/uvicorn" ]]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -r "$HERE/backend/requirements.txt"
fi
export PYTHONPATH="$HERE/backend${PYTHONPATH:+:$PYTHONPATH}"

if have http://127.0.0.1:8788/v1/health; then
  ok "FastAPI :8788 allerede oppe"
else
  nohup "$VENV/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8788 \
    --reload --reload-dir "$HERE/backend" >"$LOG/uvicorn.log" 2>&1 &
  echo $! >"$LOG/uvicorn.pid"
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    have http://127.0.0.1:8788/v1/health && break
    sleep 0.4
  done
  have http://127.0.0.1:8788/v1/health && ok "FastAPI :8788" || warn "FastAPI kom ikke opp — $LOG/uvicorn.log"
fi

if have http://127.0.0.1:5173/; then
  ok "Vite :5173 allerede oppe"
else
  (cd "$HERE/web" && nohup npm run dev >"$LOG/vite.log" 2>&1 & echo $! >"$LOG/vite.pid")
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    have http://127.0.0.1:5173/ && break
    sleep 0.4
  done
  have http://127.0.0.1:5173/ && ok "Vite :5173" || warn "Vite kom ikke opp — $LOG/vite.log"
fi

echo
echo "UI          http://127.0.0.1:5173/"
echo "API         http://127.0.0.1:8788/v1/health"
echo "Hiroshima   skuff i UI (ikke :8787)"
echo "8787        valgfri: sudo kalived-ctl api"
echo "workspace   $ROOT"
qdrant_ok=0
for _ in 1 2 3 4 5 6 7 8 9 10 12 15; do
  if have http://127.0.0.1:6333/readyz || have http://127.0.0.1:6333/healthz; then
    qdrant_ok=1
    break
  fi
  sleep 0.4
done
if [[ "$qdrant_ok" == 1 ]]; then
  ok "qdrant :6333"
else
  warn "qdrant nede"
fi
if have http://127.0.0.1:9100/minio/health/live; then
  ok "minio :9100"
else
  warn "minio nede"
fi
echo "DONE"
