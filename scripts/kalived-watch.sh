#!/usr/bin/env bash
# One-shot egress sample: ss ESTAB + ausearch kalived_connect. Fields-only window 0600.
# Confirm: sudo kalived-ctl watch
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo kalived-ctl watch" >&2
  exit 1
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
# shellcheck source=lib/kalived-config.sh
source "$ROOT/scripts/lib/kalived-config.sh"
kalived_config_load || true
if [[ "${CFG_WATCH_TIMER:-}" == "0" ]]; then
  echo "watch_timer=false — hopp over (Settings)"
  exit 0
fi
OWNER="$(kalived_owner_name)"
if [[ -z "$OWNER" ]]; then
  echo "KALIVED_OWNER eller SUDO_USER kreves" >&2
  exit 1
fi
OWNER_HOME="${KALIVED_OWNER_HOME:-$(getent passwd "$OWNER" | cut -d: -f6)}"
export KALIVED_OWNER_HOME="$OWNER_HOME"
DEST="${OWNER_HOME}/.config/kalived/hiroshima"
HELPER="$ROOT/scripts/lib/hiroshima_watch.py"
TMP="$(mktemp -d /tmp/kalived-watch.XXXXXX)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

mkdir -p "$DEST"
chmod 700 "$DEST"

ss -tpn state established >"$TMP/ss_established.txt" 2>/dev/null || true

audit_status=missing
if command -v ausearch >/dev/null 2>&1; then
  if ausearch -k kalived_connect -ts recent >"$TMP/ausearch.txt" 2>/dev/null; then
    if [[ -s "$TMP/ausearch.txt" ]]; then
      audit_status=ok
    else
      audit_status=empty
    fi
  else
    : >"$TMP/ausearch.txt"
    if grep -qs kalived_connect /etc/audit/rules.d/*.rules 2>/dev/null; then
      audit_status=empty
    else
      audit_status=missing
    fi
  fi
fi

IFACE="$(ip -4 route show default 2>/dev/null | awk '/default/ {print $5; exit}')"
export KALIVED_WATCH_IFACE="${IFACE:-}"
export KALIVED_WATCH_AUDIT="$audit_status"
python3 "$HELPER" ingest "$TMP"
kalived_chown_owner_dir "$DEST"
echo "DONE watch dest=$DEST audit=$audit_status iface=${IFACE:-?}"
