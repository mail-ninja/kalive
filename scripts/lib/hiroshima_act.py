#!/usr/bin/env python3
"""H3 actor helpers. Resolve unknown ESTAB dst IPs locally. Never print cmd lines."""
from __future__ import annotations

import ipaddress
import json
import os
import re
import sys
from pathlib import Path

OURS_FAMILIES = frozenset({"loopback", "private", "cockpit", "browser", "xAI", "Proton"})
ISOLATABLE = frozenset({"unknown"})
BROWSER = frozenset(
    {
        "chromium",
        "chrome",
        "chrome_crashpad_handler",
        "firefox",
        "firefox-esr",
        "firefox-bin",
        "brave",
        "brave-browser",
        "x-www-browser",
    }
)
COCKPIT_PORTS = frozenset({5173, 6333, 6379, 8787, 8788, 9100, 9101, 45959, 7878})
OURS_COMM = frozenset(
    {
        "grok",
        "uvicorn",
        "python3",
        "python3.14",
        "node",
        "MainThread",
        "systemd",
        "NetworkManager",
        *BROWSER,
    }
)
_SS_FLOW = re.compile(
    r"(?P<local>\S+):(?P<lport>\d+)\s+(?P<peer>\S+):(?P<pport>\d+)\s+users:\(\(\"(?P<comm>[^\"]+)\""
)


def dst_family(addr: str) -> str:
    raw = str(addr or "").strip().strip("[]")
    if not raw or raw in ("localhost", "127.0.0.1", "::1"):
        return "loopback"
    low = raw.lower()
    if "x.ai" in low or low.endswith(".xai"):
        return "xAI"
    if "proton" in low:
        return "Proton"
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        return "unknown"
    if ip.is_loopback:
        return "loopback"
    if ip in ipaddress.ip_network("10.2.0.0/16"):
        return "Proton"
    if ip.is_link_local:
        return "private"
    lan = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10", "fc00::/7")
    if any(ip in ipaddress.ip_network(n) for n in lan):
        return "private"
    return "unknown"


def flow_family(comm: str, addr: str, port: int) -> str:
    fam = dst_family(addr)
    if fam != "unknown":
        return fam
    c = str(comm or "").lower()
    if c == "grok":
        return "xAI"
    if c in BROWSER:
        return "browser"
    if int(port) in COCKPIT_PORTS:
        return "cockpit"
    return "unknown"


def peer_ip(raw: str) -> str | None:
    s = str(raw or "").strip().strip("[]")
    try:
        ipaddress.ip_address(s)
    except ValueError:
        return None
    return s


def unknown_dst_ips(snap: Path) -> list[str]:
    p = snap / "ss_established.txt"
    if not p.is_file():
        return []
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for m in _SS_FLOW.finditer(text):
        comm = m.group("comm").strip()
        peer = m.group("peer").strip()
        try:
            port = int(m.group("pport"))
        except ValueError:
            continue
        fam = flow_family(comm, peer, port)
        if fam not in ISOLATABLE:
            continue
        ip = peer_ip(peer)
        if not ip or ip in seen:
            continue
        seen.add(ip)
        found.append(ip)
        if len(found) >= 8:
            break
    return found


def latest_snap(data: Path) -> Path | None:
    status = data / "logs" / "status"
    if not status.is_dir():
        return None
    best = None
    for d in status.iterdir():
        if d.is_dir() and (d / "verdict.json").is_file():
            if best is None or d.name > best.name:
                best = d
    return best


def check_kill(pid: int, exe: str) -> str | None:
    if pid < 2:
        return "pid < 2"
    name = Path(str(exe or "")).name
    if not name or name.lower() in {c.lower() for c in OURS_COMM}:
        return "ours-comm"
    if "/" in str(exe) and ".." in Path(exe).parts:
        return "bad-exe"
    comm_path = Path(f"/proc/{pid}/comm")
    exe_path = Path(f"/proc/{pid}/exe")
    if not comm_path.is_file():
        return "no-proc"
    try:
        comm = comm_path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return "no-comm"
    if comm != name and comm.lower() != name.lower():
        return f"comm-mismatch:{comm}"
    try:
        real = os.readlink(exe_path)
        if Path(real).name not in (name, comm) and name not in real:
            return f"exe-mismatch:{Path(real).name}"
    except OSError:
        return "no-exe"
    return None


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: hiroshima_act.py unknown-dsts SNAP | check-kill PID EXE", file=sys.stderr)
        return 2
    cmd = argv[1]
    if cmd == "unknown-dsts":
        snap = Path(argv[2] if len(argv) > 2 else ".")
        for ip in unknown_dst_ips(snap):
            print(ip)
        return 0
    if cmd == "check-kill" and len(argv) >= 4:
        err = check_kill(int(argv[2]), argv[3])
        if err:
            print(err, file=sys.stderr)
            return 2
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
