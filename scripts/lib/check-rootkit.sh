# shellcheck shell=bash

_allow_hit() {
  local line="$1" allowf="$2"
  [[ -f "$allowf" ]] || return 1
  local tok
  while IFS= read -r tok || [[ -n "$tok" ]]; do
    [[ -z "$tok" || "$tok" == \#* ]] && continue
    if echo "$line" | grep -qF "$tok"; then
      return 0
    fi
  done < "$allowf"
  return 1
}

check_rootkit() {
  local allow_rk="$ROOT/defs/kali-allow/rkhunter-allow.txt"
  local allow_ck="$ROOT/defs/kali-allow/chkrootkit-allow.txt"
  local rk="$OUT/hunt_rkhunter.txt"
  local ck="$OUT/hunt_chkrootkit.txt"

  if [[ ! -f "$rk" ]]; then
    add_finding INFO ROOT-RKH "rkhunter-output mangler (kjør playbooks/rkhunter-setup.sh)" "" "hunt_rkhunter.txt"
  elif grep -q 'rkhunter missing' "$rk"; then
    add_finding INFO ROOT-RKH "rkhunter ikke installert" "" "hunt_rkhunter.txt"
  else
    local alerts="" warns=""
    while IFS= read -r line || [[ -n "$line" ]]; do
      [[ -z "$line" ]] && continue
      if echo "$line" | grep -qiE 'INFECTED|Rootkit module found|possible rootkit'; then
        if _allow_hit "$line" "$allow_rk"; then
          continue
        fi
        alerts+="$line"$'\n'
        continue
      fi
      if echo "$line" | grep -qiE '^Warning'; then
        if _allow_hit "$line" "$allow_rk"; then
          continue
        fi
        warns+="$line"$'\n'
      fi
    done < "$rk"
    if [[ -n "$alerts" ]]; then
      add_finding ALERT ROOT-RKH "rkhunter: mulig rootkit etter Kali-whitelist" "$alerts" "hunt_rkhunter.txt"
    fi
    if [[ -n "$warns" ]]; then
      add_finding WARN ROOT-RKH "rkhunter warnings ikke i kali-allow" "$warns" "hunt_rkhunter.txt"
    fi
  fi

  if [[ ! -f "$ck" ]]; then
    add_finding INFO ROOT-RKH "chkrootkit-output mangler" "" "hunt_chkrootkit.txt"
  elif grep -q 'chkrootkit missing' "$ck"; then
    add_finding INFO ROOT-RKH "chkrootkit ikke installert" "" "hunt_chkrootkit.txt"
  else
    local calerts="" cwarns=""
    while IFS= read -r line || [[ -n "$line" ]]; do
      [[ -z "$line" ]] && continue
      # Section headers are not infections.
      if echo "$line" | grep -qE '^WARNING: The following suspicious files|^WARNING: Output from ifpromisc'; then
        continue
      fi
      if echo "$line" | grep -q '\[From Debian package:'; then
        continue
      fi
      if echo "$line" | grep -qE 'PACKET SNIFFER\(/usr/sbin/NetworkManager|PACKET SNIFFER\(/usr/sbin/wpa_supplicant|PACKET SNIFFER\(/usr/sbin/tcpdump'; then
        continue
      fi
      if _allow_hit "$line" "$allow_ck"; then
        continue
      fi
      if echo "$line" | grep -qiE 'INFECTED|infested|Rootkit'; then
        calerts+="$line"$'\n'
        continue
      fi
      if echo "$line" | grep -qE 'PACKET SNIFFER\('; then
        cwarns+="$line"$'\n'
        continue
      fi
      if echo "$line" | grep -qE '^/'; then
        cwarns+="$line"$'\n'
      fi
    done < "$ck"
    if [[ -n "$calerts" ]]; then
      add_finding ALERT ROOT-RKH "chkrootkit treff etter Kali-whitelist" "$calerts" "hunt_chkrootkit.txt"
    fi
    if [[ -n "$cwarns" ]]; then
      add_finding WARN ROOT-RKH "chkrootkit støy ikke i kali-allow" "$cwarns" "hunt_chkrootkit.txt"
    fi
  fi

  if [[ -f "$OUT/hunt_bpf.txt" ]] && ! grep -q 'bpftool missing' "$OUT/hunt_bpf.txt"; then
    if [[ -s "$OUT/hunt_bpf.txt" ]] && grep -qE 'id [0-9]' "$OUT/hunt_bpf.txt"; then
      add_finding WARN ROOT-BPF "bpftool viser programmer (sjekk manuelt)" "$(head -15 "$OUT/hunt_bpf.txt")" "hunt_bpf.txt"
    fi
  fi
}
