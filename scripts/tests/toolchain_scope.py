#!/usr/bin/env python3
"""npm/bun/pip/cargo only under apps/ or docs/."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cockpit" / "backend"))
os.environ.setdefault("KALIVED_WORKSPACE", str(ROOT))

from app.workspace import toolchain_ok  # noqa: E402

fail = 0


def ok(msg: str) -> None:
    print("  OK", msg)


def bad(msg: str) -> None:
    global fail
    fail = 1
    print("  FAIL", msg)


print("[toolchain scope]")
if toolchain_ok("python3 scripts/tests/intent_fill.py"):
    ok("plain python")
else:
    bad("python denied")
if not toolchain_ok("npm install"):
    ok("npm root denied")
else:
    bad("npm root allowed")
if not toolchain_ok("npx vite"):
    ok("npx root denied")
else:
    bad("npx root")
if toolchain_ok("cd apps/mjau-park && npm install"):
    ok("cd apps + npm")
else:
    bad("cd apps")
if toolchain_ok("npm --prefix apps/foo run dev"):
    ok("--prefix apps")
else:
    bad("prefix")
if toolchain_ok("pip install -t docs/lib requests"):
    ok("pip into docs")
else:
    bad("pip docs")
if not toolchain_ok("pip install requests"):
    ok("pip root denied")
else:
    bad("pip root")

print("[toolchain external]")
import tempfile

from app import workspace as w

ext = Path(tempfile.mkdtemp(prefix="kalived-tc-"))
os.environ["KALIVED_WORKSPACES"] = str(ext / "ws.json")
os.environ["KALIVED_WS_ALLOW"] = str(ext)
(ext / "proj").mkdir()
w.reset_live()
op = w.open_workspace(str(ext / "proj"))
if op.get("ok") and toolchain_ok("npm install"):
    ok("npm allowed outside kalived")
else:
    bad("external npm " + str(op))
w.reset_live()

sys.exit(fail)
