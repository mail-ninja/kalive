#!/usr/bin/env bash
# Stop Debian chkrootkit/rkhunter/debsums/exim timers (kalived eier scannen).
# Ingen ALERT-gate — dette reduserer støy fra pakkene vi nettopp installerte.
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi
systemctl disable --now chkrootkit.timer chkrootkit.service exim4-base.timer 2>/dev/null || true
chmod a-x /etc/cron.daily/rkhunter /etc/cron.weekly/rkhunter \
  /etc/cron.daily/chkrootkit /etc/cron.daily/debsums \
  /etc/cron.weekly/debsums /etc/cron.monthly/debsums \
  /etc/cron.daily/exim4-base 2>/dev/null || true
echo "Vendor rk/debsums/exim cron+timer disabled (kalived scan remains)."
echo "DONE"
