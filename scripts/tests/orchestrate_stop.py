#!/usr/bin/env python3
"""Stop-when-done brakes for the build loop."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cockpit" / "backend"))
os.environ.setdefault("KALIVED_WORKSPACE", str(ROOT))

from app.orchestrate import is_fail, is_verify, next_brake  # noqa: E402
from app.orchestrate import SEE_CAP, WRITE_NUDGE_AT  # noqa: E402

fail = 0


def ok(msg: str) -> None:
    print("  OK", msg)


def bad(msg: str) -> None:
    global fail
    fail = 1
    print("  FAIL", msg)


def step(**kw):
    return next_brake(
        verified=kw.get("verified", False),
        see_streak=kw.get("see_streak", 0),
        names=kw.get("names") or [],
        args_list=kw.get("args_list"),
        got_verify=kw.get("got_verify", False),
        got_edit=kw.get("got_edit", False),
        got_fail=kw.get("got_fail", False),
        see_only_count=kw.get("see_only_count", 0),
    )


print("[verify helpers]")
if is_verify("repo_bash", {"exit_code": 0}):
    ok("bash 0")
else:
    bad("bash 0")
if not is_verify("repo_bash", {"exit_code": 1}):
    ok("bash 1 not verify")
else:
    bad("bash 1 counted as verify")
if is_verify("preview_serve", {"listening": True, "url": "http://127.0.0.1:8765/"}):
    ok("preview listening")
else:
    bad("preview")
if is_fail("repo_bash", {"exit_code": 2}):
    ok("bash fail")
else:
    bad("bash fail")

print("[bash 0 then grep → force stop]")
s = step(got_verify=True, names=["repo_bash"])
if s["nudge"] and not s["force_stop"] and s["verified"]:
    ok("nudge after test")
else:
    bad("nudge " + str(s))
s2 = step(verified=True, see_streak=0, names=["repo_grep", "repo_glob"], got_verify=False)
if s2["force_stop"] and s2["see_streak"] == 1:
    ok("grep after verify forces stop")
else:
    bad("force " + str(s2))

print("[failed test does not stop]")
s3 = step(verified=True, got_fail=True, names=["repo_bash"])
if not s3["verified"] and not s3["force_stop"]:
    ok("fail clears verified")
else:
    bad("fail " + str(s3))

print("[edit after verify requires re-verify]")
s4 = step(verified=True, got_edit=True, names=["repo_edit"])
if not s4["verified"] and not s4["force_stop"]:
    ok("edit clears verified")
else:
    bad("edit " + str(s4))

print("[edit + bash 0 same round]")
s5 = step(got_edit=True, got_verify=True, names=["repo_edit", "repo_bash"])
if s5["verified"] and s5["nudge"] and not s5["force_stop"]:
    ok("verify wins over edit in same round")
else:
    bad("same round " + str(s5))

print("[status after commit]")
s6 = step(
    verified=True,
    names=["repo_git"],
    args_list=[{"action": "status"}],
)
if s6["force_stop"]:
    ok("git status after verify stops")
else:
    bad("git status " + str(s6))

print("[see-only without verify nudges write, does not force stop]")
s7 = step(names=["repo_glob", "repo_read"], see_only_count=WRITE_NUDGE_AT - 1)
if s7["write_nudge"] and not s7["force_stop"] and s7["see_only_count"] == WRITE_NUDGE_AT:
    ok("write nudge after 3 see-only")
else:
    bad("write nudge " + str(s7))
s8 = step(names=["repo_read"], see_only_count=SEE_CAP - 1)
if s8["see_cap_hit"] and s8["write_nudge"] and not s8["force_stop"]:
    ok("see-cap hits without DONE")
else:
    bad("see-cap " + str(s8))
s9 = step(got_edit=True, names=["repo_write"], see_only_count=SEE_CAP)
if s9["see_only_count"] == 0 and not s9["write_nudge"] and not s9["force_stop"]:
    ok("write clears see-only count")
else:
    bad("write clear " + str(s9))

sys.exit(fail)
