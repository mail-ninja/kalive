#!/usr/bin/env bash
# Fase 4 + 5 i rekkefølge. Run: sudo bash playbooks/run-auditd-then-aide.sh
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
bash "$ROOT/playbooks/journald-persistent.sh"
bash "$ROOT/playbooks/auditd-mini.sh"
bash "$ROOT/playbooks/ufw-logging-medium.sh"
bash "$ROOT/playbooks/aide-init.sh"
echo ""
echo "Neste: sudo $ROOT/scripts/kalived-scan.sh"
