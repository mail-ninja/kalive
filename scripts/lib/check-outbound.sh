# shellcheck shell=bash

check_outbound() {
  local f="$OUT/ss_established.txt"
  if [[ ! -f "$f" ]]; then
    if kalived_is_live; then
      add_finding ERROR SCAN "mangler ss_established.txt" "" "ss_established.txt"
    else
      add_finding INFO SNAP-MISS "ss_established.txt ikke i snapshotet" "" "ss_established.txt"
    fi
    return 0
  fi
  local py
  py="$(command -v python3 || command -v python || true)"
  [[ -n "$py" ]] || return 0
  local hits
  hits="$OUT/outbound_hits.txt"
  if ! "$py" - "$f" "$ROOT/baselines/machine/outbound_proc.allow" "$OUT/hunt_estab_proc.txt" "$hits" << 'PY'
import os, re, json, sys
estab, allowp, procp, dst = sys.argv[1:5]
outdir = os.environ.get("OUT", "")
proton = False
for fn in ("ip_addr.txt", "nm_active.txt"):
    pth = os.path.join(outdir, fn)
    if os.path.isfile(pth) and "proton" in open(pth, encoding="utf-8", errors="replace").read().lower():
        proton = True
        break
vpn_peers = set()
if proton:
    vpn_peers.add("10.2.0.1")
allow = set()
if os.path.isfile(allowp):
    for line in open(allowp, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#"):
            allow.add(line)
procs = {}
if os.path.isfile(procp):
    for line in open(procp, encoding="utf-8", errors="replace"):
        m = re.search(r"pid=(\d+)\s+comm=(\S+)\s+cwd=(\S+)\s+exe=(\S+)\s+cmd=(.*)", line)
        if m:
            procs[m.group(1)] = {"comm": m.group(2), "cwd": m.group(3), "exe": m.group(4), "cmd": m.group(5)}

def split_addr(a):
    if a.startswith("["):
        host, _, rest = a[1:].partition("]:")
        return host, rest
    host, _, port = a.rpartition(":")
    return host, port

loop = {"127.0.0.1", "::1"}
shellish = re.compile(r"^(bash|sh|dash|zsh|ncat|nc|socat|perl|php|ruby)$")
rows = []
with open(estab, encoding="utf-8", errors="replace") as fh:
    for raw in fh:
        line = raw.strip()
        if not line or line.startswith("Recv-Q") or line.startswith("==="):
            continue
        m = re.match(
            r"^\s*\S+\s+\S+\s+(\S+)\s+(\S+)(?:\s+users:\(\(\"([^\"]+)\",pid=(\d+))?",
            line,
        )
        if not m:
            continue
        local, peer, comm, pid = m.group(1), m.group(2), m.group(3) or "", m.group(4) or ""
        phost, _pport = split_addr(peer)
        lhost, _ = split_addr(local)
        if phost in loop or lhost in loop:
            continue
        if phost in ("0.0.0.0", "*", ""):
            continue
        meta = procs.get(pid, {})
        cwd = meta.get("cwd", "")
        cmd = meta.get("cmd", "")
        comm = comm or meta.get("comm") or "ukjent"
        cl = cmd.lower()
        if "protonvpn" in cl or "proton-vpn" in cl:
            continue
        if phost in vpn_peers:
            continue
        if cwd.startswith("/tmp") or cwd.startswith("/dev/shm"):
            rows.append(("ALERT", "PROC-TMPNET", f"Prosess med cwd {cwd} har ESTAB mot {peer} ({comm} pid {pid})", line[:300]))
            continue
        if shellish.match(comm):
            rows.append(("ALERT", "NET-ESTAB", f"Shell/netcat-lignende ESTAB: {comm} pid {pid} → {peer}", line[:300]))
            continue
        if comm in ("python", "python3") and "http.server" not in cl:
            rows.append(("ALERT", "NET-ESTAB", f"python ESTAB mot {peer} (pid {pid}) — ikke VPN-allow", cmd or line[:300]))
            continue
        if comm in allow:
            continue
        rows.append(("WARN", "NET-ESTAB", f"Ukjent prosess {comm} ESTAB mot {peer} (pid {pid})", line[:300]))
with open(dst, "w", encoding="utf-8") as out:
    for sev, fid, title, detail in rows:
        out.write(json.dumps({"severity": sev, "id": fid, "title": title, "detail": detail}, ensure_ascii=False) + "\n")
PY
  then
    add_finding ERROR SCAN "outbound-parser krasjet" "se scan.log" "ss_established.txt"
    return 0
  fi
  if [[ -s "$hits" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      [[ -z "$line" ]] && continue
      local sev id title detail
      sev="$("$py" -c "import json,sys; print(json.loads(sys.argv[1])['severity'])" "$line")"
      id="$("$py" -c "import json,sys; print(json.loads(sys.argv[1])['id'])" "$line")"
      title="$("$py" -c "import json,sys; print(json.loads(sys.argv[1])['title'])" "$line")"
      detail="$("$py" -c "import json,sys; print(json.loads(sys.argv[1]).get('detail',''))" "$line")"
      add_finding "$sev" "$id" "$title" "$detail" "ss_established.txt"
    done < "$hits"
  fi
  return 0
}
