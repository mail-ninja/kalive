#!/usr/bin/env python3
"""H3: env overlay, unknown-dst isolation set, kill-pid gates. No live ufw."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cockpit" / "backend"))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from hiroshima_act import (  # noqa: E402
    check_kill,
    dst_family,
    pick_uplink_iface,
    unknown_dst_ips,
    unknown_dst_rows,
    ufw_hit_rows,
)

FIX = Path(__file__).resolve().parent / "fixtures" / "h1-tether"
UNK = Path(__file__).resolve().parent / "fixtures" / "h3-unknown"


def test_overlay(tmp: Path) -> None:
    os.environ["HOME"] = str(tmp)
    from app.hiroshima_decide import load_env_overlay, write_env_overlay

    cur = write_env_overlay("Hotspot", "tether")
    assert cur["Hotspot"] == "tether"
    cur = write_env_overlay("Cafe", "travel")
    assert cur["Cafe"] == "travel"
    assert load_env_overlay()["Hotspot"] == "tether"
    p = tmp / ".config" / "kalived" / "env_class.toml"
    assert p.is_file()
    assert (p.stat().st_mode & 0o777) == 0o600
    text = p.read_text(encoding="utf-8")
    assert "Hotspot" in text and "tether" in text
    try:
        write_env_overlay("Hotspot", "campus")
        raise AssertionError("bad class")
    except ValueError:
        pass
    print("OK overlay", p)


def test_unknown() -> None:
    assert dst_family("198.51.100.9") == "unknown"
    assert dst_family("10.0.0.1") == "private"
    empty = unknown_dst_ips(FIX)
    assert empty == [], empty
    ips = unknown_dst_ips(UNK)
    assert ips == ["198.51.100.9"], ips
    rows = unknown_dst_rows(UNK)
    assert rows and rows[0]["ip"] == "198.51.100.9" and rows[0]["port"] == 443, rows
    assert rows[0]["exe"] == "python3" and rows[0]["family"] == "unknown"
    print("OK unknown-dsts", ips)


def test_uplink_iface() -> None:
    proton = "1.1.1.1 via 10.2.0.1 dev proton0 src 10.2.0.2 uid 1000 \n    cache "
    usb = "default via 10.0.0.1 dev usb0 proto dhcp metric 100\n"
    assert pick_uplink_iface(proton, usb) == "proton0"
    assert pick_uplink_iface("", usb) == "usb0"
    assert pick_uplink_iface("1.1.1.1 dev lo src 127.0.0.1", usb) == "usb0"
    assert pick_uplink_iface("", "", "proton0") == "proton0"
    assert pick_uplink_iface("", "", "lo") == ""
    print("OK uplink-iface")


def test_ufw_hits() -> None:
    hit_dir = ROOT / "scripts" / "testdata" / "cases" / "warn_ufw_hit"
    rows = ufw_hit_rows(hit_dir)
    assert rows and rows[0]["src"] == "198.51.100.9", rows
    assert rows[0]["dpt"] == 8787
    assert rows[0].get("iface") == "eth0"
    assert ufw_hit_rows(FIX) == []
    print("OK ufw-hits", rows[0])


def test_kill() -> None:
    assert check_kill(1, "evil") == "pid < 2"
    assert check_kill(9, "chromium") == "ours-comm"
    assert check_kill(9, "uvicorn") == "ours-comm"
    print("OK kill-gates")


def main() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        test_overlay(Path(d))
    test_unknown()
    test_uplink_iface()
    test_ufw_hits()
    test_kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
