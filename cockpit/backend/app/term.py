"""Cockpit PTY — local forkpty only. 8787 is left alone."""
from __future__ import annotations

import asyncio
import json
import os
import pwd
import select
import signal
import struct
import termios
import fcntl
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect


def _winsize(fd: int, rows: int, cols: int) -> None:
    rows = max(1, min(int(rows), 200))
    cols = max(2, min(int(cols), 400))
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def _spawn() -> tuple[int, int]:
    pid, master = os.forkpty()
    if pid == 0:
        try:
            os.environ["TERM"] = "xterm-256color"
            os.environ["COLORTERM"] = "truecolor"
            home = str(Path.home())
            os.chdir(home if os.path.isdir(home) else "/")
            try:
                shell = pwd.getpwuid(os.getuid()).pw_shell or "/bin/zsh"
            except KeyError:
                shell = "/bin/zsh"
            if not os.path.isfile(shell):
                shell = "/bin/bash"
            os.execv(shell, [shell, "-l"])
        except Exception:
            os._exit(127)
    fl = fcntl.fcntl(master, fcntl.F_GETFL)
    fcntl.fcntl(master, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    _winsize(master, 24, 80)
    return pid, master


def _read_pty(fd: int) -> bytes:
    r, _, _ = select.select([fd], [], [], 0.4)
    if fd not in r:
        return b""
    try:
        return os.read(fd, 8192)
    except OSError:
        return b""


async def handle_term(ws: WebSocket) -> None:
    await ws.accept()
    uid = os.geteuid()
    try:
        name = pwd.getpwuid(uid).pw_name
    except KeyError:
        name = str(uid)
    await ws.send_text(f"\r\n[cockpit PTY uid={uid} {name} — sudo-passord her, ikke i chat]\r\n")
    pid, master = _spawn()
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    async def from_pty() -> None:
        try:
            while not stop.is_set():
                data = await loop.run_in_executor(None, _read_pty, master)
                if data:
                    await ws.send_bytes(data)
        except (WebSocketDisconnect, RuntimeError, OSError):
            pass
        finally:
            stop.set()

    async def from_ws() -> None:
        try:
            while not stop.is_set():
                msg = await ws.receive()
                if msg["type"] == "websocket.disconnect":
                    break
                raw = msg.get("bytes")
                if raw is None and msg.get("text"):
                    raw = msg["text"].encode("utf-8")
                if not raw:
                    continue
                if raw.startswith(b'{"type":"resize"'):
                    try:
                        spec = json.loads(raw.decode("utf-8"))
                        _winsize(master, int(spec.get("rows") or 24), int(spec.get("cols") or 80))
                    except (ValueError, json.JSONDecodeError, OSError):
                        pass
                    continue
                os.write(master, raw)
        except (WebSocketDisconnect, RuntimeError, OSError):
            pass
        finally:
            stop.set()

    try:
        await asyncio.gather(from_pty(), from_ws())
    finally:
        stop.set()
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        try:
            os.close(master)
        except OSError:
            pass
        try:
            os.waitpid(pid, os.WNOHANG)
        except OSError:
            pass
