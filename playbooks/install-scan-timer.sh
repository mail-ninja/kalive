#!/usr/bin/env bash
# Opt-in weekly system timer. Requires helper first.
# Run: sudo bash playbooks/install-scan-timer.sh
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/kalived-gate.sh
source "$ROOT/playbooks/lib/kalived-gate.sh"
kalived_require_not_alert

if [[ ! -x /usr/local/lib/kalived/scripts/kalived-scan.sh ]]; then
  echo "Kjør playbooks/install-kalived-helper.sh først" >&2
  exit 1
fi
install -m 644 "$ROOT/systemd/kalived-scan.service" /etc/systemd/system/kalived-scan.service
install -m 644 "$ROOT/systemd/kalived-scan.timer" /etc/systemd/system/kalived-scan.timer
# Rewrite data dir owner if SUDO_USER set
if [[ -n "${SUDO_USER:-}" ]]; then
  sed -i "s|^Environment=KALIVED_OWNER=.*|Environment=KALIVED_OWNER=${SUDO_USER}|" /etc/systemd/system/kalived-scan.service
  sed -i "s|^Environment=KALIVED_DATA=.*|Environment=KALIVED_DATA=/home/${SUDO_USER}/kalived|" /etc/systemd/system/kalived-scan.service
fi
systemctl daemon-reload
systemctl enable --now kalived-scan.timer
systemctl status kalived-scan.timer --no-pager || true
if ! grep -q SuccessExitStatus /etc/systemd/system/kalived-scan.service; then
  echo "FAIL: SuccessExitStatus mangler" >&2
  exit 3
fi
kalived_changelog "install-scan-timer.sh" \
  "- kalived-scan.timer weekly enabled. SuccessExitStatus=1 2. Opt-in av operator."
echo "DONE"
echo "Neste: systemctl list-timers kalived-scan.timer"
