#!/usr/bin/env python3
"""H4: watch window has families only. python ESTAB unknown is alert_family. No live tshark."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from hiroshima_watch import (  # noqa: E402
    ingest_dir,
    parse_saddr,
    payload_leaks_watch,
    read_window,
    sni_family,
)

FIX = Path(__file__).resolve().parent / "fixtures" / "h4-watch"
GAL = Path(__file__).resolve().parent / "fixtures" / "h1-gal"


def _assert_clean(doc: dict, label: str) -> None:
    blob = json.dumps(doc, ensure_ascii=False)
    leaks = payload_leaks_watch(doc)
    assert not leaks, (label, leaks, blob[:400])
    assert "198.51" not in blob, label
    assert "203.0.113" not in blob, label
    assert "evil.example" not in blob, label
    assert "mozilla.com" not in blob, label
    assert "dns.google" not in blob, label
    assert "cmd=" not in blob, label
    assert "sni_h" not in blob, label


def test_saddr() -> None:
    ip, port = parse_saddr("020001BBC6336409")
    assert ip == "198.51.100.9" and port == 443, (ip, port)
    ip, port = parse_saddr("020001BB7F000001")
    assert ip == "127.0.0.1" and port == 443, (ip, port)
    print("OK saddr")


def test_watch(tmp: Path) -> None:
    os.environ["HOME"] = str(tmp)
    os.environ["KALIVED_OWNER_HOME"] = str(tmp)
    doc = ingest_dir(FIX, iface="wlan0", audit_status="ok")
    _assert_clean(doc, "h4-watch")
    assert doc["class"] == "alert_family", doc["class"]
    assert doc["unknown"] >= 1, doc
    assert "python3" in (doc.get("suspect") or []), doc.get("suspect")
    assert doc["unmapped"] >= 1, doc
    p = tmp / ".config" / "kalived" / "hiroshima" / "window.json"
    assert p.is_file()
    assert (p.stat().st_mode & 0o777) == 0o600
    again = read_window()
    assert again and again["class"] == "alert_family"
    buf = tmp / ".config" / "kalived" / "hiroshima" / "watch.jsonl"
    assert buf.is_file()
    assert (buf.stat().st_mode & 0o777) == 0o600
    print("OK watch", doc["class"], "unknown", doc["unknown"], "unmapped", doc["unmapped"])


def test_gal(tmp: Path) -> None:
    os.environ["HOME"] = str(tmp)
    os.environ["KALIVED_OWNER_HOME"] = str(tmp)
    doc = ingest_dir(GAL, iface="wlan0", audit_status="missing")
    _assert_clean(doc, "h4-gal")
    assert doc["unknown"] == 0, doc
    assert doc["class"] == "noise", doc["class"]
    assert doc.get("audit") == "missing"
    print("OK gal-watch unknown=0 class=noise unmapped", doc.get("unmapped"))


def test_sni() -> None:
    assert sni_family("api.x.ai") == "xAI"
    assert sni_family("firefox.settings.services.mozilla.com") == "browser"
    assert sni_family("evil.example.com") == "unknown"
    print("OK sni-family")


def main() -> int:
    import tempfile

    test_saddr()
    test_sni()
    with tempfile.TemporaryDirectory() as d:
        test_watch(Path(d))
    with tempfile.TemporaryDirectory() as d:
        test_gal(Path(d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
