#!/usr/bin/env python3
"""H1: digest + rules port. No live Jev. Fixture must not leak payload."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cockpit" / "backend"))

from app.hiroshima_decide import (  # noqa: E402
    digest_from_snapshot,
    payload_leaks,
    port,
)

FIX = Path(__file__).resolve().parent / "fixtures" / "h1-gal"
LIVE = ROOT / "logs" / "status" / "2026-09-29_112349"


def check(snap: Path, label: str) -> None:
    d = digest_from_snapshot(snap)
    assert d["protocol"] == "hiroshima", label
    env = d.get("env") or {}
    assert env.get("ssid") == "Gal", (label, env)
    assert env.get("class") == "tether", (label, env)
    blob = json.dumps(d)
    assert "frame.time" not in blob
    assert "http.host" not in blob
    assert "dns.qry" not in blob
    assert "--crashpad" not in blob
    proto = port(snap, live=False)
    assert proto["class"] in ("noise", "env_shift"), (label, proto["class"])
    assert proto["class"] == "env_shift", (label, proto["class"])
    assert proto["verdict"] == "WARN"
    assert float(proto.get("dual") or 0) < 0.5
    assert proto["playbook"] in ("aide-init", "none", "install-kalived-helper")
    assert proto["playbook"] != "isolate-dst"
    assert any("ROOT-RKH" in g or "mangler" in g.lower() for g in (proto.get("sensor_gaps") or [])), proto.get(
        "sensor_gaps"
    )
    assert not payload_leaks(proto), proto.get("leak")
    print("OK", label, proto["class"], proto["playbook"], proto["src"], "gaps", len(proto.get("sensor_gaps") or []))


def main() -> int:
    check(FIX, "fixture")
    if LIVE.is_dir() and (LIVE / "verdict.json").is_file():
        check(LIVE, "live-snapshot")
    else:
        print("skip live-snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
