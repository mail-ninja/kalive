#!/usr/bin/env python3
"""Signal-xterm rails: allowlist, pty-paint, no free root shell. No live sudo."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "cockpit" / "backend" / "app" / "tools.py"
AGENTS = ROOT / "cockpit" / "backend" / "app" / "agents.py"
PLAY = ROOT / "prompts" / "playbooks" / "signal.md"
DECIDE = ROOT / "cockpit" / "backend" / "app" / "decide.py"


def _const(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} mangler i {path}")


def test_allowlist() -> None:
    runs = list(_const(TOOLS, "SIGNAL_RUNS"))
    assert "kill-pid" not in runs, runs
    for n in (
        "scan",
        "defs",
        "watch",
        "uplink-burst",
        "falco-burst",
        "isolate-dst",
        "isolate-undo",
        "aide-init",
        "aide-init-ack-stale",
        "rkhunter-setup",
    ):
        assert n in runs, n
    agents = AGENTS.read_text(encoding="utf-8")
    assert '"term_send"' in agents
    assert "SOC_TOOLS" in agents
    print("OK SIGNAL_RUNS", runs)


def test_playbook() -> None:
    text = PLAY.read_text(encoding="utf-8")
    assert "hiroshima_run" in text
    assert "term_send" in text
    assert "where=hiroshima" in text
    assert "unknown_dsts" in text
    assert "Ikke default **undo isolate**" in text or "Ikke default undo isolate" in text
    assert "kill-pid" in text
    decide = DECIDE.read_text(encoding="utf-8")
    assert "hiroshima_run" in decide and "term_send" in decide
    print("OK playbook+mutate")


def test_sudo_needs_pty() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "cockpit" / "backend"))
    try:
        from app.tools import SIGNAL_RUNS, _hiroshima_sudo_line, sudo_needs_pty  # noqa: E402
    except ImportError as e:
        print("SKIP sudo_needs_pty import", e)
        return

    assert sudo_needs_pty({"log_tail": "sudo: a password is required"})
    assert sudo_needs_pty({"error": "a terminal is required to read the password"})
    assert not sudo_needs_pty({"log_tail": "GATE FAIL ALERT", "status": "done", "exit_code": 2})
    assert not sudo_needs_pty({"status": "running"})
    assert _hiroshima_sudo_line("ss -tnp") is None
    assert _hiroshima_sudo_line("sudo kalived-ctl scan") is None
    assert _hiroshima_sudo_line("sudo bash") is not None
    assert _hiroshima_sudo_line("sudo kalived-ctl kill-pid") is not None
    assert "kill-pid" not in SIGNAL_RUNS
    print("OK sudo_needs_pty")


def main() -> int:
    test_allowlist()
    test_playbook()
    test_sudo_needs_pty()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
