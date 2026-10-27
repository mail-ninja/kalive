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
    is_identity_binary,
    parse_paths,
)

WARN_FIX = ROOT / "scripts" / "testdata" / "cases" / "warn_aide_classes" / "aide_check.txt"
ALERT_FIX = ROOT / "scripts" / "testdata" / "cases" / "alert_aide_identity" / "aide_check.txt"
PKG_DIR = ROOT / "scripts" / "testdata" / "cases" / "warn_aide_pkg"
NODPKG_DIR = ROOT / "scripts" / "testdata" / "cases" / "alert_aide_identity_nodpkg"
ADDED_DIR = ROOT / "scripts" / "testdata" / "cases" / "warn_aide_pkg_added"
BINARY_DIR = ROOT / "scripts" / "testdata" / "cases" / "warn_aide_pkg_binary"
STALE_DIR = ROOT / "scripts" / "testdata" / "cases" / "alert_aide_identity_stale"
STALE_OK_DIR = ROOT / "scripts" / "testdata" / "cases" / "warn_aide_stale"
STALE_FAIL_DIR = ROOT / "scripts" / "testdata" / "cases" / "alert_aide_stale_failed"
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
            "stale",
            "pkg",
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
    assert is_identity_binary("/usr/bin/sudo")
    assert is_identity_binary("/usr/bin/passwd")
    assert not is_identity_binary("/etc/ssh/ssh_config")
    assert not is_identity_binary("/etc/ssh/ssh_host_mldsa44_ed25519_key")
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


def test_pkg_window_is_warn() -> None:
    recs = findings_from_report(
        (PKG_DIR / "aide_check.txt").read_text(encoding="utf-8"),
        {},
        PKG_DIR,
    )
    sevs = _sevs(recs)
    ids = {r.get("id") for r in recs}
    blob = _titles(recs) + "\n" + "\n".join(r.get("detail", "") for r in recs)
    assert sevs.get("pkg") == "WARN", recs
    assert "FIM-AIDE-PKG" in ids, recs
    assert "identity" not in sevs, recs
    assert sevs.get("snap_proton") == "WARN", recs
    assert "/usr/bin/sudo" in blob
    assert "/etc/ssh/ssh_host_mldsa44_ed25519_key" in blob
    assert "proton" in blob.lower()
    print("OK pkg window → FIM-AIDE-PKG WARN, Proton WARN")


def _blob_for(recs: list[dict], cls: str) -> str:
    parts: list[str] = []
    for r in recs:
        title = r.get("title", "")
        if f"AIDE {cls}:" in title or title.startswith(f"AIDE {cls}"):
            parts.append(title)
            parts.append(r.get("detail") or "")
    return "\n".join(parts)


def test_added_key_stat_mtime_is_pkg() -> None:
    recs = findings_from_report(
        (ADDED_DIR / "aide_check.txt").read_text(encoding="utf-8"),
        {},
        ADDED_DIR,
    )
    sevs = _sevs(recs)
    ids = {r.get("id") for r in recs}
    pkg = _blob_for(recs, "pkg")
    ident = _blob_for(recs, "identity")
    blob = _titles(recs) + "\n" + "\n".join(r.get("detail", "") for r in recs)
    assert sevs.get("pkg") == "WARN", recs
    assert "FIM-AIDE-PKG" in ids, recs
    assert "identity" not in sevs, recs
    assert ident == ""
    assert "/etc/ssh/ssh_host_mldsa44_ed25519_key" in pkg
    assert sevs.get("snap_proton") == "WARN", recs
    assert "proton" in blob.lower()
    print("OK Added uten AIDE-Mtime → FIM-AIDE-PKG, Proton WARN")


def test_binary_ignores_build_mtime() -> None:
    recs = findings_from_report(
        (BINARY_DIR / "aide_check.txt").read_text(encoding="utf-8"),
        {},
        BINARY_DIR,
    )
    sevs = _sevs(recs)
    ids = {r.get("id") for r in recs}
    pkg = _blob_for(recs, "pkg")
    assert sevs.get("pkg") == "WARN", recs
    assert "FIM-AIDE-PKG" in ids, recs
    assert "identity" not in sevs, recs
    assert "/usr/bin/sudo" in pkg
    assert sevs.get("snap_proton") == "WARN", recs
    print("OK sudo byggetid ignorert, configure i scan-vindu → PKG")


def test_stale_identity_stays_alert() -> None:
    recs = findings_from_report(
        (STALE_DIR / "aide_check.txt").read_text(encoding="utf-8"),
        {},
        STALE_DIR,
    )
    sevs = _sevs(recs)
    ids = {r.get("id") for r in recs}
    ident = _blob_for(recs, "identity")
    pkg = _blob_for(recs, "pkg")
    blob = _titles(recs) + "\n" + "\n".join(r.get("detail", "") for r in recs)
    assert sevs.get("identity") == "ALERT", recs
    assert sevs.get("pkg") == "WARN", recs
    assert "FIM-AIDE-PKG" in ids, recs
    assert "/etc/ssh/ssh_config" in ident
    assert "20-systemd-ssh-proxy.conf" in ident
    assert "/usr/bin/passwd" in ident
    assert "/usr/bin/su" in ident
    assert "/usr/bin/sudo" in pkg
    assert "/etc/ssh/ssh_host_mldsa44_ed25519_key" in pkg
    assert "/etc/ssh/ssh_config" not in pkg
    assert "/usr/bin/passwd" not in pkg
    assert sevs.get("snap_proton") == "WARN", recs
    assert "proton" in blob.lower()
    print("OK stale ssh_config/proxy/passwd/su identity; nøkler+sudo PKG; Proton WARN")


def test_debsums_ok_is_stale_warn() -> None:
    recs = findings_from_report(
        (STALE_OK_DIR / "aide_check.txt").read_text(encoding="utf-8"),
        {},
        STALE_OK_DIR,
    )
    sevs = _sevs(recs)
    ids = {r.get("id") for r in recs}
    stale = _blob_for(recs, "stale")
    ident = _blob_for(recs, "identity")
    pkg = _blob_for(recs, "pkg")
    blob = _titles(recs) + "\n" + "\n".join(r.get("detail", "") for r in recs)
    assert sevs.get("stale") == "WARN", recs
    assert "FIM-AIDE-STALE" in ids, recs
    assert "identity" not in sevs, recs
    assert ident == ""
    assert "/etc/ssh/ssh_config" in stale
    assert "20-systemd-ssh-proxy.conf" in stale
    assert "20-systemd-userdb.conf" in stale
    assert "/usr/bin/passwd" in stale
    assert "/usr/bin/su" in stale
    assert "/usr/bin/sudo" in pkg
    assert "ssh_host_mldsa44" in pkg
    assert sevs.get("snap_proton") == "WARN", recs
    assert "proton" in blob.lower()
    print("OK fem debsums-OK → FIM-AIDE-STALE WARN, nøkler+sudo PKG, Proton WARN")


def test_one_debsums_failed_is_identity() -> None:
    recs = findings_from_report(
        (STALE_FAIL_DIR / "aide_check.txt").read_text(encoding="utf-8"),
        {},
        STALE_FAIL_DIR,
    )
    sevs = _sevs(recs)
    ids = {r.get("id") for r in recs}
    ident = _blob_for(recs, "identity")
    stale = _blob_for(recs, "stale")
    assert sevs.get("identity") == "ALERT", recs
    assert "FIM-AIDE-STALE" in ids, recs
    assert "/usr/bin/passwd" in ident
    assert "/usr/bin/passwd" not in stale
    assert "/etc/ssh/ssh_config" in stale
    assert sevs.get("snap_proton") == "WARN", recs
    print("OK én debsums-FAILED → identity ALERT, resten STALE, Proton WARN")


def test_same_paths_without_dpkg_alert() -> None:
    recs = findings_from_report(
        (NODPKG_DIR / "aide_check.txt").read_text(encoding="utf-8"),
        {},
        NODPKG_DIR,
    )
    sevs = _sevs(recs)
    ids = {r.get("id") for r in recs}
    assert sevs.get("identity") == "ALERT", recs
    assert "FIM-AIDE-PKG" not in ids, recs
    assert sevs.get("snap_proton") == "WARN", recs
    print("OK same paths uten dpkg → identity ALERT, Proton WARN")


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


def test_scan_pkg_warn() -> None:
    rc, doc = _scan("warn_aide_pkg")
    assert rc == 1 and doc["verdict"] == "WARN", (rc, doc.get("verdict"), doc.get("findings"))
    ids = [f.get("id") for f in doc.get("findings") or []]
    titles = " ".join(f.get("title", "") for f in doc.get("findings") or [])
    assert "FIM-AIDE-PKG" in ids, ids
    assert "AIDE identity" not in titles
    assert "snap_proton" in titles
    print("OK scan pkg WARN exit 1, Proton WARN")


def test_scan_added_pkg_warn() -> None:
    rc, doc = _scan("warn_aide_pkg_added")
    assert rc == 1 and doc["verdict"] == "WARN", (rc, doc.get("verdict"), doc.get("findings"))
    ids = [f.get("id") for f in doc.get("findings") or []]
    titles = " ".join(f.get("title", "") for f in doc.get("findings") or [])
    details = " ".join(f.get("detail", "") for f in doc.get("findings") or [])
    blob = titles + " " + details
    assert "FIM-AIDE-PKG" in ids, ids
    assert "AIDE identity" not in titles
    assert "ssh_host_mldsa44" in blob
    assert "snap_proton" in titles
    print("OK scan Added-key WARN exit 1, Proton WARN")


def test_scan_binary_pkg_warn() -> None:
    rc, doc = _scan("warn_aide_pkg_binary")
    assert rc == 1 and doc["verdict"] == "WARN", (rc, doc.get("verdict"), doc.get("findings"))
    ids = [f.get("id") for f in doc.get("findings") or []]
    titles = " ".join(f.get("title", "") for f in doc.get("findings") or [])
    details = " ".join(f.get("detail", "") for f in doc.get("findings") or [])
    assert "FIM-AIDE-PKG" in ids, ids
    assert "AIDE identity" not in titles
    assert "/usr/bin/sudo" in details
    assert "snap_proton" in titles
    print("OK scan sudo-binær WARN exit 1, Proton WARN")


def test_scan_stale_alert() -> None:
    rc, doc = _scan("alert_aide_identity_stale")
    assert rc == 2 and doc["verdict"] == "ALERT", (rc, doc.get("verdict"), doc.get("findings"))
    ids = [f.get("id") for f in doc.get("findings") or []]
    titles = " ".join(f.get("title", "") for f in doc.get("findings") or [])
    details = " ".join(f.get("detail", "") for f in doc.get("findings") or [])
    ident = " ".join(
        f.get("detail", "") for f in doc.get("findings") or [] if f.get("title", "").startswith("AIDE identity")
    )
    pkg = " ".join(
        f.get("detail", "") for f in doc.get("findings") or [] if f.get("title", "").startswith("AIDE pkg")
    )
    assert "FIM-AIDE" in ids, ids
    assert "FIM-AIDE-PKG" in ids, ids
    assert "identity" in titles
    assert "snap_proton" in titles
    assert "/etc/ssh/ssh_config" in ident
    assert "/usr/bin/passwd" in ident
    assert "/usr/bin/su" in ident
    assert "/usr/bin/sudo" in pkg
    assert "ssh_host_mldsa44" in pkg
    print("OK scan stale identity ALERT exit 2, nøkler+sudo PKG, Proton WARN")


def test_scan_stale_ok_warn() -> None:
    rc, doc = _scan("warn_aide_stale")
    assert rc == 1 and doc["verdict"] == "WARN", (rc, doc.get("verdict"), doc.get("findings"))
    ids = [f.get("id") for f in doc.get("findings") or []]
    titles = " ".join(f.get("title", "") for f in doc.get("findings") or [])
    stale = " ".join(
        f.get("detail", "") for f in doc.get("findings") or [] if f.get("title", "").startswith("AIDE stale")
    )
    ident = " ".join(
        f.get("detail", "") for f in doc.get("findings") or [] if f.get("title", "").startswith("AIDE identity")
    )
    pkg = " ".join(
        f.get("detail", "") for f in doc.get("findings") or [] if f.get("title", "").startswith("AIDE pkg")
    )
    assert "FIM-AIDE-STALE" in ids, ids
    assert "AIDE identity" not in titles
    assert ident == ""
    assert "/etc/ssh/ssh_config" in stale
    assert "20-systemd-userdb.conf" in stale
    assert "/usr/bin/passwd" in stale
    assert "/usr/bin/su" in stale
    assert "/usr/bin/sudo" in pkg
    assert "snap_proton" in titles
    print("OK scan fem STALE WARN exit 1, Proton WARN")


def test_scan_stale_failed_alert() -> None:
    rc, doc = _scan("alert_aide_stale_failed")
    assert rc == 2 and doc["verdict"] == "ALERT", (rc, doc.get("verdict"), doc.get("findings"))
    ids = [f.get("id") for f in doc.get("findings") or []]
    ident = " ".join(
        f.get("detail", "") for f in doc.get("findings") or [] if f.get("title", "").startswith("AIDE identity")
    )
    assert "FIM-AIDE" in ids, ids
    assert "/usr/bin/passwd" in ident
    titles = " ".join(f.get("title", "") for f in doc.get("findings") or [])
    assert "snap_proton" in titles
    print("OK scan én FAILED identity ALERT exit 2, Proton WARN")


def test_scan_nodpkg_alert() -> None:
    rc, doc = _scan("alert_aide_identity_nodpkg")
    assert rc == 2 and doc["verdict"] == "ALERT", (rc, doc.get("verdict"))
    ids = [f.get("id") for f in doc.get("findings") or []]
    titles = " ".join(f.get("title", "") for f in doc.get("findings") or [])
    assert "FIM-AIDE-PKG" not in ids, ids
    assert "identity" in titles
    assert "snap_proton" in titles
    print("OK scan uten dpkg ALERT exit 2, Proton WARN")


def _fake_data(verdict: str, findings: list | None = None) -> Path:
    td = Path(tempfile.mkdtemp())
    stamp = td / "logs" / "status" / "2026-01-01_000000"
    stamp.mkdir(parents=True)
    (stamp / "meta.txt").write_text("kalived_scan=1\nsudo=1\n", encoding="utf-8")
    (stamp / "verdict.json").write_text(
        json.dumps(
            {
                "verdict": verdict,
                "exit_code": 2 if verdict == "ALERT" else 1,
                "findings": findings or [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return td


_STALE_FINDING = {
    "severity": "WARN",
    "id": "FIM-AIDE-STALE",
    "title": "AIDE stale: /etc/ssh/ssh_config, /usr/bin/passwd",
    "detail": "/etc/ssh/ssh_config\n/etc/ssh/ssh_config.d/20-systemd-ssh-proxy.conf\n/etc/ssh/sshd_config.d/20-systemd-userdb.conf\n/usr/bin/passwd\n/usr/bin/su",
    "source": "aide_check.txt",
}


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


def test_aide_init_all_forbidden() -> None:
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
    assert p.returncode == 2, (p.returncode, p.stderr)
    blob = p.stderr + p.stdout
    assert "forbudt" in blob
    print("OK --all forbudt exit 2")


def test_gate_open_on_pkg_warn() -> None:
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
    assert dest.is_file()
    print("OK gate åpen på PKG-WARN/WARN")


def test_gate_stale_denied_without_ack() -> None:
    data = _fake_data("WARN", [_STALE_FINDING])
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
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)
    blob = p.stderr + p.stdout
    assert "STALE" in blob or "stale" in blob
    assert "uacka" in blob
    assert not (data / "aide-scope.json").exists()
    print("OK gate stengt på uacka STALE")


def test_gate_ack_stale_writes_paths() -> None:
    data = _fake_data("WARN", [_STALE_FINDING])
    dest = data / "aide-scope.json"
    env = os.environ.copy()
    env["KALIVED_AIDE_INIT_DRY"] = "1"
    env["KALIVED_DATA"] = str(data)
    env["KALIVED_AIDE_SCOPE"] = str(dest)
    p = subprocess.run(
        ["bash", str(INIT), "--ack-stale"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
    doc = json.loads(dest.read_text(encoding="utf-8"))
    prefs = doc.get("prefixes") or []
    assert "/etc/sudoers.d/kalived" in prefs
    assert "/etc/ssh/ssh_config" in prefs
    assert "/usr/bin/passwd" in prefs
    assert "/usr/bin/su" in prefs
    assert not any("proton" in str(x).lower() for x in prefs)
    print("OK --ack-stale skriver ssh/passwd i scope, Proton ute")


def test_gate_ack_stale_denied_on_identity() -> None:
    data = _fake_data(
        "ALERT",
        [
            {
                "severity": "ALERT",
                "id": "FIM-AIDE",
                "title": "AIDE identity: /usr/bin/passwd",
                "detail": "/usr/bin/passwd",
            },
            _STALE_FINDING,
        ],
    )
    env = os.environ.copy()
    env["KALIVED_AIDE_INIT_DRY"] = "1"
    env["KALIVED_DATA"] = str(data)
    env["KALIVED_AIDE_SCOPE"] = str(data / "aide-scope.json")
    p = subprocess.run(
        ["bash", str(INIT), "--ack-stale"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert p.returncode != 0, (p.returncode, p.stdout, p.stderr)
    assert "ALERT" in (p.stderr + p.stdout)
    print("OK --ack-stale nektes på identity-ALERT")


def test_ctl_never_all() -> None:
    text = CTL.read_text(encoding="utf-8")
    exec_lines = [ln for ln in text.splitlines() if "aide-init.sh" in ln and "exec" in ln]
    assert exec_lines, "mangler exec aide-init"
    assert any("--force" in ln for ln in exec_lines)
    assert all("--all" not in ln for ln in exec_lines)
    assert all("--ack-stale" not in ln for ln in exec_lines)
    print("OK ctl aide-init is --force only")


def main() -> int:
    test_classify()
    test_parse_live_format()
    test_warn_classes()
    test_freeze_keeps_proton()
    test_pkg_window_is_warn()
    test_added_key_stat_mtime_is_pkg()
    test_binary_ignores_build_mtime()
    test_stale_identity_stays_alert()
    test_debsums_ok_is_stale_warn()
    test_one_debsums_failed_is_identity()
    test_same_paths_without_dpkg_alert()
    test_identity_alert_keeps_snap()
    test_scan_fixture_warn()
    test_scan_fixture_freeze()
    test_scan_identity()
    test_scan_pkg_warn()
    test_scan_added_pkg_warn()
    test_scan_binary_pkg_warn()
    test_scan_stale_alert()
    test_scan_stale_ok_warn()
    test_scan_stale_failed_alert()
    test_scan_nodpkg_alert()
    test_aide_init_force_alert_denied()
    test_aide_init_force_warn_scoped()
    test_gate_open_on_pkg_warn()
    test_gate_stale_denied_without_ack()
    test_gate_ack_stale_writes_paths()
    test_gate_ack_stale_denied_on_identity()
    test_aide_init_all_forbidden()
    test_ctl_never_all()
    print("ALL OK aide_scope")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
