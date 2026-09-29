#!/usr/bin/env bash
# UFW deny-out to unknown ESTAB dst IPs from latest snapshot. Rollback file 0600.
# Confirm via: sudo kalived-ctl isolate-dst
# Does not take dest on argv. Family from ~/.config/kalived/act.json (default unknown).
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo kalived-ctl isolate-dst" >&2
  exit 1
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
# shellcheck source=lib/kalived-gate.sh
source "$HERE/lib/kalived-gate.sh"
kalived_require_not_alert || exit 2

OWNER_HOME="${KALIVED_OWNER_HOME:-$(getent passwd "${SUDO_USER:-void}" | cut -d: -f6)}"
DATA="${KALIVED_DATA:-$OWNER_HOME/kalived}"
ACT="${OWNER_HOME}/.config/kalived/act.json"
RB="${OWNER_HOME}/.config/kalived/isolate-rollback.json"
HELPER="$ROOT/scripts/lib/hiroshima_act.py"
SNAP="$(kalived_latest_scan_dir)"
[[ -n "$SNAP" ]] || { echo "ingen snapshot" >&2; exit 2; }

FAMILY="unknown"
if [[ -f "$ACT" ]]; then
  FAMILY="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('family') or 'unknown')" "$ACT" 2>/dev/null || echo unknown)"
fi
if [[ "$FAMILY" != "unknown" ]]; then
  echo "GATE: isolate-dst v1 isolerer bare family=unknown (fikk $FAMILY)" >&2
  exit 2
fi

mapfile -t IPS < <(python3 "$HELPER" unknown-dsts "$SNAP")
if [[ "${#IPS[@]}" -eq 0 ]]; then
  echo "ingen ukjent dst i snapshot — ingenting å isolere"
  exit 0
fi

DRY="${ISOLATE_DRY:-0}"
added=()
for ip in "${IPS[@]}"; do
  [[ "$ip" =~ ^[0-9a-fA-F:.]+$ ]] || continue
  echo "deny out to $ip"
  if [[ "$DRY" != "1" ]]; then
    ufw deny out to "$ip" comment "kalived-isolate" || true
  fi
  added+=("$ip")
done
python3 - "$RB" "${added[@]}" <<'PY'
import json, os, sys, time
from pathlib import Path
dest = Path(sys.argv[1])
ips = sys.argv[2:]
dest.parent.mkdir(parents=True, exist_ok=True)
doc = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "ips": ips, "comment": "kalived-isolate"}
dest.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
os.chmod(dest, 0o600)
PY
if [[ -n "${SUDO_USER:-}" ]]; then
  chown "${SUDO_USER}:${SUDO_USER}" "$RB" 2>/dev/null || true
fi
kalived_changelog "isolate-dst.sh" "- UFW deny out to ${#added[@]} unknown dst (rollback isolate-undo)"
echo "DONE n=${#added[@]} rollback=$RB"
