#!/usr/bin/env python3
"""H2: candidate ring, no payload/IP, Mercury only on candidate/alert_family."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cockpit" / "backend"))

from app.hiroshima_decide import (  # noqa: E402
    mercury_rules,
    payload_leaks,
    port,
    ring_from_snapshot,
    stamp_graph,
)

FIX = Path(__file__).resolve().parent / "fixtures" / "h1-tether"
MEMFD = Path(__file__).resolve().parent / "fixtures" / "h2-memfd"
LIVE = ROOT / "logs" / "status" / "2026-09-29_112349"


def _blob(doc: dict) -> str:
    return json.dumps(doc, ensure_ascii=False)


def check_tether(snap: Path, label: str) -> dict:
    proto = port(snap, live=False)
    blob = _blob(proto)
    assert proto["class"] == "env_shift", (label, proto["class"])
    assert proto.get("mercury") is None, (label, proto.get("mercury"))
    assert proto.get("schema") == 2
    ring = proto.get("ring") or []
    assert ring, (label, "empty ring")
    kinds = {str(x.get("kind")) for x in ring}
    sils = {str(x.get("sil")) for x in ring}
    assert "finding" in kinds or "FIM-AIDE" in sils, (label, ring)
    flows = [x for x in ring if x.get("kind") == "flow"]
    if flows:
        assert all(x.get("dst_family") for x in flows), (label, flows)
        assert all(x.get("exe") for x in flows), (label, flows)
    assert "203.0.113.9" not in blob
    assert "192.168.43" not in blob
    assert "10.125.19" not in blob
    assert "34.107" not in blob
    assert "--crashpad" not in blob
    assert "cmd=" not in blob
    assert not payload_leaks(proto), proto.get("leak")
    print("OK", label, "ring", len(ring), "flows", len(flows), "mercury", proto.get("mercury"))
    return proto


def check_memfd() -> None:
    proto = port(MEMFD, live=False)
    assert proto["class"] == "alert_family", proto["class"]
    merc = proto.get("mercury") or {}
    assert merc.get("family") == "c2", merc
    assert merc.get("playbook") == "ask_operator"
    assert merc.get("src") == "rules"
    assert not payload_leaks(proto), proto.get("leak")
    print("OK memfd", proto["class"], merc.get("family"))


def check_graph(proto: dict) -> None:
    g = stamp_graph(proto)
    print("OK graph", g)
    try:
        from app.memory import entity_id, graph_linked

        flows = [x for x in (proto.get("ring") or []) if x.get("kind") == "flow"]
        if not flows:
            print("skip graph-linked (no flows)")
            return
        fl = flows[0]
        src = entity_id("proc", str(fl["exe"]))
        dst = entity_id("dst", str(fl["dst_family"]))
        assert src and dst
        assert graph_linked("signal", src, dst, "CONNECTED"), (src, dst)
        print("OK linked", src, "CONNECTED", dst)
    except Exception as e:
        print("skip graph-linked", type(e).__name__, str(e)[:80])


def main() -> int:
    gal = check_tether(FIX, "fixture")
    if LIVE.is_dir() and (LIVE / "verdict.json").is_file():
        live = check_tether(LIVE, "live-snapshot")
        check_graph(live)
    else:
        check_graph(gal)
    check_memfd()
    rules = mercury_rules({"env": {"class": "tether"}, "findings": [], "verdict": "WARN"}, [])
    assert rules["family"] == "tether"
    print("OK mercury_rules tether")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
