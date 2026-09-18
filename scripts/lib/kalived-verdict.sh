# shellcheck shell=bash
# Findings + banner + verdict.json. TITLE bokmål, ID engelsk.

FINDINGS_JSONL="${FINDINGS_JSONL:-}"

kalived_init_findings() {
  FINDINGS_JSONL="$OUT/findings.jsonl"
  : > "$FINDINGS_JSONL"
}

# add_finding SEVERITY ID TITLE DETAIL [SOURCE]
add_finding() {
  local sev="$1" id="$2" title="$3" detail="${4:-}" source="${5:-}"
  case "$sev" in
    ERROR|ALERT|WARN|INFO) ;;
    *) kalived_log "bad severity $sev"; sev=ERROR ;;
  esac
  if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
    printf '%s\n' "$sev $id $title" >> "$OUT/findings.txt"
    return 0
  fi
  local py
  py="$(command -v python3 || command -v python)"
  FINDINGS_JSONL="${FINDINGS_JSONL:-$OUT/findings.jsonl}"
  "$py" - "$FINDINGS_JSONL" "$sev" "$id" "$title" "$detail" "$source" << 'PY'
import json, sys
path, sev, fid, title, detail, source = sys.argv[1:7]
rec = {"severity": sev, "id": fid, "title": title, "detail": detail, "source": source}
with open(path, "a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
PY
}

_rank() {
  case "$1" in
    ERROR) echo 4 ;;
    ALERT) echo 3 ;;
    WARN) echo 2 ;;
    INFO) echo 1 ;;
    *) echo 0 ;;
  esac
}

compute_verdict() {
  local best=CLEAN best_n=0 sev n
  if [[ ! -f "${FINDINGS_JSONL:-/dev/null}" ]]; then
    echo CLEAN
    return 0
  fi
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" ]] && continue
    sev="$(printf '%s' "$line" | sed -n 's/.*"severity": "\([^"]*\)".*/\1/p')"
    n="$(_rank "$sev")"
    if [[ "$n" -gt "$best_n" ]]; then
      best_n=$n
      case "$n" in
        4) best=ERROR ;;
        3) best=ALERT ;;
        2) best=WARN ;;
        *) best=CLEAN ;;
      esac
    fi
  done < "$FINDINGS_JSONL"
  echo "$best"
}

verdict_exit_code() {
  case "$1" in
    CLEAN) echo 0 ;;
    WARN) echo 1 ;;
    ALERT) echo 2 ;;
    ERROR) echo 3 ;;
    *) echo 3 ;;
  esac
}

_findings_lines() {
  local want="$1"
  local py
  py="$(command -v python3 || command -v python || true)"
  if [[ -z "$py" || ! -f "$FINDINGS_JSONL" ]]; then
    return 0
  fi
  "$py" - "$FINDINGS_JSONL" "$want" << 'PY'
import json, sys
path, want = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get("severity") != want:
            continue
        title = rec.get("title") or rec.get("id")
        print(f"  [{want}] {title}")
PY
}

_banner_quality() {
  local raw="-" kept="-" listen="lo-only" aide="skip" pcap="skip" exitc="${EXIT_CODE:-?}"
  local py
  py="$(command -v python3 || command -v python || true)"
  if [[ -f "$OUT/hunt_hidden_raw.txt" ]]; then
    raw="$(grep '^hidden_raw=' "$OUT/hunt_hidden_raw.txt" 2>/dev/null | cut -d= -f2 || true)"
  elif [[ -f "$OUT/hunt_procs_summary.json" && -n "$py" ]]; then
    raw="$("$py" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("hidden_raw", d.get("hidden_count","-")))' "$OUT/hunt_procs_summary.json" 2>/dev/null || true)"
  fi
  if [[ -f "$OUT/hunt_hidden_kept.txt" ]]; then
    kept="$(grep '^hidden_kept=' "$OUT/hunt_hidden_kept.txt" 2>/dev/null | cut -d= -f2 || true)"
  elif [[ -f "$OUT/hunt_procs_summary.json" && -n "$py" ]]; then
    kept="$("$py" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("hidden_kept","-"))' "$OUT/hunt_procs_summary.json" 2>/dev/null || true)"
  fi
  raw="${raw:--}"
  kept="${kept:--}"
  if [[ -f "${FINDINGS_JSONL:-}" ]] && grep -q '"id": "NET-LISTEN-EXT"' "$FINDINGS_JSONL"; then
    listen="ext"
  fi
  if [[ -f "$OUT/aide_check.txt" ]]; then
    if grep -qiE 'NO differences|Looks okay' "$OUT/aide_check.txt"; then
      aide="ok"
    elif grep -qiE 'failed to open|No such file|mangler' "$OUT/aide_check.txt"; then
      aide="none"
    elif [[ -s "$OUT/aide_check.txt" ]]; then
      aide="diff"
    fi
  fi
  if [[ -f "$OUT/hunt_pcap_summary.json" && -n "$py" ]]; then
    pcap="$("$py" -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("vs_ss") or d.get("status") or "ok")' "$OUT/hunt_pcap_summary.json" 2>/dev/null || echo ok)"
  elif [[ -f "$OUT/hunt_pcap.txt" ]] && grep -q 'tshark missing' "$OUT/hunt_pcap.txt"; then
    pcap="miss"
  elif [[ -f "$OUT/hunt_pcap.txt" ]] && grep -q 'pcap_localhost=0' "$OUT/hunt_pcap.txt"; then
    pcap="off"
  fi
  printf 'exit=%s | hidden_raw=%s kept=%s | listen=%s | aide=%s | pcap=%s' "$exitc" "$raw" "$kept" "$listen" "$aide" "$pcap"
}

print_banner() {
  local verdict="$1"
  local fd="${KALIVED_BANNER_FD:-1}"
  local color reset="" q
  q="$(_banner_quality)"
  case "$verdict" in
    ERROR|ALERT) color="$(kalived_color red)" ;;
    WARN) color="$(kalived_color yellow)" ;;
    CLEAN) color="$(kalived_color green)" ;;
    *) color="" ;;
  esac
  reset="$(kalived_color reset)"
  _emit() { printf '%s\n' "$*" >&"$fd"; }

  case "$verdict" in
    ALERT)
      _emit "${color}!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!${reset}"
      _emit "${color}  ALERT — mulig kompromittering${reset}"
      _emit "${color}  ${q}${reset}"
      _emit "${color}!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!${reset}"
      printf '\a' >&"$fd" || true
      _findings_lines ALERT >&"$fd"
      _findings_lines ERROR >&"$fd"
      _emit "  Snapshot: $OUT"
      _emit "  Hva du bør gjøre:"
      _emit "    1. Ikke ignorér dette. Ikke reboot før evidens er lagret (snapshot over)."
      _emit "    2. Les VERDICT.md i snapshot-mappen linje for linje."
      _emit "    3. Isoler nett hvis aktiv innbrudd virker sannsynlig (trekk tether / slå av wifi)."
      _emit "    4. Ikke installer AIDE/rkhunter «for å rydde» på denne tilstanden."
      _emit "    5. Identifiser PID/cwd/exe fra snapshotet før du dreper noe."
      ;;
    WARN)
      _emit "${color}************************************************************${reset}"
      _emit "${color}  WARN — avvik / hygiene, ikke nødvendigvis innbrudd${reset}"
      _emit "${color}  ${q}${reset}"
      _emit "${color}************************************************************${reset}"
      _findings_lines WARN >&"$fd"
      _emit "  Snapshot: $OUT"
      _emit "  Dette er ikke et innbruddsvarsel. Les VERDICT.md hvis du er usikker."
      ;;
    CLEAN)
      _emit "${color}============================================================${reset}"
      _emit "${color}  CLEAN | ${q}${reset}"
      _emit "${color}============================================================${reset}"
      _emit "  Sudo: $([ "${KALIVED_SUDO_FLAG:-0}" = 1 ] && echo ja || echo nei) | Snapshot: $OUT"
      ;;
    ERROR)
      _emit "${color}################################################################${reset}"
      _emit "${color}  ERROR — scannen kunne ikke fullføres${reset}"
      _emit "${color}  ${q}${reset}"
      _emit "${color}################################################################${reset}"
      _findings_lines ERROR >&"$fd"
      _findings_lines ALERT >&"$fd"
      _emit "  Snapshot: $OUT"
      _emit "  Dette er ikke et CLEAN. Ikke stol på fravær av ALERT. Se scan.log. Exit 3."
      ;;
  esac

  if [[ "$verdict" == "ALERT" || "$verdict" == "ERROR" ]]; then
    if [[ "${KALIVED_FIXTURE:-0}" != "1" && "${CFG_NOTIFY_ON_ALERT:-1}" == "1" && -n "${DISPLAY:-}" ]] && command -v notify-send >/dev/null 2>&1; then
      local first
      first="$( _findings_lines "$verdict" | head -1 | tr -d '\r' )"
      notify-send --urgency=critical "kalived $verdict" "${first:-se VERDICT.md}" 2>/dev/null || true
    fi
  fi
}

write_verdict_md() {
  local verdict="$1" exitc="$2"
  {
    echo "# kalived verdict: $verdict"
    echo
    echo "- stamp: $STAMP"
    echo "- exit: $exitc"
    echo "- sudo: ${KALIVED_SUDO_FLAG:-0}"
    echo
    echo "## Funn"
    if [[ -f "$FINDINGS_JSONL" ]]; then
      local py
      py="$(command -v python3 || command -v python)"
      "$py" - "$FINDINGS_JSONL" << 'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        print(f"- **{r['severity']}** `{r['id']}` — {r.get('title','')}")
        if r.get("detail"):
            print(f"  - {r['detail']}")
PY
    else
      echo "(ingen)"
    fi
  } > "$OUT/VERDICT.md"
}

write_verdict_json() {
  local verdict="$1" exitc="$2"
  local py
  py="$(command -v python3 || command -v python || true)"
  if [[ -z "$py" ]]; then
    add_finding ERROR SCAN "python3 mangler" "kan ikke skrive verdict.json"
    printf '{"verdict":"ERROR","exit_code":3}\n' > "$OUT/verdict.json"
    return 0
  fi
  "$py" - "$OUT/verdict.json" "$FINDINGS_JSONL" "$verdict" "$exitc" "$STAMP" "${KALIVED_SUDO_FLAG:-0}" "$OUT" "${ROOT:-}" << 'PY'
import json, sys, os
out, findings_path, verdict, exitc, stamp, sudo, snap, root = sys.argv[1:9]
findings = []
if os.path.isfile(findings_path):
    with open(findings_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                findings.append(json.loads(line))
refs = []
used = [
    "baselines/machine/prev_snapshot.txt",
    "baselines/machine/lsmod.expected",
    "baselines/machine/preload_allow.txt",
    "baselines/machine/suid.expected",
    "baselines/machine/systemd_allow.txt",
    "baselines/machine/outbound_proc.allow",
    "baselines/machine/input_holders.allow",
]
if root:
    prevp = os.path.join(root, "baselines/machine/prev_snapshot.txt")
    if os.path.isfile(prevp):
        prev = open(prevp, encoding="utf-8").read().strip()
        if prev:
            refs.append(prev)
    for rel in used:
        if os.path.isfile(os.path.join(root, rel)):
            refs.append(rel)
doc = {
    "schema": 1,
    "verdict": verdict,
    "exit_code": int(exitc),
    "stamp": stamp,
    "sudo": int(sudo),
    "snapshot": snap,
    "baseline_ref": refs,
    "findings": findings,
}
with open(out, "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, indent=2)
    f.write("\n")
PY
}

# run_mod NAME CMD...  — non-zero from a module is ERROR, never WARN.
run_mod() {
  local n="$1"
  shift
  if ! "$@"; then
    add_finding ERROR SCAN "modul $n krasjet" "se scan.log"
  fi
  return 0
}
