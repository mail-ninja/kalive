#!/usr/bin/env bash
# Harvest Suricata eve.json → hunt_suricata.jsonl under a stamp (sid, signature, app_proto, exe).
# Unit is always-on while the link is up (not an 8s burst). Scan only copies a redacted extract.
# Never ~/.config/kalived/hiroshima/. Never Qdrant. Never dest-IP/SNI/payload/pcap.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
# shellcheck source=lib/kalived-config.sh
source "$ROOT/scripts/lib/kalived-config.sh"

if [[ -n "${KALIVED_OUT:-}" ]]; then
  OUT="$KALIVED_OUT"
else
  STAMP="$(date +%Y-%m-%d_%H%M%S)"
  OUT="${KALIVED_DATA:-$ROOT}/logs/status/$STAMP"
  if [[ -e "$OUT" ]]; then
    OUT="${OUT}_$$"
  fi
fi
mkdir -p "$OUT"
NOTE="$OUT/hunt_suricata.txt"
JSONL="$OUT/hunt_suricata.jsonl"
LIB="$ROOT/scripts/lib/suricata_eve.py"
EVE="${KALIVED_SURICATA_EVE:-/var/log/suricata/eve.json}"
SS="$OUT/ss_established.txt"

_suri_own() {
  kalived_chown_owner_0600 "$NOTE"
  kalived_chown_owner_0600 "$JSONL"
}
trap _suri_own EXIT

case "$OUT" in
  */.config/kalived/hiroshima|*/.config/kalived/hiroshima/*)
    echo "GATE: Suricata skriver ikke til ~/.config/kalived/hiroshima/" >&2
    exit 2
    ;;
esac

if [[ "${KALIVED_SURICATA_DRY:-0}" == "1" ]]; then
  echo "suricata dry harvest" > "$NOTE"
  : > "$JSONL"
  echo "DRY suricata harvest → $JSONL" >&2
  echo "DONE" >&2
  exit 0
fi

if ! command -v suricata >/dev/null 2>&1 && [[ -z "${KALIVED_SURICATA_EVE:-}" ]]; then
  echo "suricata missing" > "$NOTE"
  : > "$JSONL"
  echo "[*] suricata absent — hopp over harvest (playbooks/install-suricata-host.sh printer apt)" >&2
  echo "DONE" >&2
  exit 0
fi

if [[ ! -f "$EVE" ]]; then
  echo "suricata eve empty" > "$NOTE"
  : > "$JSONL"
  echo "[*] suricata eve mangler — tom jsonl" >&2
  echo "DONE" >&2
  exit 0
fi

ss_arg=()
if [[ -f "$SS" ]]; then
  ss_arg=("$SS")
fi
python3 "$LIB" aggregate "$EVE" "$JSONL" "${ss_arg[@]}" >/dev/null
n=0
if [[ -s "$JSONL" ]]; then
  n="$(wc -l < "$JSONL" | tr -d ' ')"
fi
echo "eve=$EVE alerts=$n" > "$NOTE"
echo "DONE suricata harvest → $JSONL alerts=$n" >&2
exit 0
