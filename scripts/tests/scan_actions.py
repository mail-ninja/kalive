#!/usr/bin/env python3
"""Confirm-ark rows: CLEAN, STALE, deleted-dpkg, identity ALERT, drop unknown run."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from scan_actions import (  # noqa: E402
    ALLOWED_RUNS,
    BROTLI_ARCHIVE,
    CONFIRM_RUNS,
    HELPER_PTY,
    actions_from_verdict,
    port_actions,
    signal_port,
)

CTL = ROOT / "scripts" / "kalived-ctl"
NOPASSWD = ROOT / "playbooks" / "install-nopasswd-ctl.sh"
HIRO = ROOT / "cockpit" / "backend" / "app" / "hiroshima.py"
UI = ROOT / "cockpit" / "web" / "src" / "lib" / "Hiroshima.svelte"


def _runs(rows: list[dict]) -> list[str | None]:
    return [r.get("run") for r in rows]


def _ids(rows: list[dict]) -> list[str]:
    return [r.get("id") for r in rows]


def test_clean() -> None:
    rows = actions_from_verdict({"verdict": "CLEAN", "exit_code": 0, "findings": []})
    assert len(rows) == 1, rows
    assert rows[0]["id"] == "close"
    assert rows[0]["run"] is None
    assert rows[0]["confirm"] is False
    assert "Ingenting" in rows[0]["title"]
    print("OK CLEAN → én lukk-rad")


def test_stale_without_identity() -> None:
    doc = {
        "verdict": "WARN",
        "exit_code": 1,
        "findings": [
            {
                "severity": "WARN",
                "id": "FIM-AIDE-STALE",
                "title": "AIDE stale: /usr/bin/passwd",
                "detail": "/usr/bin/passwd\n/etc/ssh/ssh_config",
            },
            {
                "severity": "WARN",
                "id": "FIM-AIDE",
                "title": "AIDE snap_proton",
                "detail": "/snap/proton-vpn-1",
            },
            {
                "severity": "WARN",
                "id": "FIM-AIDE-PKG",
                "title": "AIDE pkg: /usr/bin/sudo",
                "detail": "/usr/bin/sudo",
            },
        ],
    }
    rows = actions_from_verdict(doc)
    assert "ack-stale" in _ids(rows), rows
    ack = next(r for r in rows if r["id"] == "ack-stale")
    assert ack["run"] == "aide-init-ack-stale"
    assert ack["confirm"] is True
    assert "/usr/bin/passwd" in ack["why"]
    assert "/etc/ssh/ssh_config" in ack["why"]
    assert "aide-init" not in _runs(rows)
    assert "kill-pid" not in _runs(rows)
    # Proton/PKG: ingen egen rad
    assert "proton" not in " ".join(_ids(rows)).lower()
    print("OK STALE uten identity → ack-rad, Proton/PKG uten handling")


def test_identity_alert_no_aide() -> None:
    doc = {
        "verdict": "ALERT",
        "exit_code": 2,
        "findings": [
            {
                "severity": "ALERT",
                "id": "FIM-AIDE",
                "title": "AIDE identity: /usr/bin/passwd",
                "detail": "/usr/bin/passwd",
            },
            {
                "severity": "WARN",
                "id": "FIM-AIDE-STALE",
                "title": "AIDE stale: /etc/ssh/ssh_config",
                "detail": "/etc/ssh/ssh_config",
            },
        ],
    }
    rows = actions_from_verdict(doc)
    assert "ack-stale" not in _ids(rows), rows
    assert "aide-init-ack-stale" not in _runs(rows)
    assert "aide-init" not in _runs(rows)
    assert all(r.get("run") is None for r in rows)
    print("OK identity ALERT → ingen aide-init, ingen ack-stale")


def test_deleted_dpkg_no_kill() -> None:
    doc = {
        "verdict": "ALERT",
        "exit_code": 2,
        "findings": [
            {
                "severity": "ALERT",
                "id": "PROC-DELETED",
                "title": "Kjørende binær er (deleted)",
                "detail": "pid=1892 exe=/usr/libexec/at-spi-bus-launcher (deleted) cmd=/usr/libexec/at-spi-bus-launcher --launch\n"
                "pid=1950 exe=/usr/libexec/at-spi2-registryd (deleted) cmd=/usr/libexec/at-spi2-registryd",
            }
        ],
    }
    rows = actions_from_verdict(doc)
    assert "close-deleted-dpkg" in _ids(rows), rows
    assert "kill-pid" not in _runs(rows)
    assert all(r.get("run") is None for r in rows)
    why = " ".join(r["why"] for r in rows)
    assert "at-spi" in why
    assert "cmd=" not in why
    print("OK PROC-DELETED dpkg → lukk, ikke kill")


def test_deleted_unpackaged_ask() -> None:
    doc = {
        "verdict": "ALERT",
        "exit_code": 2,
        "findings": [
            {
                "severity": "ALERT",
                "id": "PROC-DELETED",
                "title": "Kjørende binær er (deleted)",
                "detail": "pid=5678 exe=/tmp/.x (deleted) cmd=/tmp/.x",
            }
        ],
    }
    rows = actions_from_verdict(doc)
    assert "ask-operator" in _ids(rows), rows
    assert "close-deleted-dpkg" not in _ids(rows)
    assert "kill-pid" not in _runs(rows)
    assert "isolate-dst" not in _runs(rows)
    print("OK PROC-DELETED /tmp → ask_operator, ingen kill")


def test_memfd_ask() -> None:
    doc = {
        "verdict": "ALERT",
        "findings": [
            {
                "severity": "ALERT",
                "id": "PROC-MEMFD",
                "title": "memfd-exec",
                "detail": "pid=9 exe=memfd:pay (deleted) cmd=memfd:pay",
            }
        ],
    }
    rows = actions_from_verdict(doc)
    assert "ask-operator" in _ids(rows), rows
    assert "kill-pid" not in _runs(rows)
    print("OK PROC-MEMFD → ask_operator")


def test_helper_and_runtime_text() -> None:
    doc = {
        "verdict": "WARN",
        "findings": [
            {"severity": "WARN", "id": "HELPER-STALE", "title": "helper bak git", "detail": ""},
            {"severity": "WARN", "id": "HOST-RUNTIME", "title": "brotli 1.2.0 < 1.2.1", "detail": ""},
        ],
    }
    rows = actions_from_verdict(doc)
    helper = next(r for r in rows if r["id"] == "helper-pty")
    runtime = next(r for r in rows if r["id"] == "runtime-apt")
    assert helper["run"] is None and helper["confirm"] is False
    assert helper["text"] == HELPER_PTY
    assert runtime["run"] is None
    assert runtime["title"] == "Brotli: vent på Kali"
    assert "kali-rolling" in runtime["why"]
    assert "ja apt" not in runtime["title"].lower()
    print("OK HELPER-STALE PTY + HOST-RUNTIME vent på Kali")


def test_isolate_home_vs_travel() -> None:
    base = {"verdict": "WARN", "findings": []}
    home = actions_from_verdict(
        base, protocol={"isolatable": True, "env": {"class": "home"}}
    )
    assert "isolate-dst" in _ids(home), home
    iso = next(r for r in home if r["id"] == "isolate-dst")
    assert iso["run"] == "isolate-dst" and iso["confirm"] is True
    assert iso["extra"]["family"] == "unknown"
    travel = actions_from_verdict(
        base,
        protocol={
            "isolatable": True,
            "env": {"class": "travel", "ssid": "Breeze Guest"},
            "ufw": {"allow_dns_proton": 0},
        },
    )
    assert "travel-harden" in _ids(travel), travel
    assert "isolate-skip" not in _ids(travel)
    assert "isolate-dst" not in _runs(travel)
    th = next(r for r in travel if r["id"] == "travel-harden")
    assert th["run"] is None and th["confirm"] is False
    assert "Breeze Guest" in th["why"]
    assert "VPN" in th["why"]
    tether = actions_from_verdict(
        base, protocol={"isolatable": True, "env": {"class": "tether"}}
    )
    assert "travel-harden" in _ids(tether)
    hotel = actions_from_verdict(
        {"verdict": "CLEAN", "findings": []},
        protocol={"isolatable": False, "env": {"class": "travel", "ssid": "Breeze Guest"}},
    )
    assert "travel-harden" in _ids(hotel), hotel
    print("OK isolate home vs travel-harden (gjestenett)")


def test_proton_up_from_ring_not_stripped_ufw() -> None:
    env = {"class": "travel", "ssid": "Breeze Guest"}
    # Live bug: protocol.ufw has no allow_dns_proton, but ring has Proton.
    proto = {
        "isolatable": True,
        "env": env,
        "ufw": {"block": 99, "allow": 508, "hits_listen": 0, "lines": 1761},
        "ring": [
            {"id": "dns:Proton", "dst_family": "Proton", "sil": "NET-DNS"},
            {"id": "dns:unknown", "dst_family": "unknown", "sil": "NET-DNS"},
        ],
    }
    doc = {
        "verdict": "WARN",
        "findings": [
            {
                "severity": "INFO",
                "id": "NET-DNS",
                "title": "Nameserver er ProtonVPN-gw (ikke hijack)",
                "detail": "",
            },
            {
                "severity": "WARN",
                "id": "FIM-AIDE",
                "title": "AIDE snap_proton",
                "detail": "/etc/udev/rules.d/70-snap.proton-vpn.rules",
            },
        ],
    }
    rows = actions_from_verdict(doc, protocol=proto)
    th = next(r for r in rows if r["id"] == "travel-harden")
    assert "oppe" in th["title"].lower() or "oppe" in th["why"].lower(), th
    assert "nede" not in th["why"]
    assert "ikke synlig" not in th["why"]
    assert th["run"] is None
    # snap-WARN alone is install, not tunnel
    down = actions_from_verdict(
        {
            "verdict": "WARN",
            "findings": [
                {
                    "severity": "WARN",
                    "id": "FIM-AIDE",
                    "title": "AIDE snap_proton",
                    "detail": "/etc/udev/rules.d/70-snap.proton-vpn.rules",
                }
            ],
        },
        protocol={"env": env, "ufw": {"block": 1, "allow": 1, "hits_listen": 0, "lines": 10}},
    )
    th2 = next(r for r in down if r["id"] == "travel-harden")
    assert "nede" in th2["why"] or "slå på VPN" in th2["why"], th2
    print("OK proton-på-ark: ring/NET-DNS = oppe; snap-WARN alene = nede")


def test_rollback_undo() -> None:
    rows = actions_from_verdict(
        {"verdict": "CLEAN", "findings": []}, protocol={"rollback": True}
    )
    assert "isolate-undo" in _ids(rows), rows
    undo = next(r for r in rows if r["id"] == "isolate-undo")
    assert undo["run"] == "isolate-undo" and undo["confirm"] is True
    print("OK rollback → isolate-undo")


def test_drop_unknown_run() -> None:
    rows = actions_from_verdict(
        {
            "verdict": "WARN",
            "findings": [
                {
                    "severity": "WARN",
                    "id": "FIM-AIDE-STALE",
                    "title": "stale",
                    "detail": "/usr/bin/passwd",
                }
            ],
        }
    )
    before = [r["id"] for r in rows]
    dropped = port_actions(rows, {"run": "kill-pid", "why": "agent vil drepe"})
    assert [r["id"] for r in dropped] == before
    assert dropped[0]["why"] != "agent vil drepe"
    assert "kill-pid" not in _runs(dropped)
    suricata = port_actions(rows, {"run": "suricata", "id": "ack-stale"})
    assert [r["id"] for r in suricata] == before
    print("OK ukjent run droppes")


def test_port_rewrites_why_and_rank() -> None:
    rows = actions_from_verdict(
        {
            "verdict": "WARN",
            "findings": [
                {"severity": "WARN", "id": "HELPER-STALE", "title": "helper", "detail": ""},
                {
                    "severity": "WARN",
                    "id": "FIM-AIDE-STALE",
                    "title": "stale",
                    "detail": "/usr/bin/passwd",
                },
            ],
        }
    )
    assert "ack-stale" in _ids(rows) and "helper-pty" in _ids(rows)
    assert _ids(rows).index("helper-pty") > _ids(rows).index("ack-stale")
    moved = port_actions(rows, {"id": "helper-pty", "why": "install helper før freeze"})
    assert moved[0]["id"] == "helper-pty"
    assert moved[0]["why"] == "install helper før freeze"
    ported = port_actions(
        rows, {"run": "aide-init-ack-stale", "why": "frys passwd mot gammel baseline"}
    )
    assert ported[0]["run"] == "aide-init-ack-stale"
    assert ported[0]["why"] == "frys passwd mot gammel baseline"
    assert ported[0]["id"] == "ack-stale"
    print("OK agent porter why og flytter rad øverst")


def test_mercury_ask_does_not_hide_safe_row() -> None:
    doc = {
        "verdict": "ALERT",
        "findings": [
            {
                "severity": "ALERT",
                "id": "PROC-DELETED",
                "title": "deleted",
                "detail": "pid=1892 exe=/usr/libexec/at-spi-bus-launcher (deleted) cmd=/usr/libexec/at-spi-bus-launcher",
            }
        ],
        "protocol": {"playbook": "ask_operator", "mercury": {"playbook": "ask_operator", "why": "hard-artifact"}},
    }
    rows = actions_from_verdict(doc)
    ported = port_actions(rows, {"id": "ask-operator", "why": "hard-artifact"})
    assert "close-deleted-dpkg" in _ids(ported)
    assert "ask-operator" not in _ids(ported)
    # pick id ask-operator does not exist → unchanged, still the dpkg close row
    assert ported[0]["id"] == "close-deleted-dpkg"
    print("OK mercury ask_operator skjuler ikke dpkg-lukk")


def test_signal_port_drops_unknown_run_and_rewrites_why() -> None:
    rows = actions_from_verdict(
        {
            "verdict": "WARN",
            "findings": [
                {
                    "severity": "WARN",
                    "id": "HOST-RUNTIME",
                    "title": "brotli 1.2.0 < 1.2.1",
                    "detail": "brotli 1.2.0-4+b2 < 1.2.1",
                }
            ],
        },
        protocol={"env": {"class": "travel", "ssid": "Breeze Guest"}},
    )
    ported = signal_port(
        rows,
        protocol={"env": {"class": "travel", "ssid": "Breeze Guest"}},
        picks=[{"run": "kill-pid", "why": "drepe"}, {"id": "runtime-apt", "why": "arkivet har ikke 1.2.1"}],
    )
    assert "kill-pid" not in _runs(ported)
    assert ported[0]["id"] == "travel-harden"
    runtime = next(r for r in ported if r["id"] == "runtime-apt")
    assert runtime["why"] == "arkivet har ikke 1.2.1"
    assert BROTLI_ARCHIVE
    print("OK signal_port dropper ukjent run, porter why, travel først")


def test_no_invented_runs() -> None:
    assert "kill-pid" not in ALLOWED_RUNS
    assert "aide-init" not in ALLOWED_RUNS
    assert "scan" not in ALLOWED_RUNS
    assert CONFIRM_RUNS == {"aide-init-ack-stale", "isolate-dst", "isolate-undo"}
    print("OK allowlist er lukket")


def test_ctl_ack_stale_verb() -> None:
    text = CTL.read_text(encoding="utf-8")
    assert "aide-init-ack-stale" in text
    exec_lines = [ln for ln in text.splitlines() if "aide-init.sh" in ln and "exec" in ln]
    assert any("--force" in ln and "--ack-stale" not in ln for ln in exec_lines)
    assert any("--ack-stale" in ln for ln in exec_lines)
    assert all("--all" not in ln for ln in exec_lines)
    sudoers = NOPASSWD.read_text(encoding="utf-8")
    assert "aide-init-ack-stale" in sudoers
    hiro = HIRO.read_text(encoding="utf-8")
    assert '"aide-init-ack-stale"' in hiro
    assert "_attach_actions" in hiro
    assert "signal_port" in hiro
    ui = UI.read_text(encoding="utf-8")
    assert "kalived.hiroshima.sheet" in ui
    assert "etter scan" in ui
    assert "/v1/hiroshima/health" in ui
    assert "fixture=1" in hiro
    assert "sudo=1" in hiro
    print("OK ctl aide-init-ack-stale; aide-init forblir --force; --all ute")


def main() -> int:
    test_clean()
    test_stale_without_identity()
    test_identity_alert_no_aide()
    test_deleted_dpkg_no_kill()
    test_deleted_unpackaged_ask()
    test_memfd_ask()
    test_helper_and_runtime_text()
    test_isolate_home_vs_travel()
    test_proton_up_from_ring_not_stripped_ufw()
    test_rollback_undo()
    test_drop_unknown_run()
    test_port_rewrites_why_and_rank()
    test_mercury_ask_does_not_hide_safe_row()
    test_signal_port_drops_unknown_run_and_rewrites_why()
    test_no_invented_runs()
    test_ctl_ack_stale_verb()
    print("ALL OK scan_actions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
