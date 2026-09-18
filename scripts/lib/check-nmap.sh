# shellcheck shell=bash

check_nmap() {
  local f="$OUT/hunt_nmap.txt"
  local g="$OUT/hunt_nmap.gnmap"
  if [[ ! -f "$f" && ! -f "$g" ]]; then
    if kalived_is_live && [[ "${CFG_NMAP_LOCALHOST:-1}" == "1" ]]; then
      add_finding INFO NET-NMAP "nmap-dump mangler" "" "hunt_nmap.txt"
    fi
    return 0
  fi
  if grep -q 'nmap missing' "$f" 2>/dev/null; then
    add_finding INFO NET-NMAP "nmap ikke installert" "" "hunt_nmap.txt"
    return 0
  fi
  if grep -q 'nmap_localhost=0' "$f" 2>/dev/null; then
    return 0
  fi
  local py
  py="$(command -v python3 || command -v python || true)"
  [[ -n "$py" ]] || return 0
  local tmp
  tmp="$(mktemp)"
  if ! "$py" - "${g:-/dev/null}" "$OUT/ss_tulpn.txt" "$tmp" << 'PY'
import re, sys, os
gnmap, ss, dst = sys.argv[1], sys.argv[2], sys.argv[3]
nmap_ports = set()
if os.path.isfile(gnmap):
    for line in open(gnmap, encoding="utf-8", errors="replace"):
        if "Ports:" not in line:
            continue
        for m in re.finditer(r"(\d+)/open/tcp", line):
            nmap_ports.add(int(m.group(1)))
ss_ports = set()
if os.path.isfile(ss):
    for line in open(ss, encoding="utf-8", errors="replace"):
        if "LISTEN" not in line:
            continue
        m = re.search(r"(\d+\.\d+\.\d+\.\d+|\[::\]|\[::1\]|\*|0\.0\.0\.0):(\d+)", line)
        if not m:
            continue
        host, port = m.group(1), int(m.group(2))
        if host in ("127.0.0.1", "::1", "0.0.0.0", "*", "[::]", "[::1]"):
            ss_ports.add(port)
hidden = sorted(nmap_ports - ss_ports)
missing = sorted(ss_ports - nmap_ports)
open(dst, "w", encoding="utf-8").write(
    "hidden=" + ",".join(map(str, hidden)) + "\n"
    + "ss_only=" + ",".join(map(str, missing)) + "\n"
)
PY
  then
    add_finding ERROR SCAN "nmap-parser krasjet" "" "hunt_nmap.txt"
    rm -f "$tmp"
    return 0
  fi
  local hidden ss_only
  hidden="$(grep '^hidden=' "$tmp" | cut -d= -f2-)"
  ss_only="$(grep '^ss_only=' "$tmp" | cut -d= -f2-)"
  rm -f "$tmp"
  if [[ -n "$hidden" ]]; then
    add_finding ALERT NET-NMAP "nmap ser åpen TCP på 127.0.0.1 som ss ikke viser: $hidden" \
      "ss vs nmap dual-source" "hunt_nmap.gnmap"
  fi
  if [[ -n "$ss_only" ]]; then
    add_finding INFO NET-NMAP "ss LISTEN som nmap ikke bekreftet på 127.0.0.1: $ss_only" \
      "typisk timing eller kun-LAN bind" "hunt_nmap.gnmap"
  fi
  if [[ -f "$OUT/hunt_nmap_sv.txt" ]] && grep -qiE 'meterpreter|backdoor|trojan' "$OUT/hunt_nmap_sv.txt"; then
    add_finding ALERT NET-NMAP-SVC "nmap -sV: tjenestenavn ser ut som bakdør" \
      "$(grep -iE 'meterpreter|backdoor|trojan' "$OUT/hunt_nmap_sv.txt" | head -10)" \
      "hunt_nmap_sv.txt"
  fi
}
