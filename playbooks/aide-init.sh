#!/usr/bin/env bash
# Path-scoped AIDE freeze by default (overlay JSON). Does NOT run aide --init.
# Default --paths: sudoers.d/kalived + helper/ctl + kalived-watch units.
# Proton-snap, udev 70-snap.proton-vpn.rules og snapd-mount forblir åpne WARN.
# --all: full DB-rebuild. Proton forsvinner da fra FIM til neste reelle endring.
# Confirm / kalived-ctl kaller ALDRI --all (bare --force).
# --force: hopp over always_prompt / clean_only. NEKTES ved siste verdict ALERT|ERROR.
# --force-alert: re-baseline selv om siste scan er ALERT (kun etter evidens er lagret).
# Rollback scoped: rm -f ~/.config/kalived/aide-scope.json /var/lib/aide/kalived-scope.json
# Rollback --all: rm -f /var/lib/aide/kalived.db.gz /etc/aide/kalived.conf
set -euo pipefail
DRY="${KALIVED_AIDE_INIT_DRY:-0}"
if [[ "$DRY" != "1" && "$(id -u)" -ne 0 ]]; then
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
ALL=0
PATHS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift ;;
    --force-alert) FORCE=1; FORCE_ALERT=1; shift ;;
    --all) ALL=1; shift ;;
    --paths)
      IFS=',' read -ra PATHS <<< "${2:-}"
      shift 2
      ;;
    --paths=*)
      IFS=',' read -ra PATHS <<< "${1#--paths=}"
      shift
      ;;
    *)
      echo "ukjent flagg: $1 (gyldig: --force | --force-alert | --all | --paths p1,p2)" >&2
      exit 2
      ;;
  esac
done
if [[ ${#PATHS[@]} -eq 0 ]]; then
  mapfile -t PATHS < <(python3 -c "import sys; sys.path.insert(0, sys.argv[1]); from aide_classify import DEFAULT_SCOPE; print('\n'.join(DEFAULT_SCOPE))" "$ROOT/scripts/lib")
fi
if [[ "$FORCE_ALERT" == "1" ]]; then
  echo "aide-init --force-alert: hopper over ALERT-gate (evidens må allerede være lagret)" >&2
else
  kalived_require_not_alert
fi
if [[ "$FORCE" == "1" && "$FORCE_ALERT" != "1" ]]; then
  echo "aide-init --force: bevisst re-baseline (ALERT-gate gjelder fortsatt). WARN er lov." >&2
fi
kalived_config_load || exit 3

POLICY="${KALIVED_AIDE_INIT_POLICY:-$CFG_AIDE_INIT_POLICY}"
if [[ "$FORCE" != "1" && "$POLICY" == "always_prompt" ]]; then
  if [[ ! -t 0 ]]; then
    echo "GATE FAIL: aide_init_policy=always_prompt og ingen TTY" >&2
    exit 2
  fi
  read -r -p "Init AIDE (scoped, ikke Proton) på denne hosten? [y/N] " ans
  [[ "$ans" == "y" || "$ans" == "Y" ]] || exit 2
fi
dir="$(kalived_latest_scan_dir)"
verdict="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('verdict',''))" "$dir/verdict.json")"
if [[ "$FORCE" != "1" && "$POLICY" == "clean_only" && "$verdict" != "CLEAN" ]]; then
  echo "GATE FAIL: aide_init_policy=clean_only og verdict=$verdict" >&2
  exit 2
fi

if [[ "$ALL" == "1" ]]; then
  cat >&2 << 'EOF'
FULL AIDE-DB REBUILD (--all).
Proton-snap, udev 70-snap.proton-vpn.rules og snapd-mount forsvinner fra FIM
til neste reelle endring. Confirm i Hiroshima kaller IKKE --all.
EOF
  if [[ "$DRY" == "1" ]]; then
    echo "DRY: skip aide --init" >&2
    exit 0
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
  kalived_changelog "aide-init.sh --all" \
    "- FULL AIDE-DB. Proton borte fra FIM til neste reelle endring. Gate: $verdict force=$FORCE force_alert=$FORCE_ALERT."
  echo "DONE" >&2
  exit 0
fi

echo "scoped aide-init: fryser kalived-filer, ikke Proton" >&2
echo "paths: ${PATHS[*]}" >&2
dest="${KALIVED_AIDE_SCOPE:-}"
if [[ -z "$dest" ]]; then
  dest="$(kalived_owner_home)/.config/kalived/aide-scope.json"
fi
python3 "$ROOT/scripts/lib/aide_classify.py" write-scope "$dest" "${PATHS[@]}"
if [[ "$DRY" != "1" && "$(id -u)" -eq 0 ]]; then
  install -m 600 "$dest" /var/lib/aide/kalived-scope.json 2>/dev/null || {
    mkdir -p /var/lib/aide
    install -m 600 "$dest" /var/lib/aide/kalived-scope.json
  }
  owner="${KALIVED_OWNER:-${SUDO_USER:-}}"
  if [[ -n "$owner" && "$owner" != "root" ]]; then
    chown "${owner}:${owner}" "$dest" 2>/dev/null || true
  fi
fi
if [[ "$DRY" != "1" ]]; then
  kalived_changelog "aide-init.sh (scoped)" \
    "- overlay $dest. Fryser kalived-filer, ikke Proton. Gate: $verdict force=$FORCE force_alert=$FORCE_ALERT."
fi
echo "AIDE scope: $dest (Proton/snapd/udev åpne)" >&2
echo "DONE" >&2
