#!/usr/bin/env python3
"""Path-scoped AIDE: classes, freeze overlay, aide-init --force ALERT gate."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from aide_classify import (  # noqa: E402
    DEFAULT_SCOPE,
    classify_path,
    decode_path,
    findings_from_report,
    parse_paths,
)

WARN_FIX = ROOT / "scripts" / "testdata" / "cases" / "warn_aide_classes" / "aide_check.txt"
ALERT_FIX = ROOT / "scripts" / "testdata" / "cases" / "alert_aide_identity" / "aide_check.txt"
SCAN = ROOT / "scripts" / "kalived-scan.sh"
INIT = ROOT / "playbooks" / "aide-init.sh"
CTL = ROOT / "scripts" / "kalived-ctl"


def _titles(recs: list[dict]) -> str:
    return "\n".join(r.get("title", "") for r in recs)


def _sevs(recs: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for r in recs:
        t = r.get("title", "")
        for cls in (
            "identity",
            "self_sudoers",
            "snap_proton",
            "snap_other",
            "self_helper",
            "other",
        ):
            if cls in t:
                out[cls] = r.get("severity", "")
    return out


def test_classify() -> None:
    assert classify_path("/etc/sudoers.d/kalived") == "self_sudoers"
    assert classify_path("/etc/sudoers") == "identity"
    assert classify_path("/etc/passwd") == "identity"
    assert classify_path("/usr/sbin/kalived-ctl") == "self_helper"
    assert classify_path("/usr/local/lib/kalived/scripts/kalived-watch.sh") == "self_helper"
    assert classify_path("/etc/systemd/system/kalived-watch.timer") == "self_helper"
    raw = "/etc/systemd/system/snap-proton\\x2dvpn-11.mount"
    assert decode_path(raw) == "/etc/systemd/system/snap-proton-vpn-11.mount"
    assert classify_path(raw) == "snap_proton"
    assert classify_path("/etc/udev/rules.d/70-snap.proton-vpn.rules") == "snap_proton"
    assert classify_path("/etc/systemd/system/snap-snapd-28254.mount") == "snap_other"
    assert classify_path("/etc/cron.d/evil") == "other"
    print("OK classify")


def test_parse_live_format() -> None:
    text = WARN_FIX.read_text(encoding="utf-8")
    paths = [p for _, p in parse_paths(text)]
    assert "/etc/sudoers.d/kalived" in paths
    assert "/etc/systemd/system/snap-proton-vpn-11.mount" in paths
    assert "/etc/udev/rules.d/70-snap.proton-vpn.rules" in paths
    assert "/etc/systemd/system" not in paths  # dir mtime skipped
    assert "/usr/sbin/kalived-ctl" in paths
    print("OK parse")


def test_warn_classes() -> None:
    recs = findings_from_report(WARN_FIX.read_text(encoding="utf-8"), {})
    sevs = _sevs(recs)
    blob = _titles(recs) + "\n" + "\n".join(r.get("detail", "") for r in recs)
    assert sevs.get("self_sudoers") == "WARN", recs
    assert sevs.get("snap_proton") == "WARN", recs
    assert sevs.get("snap_other") == "WARN", recs
    assert sevs.get("self_helper") == "INFO", recs
    assert "identity" not in sevs
    assert "/etc/sudoers.d/kalived" in blob
    assert "proton" in blob.lower()
    print("OK warn classes (sudoers+proton WARN, helper INFO)")


def test_freeze_keeps_proton() -> None:
    scope = {"mode": "scoped", "prefixes": list(DEFAULT_SCOPE), "sha256": {}}
    recs = findings_from_report(WARN_FIX.read_text(encoding="utf-8"), scope)
    sevs = _sevs(recs)
    blob = _titles(recs) + "\n" + "\n".join(r.get("detail", "") for r in recs)
    assert "self_sudoers" not in sevs, recs
    assert "self_helper" not in sevs, recs
    assert sevs.get("snap_proton") == "WARN", recs
    assert sevs.get("snap_other") == "WARN", recs
    assert "proton" in blob.lower()
    print("OK freeze: sudoers gone, Proton still WARN")


def test_identity_alert_keeps_snap() -> None:
    recs = findings_from_report(ALERT_FIX.read_text(encoding="utf-8"), {})
    sevs = _sevs(recs)
    assert sevs.get("identity") == "ALERT", recs
    assert sevs.get("snap_proton") == "WARN", recs
    assert sevs.get("snap_other") == "WARN", recs
    print("OK identity ALERT does not swallow snap")


def _scan(case: str, env: dict[str, str] | None = None) -> tuple[int, dict]:
    e = os.environ.copy()
    e.pop("KALIVED_AIDE_SCOPE", None)
    if env:
        e.update(env)
    e["KALIVED_FIXTURE"] = "1"
    p = subprocess.run(
        ["bash", str(SCAN), "--fixture", str(ROOT / "scripts" / "testdata" / "cases" / case), "--quiet", "--skip-hunt"],
        capture_output=True,
        text=True,
        env=e,
        check=False,
    )
    doc = json.loads(p.stdout)
    return p.returncode, doc


def test_scan_fixture_warn() -> None:
    rc, doc = _scan("warn_aide_classes")
    assert rc == 1 and doc["verdict"] == "WARN", (rc, doc.get("verdict"), doc.get("findings"))
    titles = " ".join(f.get("title", "") for f in doc.get("findings") or [])
    details = " ".join(f.get("detail", "") for f in doc.get("findings") or [])
    blob = titles + " " + details
    assert "self_sudoers" in blob, titles
    assert "snap_proton" in blob, titles
    assert "self_helper" in blob, titles
    print("OK scan fixture WARN sudoers+Proton, helper INFO")


def test_scan_fixture_freeze() -> None:
    with tempfile.TemporaryDirectory() as td:
        scope = Path(td) / "aide-scope.json"
        scope.write_text(
            json.dumps({"schema": 1, "mode": "scoped", "prefixes": list(DEFAULT_SCOPE), "sha256": {}}) + "\n",
            encoding="utf-8",
        )
        rc, doc = _scan("warn_aide_classes", {"KALIVED_AIDE_SCOPE": str(scope)})
        assert rc == 1 and doc["verdict"] == "WARN", (rc, doc.get("verdict"))
        titles = " ".join(f.get("title", "") for f in doc.get("findings") or [])
        details = " ".join(f.get("detail", "") for f in doc.get("findings") or [])
        blob = titles + " " + details
        assert "self_sudoers" not in blob, titles
        assert "snap_proton" in blob, titles
        print("OK scan after scoped freeze: Proton WARN, sudoers gone")


def test_scan_identity() -> None:
    rc, doc = _scan("alert_aide_identity")
    assert rc == 2 and doc["verdict"] == "ALERT", (rc, doc.get("verdict"))
    titles = " ".join(f.get("title", "") for f in doc.get("findings") or [])
    assert "identity" in titles
    assert "snap_proton" in titles
    print("OK scan identity ALERT + Proton WARN")


def _fake_data(verdict: str) -> Path:
    td = Path(tempfile.mkdtemp())
    stamp = td / "logs" / "status" / "2026-01-01_000000"
    stamp.mkdir(parents=True)
    (stamp / "meta.txt").write_text("kalived_scan=1\nsudo=1\n", encoding="utf-8")
    (stamp / "verdict.json").write_text(
        json.dumps({"verdict": verdict, "exit_code": 2 if verdict == "ALERT" else 1, "findings": []}) + "\n",
        encoding="utf-8",
    )
    return td


def test_aide_init_force_alert_denied() -> None:
    data = _fake_data("ALERT")
    env = os.environ.copy()
    env["KALIVED_AIDE_INIT_DRY"] = "1"
    env["KALIVED_DATA"] = str(data)
    env["KALIVED_AIDE_SCOPE"] = str(data / "aide-scope.json")
    p = subprocess.run(
        ["bash", str(INIT), "--force"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert p.returncode != 0, (p.returncode, p.stdout, p.stderr)
    assert "ALERT" in (p.stderr + p.stdout)
    print("OK aide-init --force ALERT exit", p.returncode)


def test_aide_init_force_warn_scoped() -> None:
    data = _fake_data("WARN")
    dest = data / "aide-scope.json"
    env = os.environ.copy()
    env["KALIVED_AIDE_INIT_DRY"] = "1"
    env["KALIVED_DATA"] = str(data)
    env["KALIVED_AIDE_SCOPE"] = str(dest)
    p = subprocess.run(
        ["bash", str(INIT), "--force"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
    assert dest.is_file(), dest
    doc = json.loads(dest.read_text(encoding="utf-8"))
    assert doc.get("mode") == "scoped"
    assert "/etc/sudoers.d/kalived" in doc.get("prefixes", [])
    assert "fryser kalived-filer, ikke Proton" in (p.stderr + p.stdout)
    print("OK aide-init --force WARN writes scoped overlay")


def test_aide_init_all_warns_proton() -> None:
    data = _fake_data("WARN")
    env = os.environ.copy()
    env["KALIVED_AIDE_INIT_DRY"] = "1"
    env["KALIVED_DATA"] = str(data)
    p = subprocess.run(
        ["bash", str(INIT), "--force", "--all"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert p.returncode == 0, (p.returncode, p.stderr)
    blob = p.stderr + p.stdout
    assert "--all" in blob and "Proton" in blob
    print("OK --all prints Proton FIM warning")


def test_ctl_never_all() -> None:
    text = CTL.read_text(encoding="utf-8")
    exec_lines = [ln for ln in text.splitlines() if "aide-init.sh" in ln and "exec" in ln]
    assert exec_lines, "mangler exec aide-init"
    assert any("--force" in ln for ln in exec_lines)
    assert all("--all" not in ln for ln in exec_lines)
    print("OK ctl aide-init is --force only")


def main() -> int:
    test_classify()
    test_parse_live_format()
    test_warn_classes()
    test_freeze_keeps_proton()
    test_identity_alert_keeps_snap()
    test_scan_fixture_warn()
    test_scan_fixture_freeze()
    test_scan_identity()
    test_aide_init_force_alert_denied()
    test_aide_init_force_warn_scoped()
    test_aide_init_all_warns_proton()
    test_ctl_never_all()
    print("ALL OK aide_scope")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
