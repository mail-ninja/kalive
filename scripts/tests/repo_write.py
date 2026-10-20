#!/usr/bin/env python3
"""repo_write, windowed repo_read, grep summary. Isolated tmp workspace."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cockpit" / "backend"))

td = tempfile.mkdtemp(prefix="kalived-write-")
os.environ["KALIVED_WORKSPACE"] = td
os.environ.setdefault("KALIVED_UP_LOG", "/tmp/kalived-write-test")

from app.tools import call_tool  # noqa: E402

fail = 0


def ok(msg: str) -> None:
    print("  OK", msg)


def bad(msg: str) -> None:
    global fail
    fail = 1
    print("  FAIL", msg)


print("[write new nested]")
w = call_tool("repo_write", {"path": "docs/_lab/hi.py", "text": "print(1)\nprint(2)\nprint(3)\n"}, allow_mutate=True)
if w.get("wrote") and w.get("path") == "docs/_lab/hi.py" and Path(td, "docs/_lab/hi.py").is_file():
    ok("nested write")
else:
    bad("write " + str(w))

print("[write without hake]")
no = call_tool("repo_write", {"path": "x.py", "text": "nope"}, allow_mutate=False)
if "hake" in str(no.get("error") or "").lower() or "mutating" in str(no.get("error") or "").lower():
    ok("blocked")
else:
    bad("leaked " + str(no))

print("[read window]")
rd = call_tool("repo_read", {"path": "docs/_lab/hi.py", "start_line": 2, "n_lines": 1})
if rd.get("start_line") == 2 and "print(2)" in str(rd.get("text") or "") and "print(1)" not in str(rd.get("text") or ""):
    ok("window")
else:
    bad("read " + str(rd))

print("[grep summary]")
g = call_tool("repo_grep", {"query": "print", "glob": "docs/_lab/*"})
if g.get("n") and g.get("summary") and "hi.py:" in str(g.get("summary")) and g.get("path") == "docs/_lab/hi.py":
    ok("grep")
else:
    bad("grep " + str(g))

print("[escape]")
esc = call_tool("repo_write", {"path": "../secret.py", "text": "x"}, allow_mutate=True)
if esc.get("error"):
    ok("path escape")
else:
    bad("escaped " + str(esc))

sys.exit(fail)
