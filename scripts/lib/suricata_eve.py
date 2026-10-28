#!/usr/bin/env python3
"""Parse Suricata eve.json → hunt_suricata.jsonl. Fields: sid, signature, app_proto, exe, n."""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ALLOWED = ("sid", "signature", "app_proto", "exe", "n")
SIG_OK = re.compile(r"^[A-Za-z0-9 .,_/:+()-]{1,80}$")
PROTO_OK = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,20}$")
EXE_OK = re.compile(r"^[A-Za-z0-9._+-]+$")
_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IP6 = re.compile(r"\b(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}\b")
_SS_PEER = re.compile(
    r"(?P<peer>\S+):(?P<pport>\d+)\s+users:\(\(\"(?P<comm>[^\"]+)\""
)

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
# Suricata decoder/stream events (not ET/malware). 2200121 Ethertype unknown is wifi noise.
DECODER_SID_MIN = 2_200_000
DECODER_SID_MAX = 2_299_999


def _basename_exe(raw: str) -> str:
    s = str(raw or "").strip().split()[0] if raw else ""
    s = s.replace(" (deleted)", "").replace("(deleted)", "").strip()
    if "/" in s:
        s = s.rsplit("/", 1)[-1] or s
    s = s[:80]
    if not s or not EXE_OK.match(s):
        return ""
    return s


def _redact_sig(raw: str) -> str:
    s = " ".join(str(raw or "").split())
    s = _IP.sub("x", s)
    s = _IP6.sub("x", s)
    s = s.replace("evil.example.com", "x")
    s = s[:80]
    if not SIG_OK.match(s):
        s = re.sub(r"[^A-Za-z0-9 .,_/:+()-]", " ", s)
        s = " ".join(s.split())[:80]
    if not s:
        return "alert"
    return s


def _app_proto(obj: dict[str, Any]) -> str:
    p = str(obj.get("app_proto") or "").strip().lower()
    if PROTO_OK.match(p):
        return p
    proto = str(obj.get("proto") or "").strip().lower()
    if PROTO_OK.match(proto):
        return proto
    return "unknown"


def exe_from_ss(ss_text: str, dest_ip: str) -> str:
    """Match dest_ip against ss ESTAB peer; return comm basename. Drop the IP."""
    want = str(dest_ip or "").strip().strip("[]")
    if not want or not ss_text:
        return ""
    for m in _SS_PEER.finditer(ss_text):
        peer = m.group("peer").strip().strip("[]")
        if peer == want:
            return _basename_exe(m.group("comm"))
    return ""


def parse_event(obj: dict[str, Any], *, ss_text: str = "") -> tuple[int, str, str, str] | None:
    """Return (sid, signature, app_proto, exe) or None. Drop dest-IP/SNI/payload."""
    if not isinstance(obj, dict):
        return None
    if str(obj.get("event_type") or "") != "alert":
        return None
    alert = obj.get("alert") if isinstance(obj.get("alert"), dict) else {}
    try:
        sid = int(alert.get("signature_id") or obj.get("sid") or 0)
    except (TypeError, ValueError):
        return None
    if sid < 1 or sid > 99_999_999:
        return None
    sig = _redact_sig(str(alert.get("signature") or obj.get("signature") or "alert"))
    proto = _app_proto(obj)
    dest = str(obj.get("dest_ip") or "")
    exe = exe_from_ss(ss_text, dest) if dest else ""
    return sid, sig, proto, exe


def parse_line(line: str, *, ss_text: str = "") -> tuple[int, str, str, str] | None:
    s = line.strip()
    if not s.startswith("{"):
        return None
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    return parse_event(obj, ss_text=ss_text)


def aggregate(text: str, *, ss_text: str = "") -> list[dict[str, Any]]:
    counts: Counter[tuple[int, str, str, str]] = Counter()
    for line in text.splitlines():
        rec = parse_line(line, ss_text=ss_text)
        if rec:
            counts[rec] += 1
    out = []
    for (sid, sig, proto, exe), n in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
        row: dict[str, Any] = {
            "sid": int(sid),
            "signature": sig,
            "app_proto": proto,
            "n": int(n),
        }
        if exe:
            row["exe"] = exe
        out.append(row)
    return out


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows:
            slim = {k: row.get(k) for k in ALLOWED if k in row and row.get(k) not in ("", None)}
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
        try:
            sid = int(obj.get("sid") or 0)
        except (TypeError, ValueError):
            continue
        if sid < 1:
            continue
        sig = _redact_sig(str(obj.get("signature") or "alert"))
        proto = str(obj.get("app_proto") or "unknown")
        if not PROTO_OK.match(proto):
            proto = "unknown"
        try:
            n = int(obj.get("n") or 1)
        except (TypeError, ValueError):
            n = 1
        row: dict[str, Any] = {"sid": sid, "signature": sig, "app_proto": proto, "n": n}
        exe = _basename_exe(str(obj.get("exe") or ""))
        if exe:
            row["exe"] = exe
        rows.append(row)
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


def is_decoder_sid(sid: int | str) -> bool:
    try:
        n = int(sid)
    except (TypeError, ValueError):
        return False
    return DECODER_SID_MIN <= n <= DECODER_SID_MAX


def _row_sid(row: dict[str, Any]) -> int:
    try:
        return int(row.get("sid") or 0)
    except (TypeError, ValueError):
        return 0


def _flow_match(rows: list[dict[str, Any]], ids: dict[str, str]) -> bool:
    """Decoder dual only when this alert's flow matches nett or Falco. FIM is not a flow."""
    if not any(str(r.get("exe") or "").strip() for r in rows):
        return False
    _, net = dual_domains(ids)
    falco = ids.get("HOST-FALCO") in ("WARN", "ALERT")
    return bool(net or falco)


def _bits(rows: list[dict[str, Any]]) -> tuple[list[str], str]:
    shown = rows[:8]
    extra = f" (+{len(rows) - 8})" if len(rows) > 8 else ""
    bits: list[str] = []
    for r in shown:
        bit = f"sid={r['sid']} {r['signature']} app={r['app_proto']} n={r['n']}"
        if r.get("exe"):
            bit += f" exe={r['exe']}"
        bits.append(bit)
    return bits, extra


def _host_finding(sev: str, title: str, bits: list[str]) -> dict[str, str]:
    return {
        "severity": sev,
        "id": "HOST-SURICATA",
        "title": title[:240],
        "detail": "\n".join(bits),
        "source": "hunt_suricata.jsonl",
    }


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
                "id": "HOST-SURICATA",
                "title": "suricata absent",
                "detail": "Suricata-pakke mangler. Playbook printer apt-kommando. Scan hever ikke.",
                "source": "hunt_suricata.txt",
            }
        ]
    if missing and live:
        return [
            {
                "severity": "INFO",
                "id": "HOST-SURICATA",
                "title": "suricata harvest ikke i snapshotet",
                "detail": "live scan skriver hunt_suricata.jsonl",
                "source": "hunt_suricata.jsonl",
            }
        ]
    if not rows:
        return []
    ids = ids or {}
    signal = [r for r in rows if not is_decoder_sid(_row_sid(r))]
    decoder = [r for r in rows if is_decoder_sid(_row_sid(r))]
    if signal:
        fim, net = dual_domains(ids)
        dual = fim or net
        sev = "ALERT" if dual else "WARN"
        bits, extra = _bits(signal)
        if dual:
            title = f"Suricata + {'FIM' if fim else 'nett'}: {', '.join(bits)}{extra}"
        else:
            title = f"Suricata candidate: {', '.join(bits)}{extra}"
        return [_host_finding(sev, title, bits)]
    bits, extra = _bits(decoder)
    if _flow_match(decoder, ids):
        return [_host_finding("ALERT", f"Suricata + flow: {', '.join(bits)}{extra}", bits)]
    return [_host_finding("INFO", f"Suricata decoder: {', '.join(bits)}{extra}", bits)]


def digest_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows[:12]:
        slim: dict[str, Any] = {
            "sid": r.get("sid"),
            "signature": r.get("signature"),
            "app_proto": r.get("app_proto"),
            "n": r.get("n"),
        }
        if r.get("exe"):
            slim["exe"] = r.get("exe")
        out.append(slim)
    return out


def leaks(obj: Any) -> list[str]:
    blob = json.dumps(obj, ensure_ascii=False)
    hits = []
    if "payload" in blob.lower() and "hunt_suricata" not in blob.lower():
        hits.append("payload")
    if "sni" in blob.lower():
        hits.append("sni")
    if "pcap" in blob.lower() and "hunt_suricata" not in blob.lower():
        hits.append("pcap")
    if _IP.search(blob):
        hits.append("ip")
    return hits


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: suricata_eve.py aggregate EVE OUT_JSONL [SS_ESTABLISHED]", file=sys.stderr)
        print("       suricata_eve.py findings JSONL FINDINGS_JSONL", file=sys.stderr)
        return 2
    cmd = argv[1]
    if cmd == "aggregate":
        eve = Path(argv[2]).read_text(encoding="utf-8", errors="replace") if Path(argv[2]).is_file() else ""
        dest = Path(argv[3])
        ss_text = ""
        if len(argv) > 4 and Path(argv[4]).is_file():
            ss_text = Path(argv[4]).read_text(encoding="utf-8", errors="replace")
        rows = aggregate(eve, ss_text=ss_text)
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
