#!/usr/bin/env bash
# NOPASSWD kun for /usr/local/sbin/kalived-ctl + faste subkommandoer.
# IKKE NOPASSWD på git-treet (user-writable = root).
# Run once with password: sudo bash playbooks/install-nopasswd-ctl.sh
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OWNER="${SUDO_USER:-${KALIVED_OWNER:-}}"
if [[ -z "$OWNER" || "$OWNER" == "root" ]]; then
  echo "Kjør via sudo fra operator-konto (SUDO_USER må være satt)." >&2
  exit 1
fi

if [[ ! -x /usr/local/lib/kalived/scripts/kalived-scan.sh ]]; then
  echo "Kjør playbooks/install-kalived-helper.sh først (én gang med passord)." >&2
  exit 1
fi

# Kali sudo secure_path is /usr/sbin:/usr/bin:/sbin:/bin (no /usr/local/sbin).
install -m 755 -o root -g root "$ROOT/scripts/kalived-ctl" /usr/sbin/kalived-ctl
install -m 755 -o root -g root "$ROOT/scripts/kalived-ctl" /usr/local/sbin/kalived-ctl
# Copy api into helper tree (older helper installs may lack it)
mkdir -p /usr/local/lib/kalived/api
cp -a "$ROOT/api/." /usr/local/lib/kalived/api/
chown -R root:root /usr/local/lib/kalived/api
find /usr/local/lib/kalived/api -type f -exec chmod 644 {} \;

SUDOERS=/etc/sudoers.d/kalived
cat > "$SUDOERS" << EOF
# kalived — NOPASSWD only for root-owned dispatcher. visudo -c on install.
Defaults!/usr/sbin/kalived-ctl env_reset
Cmnd_Alias KALIVED_CTL = /usr/sbin/kalived-ctl scan, /usr/sbin/kalived-ctl api, /usr/sbin/kalived-ctl defs, /usr/sbin/kalived-ctl token-fix, /usr/sbin/kalived-ctl aide-init, /usr/sbin/kalived-ctl rkhunter-setup, /usr/sbin/kalived-ctl isolate-dst, /usr/sbin/kalived-ctl isolate-undo, /usr/sbin/kalived-ctl kill-pid, /usr/sbin/kalived-ctl watch, /usr/sbin/kalived-ctl uplink-burst, /usr/sbin/kalived-ctl falco-burst, /usr/sbin/kalived-ctl watch-timer-on, /usr/sbin/kalived-ctl watch-timer-off, /usr/sbin/kalived-ctl scan-timer-on, /usr/sbin/kalived-ctl scan-timer-off
${OWNER} ALL=(root) NOPASSWD: KALIVED_CTL
EOF
chmod 440 "$SUDOERS"
if ! visudo -cf "$SUDOERS"; then
  rm -f "$SUDOERS"
  echo "visudo FAILED — sudoers not installed" >&2
  exit 1
fi

# Fix existing root-owned token in operator home
HOME_DIR="$(getent passwd "$OWNER" | cut -d: -f6)"
if [[ -f "${HOME_DIR}/.config/kalived/api.token" ]]; then
  chown "${OWNER}:${OWNER}" "${HOME_DIR}/.config/kalived/api.token"
  chmod 600 "${HOME_DIR}/.config/kalived/api.token"
  echo "chown token → $OWNER"
fi

echo "NOPASSWD:"
echo "  sudo kalived-ctl scan    # /usr/sbin (Kali sudo PATH)"
echo "  sudo kalived-ctl api"
echo "  sudo kalived-ctl defs"
echo "  sudo kalived-ctl token-fix"
echo "  sudo kalived-ctl aide-init | rkhunter-setup | isolate-dst | isolate-undo | kill-pid"
echo "  sudo kalived-ctl watch | uplink-burst | falco-burst | watch-timer-on | watch-timer-off | scan-timer-on | scan-timer-off"
echo "Helper-oppdatering fra git krever FORTSATT passord:"
echo "  sudo bash $ROOT/playbooks/install-kalived-helper.sh"
echo "DONE"
