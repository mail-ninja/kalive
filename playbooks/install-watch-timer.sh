#!/usr/bin/env bash
# Opt-in 5-min egress-watch timer. Requires helper first.
# Run: sudo bash playbooks/install-watch-timer.sh
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/kalived-gate.sh
source "$ROOT/playbooks/lib/kalived-gate.sh"
kalived_require_not_alert

if [[ ! -x /usr/local/lib/kalived/scripts/kalived-watch.sh ]]; then
  echo "Kjør playbooks/install-kalived-helper.sh først" >&2
  exit 1
fi
install -m 644 "$ROOT/systemd/kalived-watch.service" /etc/systemd/system/kalived-watch.service
install -m 644 "$ROOT/systemd/kalived-watch.timer" /etc/systemd/system/kalived-watch.timer
if [[ -n "${SUDO_USER:-}" ]]; then
  sed -i "s|^Environment=KALIVED_OWNER=.*|Environment=KALIVED_OWNER=${SUDO_USER}|" /etc/systemd/system/kalived-watch.service
  home="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
  sed -i "s|^Environment=KALIVED_OWNER_HOME=.*|Environment=KALIVED_OWNER_HOME=${home}|" /etc/systemd/system/kalived-watch.service
  sed -i "s|^Environment=KALIVED_DATA=.*|Environment=KALIVED_DATA=${home}/kalived|" /etc/systemd/system/kalived-watch.service
fi
systemctl daemon-reload
systemctl enable --now kalived-watch.timer
systemctl status kalived-watch.timer --no-pager || true
python3 "$ROOT/scripts/lib/kalived_config.py" set watch_timer true || true
kalived_changelog "install-watch-timer.sh" \
  "- kalived-watch.timer 5 min. Opt-in. Ringbuffer ~/.config/kalived/hiroshima 0600."
echo "DONE"
echo "Neste: systemctl list-timers kalived-watch.timer"
