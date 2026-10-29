#!/usr/bin/env python3
"""Gap-fill and follow-up intent for the build agent. Pure."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cockpit" / "backend"))
os.environ.setdefault("KALIVED_WORKSPACE", str(ROOT))

from app.intent import fill_goal, format_intent, prior_messages  # noqa: E402

fail = 0


def ok(msg: str) -> None:
    print("  OK", msg)


def bad(msg: str) -> None:
    global fail
    fail = 1
    print("  FAIL", msg)


PAC = (
    "ok byggmester. lag en pacman-klone! Skriv koden i monaco og bygg en "
    "spillbar preview i iframe. detaljene er opp til deg. kjør på!"
)
BLOCKED = '**BLOCKED** — huk av «agent får kjøre»'
FOLLOW = "ok den er huket av. lag klonen i en undermappe i docs-mappa!"
GIT_ASK = "NEEDS_INPUT — hvilken repo-URL skal klones inn under docs/?"

print("[pacman follow-up is product clone, not git]")
g = fill_goal(FOLLOW, [{"user": PAC, "assistant": BLOCKED}])
if g["product_not_git"] and g["path"] == "docs/pacman/index.html" and g["retry_mutate"] and g["write_now"]:
    ok("docs/pacman + retry")
else:
    bad("pacman " + str(g))
if "git clone" in g["goal"].lower() and "produkt" not in " ".join(g["hints"]).lower():
    bad("treated as git " + g["goal"])
else:
    ok("not git clone")
txt = format_intent(g)
if "docs/pacman" in txt and "repo-URL" in txt:
    ok("intent block names path")
else:
    bad("format " + txt[:200])

print("[sanitize git-ask assistant]")
msgs = prior_messages(
    [{"user": FOLLOW, "assistant": GIT_ASK}],
    {"product_not_git": True},
)
if msgs and "git clone" in msgs[1]["content"].lower() and "misforsto" in msgs[1]["content"]:
    ok("rewrote git-ask")
elif msgs and "misforsto" in msgs[1]["content"]:
    ok("rewrote git-ask")
else:
    bad("sanitize " + str(msgs))

print("[explicit git clone stays git]")
g2 = fill_goal("klone https://github.com/foo/bar inn i docs/")
if not g2["product_not_git"] and not g2["write_now"]:
    ok("url is git clone")
else:
    bad("url " + str(g2))

print("[vague snake fills path]")
g3 = fill_goal("bygg en snake. detaljene er opp til deg. kjør på!")
if g3["kind"] in ("gapfill", "ape", "fresh") and g3["write_now"] and "snake" in g3["path"]:
    ok("snake path " + g3["path"])
else:
    bad("snake " + str(g3))

print("[ape: lag tetris!]")
g5 = fill_goal("lag tetris!")
txt5 = format_intent(g5)
if (
    g5["ape"]
    and g5["write_now"]
    and g5["path"] == "docs/tetris/index.html"
    and g5["kind"] == "ape"
    and "tetromino" in txt5.lower()
):
    ok("tetris ape → docs/tetris")
else:
    bad("tetris ape " + str(g5) + " " + txt5[:180])
g6 = fill_goal("tetris!")
if g6["ape"] and g6["path"] == "docs/tetris/index.html":
    ok("bare «tetris!»")
else:
    bad("bare tetris " + str(g6))
g7 = fill_goal(
    "lag tetris!",
    [{"user": "lag en mario-klone i docs/mario/", "assistant": "DONE"}],
)
if g7["slug"] == "tetris" and g7["path"] == "docs/tetris/index.html" and not g7["followup"]:
    ok("ape ignores prior mario")
else:
    bad("prior leak " + str(g7))
if prior_messages([{"user": "mario", "assistant": "DONE"}], g7) == []:
    ok("ape drops prior messages")
else:
    bad("prior msgs leaked")

print("[question is not write-now]")
g4 = fill_goal("hva er probe-appen?")
if not g4["write_now"] and g4["kind"] == "fresh":
    ok("ask stays ask")
else:
    bad("ask " + str(g4))

sys.exit(fail)
