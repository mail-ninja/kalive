#!/usr/bin/env python3
"""Parse Falco JSON → hunt_falco.jsonl. Fields: rule, exe, evt.type, n only."""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ALLOWED = ("rule", "exe", "evt.type", "n")
EXE_OK = re.compile(r"^[A-Za-z0-9._+-]+$")
RULE_OK = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,80}$")
EVT_OK = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,40}$")

FIM_DUAL = frozenset({"FIM-AIDE", "FIM-DEBSUMS", "PERS-PRELOAD"})
NET_DUAL = frozenset(
    {
        "NET-LISTEN-EXT",
        "NET-ESTAB",
        "NET-NMAP",
        "NET-NMAP-SVC",
        "NET-SSH-UNIT",
        "NET-PROMISC",
        "PCAP-EXTRA",
        "PROC-TMPNET",
    }
)


def _basename_exe(raw: str) -> str:
    s = str(raw or "").strip().split()[0] if raw else ""
    s = s.replace(" (deleted)", "").replace("(deleted)", "").strip()
    if s.startswith("/memfd:"):
        return "memfd"
    if "/" in s:
        s = s.rsplit("/", 1)[-1] or s
    s = s[:80]
    if not s or not EXE_OK.match(s):
        return "ukjent"
    return s


def parse_event(obj: dict[str, Any]) -> tuple[str, str, str] | None:
    """Return (rule, exe, evt.type) or None. Drop cmdline/IP/SNI."""
    if not isinstance(obj, dict):
        return None
    rule = str(obj.get("rule") or "").strip()
    fields = obj.get("output_fields") if isinstance(obj.get("output_fields"), dict) else {}
    exe = (
        fields.get("proc.exepath")
        or fields.get("proc.name")
        or obj.get("exe")
        or ""
    )
    evt = str(fields.get("evt.type") or obj.get("evt.type") or obj.get("evt_type") or "").strip()
    if not RULE_OK.match(rule):
        return None
    exe_b = _basename_exe(str(exe))
    if not EVT_OK.match(evt):
        evt = "unknown"
    return rule, exe_b, evt


def parse_line(line: str) -> tuple[str, str, str] | None:
    s = line.strip()
    if not s.startswith("{"):
        return None
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    return parse_event(obj)


def aggregate(text: str) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str, str]] = Counter()
    for line in text.splitlines():
        rec = parse_line(line)
        if rec:
            counts[rec] += 1
    out = []
    for (rule, exe, evt), n in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
        out.append({"rule": rule, "exe": exe, "evt.type": evt, "n": int(n)})
    return out


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows:
            slim = {k: row.get(k) for k in ALLOWED if k in row}
            fh.write(json.dumps(slim, ensure_ascii=False) + "\n")
    tmp.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.stat().st_size == 0:
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        rule = str(obj.get("rule") or "")
        exe = _basename_exe(str(obj.get("exe") or ""))
        evt = str(obj.get("evt.type") or "")
        try:
            n = int(obj.get("n") or 1)
        except (TypeError, ValueError):
            n = 1
        if not RULE_OK.match(rule) or not EVT_OK.match(evt):
            continue
        rows.append({"rule": rule, "exe": exe, "evt.type": evt, "n": n})
    return rows


_SEV_RANK = {"INFO": 1, "WARN": 2, "ALERT": 3, "ERROR": 4}


def _finding_ids(findings_path: Path) -> dict[str, str]:
    """id → highest severity among all rows (WARN is not overwritten by a later INFO)."""
    out: dict[str, str] = {}
    if not findings_path.is_file():
        return out
    for line in findings_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict) or not rec.get("id"):
            continue
        sid = str(rec["id"])
        sev = str(rec.get("severity") or "")
        prev = out.get(sid, "")
        if _SEV_RANK.get(sev, 0) >= _SEV_RANK.get(prev, 0):
            out[sid] = sev
    return out


def dual_domains(ids: dict[str, str]) -> tuple[bool, bool]:
    fim = any(i in FIM_DUAL and ids[i] in ("WARN", "ALERT") for i in ids)
    net = any(
        (i in NET_DUAL or (i.startswith("NET-") and i not in {"NET-UFW-NOISE", "NET-UFW-SCAN", "NET-DNS"}))
        and ids[i] in ("WARN", "ALERT")
        for i in ids
    )
    return fim, net


def findings_from_rows(
    rows: list[dict[str, Any]],
    *,
    ids: dict[str, str] | None = None,
    absent: bool = False,
    live: bool = False,
    missing: bool = False,
) -> list[dict[str, str]]:
    if absent:
        return [
            {
                "severity": "INFO",
                "id": "HOST-FALCO",
                "title": "falco absent",
                "detail": "Falco-pakke mangler. Playbook printer apt-kommando. Scan hever ikke.",
                "source": "hunt_falco.txt",
            }
        ]
    if missing and live:
        return [
            {
                "severity": "INFO",
                "id": "HOST-FALCO",
                "title": "falco-burst ikke i snapshotet",
                "detail": "sudo kalived-ctl falco-burst",
                "source": "hunt_falco.jsonl",
            }
        ]
    if not rows:
        return []
    ids = ids or {}
    fim, net = dual_domains(ids)
    dual = fim or net
    sev = "ALERT" if dual else "WARN"
    shown = rows[:8]
    extra = f" (+{len(rows) - 8})" if len(rows) > 8 else ""
    bits = [f"{r['rule']} exe={r['exe']} evt={r['evt.type']} n={r['n']}" for r in shown]
    if dual:
        title = f"Falco + {'FIM' if fim else 'nett'}: {', '.join(bits)}{extra}"
    else:
        title = f"Falco candidate: {', '.join(bits)}{extra}"
    return [
        {
            "severity": sev,
            "id": "HOST-FALCO",
            "title": title[:240],
            "detail": "\n".join(bits),
            "source": "hunt_falco.jsonl",
        }
    ]


def digest_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows[:12]:
        out.append({"rule": r.get("rule"), "exe": r.get("exe"), "evt.type": r.get("evt.type"), "n": r.get("n")})
    return out


def leaks(obj: Any) -> list[str]:
    blob = json.dumps(obj, ensure_ascii=False)
    hits = []
    if "cmdline" in blob.lower() or "proc.cmdline" in blob.lower():
        hits.append("cmdline")
    if "sni" in blob.lower():
        hits.append("sni")
    if "pcap" in blob.lower() and "hunt_falco" not in blob.lower():
        hits.append("pcap")
    if re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", blob):
        hits.append("ip")
    return hits


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: falco_burst.py aggregate RAW OUT_JSONL", file=sys.stderr)
        print("       falco_burst.py findings JSONL FINDINGS_JSONL", file=sys.stderr)
        return 2
    cmd = argv[1]
    if cmd == "aggregate":
        raw = Path(argv[2]).read_text(encoding="utf-8", errors="replace") if Path(argv[2]).is_file() else ""
        dest = Path(argv[3])
        rows = aggregate(raw)
        write_jsonl(dest, rows)
        print(json.dumps({"n": len(rows), "path": str(dest)}))
        return 0
    if cmd == "findings":
        rows = load_jsonl(Path(argv[2]))
        ids = _finding_ids(Path(argv[3])) if len(argv) > 3 else {}
        recs = findings_from_rows(rows, ids=ids)
        print(json.dumps(recs, ensure_ascii=False, indent=2))
        return 0
    print("unknown", cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
