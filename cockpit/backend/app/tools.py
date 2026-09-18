"""Capability registry. Agent loop calls these. No arbitrary shell."""
from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    name: str
    description: str
    mutating: bool = False
    parameters: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})


class PingArgs(BaseModel):
    n: int = Field(default=1, ge=1, le=8)


TOOLS: dict[str, tuple[ToolSpec, Callable[..., Any]]] = {}


def register(spec: ToolSpec):
    def wrap(fn: Callable[..., Any]):
        TOOLS[spec.name] = (spec, fn)
        return fn

    return wrap


@register(
    ToolSpec(
        name="ping",
        description="Liveness. Ikke sudo.",
        mutating=False,
        parameters={"type": "object", "properties": {"n": {"type": "integer"}}, "required": []},
    )
)
def ping(args: dict) -> dict:
    n = int(args.get("n") or 1)
    return {"pong": max(1, min(n, 8)), "ok": True}


@register(
    ToolSpec(
        name="hiroshima_verdict",
        description="Les siste kalived-verdict fra disk (ikke :8787).",
        mutating=False,
        parameters={"type": "object", "properties": {}},
    )
)
def hiroshima_verdict(_args: dict) -> dict:
    from . import hiroshima as h

    snap = h.latest_snapshot()
    if not snap:
        return {"error": "ingen snapshot"}
    doc = h._read_verdict(snap)
    findings = doc.get("findings") or []
    slim = [
        {"severity": f.get("severity"), "id": f.get("id"), "title": f.get("title")}
        for f in findings
        if isinstance(f, dict)
    ][:40]
    return {
        "stamp": doc.get("stamp"),
        "verdict": doc.get("verdict"),
        "exit_code": doc.get("exit_code"),
        "findings": slim,
    }


@register(
    ToolSpec(
        name="hiroshima_scan",
        description="Start én scan (oneshot). Returnerer job_id. Poll hiroshima_job til done, deretter STOPP. Ikke start ny. Rutine er cron/timer.",
        mutating=True,
        parameters={"type": "object", "properties": {}},
    )
)
def hiroshima_scan(_args: dict) -> dict:
    from . import hiroshima as h

    return h.start_named("scan", True)


@register(
    ToolSpec(
        name="hiroshima_run",
        description="Start én allowlistet ctl (scan|defs), oneshot. Poll til done, så stopp. Ikke loop. Krever «agent får kjøre».",
        mutating=True,
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string", "enum": ["scan", "defs"]}},
            "required": ["name"],
        },
    )
)
def hiroshima_run(args: dict) -> dict:
    from . import hiroshima as h

    name = str(args.get("name") or "")
    return h.start_named(name, True)


@register(
    ToolSpec(
        name="hiroshima_job",
        description="Status for oneshot-jobb. Poll til done/timeout/error, så slutt. Ikke start ny jobb.",
        mutating=False,
        parameters={
            "type": "object",
            "properties": {"job_id": {"type": "string"}},
            "required": ["job_id"],
        },
    )
)
def hiroshima_job(args: dict) -> dict:
    from . import hiroshima as h

    jid = str(args.get("job_id") or "")
    j = h.job_get(jid)
    if not j:
        return {"error": "ukjent job_id", "jobs": h.jobs_list()[:8]}
    return j


def list_tools() -> list[dict]:
    return [spec.model_dump() for spec, _fn in TOOLS.values()]


def openai_tools() -> list[dict]:
    out = []
    for spec, _fn in TOOLS.values():
        out.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters or {"type": "object", "properties": {}},
                },
            }
        )
    return out


def call_tool(name: str, payload: dict, *, allow_mutate: bool = False) -> dict:
    if name not in TOOLS:
        return {"error": f"unknown tool: {name}"}
    spec, fn = TOOLS[name]
    if spec.mutating and not allow_mutate:
        return {"error": "mutating: huk av «agent får kjøre» i cockpit"}
    args = payload if isinstance(payload, dict) else {}
    try:
        return fn(args)
    except Exception as e:
        return {"error": str(e)[:400]}
