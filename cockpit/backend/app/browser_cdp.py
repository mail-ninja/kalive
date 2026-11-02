"""Loopback Chromium over CDP. Ingen Playwright. Bind 127.0.0.1."""
from __future__ import annotations

import asyncio
import json
import os
import signal
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import websockets

DIR = Path(os.environ.get("KALIVED_UP_LOG", "/tmp/kalived-ui")) / "browser"
PID_PATH = DIR / "cdp.pid"
PORT_PATH = DIR / "cdp.port"
SHOT_PATH = DIR / "shot.png"
CHROMIUM = os.environ.get("KALIVED_CHROMIUM", "/usr/bin/chromium")
BLOCK_HOSTS = frozenset(
    {"0.0.0.0", "::", "169.254.169.254", "metadata.google.internal", "[::]"}
)
LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})
SKIP_ROLES = frozenset({"none", "InlineTextBox", "ignored"})


def check_url(raw: str, *, allow_external: bool = False) -> str | dict:
    s = (raw or "").strip()
    if not s or any(c.isspace() for c in s):
        return {"error": "tom url"}
    if "://" not in s:
        s = "http://" + s
    try:
        u = urlparse(s)
    except Exception:
        return {"error": "ugyldig url"}
    if u.scheme not in ("http", "https"):
        return {"error": "bare http/https"}
    if u.username or u.password:
        return {"error": "url med brukerinfo"}
    host = (u.hostname or "").lower()
    if not host or host in BLOCK_HOSTS:
        return {"error": "blokkert host"}
    if host not in LOOPBACK and not allow_external:
        return {"error": "ekstern url krever «agent får kjøre»", "host": host}
    if host == "0.0.0.0":
        return {"error": "0.0.0.0"}
    return s


def _ax_val(node: dict, key: str) -> str:
    v = node.get(key)
    if isinstance(v, dict):
        return str(v.get("value") or "")
    return str(v or "")


def flatten_ax(nodes: list, limit: int = 350) -> tuple[str, dict[str, int]]:
    by_id = {n.get("nodeId"): n for n in nodes if isinstance(n, dict)}
    refs: dict[str, int] = {}
    lines: list[str] = []
    nref = 0

    def walk(nid, depth: int) -> None:
        nonlocal nref
        if len(lines) >= limit:
            return
        n = by_id.get(nid)
        if not n:
            return
        role = _ax_val(n, "role")
        name = _ax_val(n, "name").replace("\n", " ").strip()[:80]
        ignored = bool(n.get("ignored"))
        backend = n.get("backendDOMNodeId")
        children = n.get("childIds") or []
        if ignored or role in SKIP_ROLES or (role == "generic" and not name):
            for c in children:
                walk(c, depth)
            return
        nref += 1
        ref = f"e{nref}"
        if backend:
            refs[ref] = int(backend)
        pad = "  " * min(depth, 12)
        bit = f"{pad}- {role or 'node'}"
        if name:
            bit += f' "{name}"'
        if backend:
            bit += f" [ref={ref}]"
        lines.append(bit)
        for c in children:
            walk(c, depth + 1)

    roots = [n.get("nodeId") for n in nodes if isinstance(n, dict) and not n.get("parentId")]
    if not roots and nodes:
        roots = [nodes[0].get("nodeId")]
    for r in roots:
        walk(r, 0)
    return "\n".join(lines), refs


def _free_port() -> int:
    for p in range(9222, 9300):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise RuntimeError("ingen ledig CDP-port 9222-9299")


def _http_json(url: str, timeout: float = 2.0):
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class Cdp:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._ws = None
        self._pending: dict[int, asyncio.Future] = {}
        self._nid = 0
        self._lock = threading.Lock()
        self._thread.start()
        fut = asyncio.run_coroutine_threadsafe(self._connect(), self._loop)
        fut.result(timeout=8)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _connect(self) -> None:
        self._ws = await websockets.connect(self.ws_url, max_size=8_000_000, open_timeout=6)
        self._loop.create_task(self._reader())

    async def _reader(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                mid = msg.get("id")
                if mid is not None and mid in self._pending:
                    self._pending[mid].set_result(msg)
        except Exception:
            pass

    def call(self, method: str, params: dict | None = None, timeout: float = 12.0) -> dict:
        with self._lock:
            self._nid += 1
            nid = self._nid
        payload = {"id": nid, "method": method}
        if params:
            payload["params"] = params
        fut: asyncio.Future = asyncio.run_coroutine_threadsafe(self._send(nid, payload), self._loop)
        msg = fut.result(timeout=timeout)
        if "error" in msg:
            err = msg["error"]
            text = err.get("message") if isinstance(err, dict) else str(err)
            raise RuntimeError(f"CDP {method}: {text}")
        return msg.get("result") or {}

    async def _send(self, nid: int, payload: dict) -> dict:
        assert self._ws is not None
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[nid] = fut
        await self._ws.send(json.dumps(payload))
        try:
            return await asyncio.wait_for(fut, timeout=11)
        finally:
            self._pending.pop(nid, None)

    def close(self) -> None:
        if self._ws is not None:
            asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop).result(timeout=2)
        self._loop.call_soon_threadsafe(self._loop.stop)


class Browser:
    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.port: int | None = None
        self.cdp: Cdp | None = None
        self.refs: dict[str, int] = {}
        self.url: str = ""
        self.title: str = ""

    def status(self) -> dict:
        live = bool(self.proc and _alive(self.proc.pid) and self.cdp)
        return {
            "ok": live,
            "pid": self.proc.pid if self.proc else None,
            "port": self.port,
            "url": self.url,
            "title": self.title,
            "bind": "127.0.0.1",
            "engine": "cdp",
        }

    def start(self) -> dict:
        if self.proc and _alive(self.proc.pid) and self.cdp:
            return self.status()
        self.close()
        DIR.mkdir(parents=True, exist_ok=True)
        port = _free_port()
        profile = DIR / "profile"
        profile.mkdir(parents=True, exist_ok=True)
        headed = os.environ.get("KALIVED_BROWSER_HEADED") == "1"
        cmd = [
            CHROMIUM,
            f"--remote-debugging-address=127.0.0.1",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-background-networking",
            "about:blank",
        ]
        if not headed:
            cmd.insert(1, "--headless=new")
        log = (DIR / "chromium.log").open("w", encoding="utf-8")
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except FileNotFoundError:
            return {"error": f"chromium mangler: {CHROMIUM}"}
        t0 = time.time()
        version = None
        while time.time() - t0 < 8:
            if proc.poll() is not None:
                tail = ""
                try:
                    tail = (DIR / "chromium.log").read_text(encoding="utf-8", errors="replace")[-400:]
                except OSError:
                    pass
                return {"error": "chromium døde", "log": tail}
            version = _http_json(f"http://127.0.0.1:{port}/json/version")
            if version:
                break
            time.sleep(0.15)
        if not version:
            proc.kill()
            return {"error": "CDP kom ikke opp på 127.0.0.1"}
        ws = version.get("webSocketDebuggerUrl")
        pages = _http_json(f"http://127.0.0.1:{port}/json/list") or []
        for p in pages:
            if p.get("type") == "page" and p.get("webSocketDebuggerUrl"):
                ws = p["webSocketDebuggerUrl"]
                break
        if not ws:
            proc.kill()
            return {"error": "ingen page-websocket"}
        # chromium sometimes echoes 0.0.0.0 in the ws URL — force loopback
        ws = ws.replace("0.0.0.0", "127.0.0.1")
        try:
            cdp = Cdp(ws)
        except Exception as e:
            proc.kill()
            return {"error": f"cdp connect: {e}"}
        for method in (
            "Page.enable",
            "DOM.enable",
            "Runtime.enable",
            "Accessibility.enable",
            "Network.enable",
            "Input.setIgnoreInputEvents",
        ):
            try:
                if method == "Input.setIgnoreInputEvents":
                    cdp.call(method, {"ignore": False})
                else:
                    cdp.call(method)
            except Exception:
                pass
        self.proc = proc
        self.port = port
        self.cdp = cdp
        PID_PATH.write_text(str(proc.pid), encoding="utf-8")
        PORT_PATH.write_text(str(port), encoding="utf-8")
        return self.status()

    def navigate(self, url: str, *, allow_external: bool = False) -> dict:
        checked = check_url(url, allow_external=allow_external)
        if isinstance(checked, dict):
            return checked
        if not self.cdp:
            st = self.start()
            if st.get("error"):
                return st
        assert self.cdp is not None
        self.cdp.call("Page.navigate", {"url": checked})
        t0 = time.time()
        ready = ""
        while time.time() - t0 < 10:
            try:
                ev = self.cdp.call(
                    "Runtime.evaluate",
                    {"expression": "document.readyState + '|' + location.href + '|' + document.title", "returnByValue": True},
                )
                val = str((ev.get("result") or {}).get("value") or "")
                parts = val.split("|", 2)
                ready = parts[0] if parts else ""
                if len(parts) > 1:
                    self.url = parts[1]
                if len(parts) > 2:
                    self.title = parts[2][:120]
                if ready == "complete":
                    time.sleep(0.7)
                    break
            except Exception:
                pass
            time.sleep(0.15)
        return {"ok": True, "url": self.url or checked, "title": self.title, "ready": ready}

    def snapshot(self) -> dict:
        if not self.cdp:
            return {"error": "browser nede — browser_open først"}
        tree = self.cdp.call("Accessibility.getFullAXTree")
        nodes = tree.get("nodes") or []
        text, refs = flatten_ax(nodes)
        self.refs = refs
        return {
            "ok": True,
            "url": self.url,
            "title": self.title,
            "tree": text,
            "n_refs": len(refs),
        }

    def _backend(self, ref: str) -> int | dict:
        key = str(ref or "").strip()
        if key not in self.refs:
            return {"error": f"ukjent ref {key} — ta browser_snapshot først"}
        return self.refs[key]

    def click(self, ref: str) -> dict:
        if not self.cdp:
            return {"error": "browser nede"}
        backend = self._backend(ref)
        if isinstance(backend, dict):
            return backend
        try:
            self.cdp.call("DOM.scrollIntoViewIfNeeded", {"backendNodeId": backend})
        except Exception:
            pass
        box = self.cdp.call("DOM.getContentQuads", {"backendNodeId": backend})
        quads = box.get("quads") or []
        if not quads:
            return {"error": f"ingen boks for {ref}"}
        q = quads[0]
        xs = q[0::2]
        ys = q[1::2]
        x = sum(xs) / len(xs)
        y = sum(ys) / len(ys)
        for typ in ("mousePressed", "mouseReleased"):
            self.cdp.call(
                "Input.dispatchMouseEvent",
                {"type": typ, "x": x, "y": y, "button": "left", "clickCount": 1},
            )
        time.sleep(0.2)
        return {"ok": True, "ref": ref, "x": round(x, 1), "y": round(y, 1)}

    def type_text(self, ref: str, text: str, submit: bool = False) -> dict:
        if not self.cdp:
            return {"error": "browser nede"}
        clk = self.click(ref)
        if clk.get("error"):
            return clk
        self.cdp.call("Input.insertText", {"text": str(text)[:4000]})
        if submit:
            self.cdp.call(
                "Input.dispatchKeyEvent",
                {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13},
            )
            self.cdp.call(
                "Input.dispatchKeyEvent",
                {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13},
            )
        return {"ok": True, "ref": ref, "n": len(str(text)), "submit": bool(submit)}

    def screenshot(self) -> dict:
        if not self.cdp:
            return {"error": "browser nede"}
        raw = self.cdp.call("Page.captureScreenshot", {"format": "png"})
        b64 = raw.get("data") or ""
        if not b64:
            return {"error": "tom screenshot"}
        import base64

        DIR.mkdir(parents=True, exist_ok=True)
        data = base64.b64decode(b64)
        SHOT_PATH.write_bytes(data)
        return {"ok": True, "path": str(SHOT_PATH), "bytes": len(data), "url": self.url}

    def close(self) -> dict:
        if self.cdp:
            try:
                self.cdp.close()
            except Exception:
                pass
            self.cdp = None
        if self.proc and _alive(self.proc.pid):
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
            except OSError:
                try:
                    self.proc.terminate()
                except OSError:
                    pass
            try:
                self.proc.wait(timeout=2)
            except Exception:
                try:
                    os.killpg(self.proc.pid, signal.SIGKILL)
                except OSError:
                    pass
        self.proc = None
        self.refs = {}
        self.url = ""
        self.title = ""
        for p in (PID_PATH, PORT_PATH):
            try:
                p.unlink()
            except OSError:
                pass
        return {"ok": True, "closed": True}


_browser = Browser()


def instance() -> Browser:
    return _browser
