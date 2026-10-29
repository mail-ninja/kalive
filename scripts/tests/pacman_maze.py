#!/usr/bin/env python3
"""CrackMan maze must be solvable: every pill reachable from start."""
from __future__ import annotations

import re
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
html = (ROOT / "docs" / "pacman" / "index.html").read_text(encoding="utf-8")
m = re.search(r"const RAW = \[(.*?)\]", html, re.S)
if not m:
    print("  FAIL no RAW maze")
    sys.exit(1)
rows = re.findall(r'"([^"]*)"', m.group(1))
if not rows:
    print("  FAIL empty maze")
    sys.exit(1)
w = len(rows[0])
h = len(rows)
fail = 0


def ok(msg: str) -> None:
    print("  OK", msg)


def bad(msg: str) -> None:
    global fail
    fail = 1
    print("  FAIL", msg)


print("[maze shape]")
if all(len(r) == w for r in rows):
    ok(f"{w}x{h}")
else:
    bad("ragged " + str([len(r) for r in rows]))

start = None
for y, r in enumerate(rows):
    if "@" in r:
        start = (r.index("@"), y)
        break
if start:
    ok("start " + str(start))
else:
    bad("no @")
    sys.exit(1)


def walk_pac(ch: str) -> bool:
    if ch in "BPIC@":
        ch = "."
    if ch == "#":
        return False
    if ch == "-":
        return False
    return True


q = deque([start])
seen = {start}
while q:
    x, y = q.popleft()
    for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        nx, ny = x + dx, y + dy
        if nx < 0:
            nx = w - 1
        if nx >= w:
            nx = 0
        if not (0 <= ny < h):
            continue
        if (nx, ny) in seen:
            continue
        if not walk_pac(rows[ny][nx]):
            continue
        seen.add((nx, ny))
        q.append((nx, ny))

trapped = []
pills = 0
for y, r in enumerate(rows):
    for x, ch in enumerate(r):
        if ch in ".o":
            pills += 1
            if (x, y) not in seen:
                trapped.append((x, y, ch))

print("[reachability]")
if pills >= 80:
    ok(f"{pills} pills")
else:
    bad(f"too few pills {pills}")
if not trapped:
    ok("all pills reachable")
else:
    bad("trapped " + str(trapped[:8]))

if "CrackMan" in html or "CRACK-MAN" in html:
    ok("titled CrackMan")
else:
    bad("title")
if "Rivotril" in html and "SNUT" in html and "NHO" in html and "CIA" in html:
    ok("cast + rivotril")
else:
    bad("theme")

sys.exit(fail)
