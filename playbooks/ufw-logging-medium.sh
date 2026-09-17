#!/usr/bin/env bash
# UFW logging medium (visibility). Does not change deny policy.
# Run: sudo bash playbooks/ufw-logging-medium.sh
# Rollback: ufw logging low
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/kalived-gate.sh
source "$ROOT/playbooks/lib/kalived-gate.sh"
kalived_require_not_alert

ufw logging medium
ufw status verbose | head -8
kalived_changelog "ufw-logging-medium.sh" \
  "- ufw logging medium (ikke deny-out). Gate: ikke ALERT. Rollback: ufw logging low"
echo "DONE"
