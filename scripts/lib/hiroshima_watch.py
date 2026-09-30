#!/usr/bin/env python3
"""H4 egress-watch. Fields only. Never IP, SNI, cmd, or payload in the window."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from hiroshima_act import (  # noqa: E402
    BROWSER,
    _SS_FLOW,
    dst_family,
    flow_family,
    peer_ip,
)

SCHEMA = 1
MAX_BUFFER = 2000
MAX_FLOWS = 24
SHELLISH = frozenset({"bash", "sh", "dash", "zsh", "ncat", "nc", "socat", "perl", "php", "ruby"})
_SADDR = re.compile(r"saddr=([0-9A-Fa-f]+)")
_COMM = re.compile(r'comm="([^"]+)"')
_TABS = re.compile(r"\t+")


def watch_dir() -> Path:
    home = os.environ.get("KALIVED_OWNER_HOME") or str(Path.home())
    return Path(home) / ".config" / "kalived" / "hiroshima"


def window_path() -> Path:
    return watch_dir() / "window.json"


def buffer_path() -> Path:
    return watch_dir() / "watch.jsonl"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _chmod_secret(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(p.parent, 0o700)
    if p.is_file():
        os.chmod(p, 0o600)


def sni_family(name: str) -> str:
    n = str(name or "").strip().strip(".").lower()
    if not n:
        return "unknown"
    if "x.ai" in n or n.endswith(".xai"):
        return "xAI"
    if "proton" in n:
        return "Proton"
    if any(
        x in n
        for x in (
            "mozilla",
            "firefox.com",
            "google.",
            "gvt2",
            "gvt1",
            "brave.com",
            "cloudflare",
        )
    ):
        return "browser"
    return "unknown"


def sni_hash(name: str) -> str:
    return hashlib.sha256(str(name).strip().lower().encode("utf-8")).hexdigest()[:12]


def parse_ss_text(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in _SS_FLOW.finditer(text or ""):
        comm = m.group("comm")
        peer = m.group("peer")
        try:
            pport = int(m.group("pport"))
        except (TypeError, ValueError):
            continue
        ip_fam = dst_family(peer)
        fam = flow_family(comm, peer, pport)
        rec: dict[str, Any] = {
            "exe": comm,
            "dst_family": fam,
            "ip_family": ip_fam,
            "port": pport,
            "src": "ss",
        }
        out.append(rec)
    return out


def parse_saddr(hexs: str) -> tuple[str | None, int | None]:
    h = re.sub(r"[^0-9A-Fa-f]", "", hexs or "")
    if len(h) < 16:
        return None, None
    try:
        raw = bytes.fromhex(h)
    except ValueError:
        return None, None
    fam = int.from_bytes(raw[0:2], "little") if len(raw) >= 2 else 0
    if fam == 2 and len(raw) >= 8:
        port = int.from_bytes(raw[2:4], "big")
        ip = ipaddress.IPv4Address(raw[4:8])
        return str(ip), port
    if fam == 10 and len(raw) >= 24:
        port = int.from_bytes(raw[2:4], "big")
        ip = ipaddress.IPv6Address(raw[8:24])
        return str(ip), port
    return None, None


def parse_ausearch_text(text: str) -> list[dict[str, Any]]:
    """Pair SOCKADDR + SYSCALL. Ignore PROCTITLE (cmdline)."""
    out: list[dict[str, Any]] = []
    pending_ip: str | None = None
    pending_port: int | None = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if "type=SOCKADDR" in line or line.startswith("saddr="):
            m = _SADDR.search(line)
            if m:
                pending_ip, pending_port = parse_saddr(m.group(1))
            continue
        if "type=SYSCALL" not in line:
            continue
        cm = _COMM.search(line)
        comm = cm.group(1) if cm else ""
        if not pending_ip:
            pending_ip, pending_port = None, None
            continue
        pport = int(pending_port or 0)
        ip_fam = dst_family(pending_ip)
        fam = flow_family(comm, pending_ip, pport)
        out.append(
            {
                "exe": comm or "ukjent",
                "dst_family": fam,
                "ip_family": ip_fam,
                "port": pport,
                "src": "audit",
            }
        )
        pending_ip, pending_port = None, None
    return out


def parse_tshark_fields(text: str) -> list[dict[str, Any]]:
    """ip/ipv6, port, optional SNI/qname. SNI hashed in buffer, never in window."""
    out: list[dict[str, Any]] = []
    for raw in (text or "").splitlines():
        parts = [p.strip() for p in (raw.split("\t") if "\t" in raw else _TABS.split(raw.strip()))]
        addr = ""
        port = 0
        name = ""
        for p in parts:
            if not p:
                continue
            if not addr and peer_ip(p):
                addr = p
                continue
            if p.isdigit() and port == 0:
                port = int(p)
                continue
            if not name and not p.isdigit() and peer_ip(p) is None:
                name = p
        if not addr and not name:
            continue
        ip_fam = dst_family(addr) if addr else "unknown"
        fam = sni_family(name) if name else ip_fam
        rec: dict[str, Any] = {
            "exe": None,
            "dst_family": fam if fam != "unknown" else ip_fam,
            "ip_family": ip_fam,
            "port": port,
            "src": "sni",
        }
        if name:
            rec["_sni_h"] = sni_hash(name)
        out.append(rec)
    return out


def _aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str, int, str]] = Counter()
    ip_fam: dict[tuple[str, str, int, str], str] = {}
    sni_h: dict[tuple[str, str, int, str], str] = {}
    for r in rows:
        exe = str(r.get("exe") or "") or "—"
        fam = str(r.get("dst_family") or "unknown")
        src = str(r.get("src") or "ss")
        try:
            port = int(r.get("port") or 0)
        except (TypeError, ValueError):
            port = 0
        key = (exe, fam, port, src)
        counts[key] += 1
        ip_fam[key] = str(r.get("ip_family") or fam)
        if r.get("_sni_h"):
            sni_h[key] = str(r["_sni_h"])
    flows = []
    for (exe, fam, port, src), n in counts.most_common():
        item = {
            "exe": None if exe == "—" else exe,
            "dst_family": fam,
            "ip_family": ip_fam[(exe, fam, port, src)],
            "port": port,
            "src": src,
            "n": n,
        }
        if (exe, fam, port, src) in sni_h:
            item["sni_h"] = sni_h[(exe, fam, port, src)]
        flows.append(item)
        if len(flows) >= MAX_FLOWS:
            break
    return flows


def classify_window(flows: list[dict[str, Any]]) -> str:
    """Rules only. Allow-list is a label, not a hide. Baseline is suspect."""
    unknown = [f for f in flows if f.get("dst_family") == "unknown"]
    shells = [f for f in unknown if str(f.get("exe") or "").lower() in SHELLISH]
    py = [f for f in unknown if str(f.get("exe") or "").lower().startswith("python")]
    if shells or py:
        return "alert_family"
    if unknown:
        return "candidate"
    return "noise"


def build_window(rows: list[dict[str, Any]], *, audit: str = "empty", iface: str | None = None) -> dict[str, Any]:
    flows = _aggregate(rows)
    unknown = [f for f in flows if f.get("dst_family") == "unknown"]
    unmapped = [f for f in flows if f.get("ip_family") == "unknown"]
    sni_rows = [f for f in flows if f.get("src") == "sni"]
    sni_unk = [f for f in sni_rows if f.get("dst_family") == "unknown"]
    fam_counts: Counter[str] = Counter()
    for f in flows:
        fam_counts[str(f.get("dst_family") or "unknown")] += int(f.get("n") or 1)
    public = []
    for f in flows:
        item = {
            "exe": f.get("exe"),
            "dst_family": f.get("dst_family"),
            "port": f.get("port"),
            "src": f.get("src"),
            "n": f.get("n"),
            "unmapped": f.get("ip_family") == "unknown",
        }
        public.append(item)
    doc = {
        "schema": SCHEMA,
        "ts": _now(),
        "class": classify_window(flows),
        "n": sum(int(f.get("n") or 1) for f in flows),
        "unique": len(flows),
        "unknown": len(unknown),
        "unmapped": len(unmapped),
        "suspect": [f.get("exe") for f in unknown if f.get("exe")],
        "families": dict(fam_counts),
        "audit": audit,
        "sni": {"n": len(sni_rows), "unknown": len(sni_unk)},
        "iface": iface,
        "flows": public,
    }
    return doc


def payload_leaks_watch(doc: dict[str, Any]) -> list[str]:
    blob = json.dumps(doc, ensure_ascii=False)
    leaks: list[str] = []
    if "sni_h" in blob or "_sni" in blob:
        leaks.append("sni")
    if re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", blob):
        leaks.append("ipv4")
    if "cmd=" in blob or "--crashpad" in blob:
        leaks.append("cmd")
    low = blob.lower()
    for s in ("example.com", "evil.", "mozilla.com", "google.com", "frame.time", "http.host"):
        if s in low:
            leaks.append("name")
            break
    return leaks


def write_window(doc: dict[str, Any], dest: Path | None = None) -> Path:
    leaks = payload_leaks_watch(doc)
    if leaks:
        raise ValueError("watch window leak: " + ",".join(leaks))
    path = dest or window_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)
    return path


def append_buffer(rows: list[dict[str, Any]], dest: Path | None = None) -> Path:
    path = dest or buffer_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    lines: list[str] = []
    if path.is_file():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    ts = _now()
    for r in rows:
        rec = {
            "ts": ts,
            "exe": r.get("exe"),
            "dst_family": r.get("dst_family"),
            "ip_family": r.get("ip_family"),
            "port": r.get("port"),
            "src": r.get("src"),
        }
        if r.get("_sni_h"):
            rec["sni_h"] = r["_sni_h"]
        lines.append(json.dumps(rec, ensure_ascii=False))
    lines = lines[-MAX_BUFFER:]
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)
    return path


def read_window(path: Path | None = None) -> dict[str, Any] | None:
    p = path or window_path()
    if not p.is_file():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def ingest_dir(src: Path, *, iface: str | None = None, audit_status: str | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    ss = src / "ss_established.txt"
    au = src / "ausearch.txt"
    ts = src / "tshark_fields.txt"
    if ss.is_file():
        rows.extend(parse_ss_text(ss.read_text(encoding="utf-8", errors="replace")))
    audit = audit_status or "empty"
    if au.is_file():
        text = au.read_text(encoding="utf-8", errors="replace")
        if text.strip():
            rows.extend(parse_ausearch_text(text))
            audit = "ok"
        else:
            audit = "empty"
    elif audit_status is None:
        audit = "missing"
    if ts.is_file():
        rows.extend(parse_tshark_fields(ts.read_text(encoding="utf-8", errors="replace")))
    doc = build_window(rows, audit=audit, iface=iface)
    append_buffer(rows)
    write_window(doc)
    return doc


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: hiroshima_watch.py ingest DIR | window", file=sys.stderr)
        return 2
    cmd = argv[1]
    if cmd == "window":
        doc = read_window()
        json.dump(doc or {}, sys.stdout, indent=2, ensure_ascii=False)
        print()
        return 0 if doc else 1
    if cmd == "ingest":
        src = Path(argv[2] if len(argv) > 2 else ".")
        iface = os.environ.get("KALIVED_WATCH_IFACE") or None
        audit = os.environ.get("KALIVED_WATCH_AUDIT") or None
        doc = ingest_dir(src, iface=iface, audit_status=audit)
        print("class", doc.get("class"), "n", doc.get("n"), "unknown", doc.get("unknown"), "unmapped", doc.get("unmapped"))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
