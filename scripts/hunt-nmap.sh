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
# Sieve 3: -sV only on already-open ports we do *not* already know.
# Skip 8787 (HTTP kalived-api), 45959 (containerd), 7878 (svl) — -sV TLS/http
# probes against those produce 400 / RST in our own logs.
if [[ "${CFG_NMAP_SVC_PROBE:-1}" == "1" && -f "$OUT/hunt_nmap.gnmap" ]]; then
  _skip="8787 45959 7878 ${CFG_LISTEN_PORT:-}"
  _svports=""
  for _p in $(grep -oE '[0-9]+/open/tcp' "$OUT/hunt_nmap.gnmap" | cut -d/ -f1 | sort -n | uniq); do
    _known=0
    for _s in $_skip; do
      [[ "$_p" == "$_s" ]] && _known=1 && break
    done
    [[ "$_known" == "1" ]] && continue
    _svports="${_svports:+$_svports,}$_p"
  done
  if [[ -n "$_svports" ]]; then
    echo "[*] nmap -sV -p ${_svports} 127.0.0.1 (open, unknown)" >&2
    nmap -n -Pn -sV --version-intensity 2 -p "$_svports" 127.0.0.1 \
      -oN "$OUT/hunt_nmap_sv.txt" >/dev/null 2>&1 || true
  else
    echo "sV skipped known lo ports (8787/45959/7878)" > "$OUT/hunt_nmap_sv.txt"
  fi
fi
echo "[+] nmap localhost done" >&2
