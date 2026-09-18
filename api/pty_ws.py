"""Loopback PTY over WebSocket. Shell as KALIVED_OWNER, never keep root."""
from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import pwd
import select
import struct
import termios
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_SESSIONS = 2
_live = 0


def _accept_key(key: str) -> str:
    digest = hashlib.sha1((key + WS_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def _recv_exact(sock, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("closed")
        buf += chunk
    return buf


def ws_read(sock) -> tuple[int, bytes]:
    hdr = _recv_exact(sock, 2)
    opcode = hdr[0] & 0x0F
    masked = bool(hdr[1] & 0x80)
    length = hdr[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", _recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recv_exact(sock, 8))[0]
    if length > 1_000_000:
        raise ValueError("frame too large")
    mask = _recv_exact(sock, 4) if masked else b""
    payload = _recv_exact(sock, length) if length else b""
    if masked:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return opcode, payload


def ws_write(sock, payload: bytes, opcode: int = 2) -> None:
    header = bytearray()
    header.append(0x80 | opcode)
    n = len(payload)
    if n < 126:
        header.append(n)
    elif n < 65536:
        header.append(126)
        header.extend(struct.pack("!H", n))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", n))
    sock.sendall(bytes(header) + payload)


def _winsize(fd: int, rows: int, cols: int) -> None:
    rows = max(1, min(int(rows), 200))
    cols = max(2, min(int(cols), 400))
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def _spawn(owner: str, home: str, cols: int, rows: int) -> tuple[int, int]:
    # Same uid as the API process. `sudo kalived-ctl api` → root PTY (host, not sandbox).
    pid, master = os.forkpty()
    if pid == 0:
        try:
            os.environ["TERM"] = "xterm-256color"
            os.environ["COLORTERM"] = "truecolor"
            if os.geteuid() == 0:
                os.environ["USER"] = "root"
                os.environ["LOGNAME"] = "root"
                os.environ["HOME"] = "/root"
                try:
                    os.chdir("/root")
                except OSError:
                    os.chdir("/")
                shell = "/bin/zsh" if os.path.isfile("/bin/zsh") else "/bin/bash"
            else:
                try:
                    pw = pwd.getpwnam(owner)
                    shell = pw.pw_shell if pw.pw_shell and os.path.isfile(pw.pw_shell) else "/bin/zsh"
                    os.chdir(pw.pw_dir if os.path.isdir(pw.pw_dir) else home)
                except KeyError:
                    shell = "/bin/zsh"
                    os.chdir(home if os.path.isdir(home) else "/")
            if not os.path.isfile(shell):
                shell = "/bin/bash"
            os.execv(shell, [shell, "-l"])
        except Exception:
            os._exit(127)
    _winsize(master, rows, cols)
    fl = fcntl.fcntl(master, fcntl.F_GETFL)
    fcntl.fcntl(master, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    return pid, master


def handle_term_ws(handler: BaseHTTPRequestHandler, owner: str, home: str) -> None:
    global _live
    peer = handler.client_address[0]
    if peer not in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
        handler._send(403, {"error": "terminal only on loopback"})
        return
    key = handler.headers.get("Sec-WebSocket-Key")
    if handler.headers.get("Upgrade", "").lower() != "websocket" or not key:
        handler._send(400, {"error": "websocket upgrade required"})
        return
    if _live >= MAX_SESSIONS:
        handler._send(429, {"error": "too many terminals"})
        return
    handler.send_response(101, "Switching Protocols")
    handler.send_header("Upgrade", "websocket")
    handler.send_header("Connection", "Upgrade")
    handler.send_header("Sec-WebSocket-Accept", _accept_key(key))
    handler.end_headers()
    handler.wfile.flush()
    sock = handler.connection
    sock.settimeout(None)
    pid = master = None
    _live += 1
    try:
        pid, master = _spawn(owner, home, 80, 24)
        while True:
            r, _, _ = select.select([sock, master], [], [], 120.0)
            if not r:
                continue
            if sock in r:
                opcode, payload = ws_read(sock)
                if opcode in (8,):
                    break
                if opcode == 9:
                    ws_write(sock, payload, 10)
                    continue
                if opcode in (1, 2) and payload:
                    if payload.startswith(b'{"type":"resize"'):
                        try:
                            msg = json.loads(payload.decode("utf-8"))
                            _winsize(master, int(msg.get("rows") or 24), int(msg.get("cols") or 80))
                        except (ValueError, json.JSONDecodeError, OSError):
                            pass
                    else:
                        os.write(master, payload)
            if master in r:
                try:
                    data = os.read(master, 8192)
                except BlockingIOError:
                    data = b""
                if not data:
                    break
                ws_write(sock, data, 2)
    except (ConnectionError, OSError, BrokenPipeError, ValueError):
        pass
    finally:
        _live = max(0, _live - 1)
        if master is not None:
            try:
                os.close(master)
            except OSError:
                pass
        if pid:
            try:
                os.kill(pid, 15)
            except OSError:
                pass
            try:
                os.waitpid(pid, os.WNOHANG)
            except OSError:
                pass
        try:
            ws_write(sock, b"", 8)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass
