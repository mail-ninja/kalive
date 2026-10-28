#!/usr/bin/env python3
"""H6: Suricata IDS harvest. Empty eve = no finding. No dest-IP/SNI/payload. No Qdrant/hiroshima write."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
sys.path.insert(0, str(ROOT / "cockpit" / "backend"))

from suricata_eve import (  # noqa: E402
    ALLOWED,
    _finding_ids,
    aggregate,
    digest_rows,
    findings_from_rows,
    is_decoder_sid,
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
from scan_actions import actions_from_verdict  # noqa: E402

CASES = ROOT / "scripts" / "testdata" / "cases"

SAMPLE = {
    "timestamp": "2026-10-28T12:00:00.000000+0000",
    "event_type": "alert",
    "src_ip": "10.2.0.2",
    "src_port": 44444,
    "dest_ip": "198.51.100.9",
    "dest_port": 443,
    "proto": "TCP",
    "app_proto": "tls",
    "alert": {
        "action": "allowed",
        "gid": 1,
        "signature_id": 2018959,
        "rev": 4,
        "signature": "ET MALWARE Suspicious TLS to 198.51.100.9",
        "category": "A Network Trojan was detected",
        "severity": 1,
    },
    "tls": {"sni": "evil.example.com", "version": "TLS 1.2"},
    "payload": "909090",
}

SS_SAMPLE = (
    '0      0      10.2.0.2:40338     198.51.100.9:443   '
    'users:(("firefox-esr",pid=2937562,fd=93))\n'
)


def _assert_clean(obj: object, label: str, *, rows: bool = False) -> None:
    blob = json.dumps(obj, ensure_ascii=False)
    if rows:
        hits = leaks(obj)
        assert not hits, (label, hits, blob[:500])
        assert "pcap" not in blob.lower(), label
    assert "198.51.100" not in blob, label
    assert "evil.example" not in blob, label
    assert "sni" not in blob.lower(), label
    assert "payload" not in blob.lower() or "hunt_suricata" in blob.lower(), label
    if isinstance(obj, dict):
        proto_hits = payload_leaks(obj)
        assert not proto_hits, (label, proto_hits)


def test_parse() -> None:
    rec = parse_event(SAMPLE, ss_text=SS_SAMPLE)
    assert rec == (2018959, "ET MALWARE Suspicious TLS to x", "tls", "firefox-esr"), rec
    rows = aggregate(json.dumps(SAMPLE) + "\n" + json.dumps(SAMPLE) + "\n", ss_text=SS_SAMPLE)
    assert rows == [
        {
            "sid": 2018959,
            "signature": "ET MALWARE Suspicious TLS to x",
            "app_proto": "tls",
            "n": 2,
            "exe": "firefox-esr",
        }
    ], rows
    assert set(rows[0]) <= set(ALLOWED)
    _assert_clean(rows, "aggregate", rows=True)
    dns = {"event_type": "dns", "dest_ip": "1.1.1.1", "dns": {"query": "evil.example.com"}}
    assert parse_event(dns) is None
    print("OK parse stripped dest-IP/SNI/payload; dns is not a finding")


def test_empty() -> None:
    recs = findings_from_rows([])
    assert recs == [], recs
    p = CASES / "clean_suricata_empty" / "hunt_suricata.jsonl"
    assert p.is_file(), p
    assert p.stat().st_size == 0
    assert load_jsonl(p) == []
    assert aggregate("") == []
    print("OK empty eve/jsonl no finding")


def test_findings() -> None:
    only = findings_from_rows(
        [{"sid": 2018959, "signature": "ET MALWARE Suspicious TLS to x", "app_proto": "tls", "n": 1}]
    )
    assert only[0]["severity"] == "WARN" and only[0]["id"] == "HOST-SURICATA", only
    dual_f = findings_from_rows(
        [{"sid": 7500001, "signature": "KALIVED DNS onion", "app_proto": "dns", "n": 1}],
        ids={"FIM-AIDE": "WARN"},
    )
    assert dual_f[0]["severity"] == "ALERT", dual_f
    dual_n = findings_from_rows(
        [{"sid": 2018959, "signature": "ET MALWARE Suspicious TLS to x", "app_proto": "tls", "n": 2}],
        ids={"NET-LISTEN-EXT": "ALERT"},
    )
    assert dual_n[0]["severity"] == "ALERT", dual_n
    info = findings_from_rows([], absent=True)
    assert info[0]["severity"] == "INFO" and info[0]["title"] == "suricata absent", info
    quiet = findings_from_rows(
        [{"sid": 2018959, "signature": "ET MALWARE Suspicious TLS to x", "app_proto": "tls", "n": 1}],
        ids={"FIM-AIDE": "INFO"},
    )
    assert quiet[0]["severity"] == "WARN", quiet
    assert is_decoder_sid(2_200_000) and is_decoder_sid(2_299_999)
    assert is_decoder_sid(2_200_121)
    assert not is_decoder_sid(2_199_999) and not is_decoder_sid(2_300_000)
    assert not is_decoder_sid(2_018_959) and not is_decoder_sid(7_500_001)
    eth = [{"sid": 2200121, "signature": "SURICATA Ethertype unknown", "app_proto": "unknown", "n": 3}]
    dec = findings_from_rows(eth)
    assert dec[0]["severity"] == "INFO" and "decoder" in dec[0]["title"].lower(), dec
    assert "candidate" not in dec[0]["title"].lower(), dec
    dec_fim = findings_from_rows(eth, ids={"FIM-AIDE": "WARN"})
    assert dec_fim[0]["severity"] == "INFO", dec_fim
    et_fim = findings_from_rows(
        [{"sid": 2018959, "signature": "ET MALWARE Suspicious TLS to x", "app_proto": "tls", "n": 1}],
        ids={"FIM-AIDE": "WARN"},
    )
    assert et_fim[0]["severity"] == "ALERT", et_fim
    mixed = findings_from_rows(
        eth
        + [{"sid": 2018959, "signature": "ET MALWARE Suspicious TLS to x", "app_proto": "tls", "n": 1}],
        ids={"FIM-AIDE": "WARN"},
    )
    assert mixed[0]["severity"] == "ALERT", mixed
    assert "2200121" not in mixed[0]["title"] and "2018959" in mixed[0]["title"], mixed
    flow = findings_from_rows(
        [{"sid": 2200121, "signature": "SURICATA Ethertype unknown", "app_proto": "unknown", "n": 1, "exe": "ncat"}],
        ids={"NET-ESTAB": "ALERT"},
    )
    assert flow[0]["severity"] == "ALERT" and "flow" in flow[0]["title"].lower(), flow
    falco = findings_from_rows(
        [{"sid": 2200121, "signature": "SURICATA Ethertype unknown", "app_proto": "unknown", "n": 1, "exe": "bash"}],
        ids={"HOST-FALCO": "WARN"},
    )
    assert falco[0]["severity"] == "ALERT", falco
    dec_exe_fim = findings_from_rows(
        [{"sid": 2200121, "signature": "SURICATA Ethertype unknown", "app_proto": "unknown", "n": 1, "exe": "firefox-esr"}],
        ids={"FIM-AIDE": "WARN"},
    )
    assert dec_exe_fim[0]["severity"] == "INFO", dec_exe_fim
    dec_net = findings_from_rows(eth, ids={"NET-LISTEN-EXT": "ALERT"})
    assert dec_net[0]["severity"] == "INFO", dec_net
    print("OK findings WARN/ALERT/INFO")


def test_dual_all_warn_rows(tmp: Path) -> None:
    findings = tmp / "findings.jsonl"
    findings.write_text(
        json.dumps({"severity": "WARN", "id": "FIM-AIDE", "title": "self_sudoers"})
        + "\n"
        + json.dumps({"severity": "INFO", "id": "FIM-AIDE", "title": "self_helper"})
        + "\n",
        encoding="utf-8",
    )
    ids = _finding_ids(findings)
    assert ids.get("FIM-AIDE") == "WARN", ids
    recs = findings_from_rows(
        [{"sid": 2018959, "signature": "ET MALWARE Suspicious TLS to x", "app_proto": "tls", "n": 1}],
        ids=ids,
    )
    assert recs[0]["severity"] == "ALERT", recs
    assert "Suricata + FIM" in recs[0]["title"], recs[0]["title"]
    print("OK dual uses WARN rows, not last INFO")


def _snap(tmp: Path, *, rows: list[dict] | None, findings: list[dict], verdict: str) -> Path:
    snap = tmp / "snap"
    snap.mkdir(parents=True)
    if rows is not None:
        write_jsonl(snap / "hunt_suricata.jsonl", rows)
    (snap / "verdict.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "verdict": verdict,
                "exit_code": {"CLEAN": 0, "WARN": 1, "ALERT": 2, "ERROR": 3}[verdict],
                "stamp": "h6",
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
    assert d0["suricata"] == [], d0["suricata"]
    p0 = port(empty, live=False)
    assert p0["class"] in ("noise", "env_shift"), p0["class"]
    assert p0["class"] != "candidate", p0
    _assert_clean(p0, "empty-port")

    only_rows = [
        {"sid": 2018959, "signature": "ET MALWARE Suspicious TLS to x", "app_proto": "tls", "n": 1}
    ]
    only = _snap(
        tmp / "only",
        rows=only_rows,
        findings=[{"severity": "WARN", "id": "HOST-SURICATA", "title": "Suricata candidate"}],
        verdict="WARN",
    )
    (only / "nm_active.txt").write_text(
        "Hotspot:00000000-0000-0000-0000-000000000000:802-11-wireless:wlan0\n"
    )
    d1 = digest_from_snapshot(only)
    assert d1["suricata"] == only_rows, d1["suricata"]
    _assert_clean({"suricata": d1["suricata"]}, "only-digest", rows=True)
    p1 = port(only, live=False)
    assert p1["class"] == "candidate", p1
    assert float(p1.get("dual") or 0) < 0.5, p1
    merc = p1.get("mercury") or mercury_rules(d1, [])
    assert merc.get("why") == "suricata-candidate", merc
    ring = ring_from_snapshot(only, d1)
    assert any(x.get("kind") == "suricata" and "2018959" in str(x.get("id")) for x in ring), ring
    _assert_clean(p1, "only-port")

    dual = _snap(
        tmp / "dual",
        rows=[{"sid": 7500001, "signature": "KALIVED DNS onion", "app_proto": "dns", "n": 1}],
        findings=[
            {"severity": "WARN", "id": "FIM-AIDE", "title": "AIDE self_sudoers"},
            {"severity": "ALERT", "id": "HOST-SURICATA", "title": "Suricata + FIM"},
        ],
        verdict="ALERT",
    )
    p2 = port(dual, live=False)
    assert p2["class"] == "alert_family", p2
    assert (p2.get("mercury") or {}).get("playbook") == "ask_operator", p2.get("mercury")
    _assert_clean(p2, "dual-port")

    net = _snap(
        tmp / "net",
        rows=[{"sid": 2018959, "signature": "ET MALWARE Suspicious TLS to x", "app_proto": "tls", "n": 2}],
        findings=[
            {"severity": "ALERT", "id": "NET-LISTEN-EXT", "title": "ncat 4444"},
            {"severity": "ALERT", "id": "HOST-SURICATA", "title": "Suricata + nett"},
        ],
        verdict="ALERT",
    )
    p3 = port(net, live=False)
    assert p3["class"] == "alert_family", p3
    _assert_clean(p3, "net-port")

    absent = _snap(
        tmp / "absent",
        rows=None,
        findings=[{"severity": "INFO", "id": "HOST-SURICATA", "title": "suricata absent"}],
        verdict="CLEAN",
    )
    p4 = port(absent, live=False)
    assert p4["class"] != "candidate", p4
    assert p4["class"] != "alert_family", p4

    decoder_rows = [
        {"sid": 2200121, "signature": "SURICATA Ethertype unknown", "app_proto": "unknown", "n": 3}
    ]
    decoder = _snap(
        tmp / "decoder",
        rows=decoder_rows,
        findings=[{"severity": "INFO", "id": "HOST-SURICATA", "title": "Suricata decoder"}],
        verdict="CLEAN",
    )
    p5 = port(decoder, live=False)
    assert p5["class"] != "candidate", p5
    assert p5["class"] != "alert_family", p5
    ring_d = ring_from_snapshot(decoder, digest_from_snapshot(decoder))
    assert not any(x.get("kind") == "suricata" for x in ring_d), ring_d
    decoder_fim = _snap(
        tmp / "decoder_fim",
        rows=decoder_rows,
        findings=[
            {"severity": "WARN", "id": "FIM-AIDE", "title": "AIDE self_sudoers"},
            {"severity": "INFO", "id": "HOST-SURICATA", "title": "Suricata decoder"},
        ],
        verdict="WARN",
    )
    p6 = port(decoder_fim, live=False)
    assert p6["class"] != "alert_family", p6
    assert p6["class"] != "candidate", p6
    merc6 = p6.get("mercury") or mercury_rules(digest_from_snapshot(decoder_fim), [])
    assert merc6.get("why") != "suricata-candidate", merc6
    assert merc6.get("why") != "suricata-dual", merc6
    print("OK port empty/candidate/alert/absent")


def test_sheet() -> None:
    rows = actions_from_verdict(
        {
            "verdict": "WARN",
            "findings": [
                {
                    "severity": "WARN",
                    "id": "HOST-SURICATA",
                    "title": "Suricata candidate: sid=2018959 ET MALWARE Suspicious TLS to x",
                    "detail": "sid=2018959 ET MALWARE Suspicious TLS to x app=tls n=1",
                }
            ],
        }
    )
    seen = [r for r in rows if r.get("id") == "suricata-seen"]
    assert seen, rows
    assert seen[0]["run"] is None
    assert seen[0]["confirm"] is False
    assert seen[0]["title"].startswith("Suricata så "), seen[0]
    assert "IDS" in (seen[0].get("text") or "")
    assert "isolate" in (seen[0].get("text") or "").lower()
    assert "drop" in (seen[0].get("text") or "").lower()
    assert "isolate-dst" not in [r.get("run") for r in rows]
    info_sheet = actions_from_verdict(
        {
            "verdict": "WARN",
            "findings": [
                {
                    "severity": "INFO",
                    "id": "HOST-SURICATA",
                    "title": "Suricata decoder: sid=2200121 SURICATA Ethertype unknown",
                    "detail": "sid=2200121 SURICATA Ethertype unknown app=unknown n=3",
                },
                {"severity": "WARN", "id": "FIM-AIDE", "title": "self_sudoers"},
            ],
        }
    )
    assert not any(r.get("id") == "suricata-seen" for r in info_sheet), info_sheet
    print("OK sheet Suricata så X, ingen isolate/drop")


def test_dry(tmp: Path) -> None:
    out = tmp / "status" / "dry"
    out.mkdir(parents=True)
    home = tmp / "home"
    hiro = home / ".config" / "kalived" / "hiroshima"
    hiro.mkdir(parents=True)
    env = os.environ.copy()
    env["KALIVED_SURICATA_DRY"] = "1"
    env["KALIVED_OUT"] = str(out)
    env["HOME"] = str(home)
    env["KALIVED_OWNER_HOME"] = str(home)
    r = subprocess.run(
        ["bash", str(ROOT / "scripts" / "kalived-suricata.sh")],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.returncode, r.stderr)
    jsonl = out / "hunt_suricata.jsonl"
    assert jsonl.is_file()
    assert jsonl.stat().st_size == 0
    assert jsonl.stat().st_mode & 0o777 == 0o600
    note = out / "hunt_suricata.txt"
    assert note.is_file() and note.stat().st_mode & 0o777 == 0o600
    assert not any(hiro.iterdir()), list(hiro.iterdir())
    print("OK dry harvest no hiroshima write")


def test_harvest_eve(tmp: Path) -> None:
    out = tmp / "status" / "eve"
    out.mkdir(parents=True)
    eve = tmp / "eve.json"
    eve.write_text(json.dumps(SAMPLE) + "\n", encoding="utf-8")
    (out / "ss_established.txt").write_text(SS_SAMPLE, encoding="utf-8")
    env = os.environ.copy()
    env["KALIVED_OUT"] = str(out)
    env["KALIVED_SURICATA_EVE"] = str(eve)
    env["HOME"] = str(tmp / "home")
    env["KALIVED_OWNER_HOME"] = str(tmp / "home")
    r = subprocess.run(
        ["bash", str(ROOT / "scripts" / "kalived-suricata.sh")],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.returncode, r.stderr)
    rows = load_jsonl(out / "hunt_suricata.jsonl")
    assert rows and rows[0]["sid"] == 2018959, rows
    assert rows[0].get("exe") == "firefox-esr", rows
    _assert_clean(rows, "harvest-eve", rows=True)
    empty_eve = tmp / "empty_eve.json"
    empty_eve.write_text("", encoding="utf-8")
    env["KALIVED_SURICATA_EVE"] = str(empty_eve)
    env["KALIVED_OUT"] = str(tmp / "status" / "empty")
    Path(env["KALIVED_OUT"]).mkdir(parents=True)
    r2 = subprocess.run(
        ["bash", str(ROOT / "scripts" / "kalived-suricata.sh")],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r2.returncode == 0, (r2.returncode, r2.stderr)
    empty_jsonl = Path(env["KALIVED_OUT"]) / "hunt_suricata.jsonl"
    assert empty_jsonl.is_file() and empty_jsonl.stat().st_size == 0
    print("OK harvest one alert + empty eve")


def test_tree() -> None:
    yaml = (ROOT / "defs" / "suricata.yaml").read_text(encoding="utf-8")
    rules = (ROOT / "defs" / "suricata-local.rules").read_text(encoding="utf-8")
    play = (ROOT / "playbooks" / "install-suricata-host.sh").read_text(encoding="utf-8")
    run = (ROOT / "scripts" / "kalived-suricata-run.sh").read_text(encoding="utf-8")
    harvest = (ROOT / "scripts" / "kalived-suricata.sh").read_text(encoding="utf-8")
    unit = (ROOT / "systemd" / "kalived-suricata.service").read_text(encoding="utf-8")
    ctl = (ROOT / "scripts" / "kalived-ctl").read_text(encoding="utf-8")
    scan = (ROOT / "scripts" / "kalived-scan.sh").read_text(encoding="utf-8")
    actions = (ROOT / "scripts" / "lib" / "scan_actions.py").read_text(encoding="utf-8")
    hiro = (ROOT / "cockpit" / "backend" / "app" / "hiroshima.py").read_text(encoding="utf-8")
    assert "10.0.0.0/8" in yaml and "172.16.0.0/12" in yaml and "192.168.0.0/16" in yaml
    assert "10.2.0.0/16" in yaml
    assert 'EXTERNAL_NET: "!$HOME_NET"' in yaml
    assert "- alert:" in yaml and "- dns" in yaml and "- tls" in yaml and "- flow" in yaml
    assert "pcap-log:" in yaml and "enabled: no" in yaml
    assert "bind-address" not in yaml
    assert "listen:" not in yaml.lower()
    assert "web:" not in yaml.lower()
    assert "nfq:" not in yaml and "copy-mode:" not in yaml
    assert "host-mode: sniffer-only" in yaml
    assert "unix-command:" in yaml
    assert "payload: no" in yaml
    assert " drop;" not in rules.lower() and " reject;" not in rules.lower()
    assert "no drop" in rules.lower() or "ingen" in rules.lower()
    assert "|90" not in rules and "content:\"" in rules
    assert "sid:7500001" in rules.replace(" ", "")
    assert "kalived_require_not_alert" in play
    assert "apt-get install -y suricata" in play
    assert "suricata-update" in play
    assert "printer og stopper" in play or "Apt og enable kjører ikke" in play
    assert "--af-packet=" in run
    assert " -q " not in run and " --nfq" not in run
    assert '== "lo"' in run or '!= "lo"' in run
    assert "proton0" in run and "wlan0" in run
    assert " -q " not in run
    assert "kalived_chown_owner_0600" in harvest
    assert "hiroshima/" in harvest
    assert "Qdrant" in harvest or "hiroshima/" in harvest
    assert "ConditionPathExists=/usr/bin/suricata" in unit
    assert "suricata-burst" not in ctl
    assert "check_suricata" in scan
    assert "kalived-suricata.sh" in scan
    assert "suricata-seen" in actions
    assert "isolate-dst" in actions
    allow = (ROOT / "defs" / "kali-allow" / "chkrootkit-allow.txt").read_text(encoding="utf-8")
    assert "PACKET SNIFFER(/usr/bin/suricata" in allow
    ck = (ROOT / "scripts" / "lib" / "check-rootkit.sh").read_text(encoding="utf-8")
    assert r"PACKET SNIFFER\(/usr/bin/suricata" in ck
    eve = (ROOT / "scripts" / "lib" / "suricata_eve.py").read_text(encoding="utf-8")
    assert "DECODER_SID_MIN" in eve and "is_decoder_sid" in eve
    eth = CASES / "warn_suricata_ethertype_fim"
    assert (eth / "hunt_suricata.jsonl").is_file()
    assert "2200121" in (eth / "hunt_suricata.jsonl").read_text(encoding="utf-8")
    assert "VERDICT=WARN" in (eth / "expected_verdict.txt").read_text(encoding="utf-8")
    assert "IDS=FIM-AIDE" in (eth / "expected_verdict.txt").read_text(encoding="utf-8")
    et = CASES / "alert_suricata_fim"
    assert "2018959" in (et / "hunt_suricata.jsonl").read_text(encoding="utf-8")
    assert "VERDICT=ALERT" in (et / "expected_verdict.txt").read_text(encoding="utf-8")
    start = hiro.index("PLAYBOOK_RUNS")
    chunk = hiro[start : start + 500]
    assert "suricata" not in chunk.lower()
    assert '"suricata"' not in hiro
    print("OK tree yaml/rules/playbook/unit")


def main() -> int:
    import tempfile

    test_parse()
    test_empty()
    test_findings()
    test_tree()
    test_sheet()
    with tempfile.TemporaryDirectory() as d:
        test_port(Path(d))
    with tempfile.TemporaryDirectory() as d:
        test_dry(Path(d))
    with tempfile.TemporaryDirectory() as d:
        test_harvest_eve(Path(d))
    with tempfile.TemporaryDirectory() as d:
        test_dual_all_warn_rows(Path(d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
