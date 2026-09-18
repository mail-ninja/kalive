#!/usr/bin/env bash
# Burst process inventory: ps, /proc vs ps, pstree, lsof LISTEN.
# Four sieves: bulk raw → noise → enrich kept → class (verdict reads class).
set -euo pipefail
OUT="${KALIVED_OUT:?}"
mkdir -p "$OUT"
if [[ "${KALIVED_FIXTURE:-0}" == "1" || "${KALIVED_FROM_DIR:-0}" == "1" ]]; then
  exit 0
fi
if [[ "${CFG_PROC_INVENTORY:-1}" != "1" ]]; then
  echo "proc_inventory=0" > "$OUT/hunt_ps.txt"
  exit 0
fi
echo "[*] hunt-procs (ps/proc/pstree/lsof)" >&2

ps -eo pid,ppid,user,uid,stat,lstart,cmd --no-headers > "$OUT/hunt_ps.txt" 2>/dev/null || ps auxww > "$OUT/hunt_ps.txt"
ps -eT -o pid,tid,ppid,comm --no-headers > "$OUT/hunt_ps_threads.txt" 2>/dev/null \
  || ps -eL -o pid,lwp,ppid,comm --no-headers > "$OUT/hunt_ps_threads.txt" 2>/dev/null \
  || true

_list_proc_pids() {
  find /proc -maxdepth 1 -type d -regex '/proc/[0-9]+' -printf '%f\n' 2>/dev/null | sort -n
}

{
  echo "=== /proc pids ==="
  _list_proc_pids
} > "$OUT/hunt_proc_pids.txt" 2>/dev/null || true
_list_proc_pids > "$OUT/hunt_proc_pids_a.txt" 2>/dev/null || true
sleep 0.2
_list_proc_pids > "$OUT/hunt_proc_pids_b.txt" 2>/dev/null || true
sleep 0.3

python3 - "$OUT" << 'PY' || true
import json, os, re, sys

out = sys.argv[1]
SCANNER_COMMS = {
    "kalived-scan.sh", "kalived-scan", "kalived-ctl",
    "hunt-procs.sh", "hunt-nmap.sh", "hunt-rootkit.sh", "hunt-persistence.sh",
    "nmap", "ncat", "rkhunter", "chkrootkit", "aide", "unhide", "unhide-linux",
    "unhide-tcp", "unhide-pid",
}
SCANNER_CMDLINE = (
    "kalived-scan", "hunt-procs", "hunt-nmap", "hunt-rootkit",
    "/usr/lib/nmap/nmap", "rkhunter", "chkrootkit",
)
KERNEL_NAMES = (
    "kworker", "ksoftirqd", "kthreadd", "kswapd", "kdevtmpfs",
    "khungtaskd", "khelper", "kcompactd", "kblockd",
)
TMP_PREFIXES = ("/tmp/", "/dev/shm/", "/home/")


def read_int_lines(path):
    pids = []
    if not os.path.isfile(path):
        return pids
    for line in open(path, encoding="utf-8", errors="replace"):
        s = line.strip()
        if s.isdigit():
            pids.append(s)
    return pids


def read_ps_pids(path):
    pids = set()
    if not os.path.isfile(path):
        return pids
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\s*(\d+)\s", line)
        if m:
            pids.add(m.group(1))
    return pids


def read_ps_tids(path):
    tids = set()
    tgids = set()
    if not os.path.isfile(path):
        return tids, tgids
    for line in open(path, encoding="utf-8", errors="replace"):
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            tgids.add(parts[0])
            tids.add(parts[1])
    return tids, tgids


def read_status(pid):
    d = {}
    try:
        for line in open(f"/proc/{pid}/status", encoding="utf-8", errors="replace"):
            if ":" not in line:
                continue
            k, _, v = line.partition(":")
            d[k.strip()] = v.strip()
    except OSError:
        return None
    return d


def read_comm(pid):
    try:
        return open(f"/proc/{pid}/comm", encoding="utf-8", errors="replace").read().strip()
    except OSError:
        return ""


def read_cmdline(pid):
    try:
        raw = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\x00", b" ")
        return raw.decode("utf-8", "replace").strip()[:240]
    except OSError:
        return ""


def readlink(path):
    try:
        return os.readlink(path)
    except OSError:
        return ""


def first_nstgid(st):
    raw = (st.get("NStgid") or "").split()
    return raw[0] if raw else ""


def is_thread(pid, st, ps_tids):
    tgid = (st.get("Tgid") or "").split()[0]
    nstgid = first_nstgid(st)
    if tgid and tgid != pid:
        return True, tgid
    if nstgid and nstgid != pid:
        return True, nstgid
    if pid in ps_tids and tgid and tgid != pid:
        return True, tgid
    if pid in ps_tids and tgid == pid:
        # visible to ps -eT as a process; not hidden
        return False, tgid
    return False, tgid


def looks_scanner(comm, cmd):
    c = (comm or "").strip()
    if c in SCANNER_COMMS:
        return c
    base = os.path.basename(c)
    if base in SCANNER_COMMS:
        return base
    for needle in SCANNER_CMDLINE:
        if needle in (cmd or "") or needle in c:
            return needle
    return ""


def ancestor_scanner(pid, cache, limit=8):
    seen = set()
    cur = pid
    for _ in range(limit):
        if not cur or cur in seen or cur in ("0", "1"):
            return ""
        seen.add(cur)
        st = cache.get(cur)
        if st is None:
            st = read_status(cur)
            cache[cur] = st
        if not st:
            return ""
        comm = st.get("Name") or read_comm(cur)
        cmd = read_cmdline(cur)
        hit = looks_scanner(comm, cmd)
        if hit:
            return f"{cur}:{hit}"
        cur = (st.get("PPid") or "0").split()[0]
    return ""


def kernel_style(comm):
    c = (comm or "").strip()
    inner = c[1:-1] if c.startswith("[") and c.endswith("]") else c
    return any(inner.startswith(k) or inner.startswith(k + "/") for k in KERNEL_NAMES)


def exe_base(exe):
    e = (exe or "").replace(" (deleted)", "").split("/")[-1]
    return e.split()[0] if e else ""


def comm_matches_exe(comm, exe):
    if not exe:
        return True
    base = exe_base(exe)
    c = (comm or "").strip().strip("[]")
    if not c or not base:
        return True
    if c == base or base.startswith(c) or c.startswith(base.split(".")[0]):
        return True
    if c in ("python", "python3", "bash", "sh", "dash", "perl", "ruby", "node", "java", "nvim", "vim"):
        return True
    return False


def classify(ident):
    comm = ident.get("comm") or ""
    exe = ident.get("exe") or ""
    ppid = str(ident.get("ppid") or "")
    alive = ident.get("still_alive")
    seen_ps = ident.get("seen_by_ps")
    seen_et = ident.get("seen_by_ps_eT")
    exe_l = exe.lower()
    deleted = "(deleted)" in exe_l or exe_l.startswith("memfd:") or "/memfd:" in exe_l
    if kernel_style(comm) and (ppid != "2" or exe):
        return "fakekth"
    if exe and (any(exe.startswith(p) for p in TMP_PREFIXES) or kernel_style(comm)):
        if not comm_matches_exe(comm, exe):
            return "commexe"
    if alive and not seen_ps and not seen_et and deleted:
        return "hidden"
    if alive and not seen_ps:
        return "weak"
    return "weak"


ps_path = os.path.join(out, "hunt_ps.txt")
proc_path = os.path.join(out, "hunt_proc_pids.txt")
a_path = os.path.join(out, "hunt_proc_pids_a.txt")
b_path = os.path.join(out, "hunt_proc_pids_b.txt")
thr_path = os.path.join(out, "hunt_ps_threads.txt")

ps_pids = read_ps_pids(ps_path)
ps_tids, ps_tgids = read_ps_tids(thr_path)
proc_a = read_int_lines(a_path) or read_int_lines(proc_path)
proc_b = set(read_int_lines(b_path))
proc_a_set = set(proc_a)
raw = [p for p in proc_a if p not in ps_pids]

raw_path = os.path.join(out, "hunt_hidden_raw.txt")
legacy_path = os.path.join(out, "hunt_hidden_pids.txt")
with open(raw_path, "w", encoding="utf-8") as f:
    f.write("hidden_raw=%d\n" % len(raw))
    for p in raw[:80]:
        f.write(p + "\n")
with open(legacy_path, "w", encoding="utf-8") as f:
    f.write("hidden_count=%d\n" % len(raw))
    for p in raw[:80]:
        f.write(p + "\n")

self_pids = {str(os.getpid()), str(os.getppid())}
status_cache = {}
drops = []
kept = []
drop_counts = {"gone": 0, "race_snapshot": 0, "thread": 0, "scanner_child": 0, "self": 0}

for p in raw:
    if p in self_pids:
        drops.append(f"{p} self")
        drop_counts["self"] += 1
        continue
    st = read_status(p)
    status_cache[p] = st
    if st is None:
        drops.append(f"{p} gone")
        drop_counts["gone"] += 1
        continue
    if p not in proc_b or p not in proc_a_set:
        drops.append(f"{p} race_snapshot")
        drop_counts["race_snapshot"] += 1
        continue
    thr, tgid = is_thread(p, st, ps_tids)
    if thr:
        drops.append(f"{p} thread tgid={tgid}")
        drop_counts["thread"] += 1
        continue
    if p in ps_tids:
        # listed by ps -eT → not hidden
        drops.append(f"{p} thread visible_eT tgid={tgid or p}")
        drop_counts["thread"] += 1
        continue
    comm = st.get("Name") or read_comm(p)
    cmd = read_cmdline(p)
    hit = looks_scanner(comm, cmd)
    if not hit:
        hit = ancestor_scanner(st.get("PPid", "").split()[0] if st.get("PPid") else "", status_cache)
        if hit:
            hit = "ppid:" + hit
    if hit:
        drops.append(f"{p} scanner_child {hit}")
        drop_counts["scanner_child"] += 1
        continue
    kept.append(p)

drop_path = os.path.join(out, "hunt_hidden_drop.txt")
with open(drop_path, "w", encoding="utf-8") as f:
    f.write("# sieve2 drops (not verdict)\n")
    for line in drops[:120]:
        f.write(line + "\n")

kept_path = os.path.join(out, "hunt_hidden_kept.txt")
with open(kept_path, "w", encoding="utf-8") as f:
    f.write("hidden_kept=%d\n" % len(kept))
    for p in kept[:50]:
        f.write(p + "\n")

ident_path = os.path.join(out, "hunt_proc_ident.jsonl")
classes = {"hidden": 0, "weak": 0, "fakekth": 0, "commexe": 0}
rows_ident = []
with open(ident_path, "w", encoding="utf-8") as f:
    for p in kept[:50]:
        st = status_cache.get(p) or read_status(p) or {}
        comm = st.get("Name") or read_comm(p)
        exe = readlink(f"/proc/{p}/exe")
        cwd = readlink(f"/proc/{p}/cwd")
        cmdline = read_cmdline(p)
        oom = ""
        try:
            oom = open(f"/proc/{p}/oom_score", encoding="utf-8").read().strip()
        except OSError:
            pass
        maps_head = ""
        try:
            maps_head = " | ".join(
                open(f"/proc/{p}/maps", encoding="utf-8", errors="replace").read().splitlines()[:2]
            )[:240]
        except OSError:
            pass
        uid = (st.get("Uid") or "").split()[0] if st.get("Uid") else ""
        ppid = (st.get("PPid") or "").split()[0]
        tgid = (st.get("Tgid") or "").split()[0]
        ident = {
            "pid": p,
            "comm": comm[:40],
            "cmdline": cmdline[:200],
            "exe": exe[:200],
            "ppid": ppid,
            "uid": uid,
            "cwd": cwd[:200],
            "oom": oom,
            "maps_head": maps_head,
            "tgid": tgid,
            "nstgid": first_nstgid(st),
            "still_alive": os.path.isdir(f"/proc/{p}"),
            "seen_by_ps": p in ps_pids,
            "seen_by_ps_eT": p in ps_tids,
        }
        ident["class"] = classify(ident)
        classes[ident["class"]] = classes.get(ident["class"], 0) + 1
        rows_ident.append(ident)
        f.write(json.dumps(ident, ensure_ascii=False) + "\n")

# Compact JSON for advisor (no full cmdline dump)
rows = []
try:
    for line in open(ps_path, encoding="utf-8", errors="replace"):
        parts = line.split(None, 10)
        if len(parts) < 3 or not parts[0].isdigit():
            continue
        # pid ppid user uid stat + lstart(5 tokens) + cmd
        if len(parts) >= 11 and parts[1].isdigit():
            cmd = parts[10]
        else:
            cmd = parts[-1]
        token = cmd.split()[0] if cmd.split() else "?"
        if token.startswith("["):
            continue
        comm = os.path.basename(token)
        if comm in ("ps", "bash", "Sep", "Fri", "Sat", "Sun", "Mon", "Tue", "Wed", "Thu"):
            continue
        user = parts[2] if len(parts) > 2 else "?"
        rows.append({"pid": int(parts[0]), "user": user, "comm": comm[:40]})
except OSError:
    pass

listen = []
lsof_path = os.path.join(out, "hunt_lsof_listen.txt")
if os.path.isfile(lsof_path):
    for line in open(lsof_path, encoding="utf-8", errors="replace"):
        if line.startswith("COMMAND") or "lsof missing" in line:
            continue
        m = re.search(r":(\d+)\s+\(LISTEN\)", line)
        if not m:
            continue
        comm = line.split()[0] if line.split() else "?"
        listen.append({"comm": comm[:32], "port": int(m.group(1))})

summary = {
    "visible_count": len(rows) if rows else len(ps_pids),
    "hidden_raw": len(raw),
    "hidden_kept": len(kept),
    "hidden_count": len(kept),
    "hidden_pids": kept[:20],
    "hidden_raw_pids": raw[:20],
    "drop": drop_counts,
    "classes": classes,
    "listen": listen[:30],
    "sample_comm": sorted({r["comm"] for r in rows})[:40],
}
json.dump(summary, open(os.path.join(out, "hunt_procs_summary.json"), "w", encoding="utf-8"), indent=2)
PY

if command -v pstree >/dev/null 2>&1; then
  pstree -ap > "$OUT/hunt_pstree.txt" 2>/dev/null || true
else
  echo "pstree missing (psmisc)" > "$OUT/hunt_pstree.txt"
fi

if command -v lsof >/dev/null 2>&1; then
  lsof -nP -iTCP -sTCP:LISTEN > "$OUT/hunt_lsof_listen.txt" 2>/dev/null || true
else
  echo "lsof missing" > "$OUT/hunt_lsof_listen.txt"
fi

# Re-emit listen into summary if lsof ran after python (python saw empty lsof).
if [[ -f "$OUT/hunt_procs_summary.json" && -s "$OUT/hunt_lsof_listen.txt" ]]; then
  python3 - "$OUT" << 'PY' || true
import json, os, re, sys
out = sys.argv[1]
path = os.path.join(out, "hunt_procs_summary.json")
try:
    summary = json.load(open(path, encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    raise SystemExit(0)
listen = []
lsof_path = os.path.join(out, "hunt_lsof_listen.txt")
for line in open(lsof_path, encoding="utf-8", errors="replace"):
    if line.startswith("COMMAND") or "lsof missing" in line:
        continue
    m = re.search(r":(\d+)\s+\(LISTEN\)", line)
    if not m:
        continue
    comm = line.split()[0] if line.split() else "?"
    listen.append({"comm": comm[:32], "port": int(m.group(1))})
summary["listen"] = listen[:30]
json.dump(summary, open(path, "w", encoding="utf-8"), indent=2)
PY
fi

echo "[+] hunt-procs done" >&2
