#!/usr/bin/env bash
# Init or re-baseline AIDE DB (identity/persistence paths only).
# Run: sudo bash playbooks/aide-init.sh
# Kjør på nytt etter *bevisste* systemd/file-endringer (timer, docker disable).
# Nekter hvis siste kalived-scan er ALERT/ERROR.
# Rollback: rm -f /var/lib/aide/kalived.db.gz /etc/aide/kalived.conf
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/kalived-gate.sh
source "$ROOT/playbooks/lib/kalived-gate.sh"
# shellcheck source=../scripts/lib/kalived-config.sh
source "$ROOT/scripts/lib/kalived-config.sh"
FORCE=0
if [[ "${1:-}" == "--force" ]]; then
  FORCE=1
  echo "aide-init --force: hopper over ALERT-gate (kun etter bevisst host-endring)"
fi
if [[ "$FORCE" != "1" ]]; then
  kalived_require_not_alert
fi
kalived_config_load || exit 3

POLICY="${KALIVED_AIDE_INIT_POLICY:-$CFG_AIDE_INIT_POLICY}"
if [[ "$POLICY" == "always_prompt" ]]; then
  if [[ ! -t 0 ]]; then
    echo "GATE FAIL: aide_init_policy=always_prompt og ingen TTY" >&2
    exit 2
  fi
  read -r -p "Init AIDE DB på denne hosten? [y/N] " ans
  [[ "$ans" == "y" || "$ans" == "Y" ]] || exit 2
fi
dir="$(kalived_latest_scan_dir)"
verdict="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('verdict',''))" "$dir/verdict.json")"
if [[ "$POLICY" == "clean_only" && "$verdict" != "CLEAN" ]]; then
  echo "GATE FAIL: aide_init_policy=clean_only og verdict=$verdict" >&2
  exit 2
fi

export DEBIAN_FRONTEND=noninteractive
if ! command -v aide >/dev/null 2>&1; then
  apt-get install -y aide aide-common || apt-get install -y aide
fi

install -m 644 "$ROOT/playbooks/aide-99-kalived.conf" /etc/aide/kalived.conf
mkdir -p /var/lib/aide
# Debian aide-common enables a daily full-tree check. We use a focused DB only.
systemctl disable --now dailyaidecheck.timer dailyaidecheck.service 2>/dev/null || true
echo "[*] aide --init (kan ta et minutt)…"
aide --config /etc/aide/kalived.conf --init
if [[ -f /var/lib/aide/kalived.db.new.gz ]]; then
  mv -f /var/lib/aide/kalived.db.new.gz /var/lib/aide/kalived.db.gz
elif [[ -f /var/lib/aide/kalived.db.new ]]; then
  mv -f /var/lib/aide/kalived.db.new /var/lib/aide/kalived.db.gz
fi
chmod 600 /var/lib/aide/kalived.db.gz 2>/dev/null || chmod 600 /var/lib/aide/kalived.db* 2>/dev/null || true
chown root:root /var/lib/aide/kalived.db* /etc/aide/kalived.conf
sha256sum /var/lib/aide/kalived.db.gz > "$ROOT/baselines/aide.sha256"
if [[ -n "${SUDO_USER:-}" ]]; then
  chown "${SUDO_USER}:${SUDO_USER}" "$ROOT/baselines/aide.sha256"
fi
echo "AIDE DB: $(ls -l /var/lib/aide/kalived.db.gz)"
echo "Checksum: $(cat "$ROOT/baselines/aide.sha256")"
kalived_changelog "aide-init.sh" \
  "- AIDE kalived.db.gz init (identity/persistens). Gate: $verdict. Checksum i baselines/aide.sha256"
echo "DONE"
