# shellcheck shell=bash
# Minimal TCP LISTEN check (PR 2). Full PENTEST/LOCAL-NEW lander i PR 3.

check_listen() {
  local f="$OUT/ss_tulpn.txt"
  if [[ ! -f "$f" ]]; then
    add_finding ERROR SCAN "mangler kanonisk ss_tulpn.txt" "adapter/collect feilet" "ss_tulpn.txt"
    return 0
  fi
  local py
  py="$(command -v python3 || command -v python || true)"
  if [[ -z "$py" ]]; then
    add_finding ERROR SCAN "python3 mangler" "kan ikke parse ss_tulpn.txt"
    return 0
  fi
  local tmp
  tmp="$(mktemp)"
  if ! "$py" - "$f" "$tmp" << 'PY'
import json, re, sys
src, dst = sys.argv[1], sys.argv[2]
alerts = []

def is_loopback(addr: str) -> bool:
    a = addr.strip().lower()
    if a.startswith("[") and "]" in a:
        inner = a[1:a.index("]")]
        return inner in ("::1", "127.0.0.1")
    host = a.rsplit(":", 1)[0]
    return host in ("127.0.0.1", "::1")

def proc_from(line: str) -> str:
    m = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
    if m:
        return f"{m.group(1)}, pid {m.group(2)}"
    return "ukjent prosess"

with open(src, encoding="utf-8", errors="replace") as f:
    for raw in f:
        line = raw.strip()
        if not line or line.lower().startswith("netid"):
            continue
        if "LISTEN" not in line:
            continue
        # Local Address:Port is typically field index 4 (0-based) after Netid State Recv-Q Send-Q
        parts = line.split()
        local = None
        for p in parts:
            if ":" in p and not p.startswith("users:"):
                # skip peer 0.0.0.0:* after we already took local
                local = p
                break
        if not local:
            continue
        if is_loopback(local):
            continue
        alerts.append(f"{local} ({proc_from(line)})")

with open(dst, "w", encoding="utf-8") as out:
    json.dump(alerts, out)
PY
  then
    add_finding ERROR SCAN "ss-parser krasjet" "se scan.log" "ss_tulpn.txt"
    rm -f "$tmp"
    return 0
  fi
  "$py" - "$tmp" << 'PY' >/dev/null
import json, sys
json.load(open(sys.argv[1], encoding="utf-8"))
PY
  local n
  n="$("$py" -c "import json,sys; print(len(json.load(open(sys.argv[1]))))" "$tmp")"
  if [[ "$n" -gt 0 ]]; then
    local title detail
    title="$("$py" -c "import json,sys; a=json.load(open(sys.argv[1])); print('%d TCP-lyttere utenfor localhost' % len(a))" "$tmp")"
    detail="$("$py" -c "import json,sys; print('\n'.join(json.load(open(sys.argv[1]))))" "$tmp")"
    add_finding ALERT NET-LISTEN-EXT "$title" "$detail" "ss_tulpn.txt"
  fi
  rm -f "$tmp"
  return 0
}
