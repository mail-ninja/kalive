"""Capability registry. Empty on purpose — slots exist so tools don't get bolted on later."""
from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    name: str
    description: str
    mutating: bool = False


class PingArgs(BaseModel):
    n: int = Field(default=1, ge=1, le=8)


TOOLS: dict[str, tuple[ToolSpec, Callable[..., Any]]] = {}


def register(spec: ToolSpec):
    def wrap(fn: Callable[..., Any]):
        TOOLS[spec.name] = (spec, fn)
        return fn

    return wrap


@register(ToolSpec(name="ping", description="Liveness. Ikke sudo.", mutating=False))
def ping(args: PingArgs) -> dict:
    return {"pong": args.n, "ok": True}


def list_tools() -> list[dict]:
    return [spec.model_dump() for spec, _fn in TOOLS.values()]


def call_tool(name: str, payload: dict) -> dict:
    if name not in TOOLS:
        return {"error": f"unknown tool: {name}"}
    spec, fn = TOOLS[name]
    if spec.mutating:
        return {"error": "mutating tools require confirm (not wired in heimsted)"}
    if name == "ping":
        return fn(PingArgs(**payload))
    return {"error": "no handler"}
