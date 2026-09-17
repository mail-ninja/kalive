# shellcheck shell=bash

check_kernel() {
  local t="$OUT/kernel_taint.txt"
  if [[ -f "$t" ]]; then
    local val
    val="$(tr -d ' \n' < "$t")"
    if [[ -n "$val" && "$val" != "0" && "$val" != "?" ]]; then
      add_finding WARN ROOT-TAINT "kernel tainted=$val (proprietary driver mulig)" "$val" "kernel_taint.txt"
    fi
  elif kalived_is_live; then
    add_finding INFO ROOT-TAINT "kernel_taint.txt mangler" "" "kernel_taint.txt"
  fi

  local ls="$OUT/lsmod.txt"
  local exp="$ROOT/baselines/machine/lsmod.expected"
  if [[ -f "$ls" && -s "$exp" ]]; then
    local extra
    extra="$(comm -13 <(sort -u "$exp") <(awk 'NR>1 {print $1}' "$ls" | sort -u) || true)"
    if [[ -n "$extra" ]]; then
      if echo "$extra" | grep -qiE 'hide|adore|knark|suterusu|diamorphine|reptile'; then
        add_finding ALERT ROOT-LSMOD "LKM-navn treffer kjent rootkit-familie: $extra" "$extra" "lsmod.txt"
      else
        add_finding WARN ROOT-LSMOD "Nye kernel-moduler vs freeze: $extra" "$extra" "lsmod.txt"
      fi
    fi
  fi

  local py
  py="$(command -v python3 || command -v python || true)"
  [[ -n "$py" ]] || return 0
  if [[ -f "$OUT/proc_net_tcp.txt" && -f "$OUT/ss_tulpn.txt" ]]; then
    local hidden
    hidden="$("$py" - "$OUT/proc_net_tcp.txt" "$OUT/ss_tulpn.txt" << 'PY'
import re, sys
proc, ss = sys.argv[1], sys.argv[2]

def parse_hex_ip_port(s):
    ip_h, port_h = s.split(":")
    port = int(port_h, 16)
    if len(ip_h) <= 8:
        b = bytes.fromhex(ip_h.zfill(8))
        ip = ".".join(str(x) for x in b[::-1])
    else:
        ip = ip_h  # v6 skip compare loosely
    return ip, port

listen_ss = set()
for line in open(ss, encoding="utf-8", errors="replace"):
    if "LISTEN" not in line:
        continue
    m = re.search(r"(\d+\.\d+\.\d+\.\d+|\[::\]|\[::1\]|\*):(\d+)", line)
    if m:
        listen_ss.add((m.group(1).strip("[]"), int(m.group(2))))
        if m.group(1) in ("0.0.0.0", "*"):
            listen_ss.add(("0.0.0.0", int(m.group(2))))

hidden = []
for line in open(proc, encoding="utf-8", errors="replace"):
    parts = line.split()
    if len(parts) < 10 or parts[0] in ("sl", "==="):
        continue
    st = parts[3]
    if st != "0A":
        continue
    try:
        ip, port = parse_hex_ip_port(parts[1])
    except Exception:
        continue
    if ip.startswith("127."):
        continue
    keys = [(ip, port), ("0.0.0.0", port), ("*", port)]
    if any(k in listen_ss for k in keys):
        continue
    # also match if ss has the port on 0.0.0.0
    if any(p == port and a in ("0.0.0.0", "*", ip) for a, p in listen_ss):
        continue
    hidden.append(f"{ip}:{port}")
print("\n".join(hidden[:20]))
PY
)"
    if [[ -n "$hidden" ]]; then
      add_finding ALERT ROOT-PROC-SS "LISTEN i /proc/net/tcp som ss ikke viser: $hidden" "$hidden" "proc_net_tcp.txt"
    fi
  fi
}

check_debsums() {
  local f="$OUT/hunt_debsums.txt"
  [[ -f "$f" ]] || return 0
  grep -q 'debsums missing' "$f" && return 0
  grep -q 'debsums clean' "$f" && return 0
  local crit
  crit="$(grep -E 'sudo|passwd|login|systemd|libc|ssh' "$f" | grep -viE 'OK$|clean' || true)"
  if [[ -n "$crit" ]]; then
    add_finding ALERT FIM-DEBSUMS "debsums mismatch på kjernepakke" "$crit" "hunt_debsums.txt"
    return 0
  fi
  if grep -qE 'FAILED|MISSING' "$f"; then
    add_finding WARN FIM-DEBSUMS "debsums rapporterer avvik" "$(head -20 "$f")" "hunt_debsums.txt"
  fi
}

check_dpkg_age() {
  local f="$OUT/dpkg_log_mtime.txt"
  [[ -f "$f" ]] || return 0
  local epoch
  epoch="$(awk '{print $1}' "$f")"
  [[ "$epoch" =~ ^[0-9]+$ ]] || return 0
  local now age
  now="$(date +%s)"
  age=$(( (now - epoch) / 86400 ))
  if [[ "$age" -gt 30 ]]; then
    add_finding WARN F-007 "Ingen dpkg-aktivitet på $age dager (Kali rolling, manuell upgrade)" "$(cat "$f")" "dpkg_log_mtime.txt"
  fi
}
