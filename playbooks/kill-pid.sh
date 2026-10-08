#!/usr/bin/env bash
# SIGTERM a snapshot-matched pid. exe must match /proc. Never ours/comm 1.
# Act file: ~/.config/kalived/act.json {"pid":N,"exe":"name"}
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo kalived-ctl kill-pid" >&2
  exit 1
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
# shellcheck source=lib/kalived-gate.sh
source "$HERE/lib/kalived-gate.sh"
kalived_require_not_alert || exit 2
OWNER_HOME="${KALIVED_OWNER_HOME:-$(getent passwd "${SUDO_USER:-${KALIVED_OWNER:-$(id -un)}}" | cut -d: -f6)}"
ACT="${OWNER_HOME}/.config/kalived/act.json"
HELPER="$ROOT/scripts/lib/hiroshima_act.py"
if [[ ! -f "$ACT" ]]; then
  echo "mangler act.json" >&2
  exit 2
fi
PID="$(python3 -c "import json,sys; print(int(json.load(open(sys.argv[1])).get('pid') or 0))" "$ACT")"
EXE="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('exe') or '')" "$ACT")"
python3 "$HELPER" check-kill "$PID" "$EXE" || {
  echo "GATE: kill-pid nektet" >&2
  exit 2
}
echo "SIGTERM pid=$PID exe=$EXE"
kill -TERM "$PID"
kalived_changelog "kill-pid.sh" "- SIGTERM pid=$PID exe=$EXE (exe-match)"
echo "DONE"
