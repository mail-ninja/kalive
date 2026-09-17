# shellcheck shell=bash
# SSH / enheter fra sec_units.txt (ikke live systemctl i fixture).

check_units() {
  local f="$OUT/sec_units.txt"
  if [[ ! -f "$f" ]]; then
    if kalived_is_live; then
      add_finding ERROR SCAN "mangler sec_units.txt" "collect ufullstendig" "sec_units.txt"
    else
      add_finding INFO SNAP-MISS "sec_units.txt ikke i dette snapshotet" "" "sec_units.txt"
    fi
    return 0
  fi
  local ssh_active ssh_enabled
  ssh_active="$(grep -i 'ssh active:' "$f" | awk '{print $NF}' | tail -1 || true)"
  ssh_enabled="$(grep -iE 'ssh (enabled|is-enabled):' "$f" | awk '{print $NF}' | tail -1 || true)"
  if [[ "$ssh_active" == "active" ]]; then
    add_finding ALERT NET-SSH-UNIT "SSH-server kjører" "sec_units: ssh active: $ssh_active" "sec_units.txt"
  fi
  if [[ "$ssh_enabled" == "enabled" ]]; then
    add_finding ALERT NET-SSH-UNIT "SSH-server er enabled" "sec_units: $ssh_enabled" "sec_units.txt"
  fi
  return 0
}
