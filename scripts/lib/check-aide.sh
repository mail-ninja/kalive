# shellcheck shell=bash

check_aide() {
  local f="$OUT/aide_check.txt"
  if [[ ! -f "$f" || ! -s "$f" ]]; then
    add_finding INFO FIM-AIDE "AIDE-sjekk ikke i snapshotet (kjør playbooks/aide-init.sh, så ny scan)" "" "aide_check.txt"
    return 0
  fi
  if grep -qiE 'There are no differences|AIDE found NO|Nothing to do|failed to open.*No such file' "$f"; then
    if grep -qiE 'failed to open|No such file' "$f"; then
      add_finding INFO FIM-AIDE "AIDE-DB mangler ennå" "$(head -5 "$f")" "aide_check.txt"
      return 0
    fi
    return 0
  fi
  # /etc/sudoers.d/kalived is our drop-in — WARN so aide-init gate still works after install-nopasswd-ctl.
  if grep -qE '/etc/passwd|/etc/shadow|/etc/ld.so.preload|/etc/ssh/|/usr/bin/sudo' "$f" \
    || grep -qE 'f[+]+: /etc/sudoers$' "$f"; then
    add_finding ALERT FIM-AIDE "AIDE: endring i identitet/persistens-fil" \
      "$(grep -E 'passwd|shadow|preload|sudoers|/etc/ssh|usr/bin/sudo' "$f" | head -40)" "aide_check.txt"
    return 0
  fi
  if grep -q '/etc/sudoers.d/kalived' "$f"; then
    add_finding WARN FIM-AIDE "AIDE: /etc/sudoers.d/kalived (vår NOPASSWD-drop-in). Kjør aide-init for å fryse." \
      "$(grep sudoers "$f" | head -20)" "aide_check.txt"
    return 0
  fi
  if grep -q '/etc/sudoers.d/' "$f"; then
    add_finding ALERT FIM-AIDE "AIDE: ukjent endring under /etc/sudoers.d" \
      "$(grep sudoers "$f" | head -40)" "aide_check.txt"
    return 0
  fi
  if grep -qiE 'File added|File removed|changed|Entries changed|Changed entries' "$f"; then
    local names
    names="$(grep -E '^f |^d |File: ' "$f" | sed 's/.*: //;s/^File: //' | grep -E '^/' | head -8 | tr '\n' ' ')"
    add_finding WARN FIM-AIDE "AIDE endret: ${names:-se aide_check.txt}" "$(grep -E 'Added|Removed|Changed|File: |^f |^d ' "$f" | head -30)" "aide_check.txt"
  fi
}
