#!/usr/bin/env python3
"""H5: Falco host-burst. Empty jsonl = no finding. No cmdline/SNI/pcap. No Qdrant/hiroshima write."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
sys.path.insert(0, str(ROOT / "cockpit" / "backend"))

from falco_burst import (  # noqa: E402
    ALLOWED,
    aggregate,
    digest_rows,
    findings_from_rows,
    leaks,
    load_jsonl,
    parse_event,
    write_jsonl,
)
from app.hiroshima_decide import (  # noqa: E402
    digest_from_snapshot,
    mercury_rules,
    payload_leaks,
    port,
    ring_from_snapshot,
)

CASES = ROOT / "scripts" / "testdata" / "cases"

SAMPLE = {
    "output": "memfd exec exe=/memfd:payload evt=execve cmdline=python3 -c evil",
    "priority": "Critical",
    "rule": "kalived_memfd_exec",
    "time": "2026-10-01T00:00:00.000000+0000",
    "output_fields": {
        "proc.exepath": "/memfd:payload",
        "proc.name": "python3",
        "proc.cmdline": "python3 -c 'import socket; socket.connect((\"198.51.100.9\",443))'",
        "evt.type": "execve",
        "fd.rip": "198.51.100.9",
        "fd.sip": "10.125.19.203",
        "fd.sni": "evil.example.com",
        "container.id": "host",
    },
}


def _assert_clean(obj: object, label: str, *, rows: bool = False) -> None:
    blob = json.dumps(obj, ensure_ascii=False)
    if rows:
        hits = leaks(obj)
        assert not hits, (label, hits, blob[:500])
        assert "pcap" not in blob.lower(), label
    assert "cmdline" not in blob.lower(), label
    assert "proc.cmdline" not in blob.lower(), label
    assert "198.51.100" not in blob, label
    assert "evil.example" not in blob, label
    assert "sni" not in blob.lower(), label
    if isinstance(obj, dict):
        proto_hits = payload_leaks(obj)
        assert not proto_hits, (label, proto_hits)


def test_parse() -> None:
    rec = parse_event(SAMPLE)
    assert rec == ("kalived_memfd_exec", "memfd", "execve"), rec
    rows = aggregate(json.dumps(SAMPLE) + "\n" + json.dumps(SAMPLE) + "\n")
    assert rows == [{"rule": "kalived_memfd_exec", "exe": "memfd", "evt.type": "execve", "n": 2}], rows
    assert set(rows[0]) <= set(ALLOWED)
    _assert_clean(rows, "aggregate", rows=True)
    print("OK parse stripped cmdline/IP/SNI")


def test_empty() -> None:
    recs = findings_from_rows([])
    assert recs == [], recs
    p = CASES / "clean_falco_empty" / "hunt_falco.jsonl"
    assert p.is_file(), p
    assert p.stat().st_size == 0
    assert load_jsonl(p) == []
    print("OK empty jsonl no finding")


def test_findings() -> None:
    only = findings_from_rows(
        [{"rule": "kalived_memfd_exec", "exe": "python3", "evt.type": "execve", "n": 1}]
    )
    assert only[0]["severity"] == "WARN" and only[0]["id"] == "HOST-FALCO", only
    dual_f = findings_from_rows(
        [{"rule": "kalived_write_preload", "exe": "python3", "evt.type": "openat", "n": 1}],
        ids={"FIM-AIDE": "WARN"},
    )
    assert dual_f[0]["severity"] == "ALERT", dual_f
    dual_n = findings_from_rows(
        [{"rule": "kalived_interp_connect", "exe": "python3", "evt.type": "connect", "n": 2}],
        ids={"NET-LISTEN-EXT": "ALERT"},
    )
    assert dual_n[0]["severity"] == "ALERT", dual_n
    info = findings_from_rows([], absent=True)
    assert info[0]["severity"] == "INFO" and info[0]["title"] == "falco absent", info
    quiet = findings_from_rows(
        [{"rule": "kalived_memfd_exec", "exe": "python3", "evt.type": "execve", "n": 1}],
        ids={"FIM-AIDE": "INFO"},
    )
    assert quiet[0]["severity"] == "WARN", quiet
    print("OK findings WARN/ALERT/INFO")


def _snap(tmp: Path, *, rows: list[dict] | None, findings: list[dict], verdict: str) -> Path:
    snap = tmp / "snap"
    snap.mkdir(parents=True)
    if rows is not None:
        write_jsonl(snap / "hunt_falco.jsonl", rows)
    (snap / "verdict.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "verdict": verdict,
                "exit_code": {"CLEAN": 0, "WARN": 1, "ALERT": 2, "ERROR": 3}[verdict],
                "stamp": "h5",
                "sudo": 0,
                "findings": findings,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return snap


def test_port(tmp: Path) -> None:
    empty = _snap(tmp / "empty", rows=[], findings=[], verdict="CLEAN")
    d0 = digest_from_snapshot(empty)
    assert d0["falco"] == [], d0["falco"]
    p0 = port(empty, live=False)
    assert p0["class"] in ("noise", "env_shift"), p0["class"]
    assert p0["class"] != "candidate", p0
    _assert_clean(p0, "empty-port")

    only_rows = [{"rule": "kalived_memfd_exec", "exe": "python3", "evt.type": "execve", "n": 1}]
    only = _snap(
        tmp / "only",
        rows=only_rows,
        findings=[{"severity": "WARN", "id": "HOST-FALCO", "title": "Falco candidate"}],
        verdict="WARN",
    )
    (only / "nm_active.txt").write_text("Gal:00000000-0000-0000-0000-000000000000:802-11-wireless:wlan0\n")
    d1 = digest_from_snapshot(only)
    assert d1["falco"] == only_rows, d1["falco"]
    _assert_clean({"falco": d1["falco"]}, "only-digest", rows=True)
    p1 = port(only, live=False)
    assert p1["class"] == "candidate", p1
    assert float(p1.get("dual") or 0) < 0.5, p1
    merc = p1.get("mercury") or mercury_rules(d1, [])
    assert merc.get("why") == "falco-candidate", merc
    ring = ring_from_snapshot(only, d1)
    assert any(x.get("kind") == "falco" and x.get("id") == "falco:kalived_memfd_exec:python3:execve" for x in ring), ring
    _assert_clean(p1, "only-port")

    dual = _snap(
        tmp / "dual",
        rows=[{"rule": "kalived_write_preload", "exe": "python3", "evt.type": "openat", "n": 1}],
        findings=[
            {"severity": "WARN", "id": "FIM-AIDE", "title": "AIDE self_sudoers"},
            {"severity": "ALERT", "id": "HOST-FALCO", "title": "Falco + FIM"},
        ],
        verdict="ALERT",
    )
    p2 = port(dual, live=False)
    assert p2["class"] == "alert_family", p2
    assert (p2.get("mercury") or {}).get("playbook") == "ask_operator", p2.get("mercury")
    _assert_clean(p2, "dual-port")

    net = _snap(
        tmp / "net",
        rows=[{"rule": "kalived_interp_connect", "exe": "python3", "evt.type": "connect", "n": 2}],
        findings=[
            {"severity": "ALERT", "id": "NET-LISTEN-EXT", "title": "ncat 4444"},
            {"severity": "ALERT", "id": "HOST-FALCO", "title": "Falco + nett"},
        ],
        verdict="ALERT",
    )
    p3 = port(net, live=False)
    assert p3["class"] == "alert_family", p3
    _assert_clean(p3, "net-port")

    absent = _snap(
        tmp / "absent",
        rows=None,
        findings=[{"severity": "INFO", "id": "HOST-FALCO", "title": "falco absent"}],
        verdict="CLEAN",
    )
    p4 = port(absent, live=False)
    assert p4["class"] != "candidate", p4
    assert p4["class"] != "alert_family", p4
    print("OK port empty/candidate/alert/absent")


def test_dry(tmp: Path) -> None:
    out = tmp / "status" / "dry"
    out.mkdir(parents=True)
    home = tmp / "home"
    hiro = home / ".config" / "kalived" / "hiroshima"
    hiro.mkdir(parents=True)
    env = os.environ.copy()
    env["KALIVED_FALCO_DRY"] = "1"
    env["KALIVED_OUT"] = str(out)
    env["HOME"] = str(home)
    env["KALIVED_OWNER_HOME"] = str(home)
    r = subprocess.run(
        ["bash", str(ROOT / "scripts" / "kalived-falco.sh")],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.returncode, r.stderr)
    jsonl = out / "hunt_falco.jsonl"
    assert jsonl.is_file()
    assert jsonl.stat().st_size == 0
    assert not any(hiro.iterdir()), list(hiro.iterdir())
    assert not (out / "hunt_falco_raw.jsonl").exists()
    print("OK dry burst no hiroshima write")


def test_new_stamp(tmp: Path) -> None:
    env = os.environ.copy()
    env["KALIVED_FALCO_DRY"] = "1"
    env.pop("KALIVED_OUT", None)
    env["KALIVED_DATA"] = str(tmp)
    env["HOME"] = str(tmp / "home")
    env["KALIVED_OWNER_HOME"] = str(tmp / "home")
    r = subprocess.run(
        ["bash", str(ROOT / "scripts" / "kalived-falco.sh")],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.returncode, r.stderr)
    stamps = list((tmp / "logs" / "status").glob("*/hunt_falco.jsonl"))
    assert len(stamps) == 1, stamps
    assert stamps[0].parent.name != "2026-09-30_175433"
    assert stamps[0].stat().st_size == 0
    print("OK dry mints new stamp", stamps[0].parent.name)


def test_validate() -> None:
    host = ROOT / "defs" / "falco-host.yaml"
    conf = ROOT / "defs" / "falco.yaml"
    falco = shutil.which("falco")
    if not falco:
        print("skip falco -V (no binary)")
        return
    r = subprocess.run(
        [falco, "-c", str(conf), "-V", str(host)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    blob = (r.stdout or "") + (r.stderr or "")
    assert r.returncode == 0, blob
    assert "Undefined macro" not in blob
    compact = blob.replace(" ", "")
    assert '"successful":true' in compact
    assert '"warnings":[]' in compact
    assert '"errors":[]' in compact
    assert "falco_rules.yaml" not in blob
    print("OK falco -V")


def test_tree() -> None:
    host = (ROOT / "defs" / "falco-host.yaml").read_text(encoding="utf-8")
    conf = (ROOT / "defs" / "falco.yaml").read_text(encoding="utf-8")
    play = (ROOT / "playbooks" / "install-falco-host.sh").read_text(encoding="utf-8")
    ctl = (ROOT / "scripts" / "kalived-ctl").read_text(encoding="utf-8")
    hiro = (ROOT / "cockpit" / "backend" / "app" / "hiroshima.py").read_text(encoding="utf-8")
    burst = (ROOT / "scripts" / "kalived-falco.sh").read_text(encoding="utf-8")
    assert "- macro: spawned_process" in host
    assert "evt.type in (execve, execveat)" in host
    assert "fd.rip startswith" not in host
    assert "evt.dir" not in host
    assert "falco rules rejected" in burst
    assert "falco engine failed" in burst
    assert "engine.kind=modern_ebpf" in burst
    assert "kind: modern_ebpf" in conf
    assert "kalived_latest_scan_dir" not in burst
    assert "falco_rules.yaml" not in conf
    assert "/etc/falco/falco_rules" not in host
    assert "/etc/falco/falco_rules" not in burst
    assert "rules_files: []" in conf
    assert "enabled: false" in conf
    assert "webserver:" in conf and "grpc:" in conf
    assert "kalived_require_not_alert" in play
    assert "apt-get install -y falco" in play
    assert "apt-get install" in play
    assert "systemctl enable" not in play or "disable" in play
    assert "falco-burst" in ctl
    assert "no extra arguments" in ctl
    assert '"falco-burst"' in hiro
    assert "PLAYBOOK_RUNS" in hiro
    # falco-burst is in RUNS, not PLAYBOOK_RUNS (no Qdrant)
    start = hiro.index("PLAYBOOK_RUNS")
    chunk = hiro[start : start + 400]
    assert "falco-burst" not in chunk
    assert "hiroshima/" in burst
    assert "Qdrant" in burst or "hiroshima/" in burst
    for name in (
        "kalived_memfd_exec",
        "kalived_deleted_exec",
        "kalived_write_preload",
        "kalived_interp_connect",
        "kalived_shell_from_browser",
        "kalived_lkm_load",
    ):
        assert name in host, name
    print("OK tree rules/ctl/playbook")


def main() -> int:
    import tempfile

    test_parse()
    test_empty()
    test_findings()
    test_tree()
    test_validate()
    with tempfile.TemporaryDirectory() as d:
        test_port(Path(d))
    with tempfile.TemporaryDirectory() as d:
        test_dry(Path(d))
    with tempfile.TemporaryDirectory() as d:
        test_new_stamp(Path(d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
