# shellcheck shell=bash

check_procs() {
  [[ "${CFG_PROC_INVENTORY:-1}" == "1" ]] || return 0
  local ioc="$ROOT/defs/ioc/process-names.txt"
  local psf="$OUT/hunt_ps.txt"

  if [[ ! -f "$psf" ]]; then
    if kalived_is_live; then
      add_finding INFO PROC-INV "hunt_ps.txt mangler" "" "hunt_ps.txt"
    fi
    return 0
  fi
  grep -q 'proc_inventory=0' "$psf" 2>/dev/null && return 0

  if [[ "${CFG_PROC_HIDDEN_CHECK:-1}" == "1" ]]; then
    local py
    py="$(command -v python3 || command -v python || true)"
    if [[ -n "$py" ]]; then
      local sev id title detail source
      while IFS=$'\t' read -r sev id title detail source || [[ -n "$sev" ]]; do
        [[ -z "${sev:-}" ]] && continue
        add_finding "$sev" "$id" "$title" "${detail//\\n/$'\n'}" "$source"
      done < <("$py" - "$OUT" << 'PY'
import json, os, sys

out = sys.argv[1]

def counts(path, headers):
    n = 0
    pids = []
    if not os.path.isfile(path):
        return 0, []
    for line in open(path, encoding="utf-8", errors="replace"):
        s = line.strip()
        for h in headers:
            if s.startswith(h):
                try:
                    n = int(s.split("=", 1)[1])
                except ValueError:
                    pass
        if s.isdigit():
            pids.append(s)
    if n == 0:
        n = len(pids)
    return n, pids

raw_n, raw_pids = counts(os.path.join(out, "hunt_hidden_raw.txt"), ("hidden_raw=", "hidden_count="))
if raw_n == 0 and not os.path.isfile(os.path.join(out, "hunt_hidden_raw.txt")):
    raw_n, raw_pids = counts(os.path.join(out, "hunt_hidden_pids.txt"), ("hidden_count=", "hidden_raw="))
kept_path = os.path.join(out, "hunt_hidden_kept.txt")
ident_path = os.path.join(out, "hunt_proc_ident.jsonl")
drop_path = os.path.join(out, "hunt_hidden_drop.txt")
has_kept = os.path.isfile(kept_path)
has_ident = os.path.isfile(ident_path)
kept_n, kept_pids = counts(kept_path, ("hidden_kept=",))

rows = []
if has_ident:
    for line in open(ident_path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

def emit(sev, fid, title, detail, source):
    def clean(s):
        return str(s or "").replace("\t", " ").replace("\n", "\\n")
    print("\t".join([sev, fid, clean(title), clean(detail), clean(source)]))

def fmt_rows(items):
    parts = []
    for r in items[:20]:
        parts.append("pid=%s comm=%s exe=%s ppid=%s class=%s" % (
            r.get("pid"), r.get("comm"), r.get("exe"), r.get("ppid"), r.get("class")))
    return "\n".join(parts)

drop_preview = ""
if os.path.isfile(drop_path):
    drop_preview = "\n".join(
        ln.strip() for ln in open(drop_path, encoding="utf-8", errors="replace")
        if ln.strip() and not ln.startswith("#")
    )[:400]

by = {}
for r in rows:
    cls = r.get("class") or "weak"
    by.setdefault(cls, []).append(r)

meta = {
    "hidden": ("ALERT", "PROC-HIDDEN",
               "Skjulte PID-er overlevde sil: {n} (usynlig for ps -eT, deleted/memfd)"),
    "fakekth": ("ALERT", "PROC-FAKEKTH",
                "Falsk kernel-tråd: comm [kworker…] men PPID≠2 eller userspace-exe ({n})"),
    "commexe": ("ALERT", "PROC-COMMEXE",
                "comm matcher ikke exe på tmp/shm/home eller kernel-navn ({n})"),
    "weak": ("WARN", "PROC-HIDDEN-WEAK",
             "PID lever og /proc≠ps, men exe ser normal ut ({n}) — ikke bevist skjuling"),
}

if by:
    for cls, items in by.items():
        spec = meta.get(cls, meta["weak"])
        sev, fid, title = spec
        emit(sev, fid, title.format(n=len(items)), fmt_rows(items), "hunt_proc_ident.jsonl")
    if raw_n:
        emit("INFO", "PROC-HIDDEN-NOISE",
             "Sil 1→4: hidden_raw=%d hidden_kept=%d" % (raw_n, len(rows)),
             drop_preview, "hunt_hidden_raw.txt")
elif has_kept and kept_n == 0 and raw_n > 0:
    emit("INFO", "PROC-HIDDEN-NOISE",
         "Skjulte PID-kandidater filtrert: hidden_raw=%d hidden_kept=0" % raw_n,
         drop_preview or "\n".join(raw_pids[:12]), "hunt_hidden_drop.txt")
elif has_kept and kept_n > 0:
    emit("WARN", "PROC-HIDDEN-WEAK",
         "hidden_kept=%d uten ident (ikke ALERT)" % kept_n,
         "\n".join(kept_pids[:20]), "hunt_hidden_kept.txt")
elif raw_n > 0:
    emit("INFO", "PROC-HIDDEN-RAW",
         "hidden_raw=%d uten sil 2–4 (ikke ALERT). Kjør ny scan." % raw_n,
         "\n".join(raw_pids[:20]), "hunt_hidden_pids.txt")
PY
)
    fi
  fi

  if [[ "${CFG_PROC_IOC_CHECK:-1}" == "1" && -f "$psf" ]]; then
    local hits="" tok
    if [[ -f "$ioc" ]]; then
      while IFS= read -r tok || [[ -n "$tok" ]]; do
        [[ -z "$tok" || "$tok" == \#* ]] && continue
        if grep -F "$tok" "$psf" | grep -vq 'kalived\|check-procs'; then
          hits+="$tok"$'\n'
        fi
      done < "$ioc"
      if [[ -n "$hits" ]]; then
        add_finding ALERT PROC-IOC "Prosessnavn treffer lokal IOC-liste (git)" "$hits" "hunt_ps.txt"
      fi
    fi
    if [[ -f "$ROOT/defs/cache/process-names.remote.txt" ]]; then
      hits=""
      while IFS= read -r tok || [[ -n "$tok" ]]; do
        [[ -z "$tok" || "$tok" == \#* ]] && continue
        if grep -F "$tok" "$psf" | grep -vq 'kalived\|check-procs'; then
          hits+="$tok"$'\n'
        fi
      done < "$ROOT/defs/cache/process-names.remote.txt"
      if [[ -n "$hits" ]]; then
        add_finding WARN PROC-IOC-REMOTE "Prosessnavn treffer remote defs/cache (ikke git-merget)" \
          "$hits" "defs/cache/process-names.remote.txt"
      fi
    fi
  fi
}
