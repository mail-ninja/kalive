# shellcheck shell=bash
# Extra UID 0.

check_passwd() {
  local f="$OUT/passwd.txt"
  if [[ ! -f "$f" ]]; then
    if kalived_is_live; then
      add_finding ERROR SCAN "mangler passwd.txt" "" "passwd.txt"
    else
      add_finding INFO SNAP-MISS "passwd.txt ikke i dette snapshotet" "" "passwd.txt"
    fi
    return 0
  fi
  local extra
  extra="$(awk -F: '$3==0 && $1!="root" {print $1}' "$f" || true)"
  if [[ -n "$extra" ]]; then
    add_finding ALERT PERS-UID0 "Ekstra UID 0-konto: $extra" "$extra" "passwd.txt"
  fi
  return 0
}
