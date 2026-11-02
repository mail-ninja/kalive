#!/usr/bin/env python3
"""Project chat sessions: list, save, last-used, prior pairs."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cockpit" / "backend"))
td = tempfile.mkdtemp(prefix="kalived-sess-")
os.environ["KALIVED_SESSIONS"] = td
os.environ.setdefault("KALIVED_WORKSPACE", str(ROOT))

from app.sessions import (  # noqa: E402
    canonical,
    create_session,
    get_session,
    last_from_hist,
    list_all,
    list_sessions,
    project_of,
    save_session,
)

fail = 0


def ok(msg: str) -> None:
    print("  OK", msg)


def bad(msg: str) -> None:
    global fail
    fail = 1
    print("  FAIL", msg)


print("[project_of]")
if project_of("docs/mario/index.html") == "docs/mario" and canonical("docs/mario") == "docs/mario":
    ok("docs/mario")
else:
    bad("mario " + project_of("docs/mario/index.html"))
if project_of("docs/NOW.md") == "" and project_of("README.md") == "":
    ok("files are not projects")
else:
    bad("file project")
if project_of("apps/mjau-park/src/main.ts") == "apps/mjau-park":
    ok("apps")
else:
    bad("apps")

print("[sessions]")
a = create_session("build", "docs/mario", title="pippa", hist=[{"role": "you", "text": "lag mario"}])
b = create_session("build", "docs/mario", hist=[{"role": "you", "text": "gjør hoppet høyere"}])
lst = list_sessions("build", "docs/mario")
if lst and lst[0]["id"] == b["id"] and lst[1]["id"] == a["id"]:
    ok("last used first")
else:
    bad("order " + str(lst))
save_session("build", "docs/mario", a["id"], [{"role": "you", "text": "igjen"}, {"role": "bot", "text": "DONE"}])
lst2 = list_sessions("build", "docs/mario")
if lst2[0]["id"] == a["id"]:
    ok("touch moves up")
else:
    bad("touch " + str(lst2))

katte = list_sessions("build", "docs/katte-youtube")
if katte == []:
    ok("other project empty")
else:
    bad("leak " + str(katte))
if not (Path(td) / "build" / "docs--katte-youtube").exists():
    ok("list does not mkdir")
else:
    bad("list mkdir")

create_session("build", "docs/katte-youtube", title="mjau", hist=[{"role": "you", "text": "lag katte-youtube"}])
allg = list_all("build")
projs = [g["project"] for g in allg]
if projs[0] == "docs/katte-youtube" and "docs/mario" in projs:
    ok("list_all groups last-used first")
else:
    bad("list_all " + str(projs))

print("[prior pairs]")
pr = last_from_hist(
    [
        {"role": "sys", "text": "ws up"},
        {"role": "you", "text": "lag mario"},
        {"role": "bot", "text": "DONE pippa"},
        {"role": "you", "text": "gjør hoppet høyere"},
        {"role": "bot", "text": "patched"},
    ],
    2,
)
if pr[-1]["user"] == "gjør hoppet høyere" and pr[0]["user"] == "lag mario":
    ok("pairs")
else:
    bad("pairs " + str(pr))

got = get_session("build", "docs/mario", a["id"])
if got["hist"][0]["text"] == "igjen":
    ok("get hist")
else:
    bad("get " + str(got.get("hist")))

sys.exit(fail)
