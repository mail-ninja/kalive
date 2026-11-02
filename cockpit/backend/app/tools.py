"""Capability registry. Agent loop calls these. No arbitrary shell."""
from __future__ import annotations

import time
from typing import Any, Callable

from pydantic import BaseModel, Field

SIGNAL_RUNS = (
    "scan",
    "defs",
    "watch",
    "uplink-burst",
    "falco-burst",
    "isolate-dst",
    "isolate-undo",
    "aide-init",
    "aide-init-ack-stale",
    "rkhunter-setup",
)


def sudo_needs_pty(job: dict | None) -> bool:
    """True when sudo -n failed and the operator must type a password in xterm."""
    if not isinstance(job, dict):
        return False
    blob = " ".join(str(job.get(k) or "") for k in ("error", "hint", "log_tail")).lower()
    if "password is required" in blob or "a terminal is required" in blob:
        return True
    if "sudo:" in blob and "password" in blob:
        return True
    return False


def _ctl_pty(name: str) -> dict:
    return {
        "need_pty": True,
        "open_hiroshima": True,
        "pty_write": f"sudo kalived-ctl {name}\n",
        "note": "passord i Hiroshima-xterm — ikke i chat",
        "name": name,
    }


def _wait_sudo_job(h: Any, job: dict, timeout: float = 0.6) -> dict:
    jid = str(job.get("job_id") or "")
    cur = job
    t0 = time.time()
    while time.time() - t0 < timeout:
        if sudo_needs_pty(cur):
            return cur
        if cur.get("status") != "running":
            return cur
        if not jid:
            return cur
        time.sleep(0.08)
        nxt = h.job_get(jid)
        if nxt:
            cur = nxt
    return cur


def _hiroshima_sudo_line(line: str) -> str | None:
    """Hiroshima xterm: sudo only via allowlisted kalived-ctl. None = ok."""
    parts = line.split()
    if not parts:
        return "tom linje"
    if parts[0] != "sudo":
        return None
    if "kalived-ctl" not in parts:
        return "sudo i Hiroshima bare via kalived-ctl — ikke fri root-shell"
    idx = parts.index("kalived-ctl")
    verb = parts[idx + 1] if idx + 1 < len(parts) else ""
    if verb == "kill-pid":
        return "kill-pid er Confirm i skuffen, ikke term_send"
    if verb not in SIGNAL_RUNS:
        return f"kalived-ctl {verb or '?'} ikke i signal-allowlist"
    return None


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
    doc = h._attach_protocol(h._read_verdict(snap), snap)
    findings = doc.get("findings") or []
    slim = [
        {"severity": f.get("severity"), "id": f.get("id"), "title": f.get("title")}
        for f in findings
        if isinstance(f, dict)
    ][:40]
    proto = doc.get("protocol") if isinstance(doc.get("protocol"), dict) else {}
    return {
        "stamp": doc.get("stamp"),
        "verdict": doc.get("verdict"),
        "exit_code": doc.get("exit_code"),
        "findings": slim,
        "protocol": proto,
        "unknown_dsts": doc.get("unknown_dsts") or proto.get("unknown_dsts") or [],
        "ufw_hits": doc.get("ufw_hits") or proto.get("ufw_hits") or [],
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

    job = h.start_named("scan", True)
    if job.get("need_pty"):
        return job
    if job.get("error") and not job.get("job_id"):
        return {**_ctl_pty("scan"), "error": job.get("error")}
    job = _wait_sudo_job(h, job)
    if sudo_needs_pty(job):
        return {**_ctl_pty("scan"), "job_id": job.get("job_id"), "exit_code": job.get("exit_code")}
    return job


@register(
    ToolSpec(
        name="hiroshima_run",
        description=(
            "Start én allowlistet kalived-ctl (scan|defs|watch|uplink-burst|falco-burst|"
            "isolate-dst|isolate-undo|aide-init|aide-init-ack-stale|rkhunter-setup). "
            "sudo -n først; ved passord males linja i Hiroshima-xterm. Isolate dest kommer "
            "fra siste scan-snapshot. Ikke kill-pid. Poll hiroshima_job til done. Krever «agent får kjøre»."
        ),
        mutating=True,
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string", "enum": list(SIGNAL_RUNS)}},
            "required": ["name"],
        },
    )
)
def hiroshima_run(args: dict) -> dict:
    from . import hiroshima as h

    name = str(args.get("name") or "").strip()
    if name not in SIGNAL_RUNS:
        return {"error": f"ukjent run: {name}", "have": list(SIGNAL_RUNS)}
    extra = {"family": "unknown"} if name == "isolate-dst" else None
    job = h.start_named(name, True, extra)
    if job.get("need_pty"):
        return job
    if job.get("error") and not job.get("job_id"):
        return {**_ctl_pty(name), "error": job.get("error")}
    job = _wait_sudo_job(h, job)
    if sudo_needs_pty(job):
        return {**_ctl_pty(name), "job_id": job.get("job_id"), "exit_code": job.get("exit_code")}
    return job


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
        description="Pek preview-iframe. url=http://127.0.0.1:PORT/… (loopback). html=komplett HTML-dokument. Aldri 0.0.0.0.",
        mutating=False,
        parameters={
            "type": "object",
            "properties": {"html": {"type": "string"}, "url": {"type": "string"}},
        },
    )
)
def preview_set(args: dict) -> dict:
    from . import desk
    from .preview import parse_loopback_url

    url = str(args.get("url") or "").strip()
    html = str(args.get("html") or "")
    if url:
        canon = parse_loopback_url(url)
        if not canon:
            return {"error": "url må være http(s)://127.0.0.1|localhost, reserverte porter nektet"}
        return desk.apply({"mode": "iframe", "preview": canon})
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
        name="preview_serve",
        description="Start eller stopp én loopback-preview-tjener (127.0.0.1). action=start|stop|status. dir=mappe for python http.server, eller line=egen kommando. path=URL-suffix (f.eks. _snake.html). Krever «agent får kjøre». Aldri 0.0.0.0.",
        mutating=True,
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["start", "stop", "status"]},
                "dir": {"type": "string"},
                "port": {"type": "number"},
                "line": {"type": "string"},
                "path": {"type": "string"},
            },
        },
    )
)
def preview_serve(args: dict) -> dict:
    from . import preview as pv

    action = str(args.get("action") or "start").strip().lower()
    if action == "stop":
        return pv.stop()
    if action == "status":
        return pv.status()
    port = args.get("port")
    try:
        port_i = int(port) if port is not None else None
    except (TypeError, ValueError):
        return {"error": "port må være tall"}
    return pv.start(
        dir=str(args.get("dir") or ""),
        port=port_i,
        line=str(args["line"]) if args.get("line") else None,
        path=str(args.get("path") or ""),
    )


@register(
    ToolSpec(
        name="term_send",
        description="Send én linje til xterm. where=hiroshima åpner Hiroshima-skuffen. Krever «agent får kjøre». Aldri passord. sudo i Hiroshima bare via kalived-ctl.",
        mutating=True,
        parameters={
            "type": "object",
            "properties": {
                "line": {"type": "string"},
                "where": {"type": "string", "enum": ["pty", "hiroshima"]},
            },
            "required": ["line"],
        },
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
    where = str(args.get("where") or "pty").strip().lower()
    if where not in ("pty", "hiroshima"):
        where = "pty"
    if where == "hiroshima":
        err = _hiroshima_sudo_line(line)
        if err:
            return {"error": err}
    out: dict = {"pty_write": line + "\n", "note": "sendt til xterm"}
    if where == "hiroshima":
        out["open_hiroshima"] = True
        out["need_pty"] = True
        out["note"] = "sendt til Hiroshima-xterm — passord der"
    return out


def _browser():
    from . import browser_cdp as b

    return b.instance()


@register(
    ToolSpec(
        name="browser_status",
        description="Status for kalived CDP-browser (loopback Chromium). Ikke Playwright.",
        mutating=False,
        parameters={"type": "object", "properties": {}},
    )
)
def browser_status(_args: dict) -> dict:
    return _browser().status()


@register(
    ToolSpec(
        name="browser_open",
        description="Start Chromium med CDP på 127.0.0.1 (port 9222–9299). Krever hake.",
        mutating=True,
        parameters={"type": "object", "properties": {}},
    )
)
def browser_open(_args: dict) -> dict:
    return _browser().start()


@register(
    ToolSpec(
        name="browser_navigate",
        description="Åpne URL i CDP-browser. Loopback alltid. Ekstern http(s) krever hake. Aldri 0.0.0.0.",
        mutating=True,
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    )
)
def browser_navigate(args: dict) -> dict:
    url = str(args.get("url") or "")
    allow_ext = bool(args.get("_allow_mutate"))
    return _browser().navigate(url, allow_external=allow_ext)


@register(
    ToolSpec(
        name="browser_snapshot",
        description="AX-tre med [ref=eN] for klikk/tast. Les cockpit-UI og sider Signal åpnet.",
        mutating=False,
        parameters={"type": "object", "properties": {}},
    )
)
def browser_snapshot(_args: dict) -> dict:
    return _browser().snapshot()


@register(
    ToolSpec(
        name="browser_click",
        description="Klikk [ref=eN] fra siste snapshot. Krever hake.",
        mutating=True,
        parameters={
            "type": "object",
            "properties": {"ref": {"type": "string"}},
            "required": ["ref"],
        },
    )
)
def browser_click(args: dict) -> dict:
    return _browser().click(str(args.get("ref") or ""))


@register(
    ToolSpec(
        name="browser_type",
        description="Skriv i [ref=eN]. submit=true sender Enter. Krever hake.",
        mutating=True,
        parameters={
            "type": "object",
            "properties": {
                "ref": {"type": "string"},
                "text": {"type": "string"},
                "submit": {"type": "boolean"},
            },
            "required": ["ref", "text"],
        },
    )
)
def browser_type(args: dict) -> dict:
    return _browser().type_text(
        str(args.get("ref") or ""),
        str(args.get("text") or ""),
        bool(args.get("submit")),
    )


@register(
    ToolSpec(
        name="browser_screenshot",
        description="PNG under /tmp/kalived-ui/browser/shot.png. Returnerer path, ikke base64.",
        mutating=False,
        parameters={"type": "object", "properties": {}},
    )
)
def browser_screenshot(_args: dict) -> dict:
    return _browser().screenshot()


@register(
    ToolSpec(
        name="browser_close",
        description="Stopp CDP-Chromium. Krever hake.",
        mutating=True,
        parameters={"type": "object", "properties": {}},
    )
)
def browser_close(_args: dict) -> dict:
    return _browser().close()


@register(
    ToolSpec(
        name="repo_glob",
        description="Finn filer i workspace (relativ glob, f.eks. **/*.py). Hopper over node_modules/.venv/logs.",
        mutating=False,
        parameters={"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]},
    )
)
def repo_glob(args: dict) -> dict:
    from . import workspace as w

    try:
        hits = w.glob(str(args.get("pattern") or "**/*"))
    except Exception as e:
        return {"error": str(e)[:240]}
    return {"root": str(w.root()), "hits": hits, "n": len(hits)}


@register(
    ToolSpec(
        name="repo_grep",
        description="Regex-søk i workspace. glob valgfri.",
        mutating=False,
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}, "glob": {"type": "string"}},
            "required": ["query"],
        },
    )
)
def repo_grep(args: dict) -> dict:
    from . import workspace as w

    try:
        hits = w.grep(str(args.get("query") or ""), str(args.get("glob") or "**/*"))
    except Exception as e:
        return {"error": str(e)[:240]}
    summary = "\n".join(f"{h.get('path')}:{h.get('line')}: {h.get('text')}" for h in hits[:20])
    out: dict = {"hits": hits, "n": len(hits), "summary": summary or "ingen treff"}
    if hits:
        out["path"] = hits[0].get("path")
        out["line"] = hits[0].get("line")
    return out


@register(
    ToolSpec(
        name="repo_read",
        description="Les én fil relativ til workspace. start_line/n_lines for vindu i store filer. Ikke secrets, ikke utenfor rot.",
        mutating=False,
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer"},
                "n_lines": {"type": "integer"},
            },
            "required": ["path"],
        },
    )
)
def repo_read(args: dict) -> dict:
    from . import workspace as w

    try:
        n_lines = args.get("n_lines")
        return w.read(
            str(args.get("path") or ""),
            start_line=int(args.get("start_line") or 1),
            n_lines=int(n_lines) if n_lines is not None else None,
        )
    except Exception as e:
        return {"error": str(e)[:240]}


@register(
    ToolSpec(
        name="repo_edit",
        description="Patch én fil. old_string MÅ ha omliggende linjer (inkl. overskrift/funksjon du redigerer under). Ikke lim ny overskrift på slutten. text=hele fila bare ved total-rewrite. Krever «agent får kjøre».",
        mutating=True,
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
                "text": {"type": "string"},
            },
            "required": ["path"],
        },
    )
)
def repo_edit(args: dict) -> dict:
    from . import workspace as w

    path = str(args.get("path") or "")
    try:
        if args.get("text") is not None and not args.get("old_string"):
            return w.write(path, str(args.get("text") or ""))
        old = str(args.get("old_string") or "")
        new = str(args.get("new_string") or "")
        if not old:
            return {"error": "trenger old_string+new_string eller text"}
        return w.edit(path, old, new)
    except Exception as e:
        return {"error": str(e)[:240]}


@register(
    ToolSpec(
        name="repo_write",
        description="Skriv hele fila (ny eller overwrite). path relativ til workspace. Lager manglende mapper. Krever «agent får kjøre». Nye filer: repo_write. Patch: repo_edit.",
        mutating=True,
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}, "text": {"type": "string"}},
            "required": ["path", "text"],
        },
    )
)
def repo_write(args: dict) -> dict:
    from . import workspace as w

    args.pop("_allow_mutate", None)
    args.pop("_cancel", None)
    args.pop("_on_chunk", None)
    path = str(args.get("path") or "")
    text = str(args.get("text") if args.get("text") is not None else "")
    if len(text) > 400_000:
        return {"error": "fil for stor (maks 400k)"}
    try:
        return w.write(path, text)
    except Exception as e:
        return {"error": str(e)[:240]}


@register(
    ToolSpec(
        name="repo_bash",
        description="Kjør én kommando i workspace (cwd ~/kalived). argv[] eller line. Timeout default 120s. Krever «agent får kjøre». Ikke sudo, ikke git push. npm/bun/pip/cargo bare under apps/ eller docs/. Passord i PTY.",
        mutating=True,
        parameters={
            "type": "object",
            "properties": {
                "argv": {"type": "array", "items": {"type": "string"}},
                "line": {"type": "string"},
                "timeout_s": {"type": "number"},
            },
        },
    )
)
def repo_bash(args: dict) -> dict:
    from . import workspace as w

    cancel = args.pop("_cancel", None)
    on_chunk = args.pop("_on_chunk", None)
    args.pop("_allow_mutate", None)
    argv = args.get("argv")
    if argv is not None and not isinstance(argv, list):
        argv = None
    try:
        return w.bash(
            argv=argv,
            line=str(args["line"]) if args.get("line") else None,
            timeout_s=float(args.get("timeout_s") or 120),
            cancel=cancel,
            on_chunk=on_chunk,
        )
    except Exception as e:
        return {"error": str(e)[:240]}


@register(
    ToolSpec(
        name="repo_git",
        description="Git i workspace: action=status|diff|log|commit. commit krever haken og message; paths[] stages først. Ikke push. Status/diff/log uten hake.",
        mutating=False,
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["status", "diff", "log", "commit"]},
                "message": {"type": "string"},
                "paths": {"type": "array", "items": {"type": "string"}},
                "path": {"type": "string"},
                "staged": {"type": "boolean"},
                "n": {"type": "integer"},
            },
            "required": ["action"],
        },
    )
)
def repo_git(args: dict) -> dict:
    from . import repo_git as g

    allow = bool(args.pop("_allow_mutate", False))
    args.pop("_cancel", None)
    args.pop("_on_chunk", None)
    try:
        return g.run(
            str(args.get("action") or "status"),
            message=str(args.get("message") or ""),
            paths=args.get("paths"),
            path=str(args["path"]) if args.get("path") else None,
            staged=bool(args.get("staged")),
            n=int(args.get("n") or 12),
            allow_mutate=allow,
        )
    except Exception as e:
        return {"error": str(e)[:240]}


@register(
    ToolSpec(
        name="ask_agent",
        description="Crew: én underagent (forge|review|term). Spill/iframe → forge med beskjed iframe_write HTML. Oneshot.",
        mutating=False,
        parameters={
            "type": "object",
            "properties": {
                "id": {"type": "string", "enum": ["build", "forge", "review", "term"]},
                "text": {"type": "string"},
            },
            "required": ["id", "text"],
        },
    )
)
def ask_agent(args: dict) -> dict:
    aid = str(args.get("id") or "")
    if aid not in ("build", "forge", "review", "term"):
        return {"error": "bare build|forge|review|term"}
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


def call_tool(
    name: str,
    payload: dict,
    *,
    allow_mutate: bool = False,
    allow: list[str] | None = None,
    cancel=None,
    on_chunk=None,
) -> dict:
    if allow is not None and name not in allow:
        return {"error": f"tool {name} ikke for denne agenten"}
    if name not in TOOLS:
        return {"error": f"unknown tool: {name}"}
    spec, fn = TOOLS[name]
    if spec.mutating and not allow_mutate:
        return {"error": "mutating: huk av «agent får kjøre» i cockpit"}
    args = dict(payload) if isinstance(payload, dict) else {}
    args["_allow_mutate"] = allow_mutate
    if cancel is not None:
        args["_cancel"] = cancel
    if on_chunk is not None:
        args["_on_chunk"] = on_chunk
    try:
        return fn(args)
    except Exception as e:
        return {"error": str(e)[:400]}
