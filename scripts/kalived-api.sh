#!/usr/bin/env bash
# Local API (loopback). Mutating routes need root.
# Run: sudo ./scripts/kalived-api.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export KALIVED_ROOT="$ROOT"
export KALIVED_DATA="${KALIVED_DATA:-$ROOT}"
if [[ "$(id -u)" -eq 0 && -n "${SUDO_USER:-}" ]]; then
  export KALIVED_OWNER="$SUDO_USER"
fi
echo "kalived-api: not FastAPI — no /docs. GET / lists routes. Token: ~/.config/kalived/api.token" >&2
echo "Test (other terminal): ./scripts/tests/api-e2e.sh --live" >&2
exec python3 "$ROOT/api/server.py"
