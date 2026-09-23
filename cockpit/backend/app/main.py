"""kalived cockpit FastAPI — agents/tools. Security API stays on :8787."""
from __future__ import annotations

import os

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from pathlib import Path

from .agents import get_agent, list_public
from .catalog import fetch_models, public as catalog_public
from .desk import router as desk_router
from .workspace import router as workspace_router
from .hiroshima import ensure_watch, router as hiroshima_router
from .memory_routes import router as memory_router
from .secrets_store import put as secrets_put
from .secrets_store import status as secrets_status
from .term import handle_term
from .tools import list_tools
from .ws import handle_socket

BIND = os.environ.get("COCKPIT_BIND", "127.0.0.1")
PORT = int(os.environ.get("COCKPIT_PORT", "8788"))
TOKEN = os.environ.get("COCKPIT_TOKEN") or os.environ.get("KALIVED_API_TOKEN") or ""


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    ensure_watch()
    yield


app = FastAPI(title="kalived cockpit", version="0.1.0", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(memory_router)
app.include_router(hiroshima_router)
app.include_router(desk_router)
app.include_router(workspace_router)


def _token_ok(got: str) -> bool:
    if not TOKEN:
        return True  # heimsted: empty token = open on loopback only
    return got == TOKEN


@app.get("/v1/health")
def health():
    return {
        "ok": True,
        "service": "cockpit",
        "ws": "/v1/ws",
        "term": "/v1/term",
        "memory": "/v1/memory",
        "hiroshima": "/v1/hiroshima",
        "workspace": "/v1/workspace",
    }


@app.get("/v1/tools")
def tools():
    return {"tools": list_tools()}


@app.get("/v1/agents")
def agents():
    return {
        "agents": list_public(),
        "providers": catalog_public(live=True),
        "file": str(Path.home() / ".config/kalived/agents.json"),
    }


@app.get("/v1/providers/{pid}/models")
def provider_models(pid: str):
    return fetch_models(pid)


@app.get("/v1/agents/{agent_id}")
def agent_one(agent_id: str):
    a = get_agent(agent_id)
    if not a:
        raise HTTPException(status_code=404, detail="unknown agent")
    return a.model_dump()


class SecretsBody(BaseModel):
    """Omit a key to leave it. Empty string clears it. Never echoed back."""

    keys: dict[str, str | None] = Field(default_factory=dict)


@app.get("/v1/secrets")
def get_secrets():
    return secrets_status()


@app.put("/v1/secrets")
def put_secrets(body: SecretsBody):
    try:
        return secrets_put(body.keys)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"kunne ikke skrive env: {e}") from e


@app.websocket("/v1/term")
async def term(websocket: WebSocket, token: str = Query(default="")):
    if websocket.client and websocket.client.host not in ("127.0.0.1", "::1"):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    hdr = websocket.headers.get("authorization") or ""
    got = token
    if hdr.lower().startswith("bearer "):
        got = hdr[7:].strip()
    if not _token_ok(got):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    await handle_term(websocket)


@app.websocket("/v1/ws")
async def ws(websocket: WebSocket, token: str = Query(default="")):
    if websocket.client and websocket.client.host not in ("127.0.0.1", "::1"):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    hdr = websocket.headers.get("authorization") or ""
    got = token
    if hdr.lower().startswith("bearer "):
        got = hdr[7:].strip()
    if not _token_ok(got):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    await handle_socket(websocket)


@app.get("/")
def root():
    return JSONResponse(
        {
            "service": "kalived-cockpit",
            "plan": "cockpit/PLAN.md",
            "health": "/v1/health",
            "ws": "/v1/ws",
            "hiroshima": "/v1/hiroshima",
            "kernel_8787": "urørt",
        }
    )
