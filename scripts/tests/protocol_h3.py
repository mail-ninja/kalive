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

from hiroshima_act import check_kill, dst_family, unknown_dst_ips  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "h1-gal"
UNK = Path(__file__).resolve().parent / "fixtures" / "h3-unknown"


def test_overlay(tmp: Path) -> None:
    os.environ["HOME"] = str(tmp)
    from app.hiroshima_decide import load_env_overlay, write_env_overlay

    cur = write_env_overlay("Gal", "tether")
    assert cur["Gal"] == "tether"
    cur = write_env_overlay("Cafe", "travel")
    assert cur["Cafe"] == "travel"
    assert load_env_overlay()["Gal"] == "tether"
    p = tmp / ".config" / "kalived" / "env_class.toml"
    assert p.is_file()
    assert (p.stat().st_mode & 0o777) == 0o600
    text = p.read_text(encoding="utf-8")
    assert "Gal" in text and "tether" in text
    try:
        write_env_overlay("Gal", "campus")
        raise AssertionError("bad class")
    except ValueError:
        pass
    print("OK overlay", p)


def test_unknown() -> None:
    assert dst_family("198.51.100.9") == "unknown"
    assert dst_family("10.125.19.1") == "private"
    empty = unknown_dst_ips(FIX)
    assert empty == [], empty
    ips = unknown_dst_ips(UNK)
    assert ips == ["198.51.100.9"], ips
    print("OK unknown-dsts", ips)


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
    test_kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
