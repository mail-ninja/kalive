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


@register(
    ToolSpec(
        name="canvas_read",
        description="Les canvas (Monaco/iframe) som operator ser nå.",
        mutating=False,
        parameters={"type": "object", "properties": {}},
    )
)
def canvas_read(_args: dict) -> dict:
    from . import desk

    s = desk.snapshot()
    return {**s, "n": len(s.get("text") or "")}


@register(
    ToolSpec(
        name="canvas_open",
        description="Skriv fil til canvas. HTML-spill/app: path=*.html, language=html — da fyrer iframe automatisk. Ellers Monaco.",
        mutating=False,
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "language": {"type": "string"},
                "text": {"type": "string"},
                "mode": {"type": "string", "enum": ["monaco", "iframe"]},
            },
            "required": ["text"],
        },
    )
)
def canvas_open(args: dict) -> dict:
    from . import desk

    text = str(args.get("text") or "")
    path = str(args.get("path") or "untitled.md")
    language = str(args.get("language") or "markdown")
    mode = str(args.get("mode") or "")
    html = desk.looks_html(text, path, language)
    if mode not in ("monaco", "iframe"):
        mode = "iframe" if html else "monaco"
    upd: dict = {"path": path, "language": language if not html else "html", "text": text, "mode": mode}
    if html:
        upd["preview"] = text
        upd["mode"] = "iframe"
    return desk.apply(upd)


@register(
    ToolSpec(
        name="canvas_edit",
        description="Erstatt tekst i åpen canvas (behold path/language).",
        mutating=False,
        parameters={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    )
)
def canvas_edit(args: dict) -> dict:
    from . import desk

    return desk.apply({"text": str(args.get("text") or ""), "mode": "monaco"})


@register(
    ToolSpec(
        name="iframe_write",
        description="SKRIV OG VIS i iframe. Påkrevd når operator sier spill/iframe/vis. html=komplett <!doctype html> med CSS+JS innebygd. Ikke Monaco. Ikke .py.",
        mutating=False,
        parameters={
            "type": "object",
            "properties": {"html": {"type": "string"}, "title": {"type": "string"}},
            "required": ["html"],
        },
    )
)
def iframe_write(args: dict) -> dict:
    from . import desk

    html = str(args.get("html") or "")
    if not html.strip():
        return {"error": "html kreves"}
    if not desk.looks_html(html, "index.html", "html"):
        return {"error": "html må være et HTML-dokument (<!doctype html> eller <html>…)"}
    title = str(args.get("title") or "index.html").strip() or "index.html"
    if not title.endswith((".html", ".htm")):
        title = title + ".html"
    return desk.apply(
        {"mode": "iframe", "preview": html, "text": html, "language": "html", "path": title}
    )


@register(
    ToolSpec(
        name="preview_set",
        description="Fyr opp iframe. html=komplett HTML-dokument (spill/app) ELLER tom html for å spille det som ligger i canvas. url kun 127.0.0.1.",
        mutating=False,
        parameters={
            "type": "object",
            "properties": {"html": {"type": "string"}, "url": {"type": "string"}},
        },
    )
)
def preview_set(args: dict) -> dict:
    from . import desk

    url = str(args.get("url") or "").strip()
    html = str(args.get("html") or "")
    if url:
        ok = url.startswith("http://127.0.0.1") or url.startswith("https://127.0.0.1") or url.startswith("http://localhost")
        if not ok:
            return {"error": "url må være loopback"}
        return desk.apply({"mode": "iframe", "preview": url})
    if not html:
        snap = desk.snapshot()
        html = snap.get("preview") or snap.get("text") or ""
    if not html.strip():
        return {"error": "tom canvas — skriv HTML først"}
    if not desk.looks_html(html, "", "html"):
        return {
            "error": "canvas er ikke HTML (f.eks. .py-spec). Skriv en komplett <!doctype html>-fil og preview_set igjen.",
            "path": desk.snapshot().get("path"),
        }
    return desk.apply({"mode": "iframe", "preview": html, "text": html, "language": "html", "path": "index.html"})


@register(
    ToolSpec(
        name="term_send",
        description="Send én linje til cockpit-xterm. Krever «agent får kjøre». Aldri passord. Dedikert term-agent.",
        mutating=True,
        parameters={"type": "object", "properties": {"line": {"type": "string"}}, "required": ["line"]},
    )
)
def term_send(args: dict) -> dict:
    line = str(args.get("line") or "").strip("\n")
    if not line:
        return {"error": "tom linje"}
    low = line.lower()
    if "sudo -S" in line or "| sudo" in low or ("echo " in low and "sudo" in low):
        return {"error": "ikke sudo -S / pipe passord — skriv passord i xterm"}
    if "\n" in line:
        line = line.split("\n", 1)[0]
    return {"pty_write": line + "\n", "note": "sendt til xterm"}


@register(
    ToolSpec(
        name="ask_agent",
        description="Crew: én underagent (forge|review|term). Spill/iframe → forge med beskjed iframe_write HTML. Oneshot.",
        mutating=False,
        parameters={
            "type": "object",
            "properties": {
                "id": {"type": "string", "enum": ["forge", "review", "term"]},
                "text": {"type": "string"},
            },
            "required": ["id", "text"],
        },
    )
)
def ask_agent(args: dict) -> dict:
    aid = str(args.get("id") or "")
    if aid not in ("forge", "review", "term"):
        return {"error": "bare forge|review|term"}
    text = str(args.get("text") or "").strip()
    if not text:
        return {"error": "tom oppgave"}
    return {"dispatch": True, "agent": aid, "text": text[:4000]}


def list_tools() -> list[dict]:
    return [spec.model_dump() for spec, _fn in TOOLS.values()]


def openai_tools(names: list[str] | None = None) -> list[dict]:
    out = []
    allow = set(names) if names else None
    for spec, _fn in TOOLS.values():
        if allow is not None and spec.name not in allow:
            continue
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


def call_tool(name: str, payload: dict, *, allow_mutate: bool = False, allow: list[str] | None = None) -> dict:
    if allow is not None and name not in allow:
        return {"error": f"tool {name} ikke for denne agenten"}
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
