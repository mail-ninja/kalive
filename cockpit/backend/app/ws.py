"""WebSocket multiplex — in from day 1. See cockpit/PLAN.md."""
from __future__ import annotations

import asyncio
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
        _msg("agents", "list", {"agents": list_public(), "providers": catalog_public(), "selected": "build"})
    )
    stop = asyncio.Event()
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
            elif ch == "run" and typ == "stop":
                stop.set()
                await ws.send_json(_msg("run", "stopped", {"keep": "logs+diff"}, mid))
            elif ch == "chat" and typ == "user":
                text = str(payload.get("text") or "")
                aid = str(payload.get("agent") or "build")
                ag = get_agent(aid) or get_agent("build") or get_agent("dummy")
                assert ag is not None
                memory_bind(ag.id)
                allow = bool(payload.get("allow_mutate"))
                stop.clear()
                excerpt: list[str] = []
                tools_used: list[str] = []
                try:
                    async for ev in run_turn(
                        ag,
                        text,
                        provider=str(payload.get("provider") or "") or None,
                        model=str(payload.get("model") or "") or None,
                        allow_mutate=allow,
                        use_tools=True,
                        cancel=stop,
                    ):
                        kind = ev.get("type")
                        if kind == "token":
                            excerpt.append(str(ev.get("text") or ""))
                            await ws.send_json(_msg("chat", "token", {"text": ev.get("text") or "", "agent": ag.id}, mid))
                        elif kind == "tool":
                            tools_used.append(str(ev.get("name") or ""))
                            await ws.send_json(
                                _msg("tools", "call", {"name": ev.get("name"), "args": ev.get("args"), "round": ev.get("round"), "agent": ag.id}, mid)
                            )
                        elif kind == "tool_out":
                            await ws.send_json(
                                _msg(
                                    "tools",
                                    "out",
                                    {
                                        "text": ev.get("text") or "",
                                        "stream": ev.get("stream") or "stdout",
                                        "name": ev.get("name"),
                                        "round": ev.get("round"),
                                    },
                                    mid,
                                )
                            )
                        elif kind == "tool_result":
                            name = str(ev.get("name") or "")
                            result = ev.get("result") if isinstance(ev.get("result"), dict) else {}
                            try:
                                remember_engram(
                                    ag.id,
                                    "tool",
                                    {
                                        "name": name,
                                        "path": result.get("path") if isinstance(result, dict) else None,
                                        "text": json.dumps(result, ensure_ascii=False)[:1500],
                                        "user": text[:400],
                                    },
                                )
                            except Exception:
                                pass
                            await ws.send_json(
                                _msg("tools", "result", {"name": ev.get("name"), "result": ev.get("result"), "round": ev.get("round"), "agent": ag.id}, mid)
                            )
                        elif kind == "log":
                            await ws.send_json(_msg("log", "line", {"text": ev.get("text") or "", "agent": ag.id}, mid))
                        elif kind == "stopped":
                            await ws.send_json(_msg("run", "stopped", {"text": ev.get("text") or ""}, mid))
                    if not stop.is_set():
                        await ws.send_json(_msg("chat", "done", {"agent": ag.id}, mid))
                    remember_engram(
                        ag.id,
                        "chat",
                        {
                            "user": text[:2000],
                            "assistant": "".join(excerpt)[:3000],
                            "tools": tools_used[:20],
                            "provider": str(payload.get("provider") or ag.provider),
                            "model": str(payload.get("model") or ag.model),
                            "allow_mutate": allow,
                        },
                    )
                except WebSocketDisconnect:
                    try:
                        remember_engram(
                            ag.id,
                            "chat",
                            {
                                "user": text[:2000],
                                "assistant": "".join(excerpt)[:3000],
                                "tools": tools_used[:20],
                                "note": "ws-disconnect mid-turn",
                            },
                        )
                    except Exception:
                        pass
                    return
                except Exception as e:
                    try:
                        remember_engram(
                            ag.id,
                            "chat",
                            {
                                "user": text[:2000],
                                "assistant": "".join(excerpt)[:3000],
                                "tools": tools_used[:20],
                                "error": str(e)[:300],
                            },
                        )
                    except Exception:
                        pass
                    try:
                        await ws.send_json(_msg("chat", "error", {"error": str(e), "agent": ag.id}, mid))
                    except Exception:
                        return
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
