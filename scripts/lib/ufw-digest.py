#!/usr/bin/env python3
"""Sil 1–3 for UFW kernel journal. Writes digest JSON. Never eval log lines."""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

DROP_DPT = {67, 68, 137, 138, 139, 1900, 3702, 5353, 5355, 546, 547}
LISTEN_DEFAULT = {22, 8787, 45959, 7878}
EPHEMERAL = 32768
FIELD = re.compile(r"\b([A-Z0-9]+)=(\S+)")
ACTION = re.compile(r"\[UFW\s+(BLOCK|ALLOW|AUDIT)\]", re.I)
TS = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})")
MULTICAST_PFX = ("224.", "239.", "ff02:", "ff00:", "255.255.255.255")


def parse_ts(line: str):
    m = TS.match(line)
    if not m:
        return None
    try:
        return datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_line(line: str) -> dict | None:
    am = ACTION.search(line)
    if not am:
        return None
    fields = {k.upper(): v for k, v in FIELD.findall(line)}
    try:
        dpt = int(fields.get("DPT") or 0)
        spt = int(fields.get("SPT") or 0)
    except ValueError:
        dpt, spt = 0, 0
    return {
        "ts": parse_ts(line),
        "action": am.group(1).upper(),
        "in_if": fields.get("IN") or "",
        "out_if": fields.get("OUT") or "",
        "src": fields.get("SRC") or "",
        "dst": fields.get("DST") or "",
        "proto": (fields.get("PROTO") or "").upper(),
        "spt": spt,
        "dpt": dpt,
    }


def load_listen(ss_path: str) -> set[int]:
    ports = set(LISTEN_DEFAULT)
    try:
        text = open(ss_path, encoding="utf-8", errors="replace").read()
    except OSError:
        return ports
    for m in re.finditer(r":(\d+)\s", text):
        try:
            ports.add(int(m.group(1)))
        except ValueError:
            continue
    return ports


def is_noise(ev: dict) -> str | None:
    dpt = ev["dpt"]
    src, dst = ev["src"], ev["dst"]
    in_if, out_if = ev["in_if"], ev["out_if"]
    proto = ev["proto"]
    if dpt in DROP_DPT:
        return "well_known_noise"
    if in_if in ("lo", "lo0") or dst in ("127.0.0.1", "::1"):
        return "lo"
    if out_if == "proton0" and dst in ("10.2.0.1",) and dpt == 53:
        return "proton_dns"
    if any(dst.lower().startswith(p) for p in MULTICAST_PFX):
        return "mcast"
    if proto in ("ICMP", "ICMPV6") and any(dst.lower().startswith(p) for p in MULTICAST_PFX):
        return "icmp_mcast"
    if in_if == "" and out_if == "proton0" and ev["action"] == "ALLOW" and dpt == 53:
        return "proton_out"
    if src in ("127.0.0.1", "::1") or dst in ("127.0.0.1", "::1"):
        return "lo"
    return None


def inbound_block(ev: dict) -> bool:
    """Scan/flood only on deny-in, never ALLOW :443 downloads."""
    if ev["action"] != "BLOCK":
        return False
    if ev["in_if"] in ("", "lo", "lo0"):
        return False
    return True


def scans_for(events: list[dict]) -> list[dict]:
    by_src: dict[str, list] = defaultdict(list)
    for ev in events:
        if not inbound_block(ev):
            continue
        if ev["ts"] is None or not ev["src"] or not ev["dpt"]:
            continue
        by_src[ev["src"]].append(ev)
    out = []
    for src, rows in by_src.items():
        rows.sort(key=lambda e: e["ts"])
        i = 0
        for j, ev in enumerate(rows):
            while (ev["ts"] - rows[i]["ts"]).total_seconds() > 60:
                i += 1
            dpts = {rows[k]["dpt"] for k in range(i, j + 1) if rows[k]["dpt"]}
            if len(dpts) >= 10:
                secs = max(1, int((ev["ts"] - rows[i]["ts"]).total_seconds()))
                out.append({"src": src, "dpts": len(dpts), "secs": secs})
                break
    return out[:20]


def floods_for(events: list[dict]) -> list[dict]:
    buckets: dict[tuple, int] = defaultdict(int)
    for ev in events:
        if not inbound_block(ev):
            continue
        if ev["ts"] is None or not ev["src"]:
            continue
        sec = ev["ts"].replace(microsecond=0)
        buckets[(ev["src"], ev["dpt"], ev["proto"], sec)] += 1
    floods = []
    seen = set()
    for (src, dpt, proto, _sec), n in buckets.items():
        key = (src, dpt, proto)
        if key in seen:
            continue
        if proto.startswith("TCP") and n >= 20:
            floods.append({"src": src, "dpt": dpt, "proto": proto, "per_s": n})
            seen.add(key)
        elif proto.startswith("ICMP") and n >= 50:
            floods.append({"src": src, "dpt": dpt, "proto": proto, "per_s": n})
            seen.add(key)
    return floods[:20]


def digest(lines: list[str], listen: set[int]) -> dict:
    parsed = []
    for line in lines:
        ev = parse_line(line)
        if ev:
            parsed.append(ev)
    block = sum(1 for e in parsed if e["action"] == "BLOCK")
    allow = sum(1 for e in parsed if e["action"] == "ALLOW")
    allow_dns_proton = sum(
        1
        for e in parsed
        if e["action"] == "ALLOW" and e["dpt"] == 53 and e["dst"] == "10.2.0.1"
    )
    kept = []
    dropped = 0
    for ev in parsed:
        why = is_noise(ev)
        if why:
            dropped += 1
            continue
        kept.append(ev)
    # singleton SRC+DPT once in window → noise
    pair_n: dict[tuple, int] = defaultdict(int)
    for ev in kept:
        pair_n[(ev["src"], ev["dpt"])] += 1
    scans = scans_for(kept)
    scan_srcs = {s["src"] for s in scans}
    floods = floods_for(kept)
    interesting = []
    for ev in kept:
        pair = (ev["src"], ev["dpt"])
        if pair_n[pair] < 5 and ev["src"] not in scan_srcs:
            if ev["dpt"] not in listen:
                dropped += 1
                continue
        interesting.append(ev)
    hits = []
    seen_hit = set()
    for ev in interesting:
        in_if = ev["in_if"]
        if ev["dpt"] in listen and in_if not in ("", "lo", "lo0"):
            key = (ev["src"], ev["dpt"], ev["action"])
            if key in seen_hit:
                continue
            seen_hit.add(key)
            hits.append({"src": ev["src"], "dpt": ev["dpt"], "in": in_if, "action": ev["action"]})
    dpt_block: dict[int, int] = defaultdict(int)
    for ev in parsed:
        if ev["action"] == "BLOCK" and ev["dpt"]:
            dpt_block[ev["dpt"]] += 1
    top = [p for p, _n in sorted(dpt_block.items(), key=lambda x: -x[1])[:8]]
    return {
        "window_h": 24,
        "lines": len(parsed),
        "block": block,
        "allow": allow,
        "allow_dns_proton": allow_dns_proton,
        "dropped_noise": dropped,
        "scans": scans,
        "floods": floods,
        "hits_listen": hits[:20],
        "top_block_dpt": top,
    }


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: ufw-digest.py JOURNAL.txt digest.json [ss_tulpn.txt]", file=sys.stderr)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    ss = sys.argv[3] if len(sys.argv) > 3 else ""
    try:
        lines = open(src, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        lines = []
    listen = load_listen(ss) if ss else set(LISTEN_DEFAULT)
    doc = digest(lines, listen)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
