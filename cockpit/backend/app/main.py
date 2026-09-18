"""kalived cockpit FastAPI — agents/tools. Security API stays on :8787."""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .secrets_store import put as secrets_put
from .secrets_store import status as secrets_status
from .tools import list_tools
from .ws import handle_socket

BIND = os.environ.get("COCKPIT_BIND", "127.0.0.1")
PORT = int(os.environ.get("COCKPIT_PORT", "8788"))
TOKEN = os.environ.get("COCKPIT_TOKEN") or os.environ.get("KALIVED_API_TOKEN") or ""

app = FastAPI(title="kalived cockpit", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _token_ok(got: str) -> bool:
    if not TOKEN:
        return True  # heimsted: empty token = open on loopback only
    return got == TOKEN


@app.get("/v1/health")
def health():
    return {"ok": True, "service": "cockpit", "ws": "/v1/ws"}


@app.get("/v1/tools")
def tools():
    return {"tools": list_tools()}


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
            "hiroshima": "http://127.0.0.1:8787/",
        }
    )
