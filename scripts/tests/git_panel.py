#!/usr/bin/env python3
"""Operator git tab: stage/commit, wallE blocked, agent still cannot push."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cockpit" / "backend"))

td = tempfile.mkdtemp(prefix="kalived-gitpane-")
os.environ["KALIVED_WORKSPACE"] = td
os.environ["KALIVED_WORKSPACES"] = str(Path(td) / "workspaces.json")
os.environ["KALIVED_OWNER_HOME"] = td
os.environ["KALIVED_WS_ALLOW"] = td
os.environ["KALIVED_AI_ENV"] = str(Path(td) / "env")
os.environ.setdefault("KALIVED_UP_LOG", "/tmp/kalived-gitpane-test")

from app import git_panel as gp  # noqa: E402
from app.tools import call_tool  # noqa: E402

fail = 0


def ok(msg: str) -> None:
    print("  OK", msg)


def bad(msg: str) -> None:
    global fail
    fail = 1
    print("  FAIL", msg)


def git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=td, check=True, capture_output=True, text=True)


print("[setup]", td)
git("init", "-b", "main")
git("config", "user.email", "test@kalived.local")
git("config", "user.name", "kalived-test")
git("config", "commit.gpgsign", "false")
(Path(td) / "a.txt").write_text("one\n", encoding="utf-8")

print("[status dirty]")
st = gp.status()
if st.get("dirty") and any(f.get("path") == "a.txt" for f in st.get("files") or []):
    ok("dirty")
else:
    bad("status " + str(st))

print("[stage + commit]")
sg = gp.stage(["a.txt"])
if not sg.get("ok"):
    bad("stage " + str(sg))
else:
    ok("stage")
cm = gp.commit("add a")
if cm.get("ok") and cm.get("sha"):
    ok("commit " + str(cm.get("sha")))
else:
    bad("commit " + str(cm))

print("[wallE blocked]")
git("remote", "add", "origin", "git@github.com:mail-ninja/wallE.git")
git("remote", "add", "kalive", "git@github.com:mail-ninja/kalive.git")
pu = gp.push(remote="origin")
if "wallE" in str(pu.get("error") or ""):
    ok("origin/wallE nekta")
else:
    bad("wallE leaked " + str(pu))

print("[agent push still denied]")
ag = call_tool("repo_git", {"action": "push"}, allow_mutate=True)
if "push" in str(ag.get("error") or "").lower():
    ok("agent push denied")
else:
    bad("agent push " + str(ag))

print("[blocked helper]")
if gp._blocked("origin", "https://github.com/mail-ninja/wallE.git"):
    ok("_blocked url")
else:
    bad("_blocked missed url")

print("[github token empty]")
who = gp.github_who()
if who.get("set") is False and not who.get("login"):
    ok("ingen token")
else:
    bad("who " + str(who))

print("[https push without token]")
https = gp.push.__wrapped__ if False else None
# remote kalive is ssh in this tmp repo? add https remote
git("remote", "add", "httpsgh", "https://github.com/alterninja/hiroshima.git")
puh = gp.push(remote="httpsgh")
if "token" in str(puh.get("error") or "").lower() or "logg inn" in str(puh.get("error") or "").lower():
    ok("https without token")
else:
    bad("https push " + str(puh))

print("[init when missing]")
from app import workspace as w  # noqa: E402

empty = Path(tempfile.mkdtemp(prefix="kalived-gitinit-"))
os.environ["KALIVED_WORKSPACE"] = str(empty)
os.environ["KALIVED_WORKSPACES"] = str(empty / "workspaces.json")
os.environ["KALIVED_OWNER_HOME"] = str(empty)
os.environ["KALIVED_WS_ALLOW"] = str(empty)
w.reset_live()
st0 = gp.status()
if st0.get("repo") is False and "git-repo" in str(st0.get("error") or ""):
    ok("status not a repo")
else:
    bad("expected no repo " + str(st0))
ini = gp.init()
if ini.get("ok") and ini.get("repo") is True and (empty / ".git").is_dir():
    ok("init")
else:
    bad("init " + str(ini))
ini2 = gp.init()
if ini2.get("ok") and "allerede" in str(ini2.get("summary") or ""):
    ok("init idempotent")
else:
    bad("init2 " + str(ini2))

sys.exit(fail)
