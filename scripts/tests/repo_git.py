#!/usr/bin/env python3
"""repo_git: status/diff/log/commit, never push. Isolated tmp workspace."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cockpit" / "backend"))

td = tempfile.mkdtemp(prefix="kalived-git-")
os.environ["KALIVED_WORKSPACE"] = td
os.environ.setdefault("KALIVED_UP_LOG", "/tmp/kalived-git-test")

from app.tools import call_tool  # noqa: E402
from app import workspace as w  # noqa: E402

fail = 0


def ok(msg: str) -> None:
    print("  OK", msg)


def bad(msg: str) -> None:
    global fail
    fail = 1
    print("  FAIL", msg)


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=td, check=True, capture_output=True, text=True)


print("[setup]", td)
git("init", "-b", "main")
git("config", "user.email", "test@kalived.local")
git("config", "user.name", "kalived-test")
git("config", "commit.gpgsign", "false")
(Path(td) / "hello.txt").write_text("one\n", encoding="utf-8")

print("[status dirty]")
st = call_tool("repo_git", {"action": "status"}, allow_mutate=False)
if st.get("dirty") and st.get("branch") == "main" and any(f.get("path") == "hello.txt" for f in st.get("files") or []):
    ok("untracked hello.txt")
else:
    bad("status " + str(st))

print("[commit without hake]")
no = call_tool("repo_git", {"action": "commit", "message": "add hello", "paths": ["hello.txt"]}, allow_mutate=False)
if "hake" in str(no.get("error") or "").lower() or "mutating" in str(no.get("error") or "").lower():
    ok("commit blocked")
else:
    bad("commit leaked " + str(no))

print("[commit with hake]")
yes = call_tool(
    "repo_git",
    {"action": "commit", "message": "add hello", "paths": ["hello.txt"]},
    allow_mutate=True,
)
if yes.get("ok") and yes.get("sha"):
    ok("commit " + str(yes.get("sha")))
else:
    bad("commit " + str(yes))

print("[status clean]")
st2 = call_tool("repo_git", {"action": "status"})
if st2.get("dirty") is False and st2.get("branch") == "main":
    ok("clean")
else:
    bad("status after commit " + str(st2))

print("[log]")
lg = call_tool("repo_git", {"action": "log", "n": 5})
subs = [c.get("subject") for c in lg.get("commits") or []]
if "add hello" in subs:
    ok("log")
else:
    bad("log " + str(lg))

print("[diff empty]")
df = call_tool("repo_git", {"action": "diff"})
if not (df.get("diff") or "").strip():
    ok("no diff")
else:
    bad("unexpected diff " + str(df)[:200])

print("[push denied]")
pu = call_tool("repo_git", {"action": "push"}, allow_mutate=True)
if "push" in str(pu.get("error") or "").lower():
    ok("push denied")
else:
    bad("push " + str(pu))

print("[unknown action]")
unk = call_tool("repo_git", {"action": "rebase"})
if unk.get("error"):
    ok("rebase denied")
else:
    bad("rebase " + str(unk))

print("[path escape]")
esc = call_tool("repo_git", {"action": "commit", "message": "nope", "paths": ["../secret"]}, allow_mutate=True)
if esc.get("error"):
    ok("path escape")
else:
    bad("escaped " + str(esc))

print("[repo_bash git commit]")
bash_c = call_tool("repo_bash", {"line": "git commit -m x"}, allow_mutate=True)
if "repo_git" in str(bash_c.get("error") or ""):
    ok("bash commit redirected")
else:
    bad("bash commit " + str(bash_c))

print("[repo_bash git push]")
bash_p = call_tool("repo_bash", {"line": "git push origin main"}, allow_mutate=True)
if "push" in str(bash_p.get("error") or "").lower() or "nekta" in str(bash_p.get("error") or "").lower():
    ok("bash push denied")
else:
    bad("bash push " + str(bash_p))

print("[workspace root]")
if str(w.root()) == str(Path(td).resolve()):
    ok("isolated workspace")
else:
    bad("root " + str(w.root()))

sys.exit(fail)
