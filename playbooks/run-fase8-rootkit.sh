#!/usr/bin/env bash
# Fase 8. Run: sudo bash playbooks/run-fase8-rootkit.sh
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
bash "$ROOT/playbooks/rkhunter-setup.sh"
bash "$ROOT/scripts/update-threat-defs.sh"
echo ""
echo "Neste: sudo $ROOT/scripts/kalived-scan.sh"
echo "Scan tar lenger tid (rkhunter --check). Etterpå: sudo bash playbooks/install-kalived-helper.sh"
