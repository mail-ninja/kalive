"""MCP JSON-RPC over loopback HTTP. Samme tools som Signal/build."""
from __future__ import annotations

import json

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from .tools import TOOLS, call_tool, list_tools

PROTOCOL = "2024-11-05"
BROWSER_AND_SOC = (
    "ping",
    "browser_status",
    "browser_open",
    "browser_navigate",
    "browser_snapshot",
    "browser_click",
    "browser_type",
    "browser_screenshot",
    "browser_close",
    "hiroshima_verdict",
    "hiroshima_scan",
    "hiroshima_run",
    "hiroshima_job",
    "term_send",
)

router = APIRouter(prefix="/v1/mcp", tags=["mcp"])


class RpcIn(BaseModel):
    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str = ""
    params: dict = Field(default_factory=dict)


def _ok(rid, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _err(rid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def handle_rpc(method: str, params: dict | None, *, allow_mutate: bool, rid=1) -> dict:
    params = params or {}
    if method in ("initialize", "notifications/initialized"):
        return _ok(
            rid,
            {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "kalived", "version": "0.1.0"},
            },
        )
    if method == "tools/list":
        tools = []
        for spec in list_tools():
            if spec["name"] not in BROWSER_AND_SOC:
                continue
            tools.append(
                {
                    "name": spec["name"],
                    "description": spec.get("description") or "",
                    "inputSchema": spec.get("parameters") or {"type": "object", "properties": {}},
                }
            )
        return _ok(rid, {"tools": tools})
    if method == "tools/call":
        name = str(params.get("name") or "")
        if name not in BROWSER_AND_SOC or name not in TOOLS:
            return _err(rid, -32601, f"ukjent tool {name}")
        args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        result = call_tool(name, args, allow_mutate=allow_mutate, allow=list(BROWSER_AND_SOC))
        is_err = bool(result.get("error"))
        text = json.dumps(result, ensure_ascii=False)[:12000]
        return _ok(
            rid,
            {
                "content": [{"type": "text", "text": text}],
                "isError": is_err,
            },
        )
    if method == "ping":
        return _ok(rid, {})
    return _err(rid, -32601, f"ukjent method {method}")


@router.post("/")
def mcp_post(body: RpcIn, x_kalived_mutate: str | None = Header(default=None)):
    allow = (x_kalived_mutate or "").strip() in ("1", "true", "yes")
    return handle_rpc(body.method, body.params, allow_mutate=allow, rid=body.id)


@router.get("/")
def mcp_info():
    return {
        "ok": True,
        "protocol": PROTOCOL,
        "transport": "jsonrpc-http",
        "bind": "127.0.0.1",
        "tools": list(BROWSER_AND_SOC),
        "note": "POST JSON-RPC. Muterende kall: header X-Kalived-Mutate: 1 (samme som hake).",
        "stdio": "python -m app.mcp_stdio",
        "engine": "cdp",
    }
