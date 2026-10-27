# shellcheck shell=bash
# One finding per AIDE class. INFO does not raise. No early-return after sudoers.
# Identity + dpkg-eid + (mtime i vindu | binær med configure i scan-vindu) → FIM-AIDE-PKG.
# Identity + dpkg-eid + debsums OK + ikke i vinduet → FIM-AIDE-STALE.
# Added uten AIDE-Mtime: file_mtime.txt / live stat.

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
  if kalived_is_live; then
    if [[ -f /var/log/dpkg.log ]]; then
      tail -n 8000 /var/log/dpkg.log > "$OUT/dpkg.log" 2>/dev/null || true
    fi
    if [[ -f /var/log/dpkg.log.1 ]]; then
      tail -n 8000 /var/log/dpkg.log.1 > "$OUT/dpkg.log.1" 2>/dev/null || true
    fi
    if command -v dpkg >/dev/null 2>&1; then
      local paths tmpo
      paths="$(mktemp)"
      tmpo="$(mktemp)"
      if "$py" - "$ROOT/scripts/lib" "$f" "$paths" << 'PY'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from aide_classify import identity_paths
text = Path(sys.argv[2]).read_text(encoding="utf-8", errors="replace")
Path(sys.argv[3]).write_text("\n".join(identity_paths(text)) + "\n", encoding="utf-8")
PY
      then
        : > "$OUT/file_mtime.txt"
        while IFS= read -r p || [[ -n "$p" ]]; do
          [[ -z "$p" ]] && continue
          dpkg -S "$p" 2>/dev/null || true
          parent="${p%/*}"
          if [[ -n "$parent" && "$parent" != "$p" && "$parent" == /etc/ssh* ]]; then
            dpkg -S "$parent" 2>/dev/null || true
          fi
          if [[ -e "$p" ]]; then
            stat -c '%Y %n' "$p" >> "$OUT/file_mtime.txt" 2>/dev/null || true
          fi
        done < "$paths" > "$tmpo" || true
        mv "$tmpo" "$OUT/dpkg_owned.txt"
        "$py" - "$ROOT/scripts/lib" "$paths" "$OUT/dpkg_owned.txt" "$OUT/debsums.txt" << 'PY' || true
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from aide_classify import write_debsums_txt
paths = [ln.strip() for ln in Path(sys.argv[2]).read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
write_debsums_txt(paths, Path(sys.argv[3]), Path(sys.argv[4]))
PY
      else
        rm -f "$tmpo"
      fi
      rm -f "$paths"
    fi
  fi
  FINDINGS_JSONL="${FINDINGS_JSONL:-$OUT/findings.jsonl}"
  if ! "$py" - "$ROOT/scripts/lib" "$f" "$FINDINGS_JSONL" "$OUT" << 'PY'
import json, sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from aide_classify import findings_from_report, load_scope, scope_path

text = Path(sys.argv[2]).read_text(encoding="utf-8", errors="replace")
out_dir = Path(sys.argv[4])
recs = findings_from_report(text, load_scope(scope_path()), out_dir)
with open(sys.argv[3], "a", encoding="utf-8") as fh:
    for rec in recs:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
PY
  then
    add_finding ERROR SCAN "AIDE-klassifisering krasjet" "" "aide_check.txt"
  fi
}
