# shellcheck shell=bash
# Falco alene = WARN (candidate). Falco + FIM eller Falco + nett = ALERT.
# Tom jsonl = ingen finding. falco absent = INFO, ikke ERROR.

check_falco() {
  local jsonl="$OUT/hunt_falco.jsonl"
  local note="$OUT/hunt_falco.txt"
  local py
  py="$(command -v python3 || command -v python || true)"
  if [[ -z "$py" ]]; then
    return 0
  fi
  if [[ -f "$note" ]] && grep -qiE 'falco missing|falco absent' "$note"; then
    add_finding INFO HOST-FALCO "falco absent" \
      "Falco-pakke mangler. sudo bash playbooks/install-falco-host.sh printer apt-kommando." \
      "hunt_falco.txt"
    return 0
  fi
  if [[ -f "$note" ]] && grep -qi 'falco rules rejected' "$note"; then
    add_finding INFO HOST-FALCO "falco rules rejected" \
      "Host-regler lastet ikke (Undefined macro / falco rc≠0). Se hunt_falco.err. Ikke stock falco_rules.yaml." \
      "hunt_falco.err"
    return 0
  fi
  if [[ ! -f "$jsonl" ]]; then
    if kalived_is_live; then
      add_finding INFO HOST-FALCO "falco-burst ikke i snapshotet" \
        "sudo kalived-ctl falco-burst" "hunt_falco.jsonl"
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
from falco_burst import findings_from_rows, load_jsonl, _finding_ids

rows = load_jsonl(Path(sys.argv[2]))
ids = _finding_ids(Path(sys.argv[3]))
recs = findings_from_rows(rows, ids=ids)
with open(sys.argv[3], "a", encoding="utf-8") as fh:
    for rec in recs:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
PY
  then
    add_finding ERROR SCAN "Falco-klassifisering krasjet" "" "hunt_falco.jsonl"
  fi
}
