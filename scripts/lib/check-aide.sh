# shellcheck shell=bash
# One finding per AIDE class. INFO does not raise. No early-return after sudoers.

check_aide() {
  local f="$OUT/aide_check.txt"
  if [[ ! -f "$f" || ! -s "$f" ]]; then
    add_finding INFO FIM-AIDE "AIDE-sjekk ikke i snapshotet (kjør playbooks/aide-init.sh, så ny scan)" "" "aide_check.txt"
    return 0
  fi
  local py
  py="$(command -v python3 || command -v python || true)"
  if [[ -z "$py" ]]; then
    add_finding ERROR SCAN "python3 mangler for AIDE-klassifisering" "" "aide_check.txt"
    return 0
  fi
  FINDINGS_JSONL="${FINDINGS_JSONL:-$OUT/findings.jsonl}"
  if ! "$py" - "$ROOT/scripts/lib" "$f" "$FINDINGS_JSONL" << 'PY'
import json, sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from aide_classify import findings_from_report, load_scope, scope_path

text = Path(sys.argv[2]).read_text(encoding="utf-8", errors="replace")
recs = findings_from_report(text, load_scope(scope_path()))
with open(sys.argv[3], "a", encoding="utf-8") as fh:
    for rec in recs:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
PY
  then
    add_finding ERROR SCAN "AIDE-klassifisering krasjet" "" "aide_check.txt"
  fi
}
