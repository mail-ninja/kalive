#!/usr/bin/env bash
# Init or re-baseline AIDE DB (identity/persistence paths only).
# Run: sudo bash playbooks/aide-init.sh
# Kjør etter *bevisst* filendring (ny helper, kjent pakke) — ikke som oppvarming før scan.
# --force: hopp over always_prompt / clean_only. Hopper IKKE over ALERT-gate.
# --force-alert: re-baseline selv om siste scan er ALERT (kun etter evidens er lagret).
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
FORCE_ALERT=0
for _a in "$@"; do
  case "$_a" in
    --force) FORCE=1 ;;
    --force-alert) FORCE=1; FORCE_ALERT=1 ;;
    *)
      echo "ukjent flagg: $_a (gyldig: --force | --force-alert)" >&2
      exit 2
      ;;
  esac
done
if [[ "$FORCE_ALERT" == "1" ]]; then
  echo "aide-init --force-alert: hopper over ALERT-gate (evidens må allerede være lagret)" >&2
else
  kalived_require_not_alert
fi
if [[ "$FORCE" == "1" && "$FORCE_ALERT" != "1" ]]; then
  echo "aide-init --force: bevisst re-baseline (ALERT-gate gjelder fortsatt)" >&2
fi
kalived_config_load || exit 3

POLICY="${KALIVED_AIDE_INIT_POLICY:-$CFG_AIDE_INIT_POLICY}"
if [[ "$FORCE" != "1" && "$POLICY" == "always_prompt" ]]; then
  if [[ ! -t 0 ]]; then
    echo "GATE FAIL: aide_init_policy=always_prompt og ingen TTY" >&2
    exit 2
  fi
  read -r -p "Init AIDE DB på denne hosten? [y/N] " ans
  [[ "$ans" == "y" || "$ans" == "Y" ]] || exit 2
fi
dir="$(kalived_latest_scan_dir)"
verdict="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('verdict',''))" "$dir/verdict.json")"
if [[ "$FORCE" != "1" && "$POLICY" == "clean_only" && "$verdict" != "CLEAN" ]]; then
  echo "GATE FAIL: aide_init_policy=clean_only og verdict=$verdict" >&2
  exit 2
fi

export DEBIAN_FRONTEND=noninteractive
if ! command -v aide >/dev/null 2>&1; then
  apt-get install -y aide aide-common || apt-get install -y aide
fi

install -m 644 "$ROOT/playbooks/aide-99-kalived.conf" /etc/aide/kalived.conf
if [[ "${CFG_AIDE_WATCH_HELPER:-1}" != "1" ]]; then
  grep -vE '/usr/local/lib/kalived|/usr/sbin/kalived-ctl' /etc/aide/kalived.conf > /etc/aide/kalived.conf.tmp
  mv /etc/aide/kalived.conf.tmp /etc/aide/kalived.conf
  echo "aide_watch_helper=0 — helper-stier utelatt"
fi
mkdir -p /var/lib/aide
# Debian aide-common enables a daily full-tree check. We use a focused DB only.
systemctl disable --now dailyaidecheck.timer dailyaidecheck.service 2>/dev/null || true
echo "[*] aide --init (kan ta et minutt)…" >&2
AIDE_LOG="${KALIVED_DATA:-$ROOT}/logs/aide-init.log"
mkdir -p "$(dirname "$AIDE_LOG")"
aide --config /etc/aide/kalived.conf --init > "$AIDE_LOG" 2>&1
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
_entries="$(grep -E 'Number of entries' "$AIDE_LOG" | tail -1 | awk '{print $NF}' || true)"
echo "AIDE DB: /var/lib/aide/kalived.db.gz entries=${_entries:-?} (hash-dikt i $AIDE_LOG)" >&2
echo "Checksum: $(awk '{print $1}' "$ROOT/baselines/aide.sha256")" >&2
kalived_changelog "aide-init.sh" \
  "- AIDE kalived.db.gz init (identity/persistens). Gate: $verdict force=$FORCE force_alert=$FORCE_ALERT. Checksum i baselines/aide.sha256"
echo "DONE" >&2
