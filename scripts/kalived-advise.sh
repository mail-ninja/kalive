#!/usr/bin/env bash
# Advisor (SpaceXAI). No sudo required. Reads last or --snapshot verdict.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/kalived-ai-env.sh
source "$ROOT/scripts/lib/kalived-ai-env.sh"
kalived_ai_env_load
# shellcheck source=lib/kalived-config.sh
source "$ROOT/scripts/lib/kalived-config.sh"
kalived_config_load || true
export KALIVED_ROOT="$ROOT"
export CFG_AI_MODEL="${CFG_AI_MODEL:-grok-4.6}"
exec python3 "$ROOT/scripts/kalived-advise.py" "$@"
