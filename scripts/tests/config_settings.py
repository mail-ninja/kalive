#!/usr/bin/env python3
"""Settings/config.toml: watch_timer explicit false skips; missing does not."""
from __future__ import annotations

import os
import subprocess
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


def test_home_unbound_load(tmp: Path) -> None:
    """systemd oneshot: no HOME, set -u. Owner home + config still load."""
    cfgdir = tmp / ".config" / "kalived"
    cfgdir.mkdir(parents=True)
    (cfgdir / "config.toml").write_text(
        'watch_timer = false\nlisten_bind = "127.0.0.1"\n', encoding="utf-8"
    )
    sh = ROOT / "scripts" / "lib" / "kalived-config.sh"
    script = rf"""
set -euo pipefail
source {sh}
path="$(kalived_owner_home)/.config/kalived/config.toml"
kalived_config_load
printf 'path=%s timer=%s\n' "$path" "$CFG_WATCH_TIMER"
"""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin"),
        "KALIVED_OWNER_HOME": str(tmp),
    }
    out = subprocess.check_output(["bash", "-c", script], env=env, text=True)
    assert "timer=0" in out, out
    assert str(cfgdir / "config.toml") in out, out
    print("OK home unbound load")


def test_watch_chown_owner() -> None:
    watch = (ROOT / "scripts" / "kalived-watch.sh").read_text(encoding="utf-8")
    uplink = (ROOT / "scripts" / "kalived-uplink.sh").read_text(encoding="utf-8")
    cfg = (ROOT / "scripts" / "lib" / "kalived-config.sh").read_text(encoding="utf-8")
    assert "kalived_chown_owner_dir" in watch
    assert "kalived_chown_owner_dir" in uplink
    assert 'chown -R "${owner}:${owner}"' in cfg
    assert "if [[ -n \"${SUDO_USER:-}\" ]]; then\n  chown" not in watch
    assert "if [[ -n \"${SUDO_USER:-}\" ]]; then\n  chown" not in uplink
    unit = (ROOT / "systemd" / "kalived-watch.service").read_text(encoding="utf-8")
    assert "Environment=HOME=" in unit
    print("OK watch chown owner")


def main() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        test_roundtrip(Path(d))
        test_loopback_lock(Path(d))
    with tempfile.TemporaryDirectory() as d:
        test_missing(Path(d))
    with tempfile.TemporaryDirectory() as d:
        test_home_unbound_load(Path(d))
    test_watch_chown_owner()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
