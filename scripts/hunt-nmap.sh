#!/usr/bin/env bash
# TCP connect-scan 127.0.0.1 only. Never LAN.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${KALIVED_OUT:?}"
mkdir -p "$OUT"
if [[ "${KALIVED_FIXTURE:-0}" == "1" || "${KALIVED_FROM_DIR:-0}" == "1" ]]; then
  exit 0
fi
if [[ "${CFG_NMAP_LOCALHOST:-1}" != "1" ]]; then
  echo "nmap_localhost=0" > "$OUT/hunt_nmap.txt"
  exit 0
fi
if ! command -v nmap >/dev/null 2>&1; then
  echo "nmap missing" > "$OUT/hunt_nmap.txt"
  exit 0
fi
spec="${CFG_NMAP_PORT_SPEC:--}"
case "$spec" in
  "-"|"") p="-" ;;
  *) p="$spec" ;;
esac
echo "[*] nmap -sT 127.0.0.1 -p ${p} (localhost only)" >&2
# -n no DNS, -Pn skip host discovery, --open only open, never other targets
nmap -n -Pn -sT --open -p "$p" 127.0.0.1 -oG "$OUT/hunt_nmap.gnmap" -oN "$OUT/hunt_nmap.txt" >/dev/null 2>&1 || true
echo "target=127.0.0.1 port_spec=$p" >> "$OUT/hunt_nmap.txt"
echo "[+] nmap localhost done" >&2
