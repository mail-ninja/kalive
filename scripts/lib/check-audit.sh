# shellcheck shell=bash

check_audit() {
  local rules="$OUT/audit_rules.txt"
  local units="$OUT/sec_units.txt"
  if [[ ! -f "$rules" || ! -s "$rules" ]]; then
    add_finding INFO LOG-AUDIT "auditd-playbook ikke samlet i dette snapshotet (kjør playbooks/auditd-mini.sh hvis ikke gjort)" "" "audit_rules.txt"
    return 0
  fi
  if ! grep -q kalived_preload "$rules"; then
    add_finding WARN LOG-AUDIT "99-kalived.rules mangler kalived_preload" "" "audit_rules.txt"
  fi
  if grep -vE '^\s*#' "$rules" | grep -q kalived_usb; then
    add_finding WARN LOG-AUDIT "USB-auditregel er aktiv (forventet kommentert)" "" "audit_rules.txt"
  fi
  if [[ -f "$units" ]] && grep -q 'auditd active: inactive' "$units"; then
    add_finding WARN LOG-AUDIT "auditd er inactive etter at regler er installert" "" "sec_units.txt"
  fi
}

check_journald() {
  local f="$OUT/journald_kalived.txt"
  if [[ ! -f "$f" || ! -s "$f" ]]; then
    add_finding INFO LOG-JOURNAL "journald drop-in ikke i snapshotet (kjør playbooks/journald-persistent.sh)" "" "journald_kalived.txt"
    return 0
  fi
  if ! grep -q 'Storage=persistent' "$f"; then
    add_finding WARN LOG-JOURNAL "journald Storage er ikke persistent" "$(cat "$f")" "journald_kalived.txt"
  fi
}
