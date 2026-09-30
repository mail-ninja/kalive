#!/usr/bin/env python3
"""Settings/config.toml: watch_timer explicit false skips; missing does not."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import kalived_config as kc  # noqa: E402


def test_roundtrip(tmp: Path) -> None:
    os.environ["KALIVED_CONFIG"] = str(tmp / "config.toml")
    os.environ["HOME"] = str(tmp)
    p = kc.write({"watch_timer": True, "skip_rootkit": False, "listen_bind": "127.0.0.1"})
    assert (p.stat().st_mode & 0o777) == 0o600
    d = kc.load()
    assert d["watch_timer"] is True
    assert d["skip_rootkit"] is False
    assert kc.watch_explicit() is True
    kc.patch({"watch_timer": False})
    assert kc.watch_explicit() is False
    print("OK roundtrip", p)


def test_missing(tmp: Path) -> None:
    os.environ["KALIVED_CONFIG"] = str(tmp / "none.toml")
    assert kc.watch_explicit() is None
    print("OK missing watch_timer")


def test_loopback_lock(tmp: Path) -> None:
    os.environ["KALIVED_CONFIG"] = str(tmp / "config.toml")
    try:
        kc.patch({"listen_bind": "0.0.0.0"})
        raise AssertionError("bind")
    except ValueError:
        print("OK loopback lock")


def main() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        test_roundtrip(Path(d))
        test_loopback_lock(Path(d))
    with tempfile.TemporaryDirectory() as d:
        test_missing(Path(d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
