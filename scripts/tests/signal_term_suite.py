#!/usr/bin/env python3
"""Suite: Signal/term-verktøy, Hiroshima-knapper, cockpit-HTTP, dest-IP.

Kjører mot git-treet og live loopback :8788/:5173 når de er oppe.
Starter ikke scan/isolate/aide/rkhunter. watch/falco bare hvis KALIVED_LIVE_WATCH=1.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "cockpit" / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

HIRO = ROOT / "cockpit" / "web" / "src" / "lib" / "Hiroshima.svelte"
APP = ROOT / "cockpit" / "web" / "src" / "App.svelte"
DESK = ROOT / "cockpit" / "web" / "src" / "lib" / "desk.ts"
TOOLS = ROOT / "cockpit" / "backend" / "app" / "tools.py"
AGENTS = ROOT / "cockpit" / "backend" / "app" / "agents.py"
PLAY = ROOT / "prompts" / "playbooks" / "signal.md"
CFG = ROOT / "scripts" / "lib" / "kalived-config.sh"
HELPER_CFG = Path("/usr/local/lib/kalived/scripts/lib/kalived-config.sh")

API = os.environ.get("KALIVED_API", "http://127.0.0.1:8788")
UI = os.environ.get("KALIVED_UI", "http://127.0.0.1:5173")

SIGNAL_RUNS = (
    "scan",
    "defs",
    "watch",
    "uplink-burst",
    "falco-burst",
    "isolate-dst",
    "isolate-undo",
    "aide-init",
    "aide-init-ack-stale",
    "rkhunter-setup",
)
BUTTON_RUNS = (
    "scan",
    "aide-init",
    "rkhunter-setup",
    "isolate-dst",
    "isolate-undo",
    "watch",
    "uplink-burst",
    "falco-burst",
)
fail = 0


def ok(msg: str) -> None:
    print("  OK", msg)


def bad(msg: str) -> None:
    global fail
    fail += 1
    print("  FAIL", msg)


def get(path: str, timeout: float = 4.0):
    req = urllib.request.Request(API + path, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"error": raw.decode("utf-8", "replace")[:400]}
    except Exception as e:
        return 0, {"error": str(e)}


def post(path: str, payload: dict, timeout: float = 6.0):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API + path, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"error": raw.decode("utf-8", "replace")[:400]}
    except Exception as e:
        return 0, {"error": str(e)}


def test_button_map() -> None:
    print("[test] knapper → ctl")
    hiro = HIRO.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    desk = DESK.read_text(encoding="utf-8")
    for name in BUTTON_RUNS:
        if name == "scan":
            if "startRun('scan')" not in hiro and 'startRun("scan")' not in hiro:
                bad("scan-knapp mangler")
            else:
                ok("Kjør scan")
            continue
        needle = f"confirmRun('{name}'"
        if needle not in hiro:
            bad(f"knapp {name} mangler confirmRun")
        else:
            ok(f"Confirm {name}")
    if "pending !== name" not in hiro:
        bad("to-klikk Confirm mangler")
    else:
        ok("to-klikk Confirm")
    if "unknown dest" not in hiro.lower() and "ukjent dest" not in hiro:
        bad("dest-IP-blokk mangler i skuff")
    else:
        ok("dest-IP i skuff")
    if "UFW-treff" not in hiro:
        bad("UFW-treff-blokk mangler")
    else:
        ok("UFW-treff i skuff")
    if "need_pty" not in hiro or "ptyWrite" not in hiro:
        bad("skuff maler ikke xterm ved passord")
    else:
        ok("skuff → Hiroshima-xterm ved passord")
    if "onOpenHiroshima" not in app or "need_pty" not in app:
        bad("App åpner ikke skuff ved need_pty")
    else:
        ok("App åpner Hiroshima ved need_pty")
    if "queuedPty" not in desk:
        bad("desk.ts kø for pty mangler")
    else:
        ok("pty-kø når Term ikke er mountet")
    if "agent får kjøre" not in app:
        bad("hake mangler")
    else:
        ok("hake agent får kjøre")
    if "kjøredetaljer" not in app:
        bad("kjøredetaljer (signal-velger) mangler")
    else:
        ok("kjøredetaljer har agent-velger")


def test_allowlist() -> None:
    print("[test] Signal-allowlist")
    tree = ast.parse(TOOLS.read_text(encoding="utf-8"))
    runs = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "SIGNAL_RUNS":
                    runs = list(ast.literal_eval(node.value))
    if runs is None:
        bad("SIGNAL_RUNS mangler")
        return
    if "kill-pid" in runs:
        bad("kill-pid i SIGNAL_RUNS")
    else:
        ok("kill-pid utenfor Signal")
    for n in SIGNAL_RUNS:
        if n not in runs:
            bad(f"{n} mangler i SIGNAL_RUNS")
    agents = AGENTS.read_text(encoding="utf-8")
    if '"term_send"' not in agents or "SOC_TOOLS" not in agents:
        bad("signal mangler term_send")
    else:
        ok("SOC_TOOLS + term_send")
    play = PLAY.read_text(encoding="utf-8")
    if "where=hiroshima" not in play or "unknown_dsts" not in play:
        bad("signal.md mangler xterm/dest")
    else:
        ok("signal.md action + dest")


def test_term_rails() -> None:
    print("[test] term_send-skinner")
    from app.tools import _hiroshima_sudo_line, call_tool, sudo_needs_pty, term_send

    if call_tool("term_send", {"line": "ss -ltnp"}, allow_mutate=False).get("error", "").startswith("mutating"):
        ok("term_send krever hake")
    else:
        bad("term_send uten hake")
    r = call_tool("term_send", {"line": "ss -ltnp", "where": "hiroshima"}, allow_mutate=True)
    if r.get("pty_write") == "ss -ltnp\n" and r.get("open_hiroshima") is True:
        ok("term_send where=hiroshima")
    else:
        bad(f"term_send hiroshima {r}")
    r = call_tool("term_send", {"line": "sudo -S kalived-ctl watch"}, allow_mutate=True)
    if r.get("error"):
        ok("sudo -S avvist")
    else:
        bad("sudo -S slapp gjennom")
    if _hiroshima_sudo_line("sudo bash"):
        ok("fri root-shell avvist")
    else:
        bad("sudo bash slapp gjennom")
    if _hiroshima_sudo_line("sudo kalived-ctl kill-pid"):
        ok("kill-pid avvist i term")
    else:
        bad("kill-pid i term_send")
    if sudo_needs_pty({"log_tail": "sudo: a password is required"}):
        ok("password → pty")
    else:
        bad("password-detect")
    if not sudo_needs_pty({"log_tail": "GATE FAIL ALERT"}):
        ok("GATE FAIL er ikke passord")
    else:
        bad("GATE FAIL feiltolket som passord")


def test_mutate_gate() -> None:
    print("[test] mutate-gate")
    from app.tools import call_tool

    for name in ("hiroshima_run", "hiroshima_scan", "term_send"):
        r = call_tool(name, {"name": "watch"} if name == "hiroshima_run" else {"line": "true"}, allow_mutate=False)
        if "mutating" in str(r.get("error") or ""):
            ok(f"{name} uten hake")
        else:
            bad(f"{name} uten hake: {r}")
    r = call_tool("hiroshima_run", {"name": "kill-pid"}, allow_mutate=True)
    blob = str(r.get("error") or "") + " " + str(r.get("have") or "")
    if r.get("error") and "kill-pid" in blob:
        ok("kill-pid avvist i hiroshima_run")
    else:
        bad(f"kill-pid run {r}")
    from app import hiroshima as hiro

    r = hiro.start_named("watch", False)
    if r.get("error") and "confirm" in str(r.get("error")):
        ok("start_named uten confirm")
    else:
        bad(f"start_named uten confirm {r}")
    from app.hiroshima import RUNS

    for n in SIGNAL_RUNS:
        if n in RUNS:
            ok(f"ctl {n} i RUNS")
        else:
            bad(f"ctl {n} mangler i hiroshima.RUNS")


def test_http_cockpit() -> None:
    print("[test] live HTTP cockpit")
    code, health = get("/v1/health")
    if code == 200 and health.get("ok"):
        ok("GET /v1/health")
    else:
        bad(f"health {code} {health}")
        return
    code, agents = get("/v1/agents", timeout=12.0)
    rows = agents.get("agents") if isinstance(agents, dict) else []
    if not isinstance(rows, list):
        rows = []
    sig = next((a for a in rows if isinstance(a, dict) and a.get("id") == "signal"), None)
    tools = (sig or {}).get("tools") or []
    if code == 200 and sig and "term_send" in tools and "hiroshima_run" in tools:
        ok("signal tools live")
    else:
        bad(f"signal tools code={code} sig={sig}")
    code, verd = get("/v1/hiroshima/verdict")
    if code != 200:
        bad(f"verdict {code} {verd}")
        return
    if "unknown_dsts" not in verd or "ufw_hits" not in verd:
        bad("verdict mangler dest/ufw")
    else:
        ok(f"verdict dests={len(verd.get('unknown_dsts') or [])} ufw={len(verd.get('ufw_hits') or [])}")
    proto = verd.get("protocol") or {}
    ring = json.dumps(proto.get("ring") or [])
    if re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", ring):
        bad("IP i ring")
    else:
        ok("ring uten IP")
    watch = proto.get("watch") or {}
    wtxt = json.dumps(watch.get("flows") or [])
    if re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", wtxt):
        bad("IP i watch-flows")
    else:
        ok("watch-flows uten IP")
    for path in (
        "/v1/hiroshima/health",
        "/v1/hiroshima/watch",
        "/v1/hiroshima/env",
        "/v1/hiroshima/jobs",
        "/v1/workspace",
        "/v1/memory",
        "/v1/sessions",
        "/v1/config",
    ):
        c, body = get(path)
        if c == 200:
            ok(f"GET {path}")
        else:
            bad(f"GET {path} {c} {body}")
    for name in BUTTON_RUNS:
        c, body = post("/v1/hiroshima/run", {"name": name, "confirm": False})
        if body.get("error") and "confirm" in str(body.get("error")).lower():
            ok(f"run {name} uten confirm avvist")
        else:
            bad(f"run {name} uten confirm {c} {body}")


def test_verdict_tool() -> None:
    print("[test] hiroshima_verdict tool")
    from app.tools import call_tool

    r = call_tool("hiroshima_verdict", {}, allow_mutate=False)
    if r.get("error") == "ingen snapshot":
        ok("ingen snapshot")
        return
    if r.get("stamp") and r.get("verdict") and "unknown_dsts" in r and "ufw_hits" in r:
        ok(f"verdict tool {r.get('stamp')} {r.get('verdict')} dest={r.get('unknown_dsts')}")
        ids = [f.get("id") for f in (r.get("findings") or [])]
        print("       ids", ids[:12])
    else:
        bad(f"verdict tool {r}")


def test_dest_fixture() -> None:
    print("[test] dest-IP fixture")
    from hiroshima_act import pick_uplink_iface, unknown_dst_rows, ufw_hit_rows

    unk = ROOT / "scripts" / "tests" / "fixtures" / "h3-unknown"
    rows = unknown_dst_rows(unk)
    if rows and rows[0]["ip"] == "198.51.100.9":
        ok("unknown_dst_rows")
    else:
        bad(f"unknown_dst_rows {rows}")
    proton = "1.1.1.1 via 10.2.0.1 dev proton0 src 10.2.0.2"
    usb = "default via 10.0.0.1 dev usb0 proto dhcp"
    if pick_uplink_iface(proton, usb) == "proton0":
        ok("route get proton0 over usb0")
    else:
        bad("pick_uplink_iface")
    hits = ufw_hit_rows(ROOT / "scripts" / "testdata" / "cases" / "warn_ufw_hit")
    if hits and hits[0]["src"] == "198.51.100.9":
        ok("ufw_hit_rows")
    else:
        bad(f"ufw_hit_rows {hits}")


def test_helper_lag() -> None:
    print("[test] helper vs git (uplink-iface)")
    git = CFG.read_text(encoding="utf-8")
    if "kalived_uplink_iface" not in git or "route get 1.1.1.1" not in git:
        bad("git mangler kalived_uplink_iface")
        return
    ok("git har ip route get")
    if not HELPER_CFG.is_file():
        print("  SKIP helper ikke installert")
        return
    helper = HELPER_CFG.read_text(encoding="utf-8")
    if "kalived_uplink_iface" in helper:
        ok("helper har samme iface-fiks")
    else:
        ok("HELPER-STALE forventet: /usr/local sniffer usb0, git bruker route get")


def test_listeners() -> None:
    print("[test] lyttere — kalived vs Aegir")
    try:
        out = subprocess.check_output(["ss", "-ltnp"], text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError) as e:
        bad(f"ss {e}")
        return
    expect = {
        "5173": "kalived Vite",
        "8788": "kalived FastAPI",
        "5174": "Aegir (ikke kalived)",
        "7878": "Aegir semanticvoid-pty (ikke kalived)",
    }
    for port, label in expect.items():
        hit = any(f":{port}" in line and "LISTEN" in line for line in out.splitlines())
        print(f"       :{port} listen={hit}  {label}")
    if "127.0.0.1:8788" in out and "127.0.0.1:5173" in out:
        ok("kalived :5173/:8788 oppe")
    else:
        bad("kalived lyttere")


def test_ui_dump() -> None:
    print("[test] chromium dump-dom cockpit")
    chrom = "/usr/bin/chromium"
    if not Path(chrom).is_file():
        print("  SKIP ingen chromium")
        return
    try:
        proc = subprocess.run(
            [
                chrom,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--virtual-time-budget=8000",
                "--dump-dom",
                UI + "/",
            ],
            capture_output=True,
            text=True,
            timeout=25,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        bad(f"chromium {e}")
        return
    dom = proc.stdout or ""
    for s in ("Hiroshima", "agent får kjøre", "cli", "samtaler", "Arbeid", "Settings"):
        if s in dom:
            ok(f"UI {s}")
        else:
            bad(f"UI mangler {s}")
    if "Kjør scan" in dom:
        bad("Kjør scan synlig uten åpnet skuff")
    else:
        ok("scan-knapp skjult til skuff åpnes")


def test_signal_read_logs() -> None:
    print("[test] Signal leser siste stamp (samme som logg-analyse)")
    from app.tools import call_tool
    from hiroshima_act import unknown_dst_rows, ufw_hit_rows

    r = call_tool("hiroshima_verdict", {}, allow_mutate=False)
    stamp = r.get("stamp")
    if not stamp:
        bad("ingen stamp")
        return
    snap = ROOT / "logs" / "status" / str(stamp)
    dests = unknown_dst_rows(snap) if snap.is_dir() else []
    hits = ufw_hit_rows(snap) if snap.is_dir() else []
    print(f"       stamp {stamp} verdict={r.get('verdict')} dests={dests} ufw={hits}")
    if r.get("unknown_dsts") == dests or (not dests and not r.get("unknown_dsts")):
        ok("tool dests matcher snapshot")
    else:
        bad(f"tool dests {r.get('unknown_dsts')} vs {dests}")
    r2 = call_tool("term_send", {"line": "ip -4 route get 1.1.1.1", "where": "hiroshima"}, allow_mutate=True)
    if r2.get("open_hiroshima") and r2.get("pty_write"):
        ok("Signal kan male route-get i Hiroshima-xterm")
    else:
        bad(f"term_send route {r2}")


def main() -> int:
    print("== signal/term suite ==")
    test_button_map()
    test_allowlist()
    test_term_rails()
    test_mutate_gate()
    test_dest_fixture()
    test_helper_lag()
    test_listeners()
    test_http_cockpit()
    test_verdict_tool()
    test_signal_read_logs()
    test_ui_dump()
    print("==", "FAIL" if fail else "OK", f"n_fail={fail} ==")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
