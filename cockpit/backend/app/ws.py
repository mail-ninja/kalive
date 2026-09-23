"""WebSocket multiplex — in from day 1. See cockpit/PLAN.md."""
from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from .agents import get_agent, list_public
from .catalog import public as catalog_public
from .llm import run_turn
from .memory import ensure as memory_bind
from .memory import remember_engram
from .tools import call_tool, list_tools


def _msg(ch: str, typ: str, payload: Any, id_: str | None = None) -> dict:
    return {"v": 1, "ch": ch, "id": id_ or str(uuid.uuid4()), "type": typ, "payload": payload}


async def handle_socket(ws: WebSocket) -> None:
    await ws.accept()
    await ws.send_json(_msg("log", "line", {"text": "cockpit ws up"}))
    await ws.send_json(_msg("tools", "list", {"tools": list_tools()}))
    await ws.send_json(
        _msg("agents", "list", {"agents": list_public(), "providers": catalog_public(), "selected": "crew"})
    )
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
            if ch == "agents" and typ == "select":
                aid = str(payload.get("id") or "")
                ag = get_agent(aid)
                if not ag:
                    await ws.send_json(_msg("agents", "error", {"error": "unknown agent"}, mid))
                    continue
                memory_bind(ag.id)
                await ws.send_json(_msg("agents", "selected", ag.model_dump(), mid))
            elif ch == "chat" and typ == "user":
                text = str(payload.get("text") or "")
                aid = str(payload.get("agent") or "dummy")
                ag = get_agent(aid) or get_agent("dummy")
                assert ag is not None
                memory_bind(ag.id)
                allow = bool(payload.get("allow_mutate"))
                try:
                    async for ev in run_turn(
                        ag,
                        text,
                        provider=str(payload.get("provider") or "") or None,
                        model=str(payload.get("model") or "") or None,
                        allow_mutate=allow,
                        use_tools=True,
                    ):
                        kind = ev.get("type")
                        if kind == "token":
                            await ws.send_json(_msg("chat", "token", {"text": ev.get("text") or "", "agent": ag.id}, mid))
                        elif kind == "tool":
                            await ws.send_json(
                                _msg("tools", "call", {"name": ev.get("name"), "args": ev.get("args"), "round": ev.get("round"), "agent": ag.id}, mid)
                            )
                        elif kind == "tool_result":
                            await ws.send_json(
                                _msg("tools", "result", {"name": ev.get("name"), "result": ev.get("result"), "round": ev.get("round"), "agent": ag.id}, mid)
                            )
                        elif kind == "log":
                            await ws.send_json(_msg("log", "line", {"text": ev.get("text") or "", "agent": ag.id}, mid))
                    await ws.send_json(_msg("chat", "done", {"agent": ag.id}, mid))
                    remember_engram(
                        ag.id,
                        "chat",
                        {
                            "user": text[:2000],
                            "provider": str(payload.get("provider") or ag.provider),
                            "model": str(payload.get("model") or ag.model),
                            "allow_mutate": allow,
                        },
                    )
                except Exception as e:
                    await ws.send_json(_msg("chat", "error", {"error": str(e), "agent": ag.id}, mid))
            elif ch == "tools" and typ == "call":
                name = str(payload.get("name") or "")
                args = payload.get("args") or {}
                allow = bool(payload.get("allow_mutate"))
                result = call_tool(name, args if isinstance(args, dict) else {}, allow_mutate=allow)
                await ws.send_json(_msg("tools", "result", result, mid))
            elif ch == "editor" and typ == "save":
                from . import desk

                snap = desk.apply(
                    {
                        "path": str(payload.get("path") or "untitled.md"),
                        "language": str(payload.get("language") or "markdown"),
                        "text": str(payload.get("text") or ""),
                    }
                )
                await ws.send_json(_msg("editor", "saved", {"path": snap["path"], "n": len(snap["text"])}, mid))
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
                await ws.send_json(_msg("hiroshima", "open", {"src": "/v1/hiroshima"}, mid))
            elif typ == "ping":
                await ws.send_json(_msg("log", "pong", {"t": payload.get("t")}, mid))
            else:
                await ws.send_json(_msg("log", "line", {"text": f"unhandled {ch}/{typ}"}, mid))
    except WebSocketDisconnect:
        return
