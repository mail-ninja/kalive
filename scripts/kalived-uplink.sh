#!/usr/bin/env bash
# 30s tshark fields on the default uplink. Never -i any, never pcapng.
# Confirm: sudo kalived-ctl uplink-burst
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo kalived-ctl uplink-burst" >&2
  exit 1
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
# shellcheck source=lib/kalived-config.sh
source "$ROOT/scripts/lib/kalived-config.sh"
OWNER="$(kalived_owner_name)"
if [[ -z "$OWNER" ]]; then
  echo "KALIVED_OWNER eller SUDO_USER kreves" >&2
  exit 1
fi
OWNER_HOME="${KALIVED_OWNER_HOME:-$(getent passwd "$OWNER" | cut -d: -f6)}"
export KALIVED_OWNER_HOME="$OWNER_HOME"
DEST="${OWNER_HOME}/.config/kalived/hiroshima"
HELPER="$ROOT/scripts/lib/hiroshima_watch.py"
TMP="$(mktemp -d /tmp/kalived-uplink.XXXXXX)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

mkdir -p "$DEST"
chmod 700 "$DEST"

IFACE="$(ip -4 route show default 2>/dev/null | awk '/default/ {print $5; exit}')"
if [[ -z "$IFACE" || "$IFACE" == "lo" ]]; then
  echo "GATE: ingen uplink (default rute)" >&2
  exit 2
fi
if [[ "$IFACE" == "any" ]]; then
  echo "GATE: -i any er forbudt" >&2
  exit 2
fi

DUR="${UPLINK_DUR:-30}"
[[ "$DUR" =~ ^[0-9]+$ ]] || DUR=30
(( DUR >= 1 && DUR <= 30 )) || DUR=30
MAXP=4000

if [[ "${UPLINK_DRY:-0}" == "1" ]]; then
  echo "dry: skip tshark iface=$IFACE" >&2
  : >"$TMP/tshark_fields.txt"
else
  if ! command -v tshark >/dev/null 2>&1; then
    echo "tshark mangler" >&2
    exit 2
  fi
  echo "tshark $IFACE ${DUR}s fields" >&2
  timeout "$((DUR + 5))" tshark -i "$IFACE" -n -q \
    -a "duration:${DUR}" -c "$MAXP" \
    -f "tcp port 443 or tcp port 80 or udp port 53" \
    -T fields -E header=n -E separator=$'\t' \
    -e ip.dst -e ipv6.dst -e tcp.dstport \
    -e tls.handshake.extensions_server_name -e dns.qry.name \
    >"$TMP/tshark_fields.txt" 2>"$TMP/tshark.err" || true
fi

# Keep a current ss sample in the same window so isolate-hint still has ESTAB.
ss -tpn state established >"$TMP/ss_established.txt" 2>/dev/null || true

export KALIVED_WATCH_IFACE="$IFACE"
export KALIVED_WATCH_AUDIT="${KALIVED_WATCH_AUDIT:-empty}"
python3 "$HELPER" ingest "$TMP"
kalived_chown_owner_dir "$DEST"
echo "DONE uplink-burst iface=$IFACE dur=${DUR}s dest=$DEST"
