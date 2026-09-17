#!/usr/bin/env bash
# Fase 6+7. Run: sudo bash playbooks/run-timer-and-docker.sh
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
bash "$ROOT/playbooks/install-kalived-helper.sh"
bash "$ROOT/playbooks/install-scan-timer.sh"
bash "$ROOT/playbooks/docker-hygiene.sh" --prune
echo ""
echo "Neste: sudo $ROOT/scripts/kalived-scan.sh"
echo "Docker senere: sudo systemctl start docker"
