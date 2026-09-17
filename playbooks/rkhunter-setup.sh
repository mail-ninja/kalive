#!/usr/bin/env bash
# Install rkhunter + chkrootkit + debsums, first propupd, freeze lsmod.
# Run: sudo bash playbooks/rkhunter-setup.sh
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/kalived-gate.sh
source "$ROOT/playbooks/lib/kalived-gate.sh"
# Setup after CLEAN preferred, but WARN from FIM/rkhunter FP is OK.
kalived_require_not_alert || {
  echo "GATE: ikke ALERT-fri — avbryter (ekte ALERT). Fiks/allowlist først." >&2
  exit 2
}

export DEBIAN_FRONTEND=noninteractive
apt-get install -y rkhunter chkrootkit debsums

install -m 644 "$ROOT/playbooks/rkhunter.conf.local" /etc/rkhunter.conf.local
# Ensure main conf includes local if the package supports it
if [[ -f /etc/rkhunter.conf ]] && ! grep -q rkhunter.conf.local /etc/rkhunter.conf; then
  echo 'INSTALLDIR=/usr' >/dev/null
fi

echo "[*] rkhunter --update"
rkhunter --update || true
echo "[*] disable vendor chkrootkit/rkhunter timers (kalived eier scannen)"
systemctl disable --now chkrootkit.timer chkrootkit.service 2>/dev/null || true
chmod a-x /etc/cron.daily/rkhunter /etc/cron.weekly/rkhunter \
  /etc/cron.daily/chkrootkit /etc/cron.daily/debsums \
  /etc/cron.weekly/debsums /etc/cron.monthly/debsums 2>/dev/null || true

echo "[*] rkhunter --propupd (fil-properties mot denne CLEAN/WARN-hosten)"
rkhunter --propupd

mkdir -p "$ROOT/baselines/machine"
if [[ ! -s "$ROOT/baselines/machine/lsmod.expected" ]]; then
  lsmod | awk 'NR>1 {print $1}' | sort > "$ROOT/baselines/machine/lsmod.expected"
  if [[ -n "${SUDO_USER:-}" ]]; then
    chown "${SUDO_USER}:${SUDO_USER}" "$ROOT/baselines/machine/lsmod.expected"
  fi
  echo "Froze lsmod.expected ($(wc -l < "$ROOT/baselines/machine/lsmod.expected") modules)"
fi

echo "[*] first chkrootkit (quiet-ish)"
chkrootkit -q > /var/log/kalived-chkrootkit-first.txt 2>&1 || true
echo "[*] first rkhunter --check"
rkhunter --check --skip-keypress --report-warnings-only --nocolors \
  > /var/log/kalived-rkhunter-first.txt 2>&1 || true
echo "--- rkhunter warnings (first) ---"
head -80 /var/log/kalived-rkhunter-first.txt || true

kalived_changelog "rkhunter-setup.sh" \
  "- rkhunter+chkrootkit+debsums. --propupd. lsmod.expected freeze. Defs: defs/ + update-threat-defs.sh"
echo "DONE"
echo "Neste: sudo $ROOT/scripts/update-threat-defs.sh && sudo $ROOT/scripts/kalived-scan.sh"
