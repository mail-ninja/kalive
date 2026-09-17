#!/usr/bin/env bash
# Update threat definition sources. Extensible via defs/feeds.d/*.feed
# Run: sudo ./scripts/update-threat-defs.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${KALIVED_DATA:-$ROOT}"
STAMP="$(date +%Y-%m-%d_%H%M%S)"
LOG="$DATA/logs/defs/${STAMP}_update.log"
mkdir -p "$DATA/logs/defs" "$ROOT/defs/cache"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

{
  echo "=== update-threat-defs $STAMP ==="
  echo "defs VERSION=$(cat "$ROOT/defs/VERSION" 2>/dev/null || echo '?')"
} | tee "$LOG"

run_feed() {
  local f="$1"
  local id type enabled
  id="$(grep -E '^id=' "$f" | head -1 | cut -d= -f2-)"
  type="$(grep -E '^type=' "$f" | head -1 | cut -d= -f2-)"
  enabled="$(grep -E '^enabled=' "$f" | head -1 | cut -d= -f2-)"
  [[ "$enabled" == "1" ]] || { echo "[skip] $id ($type)"; return 0; }
  echo "[feed] $id type=$type"
  case "$type" in
    rkhunter)
      if command -v rkhunter >/dev/null 2>&1; then
        rkhunter --update || echo "rkhunter --update failed"
      else
        echo "rkhunter not installed"
      fi
      ;;
    url-ioc|json-cve|yara|news)
      echo "  not wired yet (stub). url=$(grep -E '^url=' "$f" | cut -d= -f2-)"
      echo "  enable + implement ingest in a later PR; news never auto-ALERT."
      ;;
    *)
      echo "  unknown type $type — ignored (no eval)"
      ;;
  esac
}

if command -v rkhunter >/dev/null 2>&1; then
  install -m 644 "$ROOT/playbooks/rkhunter.conf.local" /etc/rkhunter.conf.local
fi

shopt -s nullglob
for feed in "$ROOT/defs/feeds.d/"*.feed; do
  run_feed "$feed" | tee -a "$LOG"
done

echo "allowlists: $ROOT/defs/kali-allow/"
echo "DONE" | tee -a "$LOG"
if [[ -n "${SUDO_USER:-}" ]]; then
  chown -R "${SUDO_USER}:${SUDO_USER}" "$DATA/logs/defs" 2>/dev/null || true
fi
