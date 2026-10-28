# shellcheck shell=bash
# Suricata alene = WARN (candidate). Suricata + FIM eller Suricata + nett = ALERT.
# Tom jsonl = ingen finding. suricata absent = INFO, ikke ERROR.

check_suricata() {
  local jsonl="$OUT/hunt_suricata.jsonl"
  local note="$OUT/hunt_suricata.txt"
  local py
  py="$(command -v python3 || command -v python || true)"
  if [[ -z "$py" ]]; then
    return 0
  fi
  if [[ -f "$note" ]] && grep -qiE 'suricata missing|suricata absent' "$note"; then
    add_finding INFO HOST-SURICATA "suricata absent" \
      "Suricata-pakke mangler. sudo bash playbooks/install-suricata-host.sh printer apt-kommando." \
      "hunt_suricata.txt"
    return 0
  fi
  if [[ ! -f "$jsonl" ]]; then
    if kalived_is_live; then
      add_finding INFO HOST-SURICATA "suricata harvest ikke i snapshotet" \
        "live scan skriver hunt_suricata.jsonl" "hunt_suricata.jsonl"
    fi
    return 0
  fi
  if [[ ! -s "$jsonl" ]]; then
    return 0
  fi
  FINDINGS_JSONL="${FINDINGS_JSONL:-$OUT/findings.jsonl}"
  if ! "$py" - "$ROOT/scripts/lib" "$jsonl" "$FINDINGS_JSONL" << 'PY'
import json, sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from suricata_eve import findings_from_rows, load_jsonl, _finding_ids

rows = load_jsonl(Path(sys.argv[2]))
ids = _finding_ids(Path(sys.argv[3]))
recs = findings_from_rows(rows, ids=ids)
with open(sys.argv[3], "a", encoding="utf-8") as fh:
    for rec in recs:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
PY
  then
    add_finding ERROR SCAN "Suricata-klassifisering krasjet" "" "hunt_suricata.jsonl"
  fi
}
