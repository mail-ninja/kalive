# shellcheck shell=bash

check_process() {
  if [[ -f "$OUT/hunt_deleted.txt" ]]; then
    if grep -q '^pid=' "$OUT/hunt_deleted.txt"; then
      local hits
      hits="$(grep '^pid=' "$OUT/hunt_deleted.txt" || true)"
      if echo "$hits" | grep -qE '/usr/lib/firefox|/usr/lib/chromium'; then
        add_finding WARN PROC-DELETED "Deleted exe under nettleser-path (mulig FP)" "$hits" "hunt_deleted.txt"
      else
        add_finding ALERT PROC-DELETED "Kjørende binær er (deleted) eller memfd" "$hits" "hunt_deleted.txt"
      fi
      if echo "$hits" | grep -q 'memfd:'; then
        add_finding ALERT PROC-MEMFD "memfd-exec" "$hits" "hunt_deleted.txt"
      fi
    fi
  elif kalived_is_live; then
    add_finding WARN SUDO-MISS-DELETED "hunt_deleted.txt mangler" "" "hunt_deleted.txt"
  fi

  if [[ -f "$OUT/hunt_ps.txt" ]]; then
    local names
    names="$(grep -iE 'ngrok|anydesk|rustdesk|meterpreter|logkeys|pynput|teamviewer|todesk' "$OUT/hunt_ps.txt" \
      | grep -v grep | grep -v keylogscan || true)"
    if [[ -n "$names" ]]; then
      add_finding ALERT PROC-NAME "Kjørende prosess treffer bakdør-/RAT-navn (supplement, ikke evidens alene)" \
        "$names" "hunt_ps.txt"
    fi
  fi

  local f="$OUT/hunt_input.txt"
  if [[ ! -f "$f" ]]; then
    if kalived_is_live; then
      add_finding WARN SUDO-MISS-INPUT "/dev/input/event* ikke dumpet" "" "hunt_input.txt"
    else
      add_finding INFO SNAP-MISS "hunt_input.txt ikke i snapshotet" "" "hunt_input.txt"
    fi
    return 0
  fi
  local allow="$ROOT/baselines/machine/input_holders.allow"
  local py
  py="$(command -v python3 || command -v python || true)"
  [[ -n "$py" ]] || return 0
  "$py" - "$f" "$allow" << 'PY'
import os, sys
lsof, allowp = sys.argv[1], sys.argv[2]
allow = set()
if os.path.isfile(allowp):
    for line in open(allowp, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#"):
            allow.add(line)
unknown = []
for line in open(lsof, encoding="utf-8", errors="replace"):
    if line.startswith("COMMAND") or "lsof failed" in line:
        continue
    parts = line.split()
    if len(parts) < 2:
        continue
    cmd = parts[0]
    if cmd in allow:
        continue
    unknown.append(line.strip())
if unknown:
    open(lsof + ".unknown", "w").write("\n".join(unknown))
PY
  if [[ -s "$f.unknown" ]]; then
    add_finding ALERT PROC-INPUT "Ukjent holder av /dev/input/event*" "$(cat "$f.unknown")" "hunt_input.txt"
    rm -f "$f.unknown"
  else
    rm -f "$f.unknown"
  fi
}
