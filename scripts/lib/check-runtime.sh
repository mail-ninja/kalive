# shellcheck shell=bash
# HOST-RUNTIME: lokal pin-tabell + php-fpm/apache-lyttere. WARN. Ingen apt. Ingen sky.

check_runtime() {
  local py
  py="$(command -v python3 || command -v python || true)"
  [[ -n "$py" ]] || return 0
  local pins="$ROOT/baselines/machine/runtime-pins.json"
  FINDINGS_JSONL="${FINDINGS_JSONL:-$OUT/findings.jsonl}"
  if ! "$py" - "$ROOT/scripts/lib" "$pins" "$OUT" "$FINDINGS_JSONL" << 'PY'
import json, sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from runtime_pins import findings_from_snapshot

pins = Path(sys.argv[2])
out = Path(sys.argv[3])
dst = Path(sys.argv[4])
recs = findings_from_snapshot(out, pins)
with dst.open("a", encoding="utf-8") as fh:
    for rec in recs:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
PY
  then
    add_finding ERROR SCAN "runtime-sil krasjet" "se scan.log" "runtime_versions.json"
  fi
}
