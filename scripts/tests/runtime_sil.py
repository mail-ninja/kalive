#!/usr/bin/env python3
"""R1: interpreter names + HOST-RUNTIME pins. No live scan."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from runtime_pins import (  # noqa: E402
    COCKPIT_PORTS,
    INTERP_NAMES,
    brotli_ok,
    findings_from_snapshot,
    node_ok,
    parse_ver,
    php_apache_listeners,
    ver_ge,
)

PINS = json.loads((ROOT / "baselines" / "machine" / "runtime-pins.json").read_text(encoding="utf-8"))
HOST = (ROOT / "defs" / "falco-host.yaml").read_text(encoding="utf-8")
OUTBOUND = (ROOT / "scripts" / "lib" / "check-outbound.sh").read_text(encoding="utf-8")
SCAN = ROOT / "scripts" / "kalived-scan.sh"
AIDE = (ROOT / "playbooks" / "aide-init.sh").read_text(encoding="utf-8")


def test_versions() -> None:
    assert parse_ver("v24.22.1-1nodesource1")[:3] == (24, 22, 1)
    assert parse_ver("1.2.0-4+b2")[:3] == (1, 2, 0)
    assert parse_ver("20260816+nmu1")[0] == 20260816
    assert ver_ge("24.22.1", "24.22.1")
    assert ver_ge("24.22.2", "24.22.1")
    assert not ver_ge("24.21.0", "24.22.1")
    assert node_ok("v24.22.1", PINS)
    assert node_ok("v22.23.4", PINS)
    assert node_ok("v25.0.0", PINS)
    assert not node_ok("v24.21.0", PINS)
    assert not node_ok("v22.23.3", PINS)
    assert not node_ok("v23.0.0", PINS)
    assert brotli_ok("1.2.1", PINS)
    assert brotli_ok("1.2.1-1", PINS)
    assert not brotli_ok("1.2.0-4+b2", PINS)
    print("OK version pins")


def test_listeners() -> None:
    ss = (
        'tcp LISTEN 0 4096 127.0.0.1:9000 0.0.0.0:* users:(("php-fpm",pid=200,fd=8))\n'
        'tcp LISTEN 0 128 127.0.0.1:80 0.0.0.0:* users:(("apache2",pid=201,fd=4))\n'
        'tcp LISTEN 0 511 127.0.0.1:5173 0.0.0.0:* users:(("node",pid=1,fd=1))\n'
    )
    hits = php_apache_listeners(ss)
    assert len(hits) == 2, hits
    assert not php_apache_listeners('tcp LISTEN 127.0.0.1:5173 users:(("node",pid=1,fd=1))\n')
    print("OK php-fpm/apache listeners")


def test_findings(tmp: Path) -> None:
    (tmp / "runtime_versions.json").write_text(
        json.dumps({"node": "v24.21.0", "brotli": "1.2.0"}), encoding="utf-8"
    )
    (tmp / "ss_tulpn.txt").write_text(
        'tcp LISTEN 0 4096 127.0.0.1:9000 0.0.0.0:* users:(("php-fpm",pid=9,fd=1))\n',
        encoding="utf-8",
    )
    recs = findings_from_snapshot(tmp, ROOT / "baselines" / "machine" / "runtime-pins.json")
    ids = [r["id"] for r in recs]
    assert ids == ["HOST-RUNTIME", "HOST-RUNTIME"], recs
    assert all(r["severity"] == "WARN" for r in recs)
    assert "24.21.0" in recs[0]["title"]
    assert "php-fpm" in recs[1]["title"]
    clean = tmp / "clean"
    clean.mkdir()
    (clean / "runtime_versions.json").write_text(
        json.dumps({"node": "v24.22.1", "brotli": "1.2.1"}), encoding="utf-8"
    )
    (clean / "ss_tulpn.txt").write_text(
        'tcp LISTEN 0 511 127.0.0.1:5173 0.0.0.0:* users:(("node",pid=1,fd=1))\n',
        encoding="utf-8",
    )
    assert findings_from_snapshot(clean, ROOT / "baselines" / "machine" / "runtime-pins.json") == []
    empty = tmp / "empty"
    empty.mkdir()
    assert findings_from_snapshot(empty, ROOT / "baselines" / "machine" / "runtime-pins.json") == []
    print("OK HOST-RUNTIME findings")


def test_tree() -> None:
    for name in INTERP_NAMES:
        assert name in HOST, name
        assert name in OUTBOUND, name
    assert "5173" in HOST and "8788" in HOST
    assert "kalived_cockpit_connect" in HOST
    assert "cockpit_ports" in OUTBOUND
    assert "interpish" in OUTBOUND
    assert "check-runtime.sh" in SCAN.read_text(encoding="utf-8")
    assert "check_runtime" in SCAN.read_text(encoding="utf-8")
    assert "runtime_versions.json" in (ROOT / "scripts" / "collect-baseline.sh").read_text(
        encoding="utf-8"
    )
    assert "apt-get" not in (ROOT / "scripts" / "lib" / "check-runtime.sh").read_text(encoding="utf-8")
    assert "apt-get" not in (ROOT / "scripts" / "lib" / "runtime_pins.py").read_text(encoding="utf-8")
    assert COCKPIT_PORTS == frozenset({"5173", "8788"})
    # ALERT-gate urørt
    assert "kalived_require_not_alert" in AIDE
    assert "--force-alert" in AIDE
    print("OK tree interp + runtime + ALERT-gate")


def main() -> int:
    import tempfile

    test_versions()
    test_listeners()
    test_tree()
    with tempfile.TemporaryDirectory() as d:
        test_findings(Path(d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
