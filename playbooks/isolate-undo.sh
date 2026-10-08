#!/usr/bin/env bash
# Remove kalived isolate-dst UFW rules from rollback file.
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo kalived-ctl isolate-undo" >&2
  exit 1
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
# shellcheck source=lib/kalived-gate.sh
source "$HERE/lib/kalived-gate.sh"
OWNER_HOME="${KALIVED_OWNER_HOME:-$(getent passwd "${SUDO_USER:-${KALIVED_OWNER:-$(id -un)}}" | cut -d: -f6)}"
RB="${OWNER_HOME}/.config/kalived/isolate-rollback.json"
if [[ ! -f "$RB" ]]; then
  echo "ingen rollback — ingenting å angre"
  exit 0
fi
DRY="${ISOLATE_DRY:-0}"
python3 - "$RB" "$DRY" <<'PY'
import json, subprocess, sys
from pathlib import Path
rb, dry = Path(sys.argv[1]), sys.argv[2] == "1"
doc = json.loads(rb.read_text(encoding="utf-8"))
ips = doc.get("ips") or []
for ip in ips:
    if not isinstance(ip, str):
        continue
    print("delete deny out to", ip)
    if not dry:
        subprocess.run(["ufw", "delete", "deny", "out", "to", ip], check=False)
rb.unlink()
print("removed", rb)
PY
kalived_changelog "isolate-undo.sh" "- rollback isolate-dst UFW rules"
echo "DONE"
