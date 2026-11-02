#!/usr/bin/env python3
"""Open/create workspace with path policy. Isolated tmp. Never live $HOME switch."""
from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cockpit" / "backend"))

td = Path(tempfile.mkdtemp(prefix="kalived-ws-"))
os.environ["KALIVED_WORKSPACE"] = str(td / "default")
os.environ["KALIVED_WORKSPACES"] = str(td / "workspaces.json")
os.environ["KALIVED_WS_ALLOW"] = str(td)
os.environ["KALIVED_OWNER_HOME"] = str(td / "home")
os.environ.setdefault("KALIVED_UP_LOG", "/tmp/kalived-ws-test")

(td / "default").mkdir()
(td / "home").mkdir()
(td / "other").mkdir()
(td / "home" / ".ssh").mkdir()
(td / "home" / ".config" / "kalived").mkdir(parents=True)

from app import workspace as w  # noqa: E402
from app.workspace import toolchain_ok  # noqa: E402

w.reset_live()
fail = 0


def ok(msg: str) -> None:
    print("  OK", msg)


def bad(msg: str) -> None:
    global fail
    fail = 1
    print("  FAIL", msg)


print("[setup]", td)

print("[default root]")
if w.root().resolve() == (td / "default").resolve():
    ok("default")
else:
    bad("root " + str(w.root()))

print("[block home]")
home = w.check_open(str(td / "home"))
if isinstance(home, dict) and "hjemmekatalogen" in str(home.get("error") or ""):
    ok("home blocked")
else:
    bad("home " + str(home))

print("[block ssh]")
ssh = w.check_open(str(td / "home" / ".ssh"))
if isinstance(ssh, dict):
    ok("ssh blocked")
else:
    bad("ssh " + str(ssh))

print("[block secrets]")
sec = w.check_open(str(td / "home" / ".config" / "kalived"))
if isinstance(sec, dict):
    ok("secrets blocked")
else:
    bad("secrets " + str(sec))

print("[block /etc]")
etc = w.check_open("/etc")
if isinstance(etc, dict):
    ok("/etc blocked")
else:
    bad("/etc " + str(etc))

print("[open other]")
op = w.open_workspace(str(td / "other"))
if op.get("ok") and Path(op["root"]).resolve() == (td / "other").resolve() and op.get("kind") == "external":
    ok("opened other")
else:
    bad("open " + str(op))

print("[root after open]")
if w.root().resolve() == (td / "other").resolve():
    ok("live root")
else:
    bad("live " + str(w.root()))

print("[recents]")
snap = w.snapshot()
paths = [r["path"] for r in snap.get("recents") or []]
if str((td / "other").resolve()) in paths or str(td / "other") in paths:
    ok("recent")
else:
    bad("recents " + str(snap.get("recents")))

print("[mkdir here]")
md = w.mkdir_here("src")
if md.get("ok") and (td / "other" / "src").is_dir():
    ok("mkdir")
else:
    bad("mkdir " + str(md))

print("[mkdir escape]")
esc = w.mkdir_here("../nope")
if esc.get("error"):
    ok("mkdir escape")
else:
    bad("escaped mkdir " + str(esc))

print("[create workspace]")
cr = w.create_workspace(str(td), "game1", git=True)
if cr.get("ok") and (td / "game1" / ".git").exists() and w.root().name == "game1":
    ok("create")
else:
    bad("create " + str(cr))

print("[toolchain external allows npm root]")
if toolchain_ok("npm install"):
    ok("npm in external")
else:
    bad("npm denied in external")

print("[json mode 0600]")
st = os.stat(td / "workspaces.json")
if st.st_mode & 0o777 == 0o600:
    ok("json 0600")
else:
    bad("mode " + oct(st.st_mode))

print("[state persists after reset_live]")
w.reset_live()
if w.root().name == "game1":
    ok("persist")
else:
    bad("persist root " + str(w.root()))

sys.exit(fail)
