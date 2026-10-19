#!/usr/bin/env python3
"""Parser + managed loopback serve (no 0.0.0.0)."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cockpit" / "backend"))
os.environ.setdefault("KALIVED_WORKSPACE", str(ROOT))
os.environ.setdefault("KALIVED_UP_LOG", "/tmp/kalived-preview-test")

from app.preview import parse_loopback_url, probe, start, stop  # noqa: E402

fail = 0


def ok(msg: str) -> None:
    print("  OK", msg)


def bad(msg: str) -> None:
    global fail
    fail = 1
    print("  FAIL", msg)


def expect(raw: str, want: str | None) -> None:
    got = parse_loopback_url(raw)
    if got == want:
        ok(repr(raw))
    else:
        bad(f"{raw!r} -> {got!r} want {want!r}")


print("[parse]")
expect("http://127.0.0.1:8765/", "http://127.0.0.1:8765/")
expect("http://localhost:8765/docs/_snake.html", "http://127.0.0.1:8765/docs/_snake.html")
expect("127.0.0.1:8765", "http://127.0.0.1:8765/")
expect("http://0.0.0.0:8765/", None)
expect("http://127.0.0.1:8788/v1/health", None)
expect("http://127.0.0.1:5173/", None)
expect("https://example.com/", None)
expect("http://127.0.0.1:8765@evil/", None)
expect("javascript:alert(1)", None)

print("[serve]")
stop()
out = start(dir="docs", path="_snake.html")
if out.get("error"):
    bad("start " + str(out))
else:
    url = str(out.get("url") or "")
    if "127.0.0.1" in url and "_snake.html" in url and out.get("listening"):
        ok("start " + url)
    else:
        bad("start payload " + str(out))
    time.sleep(0.2)
    p = probe(url)
    if p.get("ok") and p.get("status") == 200:
        ok("probe 200")
    else:
        bad("probe " + str(p))
    # 0.0.0.0 rejected
    bad_line = start(line="python3 -m http.server 8771 --bind 0.0.0.0")
    if "0.0.0.0" in str(bad_line.get("error") or ""):
        ok("reject 0.0.0.0")
    else:
        bad("allowed 0.0.0.0 " + str(bad_line))
st = stop()
if st.get("stopped"):
    ok("stop")
else:
    bad("stop " + str(st))

sys.exit(fail)
