"""WebSocket multiplex — in from day 1. See cockpit/PLAN.md."""
from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from .tools import call_tool, list_tools


def _msg(ch: str, typ: str, payload: Any, id_: str | None = None) -> dict:
    return {"v": 1, "ch": ch, "id": id_ or str(uuid.uuid4()), "type": typ, "payload": payload}


async def handle_socket(ws: WebSocket) -> None:
    await ws.accept()
    await ws.send_json(_msg("log", "line", {"text": "cockpit ws up"}))
    await ws.send_json(_msg("tools", "list", {"tools": list_tools()}))
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json(_msg("log", "line", {"text": "bad json"}))
                continue
            ch = msg.get("ch") or "log"
            typ = msg.get("type") or ""
            mid = msg.get("id") or str(uuid.uuid4())
            payload = msg.get("payload") or {}
            if ch == "chat" and typ == "user":
                text = str(payload.get("text") or "")
                # Stub stream so the client wires token frames now, not later.
                for i, chunk in enumerate(("ok. ", "ws ", "lever. ", f"du sa: {text}")):
                    await ws.send_json(_msg("chat", "token", {"text": chunk}, mid))
                await ws.send_json(_msg("chat", "done", {}, mid))
            elif ch == "tools" and typ == "call":
                name = str(payload.get("name") or "")
                args = payload.get("args") or {}
                result = call_tool(name, args if isinstance(args, dict) else {})
                await ws.send_json(_msg("tools", "result", result, mid))
            elif ch == "editor" and typ == "open":
                await ws.send_json(
                    _msg(
                        "editor",
                        "open",
                        {
                            "path": payload.get("path") or "untitled.md",
                            "language": "markdown",
                            "text": "# cockpit\nWS + Monaco er wired.\n",
                        },
                        mid,
                    )
                )
            elif ch == "hiroshima" and typ == "open":
                await ws.send_json(_msg("hiroshima", "open", {"src": "http://127.0.0.1:8787/"}, mid))
            else:
                await ws.send_json(_msg("log", "line", {"text": f"unhandled {ch}/{typ}"}, mid))
    except WebSocketDisconnect:
        return
