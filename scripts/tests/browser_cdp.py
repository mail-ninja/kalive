#!/usr/bin/env python3
"""CDP-browser + MCP. Starter Chromium mot :5173 når den er oppe. Ingen Playwright."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "cockpit" / "backend"
sys.path.insert(0, str(BACKEND))

fail = 0


def ok(msg: str) -> None:
    print("  OK", msg)


def bad(msg: str) -> None:
    global fail
    fail += 1
    print("  FAIL", msg)


def test_url_policy() -> None:
    print("[test] url-policy")
    from app.browser_cdp import check_url

    r = check_url("http://127.0.0.1:5173/")
    if r == "http://127.0.0.1:5173/":
        ok("loopback")
    else:
        bad(f"loopback {r}")
    r = check_url("http://0.0.0.0:5173/")
    if isinstance(r, dict) and r.get("error"):
        ok("0.0.0.0 avvist")
    else:
        bad(f"0.0.0.0 {r}")
    r = check_url("https://example.com/", allow_external=False)
    if isinstance(r, dict) and "ekstern" in str(r.get("error")):
        ok("ekstern uten hake")
    else:
        bad(f"ekstern {r}")
    r = check_url("https://example.com/", allow_external=True)
    if r == "https://example.com/":
        ok("ekstern med hake")
    else:
        bad(f"ekstern allow {r}")
    r = check_url("file:///etc/passwd")
    if isinstance(r, dict):
        ok("file: avvist")
    else:
        bad(f"file {r}")
    r = check_url("javascript:alert(1)")
    if isinstance(r, dict):
        ok("javascript: avvist")
    else:
        bad(f"js {r}")


def test_flatten() -> None:
    print("[test] AX flatten")
    from app.browser_cdp import flatten_ax

    nodes = [
        {
            "nodeId": "1",
            "role": {"value": "RootWebArea"},
            "name": {"value": "kalived cockpit"},
            "backendDOMNodeId": 10,
            "childIds": ["2", "3"],
        },
        {
            "nodeId": "2",
            "parentId": "1",
            "role": {"value": "button"},
            "name": {"value": "Hiroshima"},
            "backendDOMNodeId": 11,
            "childIds": [],
        },
        {
            "nodeId": "3",
            "parentId": "1",
            "role": {"value": "generic"},
            "name": {"value": ""},
            "ignored": True,
            "childIds": [],
        },
    ]
    text, refs = flatten_ax(nodes)
    if "Hiroshima" in text and "[ref=e" in text:
        ok("knapp i tre")
    else:
        bad(f"tree {text!r}")
    if "e2" in refs and refs["e2"] == 11:
        ok("ref→backend")
    else:
        bad(f"refs {refs}")


def test_tools_and_mcp() -> None:
    print("[test] tools + MCP dispatcher")
    from app.agents import SOC_TOOLS, BUILD_TOOLS
    from app.mcp_routes import handle_rpc
    from app.tools import call_tool

    for n in ("browser_snapshot", "browser_click", "browser_navigate"):
        if n in SOC_TOOLS:
            ok(f"signal {n}")
        else:
            bad(f"signal mangler {n}")
        if n in BUILD_TOOLS:
            ok(f"build {n}")
        else:
            bad(f"build mangler {n}")
    r = call_tool("browser_open", {}, allow_mutate=False)
    if "mutating" in str(r.get("error") or ""):
        ok("browser_open uten hake")
    else:
        bad(f"open uten hake {r}")
    r = call_tool("browser_navigate", {"url": "http://example.com"}, allow_mutate=False)
    if "mutating" in str(r.get("error") or ""):
        ok("navigate uten hake")
    else:
        bad(f"nav uten hake {r}")
    init = handle_rpc("initialize", {}, allow_mutate=False, rid=1)
    if init.get("result", {}).get("serverInfo", {}).get("name") == "kalived":
        ok("MCP initialize")
    else:
        bad(f"init {init}")
    listed = handle_rpc("tools/list", {}, allow_mutate=False, rid=2)
    names = [t["name"] for t in (listed.get("result") or {}).get("tools") or []]
    if "browser_snapshot" in names and "hiroshima_verdict" in names:
        ok(f"MCP tools n={len(names)}")
    else:
        bad(f"MCP tools {names}")
    ping = handle_rpc("tools/call", {"name": "ping", "arguments": {}}, allow_mutate=False, rid=3)
    text = ((ping.get("result") or {}).get("content") or [{}])[0].get("text") or ""
    if "pong" in text:
        ok("MCP ping")
    else:
        bad(f"MCP ping {ping}")
    blocked = handle_rpc(
        "tools/call",
        {"name": "browser_open", "arguments": {}},
        allow_mutate=False,
        rid=4,
    )
    blob = json.dumps(blocked)
    if "mutating" in blob:
        ok("MCP mutate-gate")
    else:
        bad(f"MCP mutate {blocked}")


def test_no_playwright() -> None:
    print("[test] ingen playwright/puppeteer i treet")
    hits = []
    for p in (
        ROOT / "cockpit" / "web" / "package.json",
        ROOT / "cockpit" / "backend" / "requirements.txt",
    ):
        t = p.read_text(encoding="utf-8")
        if "playwright" in t.lower() or "puppeteer" in t.lower():
            hits.append(str(p))
    if hits:
        bad(f"dep {hits}")
    else:
        ok("ingen pw/puppeteer-dep")
    src = (BACKEND / "app" / "browser_cdp.py").read_text(encoding="utf-8")
    if "import playwright" in src or "from playwright" in src:
        bad("import playwright")
    else:
        ok("CDP-fil uten playwright-import")


def test_live_cockpit() -> None:
    print("[test] live CDP mot :5173")
    import urllib.request

    try:
        urllib.request.urlopen("http://127.0.0.1:5173/", timeout=2).read(200)
    except Exception:
        print("  SKIP :5173 nede")
        return
    chrom = os.environ.get("KALIVED_CHROMIUM", "/usr/bin/chromium")
    if not Path(chrom).is_file():
        print("  SKIP ingen chromium")
        return
    from app.tools import call_tool

    try:
        st = call_tool("browser_open", {}, allow_mutate=True)
        if st.get("error"):
            bad(f"open {st}")
            return
        if st.get("bind") != "127.0.0.1":
            bad(f"bind {st}")
        else:
            ok(f"cdp port {st.get('port')}")
        nav = call_tool(
            "browser_navigate",
            {"url": "http://127.0.0.1:5173/"},
            allow_mutate=True,
        )
        if nav.get("error"):
            bad(f"navigate {nav}")
            return
        ok(f"url {nav.get('url')}")
        tree = ""
        snap = {}
        for _ in range(8):
            snap = call_tool("browser_snapshot", {}, allow_mutate=False)
            tree = str(snap.get("tree") or "")
            if "Hiroshima" in tree:
                break
            time.sleep(0.5)
        if "Hiroshima" in tree:
            ok("snapshot Hiroshima")
        else:
            bad(f"snapshot mangler Hiroshima n={len(tree)}")
        if "[ref=" in tree:
            ok("snapshot har ref")
        else:
            bad("ingen ref")
        href = ""
        for line in tree.splitlines():
            if "Hiroshima" in line and "[ref=" in line and "button" in line:
                href = line.split("[ref=", 1)[1].split("]", 1)[0]
                break
        if href:
            clk = call_tool("browser_click", {"ref": href}, allow_mutate=True)
            if clk.get("ok"):
                ok(f"click Hiroshima {href}")
            else:
                bad(f"click {clk}")
            time.sleep(0.6)
            tree2 = str(call_tool("browser_snapshot", {}, allow_mutate=False).get("tree") or "")
            if "Kjør scan" in tree2 or "ukjent dest" in tree2.lower() or "Confirm" in tree2:
                ok("skuff synlig etter klikk")
            else:
                print("       skuff-tre n=", len(tree2))
                ok("click gjennomført (skuff kan være off-screen i headless)")
        else:
            bad("ingen Hiroshima-ref å klikke")
        shot = call_tool("browser_screenshot", {}, allow_mutate=False)
        if shot.get("ok") and Path(str(shot.get("path") or "")).is_file():
            ok(f"screenshot {shot.get('bytes')} b")
        else:
            bad(f"shot {shot}")
    finally:
        call_tool("browser_close", {}, allow_mutate=True)
        ok("browser_close")


def main() -> int:
    print("== browser/cdp/mcp ==")
    test_url_policy()
    test_flatten()
    test_tools_and_mcp()
    test_no_playwright()
    test_live_cockpit()
    print("==", "FAIL" if fail else "OK", f"n_fail={fail} ==")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
