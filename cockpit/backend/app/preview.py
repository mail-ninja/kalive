"""Loopback preview: one child bound to 127.0.0.1, never 0.0.0.0."""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from . import workspace as w

RESERVED_PORTS = frozenset({22, 53, 80, 443, 5173, 6333, 6379, 8787, 8788, 9100})
STATE_PATH = Path(os.environ.get("KALIVED_UP_LOG", "/tmp/kalived-ui")) / "preview.json"
LOG_PATH = STATE_PATH.with_name("preview.log")
DEFAULT_PORT = 8765

router = APIRouter(prefix="/v1/preview", tags=["preview"])


def parse_loopback_url(raw: str) -> str | None:
    s = (raw or "").strip()
    if not s or any(c.isspace() for c in s):
        return None
    if "://" not in s:
        if s.startswith(("127.0.0.1", "localhost", "[::1]")):
            s = "http://" + s
        else:
            return None
    try:
        u = urlparse(s)
    except Exception:
        return None
    if u.scheme not in ("http", "https"):
        return None
    if u.username or u.password:
        return None
    host = (u.hostname or "").lower()
    if host not in ("127.0.0.1", "localhost", "::1"):
        return None
    try:
        port = u.port or (443 if u.scheme == "https" else 80)
    except ValueError:
        return None
    if port < 1 or port > 65535 or port in RESERVED_PORTS:
        return None
    path = u.path or "/"
    query = ("?" + u.query) if u.query else ""
    host_out = "[::1]" if host == "::1" else "127.0.0.1"
    return f"{u.scheme}://{host_out}:{port}{path}{query}"


def _state() -> dict | None:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _save(st: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _kill(pid: int) -> None:
    if pid <= 0:
        return
    try:
        os.killpg(pid, 15)
    except OSError:
        try:
            os.kill(pid, 15)
        except OSError:
            return
    t0 = time.time()
    while time.time() - t0 < 2 and _alive(pid):
        time.sleep(0.1)
    if _alive(pid):
        try:
            os.killpg(pid, 9)
        except OSError:
            try:
                os.kill(pid, 9)
            except OSError:
                pass


def _port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def _pick_port(preferred: int | None) -> int:
    want = int(preferred or DEFAULT_PORT)
    for p in [want] + list(range(DEFAULT_PORT, DEFAULT_PORT + 40)):
        if p in RESERVED_PORTS or p < 1024:
            continue
        if _port_open(p):
            continue
        return p
    raise RuntimeError("ingen ledig loopback-port")


def status() -> dict:
    st = _state() or {}
    pid = int(st.get("pid") or 0)
    port = int(st.get("port") or 0)
    url = parse_loopback_url(str(st.get("url") or "")) or ""
    live = _alive(pid)
    listening = bool(port and _port_open(port))
    return {
        "pid": pid or None,
        "port": port or None,
        "url": url,
        "alive": live,
        "listening": listening,
        "cmd": st.get("cmd") or [],
        "cwd": st.get("cwd") or "",
    }


def stop() -> dict:
    st = _state() or {}
    pid = int(st.get("pid") or 0)
    if pid:
        _kill(pid)
    if STATE_PATH.exists():
        STATE_PATH.unlink()
    return {"stopped": True, "pid": pid or None}


def start(dir: str = "", port: int | None = None, line: str | None = None, path: str = "") -> dict:
    stop()
    rel = (dir or "").strip().lstrip("/")
    try:
        cwd = w.safe(rel) if rel else w.root()
    except ValueError as e:
        return {"error": str(e)}
    if not cwd.is_dir():
        return {"error": "dir finnes ikke: " + (rel or ".")}
    if line and str(line).strip():
        raw = str(line).strip()
        blob = raw.lower()
        if "0.0.0.0" in blob or "--host 0" in blob:
            return {"error": "bind bare 127.0.0.1 — ikke 0.0.0.0"}
        if w._DENY.search(raw):
            return {"error": "nekta: sudo/git push/destruktiv"}
        cmd = ["/bin/bash", "-c", raw]
        parsed_port = None
        m = re.search(r":(\d{2,5})\b", raw) or re.search(r"--port\s+(\d{2,5})\b", raw)
        if m:
            parsed_port = int(m.group(1))
        p = int(port or parsed_port or DEFAULT_PORT)
        if p in RESERVED_PORTS or p < 1024:
            return {"error": f"port {p} er reservert"}
        if _port_open(p):
            return {"error": f"port {p} opptatt"}
    else:
        try:
            p = _pick_port(port)
        except RuntimeError as e:
            return {"error": str(e)}
        cmd = [
            "python3",
            "-m",
            "http.server",
            str(p),
            "--bind",
            "127.0.0.1",
            "--directory",
            str(cwd),
        ]
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logf = open(LOG_PATH, "ab", buffering=0)
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=logf,
            stderr=logf,
            start_new_session=True,
            env={**os.environ, "NO_COLOR": "1", "PYTHONUNBUFFERED": "1"},
        )
    except FileNotFoundError:
        logf.close()
        return {"error": "ikke funnet: " + cmd[0]}
    logf.close()
    t0 = time.time()
    listening = False
    while time.time() - t0 < 12:
        if proc.poll() is not None:
            tail = LOG_PATH.read_text(encoding="utf-8", errors="replace")[-1500:] if LOG_PATH.exists() else ""
            return {"error": "prosessen døde", "exit_code": proc.returncode, "log_tail": tail, "argv": cmd}
        if _port_open(p):
            listening = True
            break
        time.sleep(0.15)
    suffix = path.strip()
    if suffix and not suffix.startswith("/"):
        suffix = "/" + suffix
    url = f"http://127.0.0.1:{p}{suffix or '/'}"
    canon = parse_loopback_url(url) or url
    st = {
        "pid": proc.pid,
        "port": p,
        "url": canon,
        "cmd": cmd,
        "cwd": str(cwd),
        "started": time.time(),
    }
    _save(st)
    out = {
        "pid": proc.pid,
        "port": p,
        "url": canon,
        "preview": canon,
        "listening": listening,
        "argv": cmd,
        "cwd": str(cwd),
        "mode": "iframe",
    }
    if not listening:
        out["note"] = "startet, venter på port — preview probe-r"
    return out


def probe(url: str) -> dict:
    canon = parse_loopback_url(url)
    if not canon:
        return {"ok": False, "error": "bare http(s)://127.0.0.1|localhost|::1, reserverte porter nektet", "url": url}
    try:
        r = httpx.get(canon, timeout=1.6, follow_redirects=False)
        loc = r.headers.get("location") or ""
        if loc:
            next_u = parse_loopback_url(loc) or parse_loopback_url(urljoin(canon, loc))
            if not next_u:
                return {"ok": False, "error": "redirect ut av loopback", "status": r.status_code, "url": canon}
        return {"ok": 200 <= r.status_code < 500, "status": r.status_code, "url": canon}
    except httpx.HTTPError as e:
        return {"ok": False, "error": type(e).__name__, "url": canon}


class ServeIn(BaseModel):
    action: str | None = None
    dir: str | None = None
    port: int | None = None
    line: str | None = None
    path: str | None = None
    url: str | None = None


@router.get("/probe")
def probe_http(url: str = ""):
    return probe(url)


@router.get("/status")
def status_http():
    return status()


@router.post("/serve")
def serve_http(body: ServeIn | None = None):
    b = body or ServeIn()
    action = (b.action or "start").strip().lower()
    if action == "stop":
        return stop()
    if action == "status":
        return status()
    return start(dir=b.dir or "", port=b.port, line=b.line, path=b.path or "")


@router.post("/stop")
def stop_http():
    return stop()
