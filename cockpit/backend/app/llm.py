"""Stream chat from env keys. Tool loop for Hiroshima commands. Never log secrets."""
from __future__ import annotations

import asyncio
import json
import queue
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx

from .agents import Agent
from .catalog import get_provider
from .agents import get_agent
from .hiroshima import MAX_ROUNDS as HIRO_ROUNDS
from .decide import gate_recall
from .memory import format_recall, recall, remember_engram
from .secrets_store import load_env
from .orchestrate import NUDGE_DONE, SHORT_DONE, is_edit, is_fail, is_verify, next_brake
from .tools import call_tool, openai_tools

_REPO = Path(__file__).resolve().parents[3]


def _system_prompt(agent: Agent) -> str:
    if agent.desk == "code" or agent.id in ("forge", "review", "term", "crew", "swarm"):
        extra = (
            "\n\nDu er i cockpit-Arbeid (kode). "
            "Workspace er filer på disk. build bruker repo_glob/grep/read/edit/write. "
            "Nye filer: repo_write. Patch: repo_edit med old_string (omliggende linjer). "
            "act=use_memory eller minne-blokken svarer: ingen tools. "
            "repo_bash er lov bak haken. Git: repo_git status|diff|log|commit (commit bak haken, aldri push). "
            "Preview = HTML på disk ELLER loopback via preview_serve/preview_set (127.0.0.1, aldri 0.0.0.0). "
            "Maks 16 tool-runder. Oneshot. Etter vellykket test/preview: DONE, ikke grep mer. "
            "Kort svar. Passord bare i xterm."
        )
    else:
        extra = (
            "\n\nDu er i cockpit. SOC-tools: hiroshima_verdict/scan/run/job. "
            f"Maks {HIRO_ROUNDS} runder. Jobber ONESHOT. Rutinescan er cron. "
            "Passord skrives aldri i chat. Scan krever «agent får kjøre»."
        )
    if agent.playbook:
        p = _REPO / "prompts" / "playbooks" / f"{agent.playbook}.md"
        if p.is_file():
            return p.read_text(encoding="utf-8") + extra
    p = _REPO / "prompts" / "advisor.md"
    if p.is_file():
        return p.read_text(encoding="utf-8") + extra
    return "Du er en hjelpsom assistent. Gjør ditt beste." + extra


def _endpoint(agent: Agent, provider: str | None, model: str | None) -> tuple[str, str, str]:
    env = load_env()
    pid = (provider or agent.provider or "xai").lower()
    spec = get_provider(pid)
    if spec:
        if spec.get("chat") is False:
            raise RuntimeError(spec.get("note") or f"{pid} er ikke en chat-provider")
        key = ""
        for k in [spec.get("key"), *(spec.get("key_alts") or [])]:
            if k and (env.get(k) or "").strip():
                key = env[k].strip()
                break
        base = (env.get(spec.get("base_env") or "") or spec["base"]).rstrip("/")
        mdl = model or agent.model or (spec["models"][0] if spec["models"] else "unknown")
        return key, base + "/chat/completions", mdl
    key = (env.get("XAI_API_KEY") or "").strip()
    base = (env.get("XAI_BASE_URL") or "https://api.x.ai/v1").rstrip("/")
    mdl = model or agent.model or "grok-4.6"
    return key, base + "/chat/completions", mdl


def _headers(key: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + key, "Content-Type": "application/json"}


async def _wait_or_pulse(aw, cancel: asyncio.Event | None, pulse_s: float = 2.5):
    """Await aw, yielding pulse events until it finishes. Cancels aw on stop."""
    task = asyncio.ensure_future(aw)
    t0 = time.monotonic()
    try:
        while True:
            if cancel is not None and cancel.is_set():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, httpx.HTTPError):
                    pass
                yield {"type": "stopped", "text": "stoppet av operator"}
                return
            done, _ = await asyncio.wait({task}, timeout=pulse_s)
            if done:
                try:
                    yield {"type": "_ok", "value": task.result()}
                except asyncio.CancelledError:
                    yield {"type": "stopped", "text": "stoppet av operator"}
                except Exception as e:
                    yield {"type": "_err", "error": e}
                return
            yield {"type": "pulse", "s": int(time.monotonic() - t0)}
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, httpx.HTTPError):
                pass


async def stream_tokens(
    agent: Agent,
    user_text: str,
    provider: str | None = None,
    model: str | None = None,
) -> AsyncIterator[str]:
    async for ev in run_turn(agent, user_text, provider=provider, model=model, allow_mutate=False, use_tools=False):
        if ev.get("type") == "token":
            yield str(ev.get("text") or "")


async def run_turn(
    agent: Agent,
    user_text: str,
    provider: str | None = None,
    model: str | None = None,
    allow_mutate: bool = False,
    use_tools: bool = True,
    cancel: asyncio.Event | None = None,
    _depth: int = 0,
) -> AsyncIterator[dict[str, Any]]:
    key, url, model_id = _endpoint(agent, provider, model)
    pid = (provider or agent.provider or "xai").lower()
    if not key:
        raise RuntimeError(f"ingen nøkkel for provider={pid} — lim inn i Settings")
    hits: list[dict] = []
    mem_block = ""
    decision: dict = {}
    t_recall_ms = 0
    t_decide_ms = 0
    if _depth == 0:
        try:
            t0 = time.perf_counter()
            hits = recall(agent.id, user_text, limit=4)
            t_recall_ms = int((time.perf_counter() - t0) * 1000)
            t1 = time.perf_counter()
            hits, decision = gate_recall(user_text, hits)
            t_decide_ms = int((time.perf_counter() - t1) * 1000)
            mem_block = format_recall(hits)
            try:
                remember_engram(
                    agent.id,
                    "decide",
                    {
                        "user": user_text[:400],
                        "act": decision.get("act"),
                        "n": decision.get("n"),
                        "source": decision.get("source"),
                        "recall_ms": t_recall_ms,
                        "decide_ms": t_decide_ms,
                    },
                )
            except Exception:
                pass
        except Exception:
            hits = []
            mem_block = ""
            decision = {}
    act = str(decision.get("act") or "")
    if mem_block:
        best = hits[0].get("score") if hits else 0
        yield {
            "type": "log",
            "text": (
                f"minne-gate: {len(hits)} treff (beste {best}) act={act or '—'} "
                f"src={decision.get('source') or 'rules'}  "
                f"{t_recall_ms}ms recall {t_decide_ms}ms decide"
            ),
        }
    elif _depth == 0:
        yield {"type": "log", "text": "minne-gate: ingen treff"}
    sys_content = _system_prompt(agent)
    if mem_block:
        sys_content = sys_content + "\n\n" + mem_block
        if act == "use_memory":
            sys_content += "\n\nact=use_memory: svar fra minne-blokken. Ikke kall repo_read."
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": sys_content},
        {"role": "user", "content": user_text},
    ]
    names = list(agent.tools) if agent.tools else None
    tools = openai_tools(names) if use_tools and act != "use_memory" else []
    tool_cap = 16 if (agent.desk == "code" or agent.id == "build") else HIRO_ROUNDS
    max_r = tool_cap + 1
    did_mutate = False
    verified = False
    see_streak = 0
    code_desk = agent.desk == "code" or agent.id == "build"
    async with httpx.AsyncClient(timeout=120.0) as client:
        for rnd in range(max_r):
            if cancel is not None and cancel.is_set():
                yield {"type": "stopped", "text": "stoppet av operator"}
                return
            if rnd >= tool_cap:
                tools = []
            last = rnd == max_r - 1 or not tools
            if last and (not messages or messages[-1].get("content") != SHORT_DONE):
                messages.append({"role": "user", "content": SHORT_DONE})
            body: dict[str, Any] = {"model": model_id, "messages": messages, "stream": last}
            if tools and not last:
                body["tools"] = tools
                body["tool_choice"] = "auto"
            if last:
                body["max_tokens"] = 400
                last_tok = time.monotonic()
                async with client.stream("POST", url, headers=_headers(key), json=body) as resp:
                    if resp.status_code >= 400:
                        err = (await resp.aread()).decode("utf-8", "replace")[:400]
                        raise RuntimeError(f"{pid} HTTP {resp.status_code}: {err}")
                    async for line in resp.aiter_lines():
                        if cancel is not None and cancel.is_set():
                            yield {"type": "stopped", "text": "stoppet av operator"}
                            return
                        now = time.monotonic()
                        if now - last_tok >= 2.5:
                            yield {"type": "pulse", "s": int(now - last_tok)}
                            last_tok = now
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data or data == "[DONE]":
                            continue
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        delta = ((chunk.get("choices") or [{}])[0].get("delta") or {}).get("content")
                        if delta:
                            last_tok = time.monotonic()
                            yield {"type": "token", "text": str(delta)}
                return
            resp = None
            async for ev in _wait_or_pulse(client.post(url, headers=_headers(key), json=body), cancel):
                if ev.get("type") == "pulse":
                    yield ev
                elif ev.get("type") == "stopped":
                    yield ev
                    return
                elif ev.get("type") == "_err":
                    raise ev["error"]
                else:
                    resp = ev.get("value")
            if resp is None:
                yield {"type": "stopped", "text": "stoppet av operator"}
                return
            if resp.status_code >= 400:
                raise RuntimeError(f"{pid} HTTP {resp.status_code}: {resp.text[:400]}")
            choice = ((resp.json().get("choices") or [{}])[0]) or {}
            msg = choice.get("message") or {}
            calls = msg.get("tool_calls") or []
            text = msg.get("content") or ""
            if not calls:
                if text:
                    yield {"type": "token", "text": str(text)}
                elif rnd >= tool_cap - 1:
                    yield {"type": "token", "text": "(tool-tak nådd — svar ut fra det som er lest)"}
                return
            messages.append({"role": "assistant", "content": text or "", "tool_calls": calls})
            round_names: list[str] = []
            round_args: list[dict] = []
            got_verify = False
            got_edit = False
            got_fail = False
            for tc in calls:
                fn = (tc.get("function") or {}) if isinstance(tc, dict) else {}
                name = str(fn.get("name") or "")
                raw_args = fn.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except json.JSONDecodeError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                round_names.append(name)
                round_args.append(args)
                yield {"type": "tool", "name": name, "args": args, "round": rnd + 1}
                if name == "repo_bash":
                    q: queue.Queue = queue.Queue()

                    def on_chunk(tag: str, s: str) -> None:
                        q.put(("out", tag, s))

                    def run() -> None:
                        try:
                            r = call_tool(
                                name,
                                args,
                                allow_mutate=allow_mutate,
                                allow=names,
                                cancel=cancel,
                                on_chunk=on_chunk,
                            )
                            q.put(("done", "", r))
                        except Exception as e:
                            q.put(("done", "", {"error": str(e)[:400]}))

                    fut = asyncio.get_running_loop().run_in_executor(None, run)
                    result = {}
                    while True:
                        try:
                            kind, tag, payload = await asyncio.to_thread(q.get, True, 0.15)
                        except queue.Empty:
                            if fut.done() and q.empty():
                                break
                            continue
                        if kind == "out":
                            yield {
                                "type": "tool_out",
                                "name": name,
                                "stream": tag,
                                "text": payload,
                                "round": rnd + 1,
                            }
                        else:
                            result = payload if isinstance(payload, dict) else {"error": str(payload)}
                            break
                    await fut
                else:
                    result = await asyncio.to_thread(
                        call_tool, name, args, allow_mutate=allow_mutate, allow=names, cancel=cancel
                    )
                yield {"type": "tool_result", "name": name, "result": result, "round": rnd + 1}
                if name in ("repo_edit", "repo_write", "repo_bash", "iframe_write", "preview_serve") or (
                    name == "repo_git" and str(args.get("action") or "") == "commit"
                ):
                    did_mutate = True
                if is_verify(name, result if isinstance(result, dict) else None):
                    got_verify = True
                if is_edit(name, args):
                    got_edit = True
                if is_fail(name, result if isinstance(result, dict) else None):
                    got_fail = True
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id") or name,
                        "content": json.dumps(result, ensure_ascii=False)[:8000],
                    }
                )
                st = result.get("status") if isinstance(result, dict) else None
                if st in ("done", "timeout", "error"):
                    messages.append(
                        {
                            "role": "user",
                            "content": "Jobben er ferdig og stoppet. Ikke start en ny. Rutine er cron/timer. Svar operator nå.",
                        }
                    )
                    tools = []
                if isinstance(result, dict) and result.get("dispatch") and _depth < 1:
                    sub = get_agent(str(result.get("agent") or ""))
                    task = str(result.get("text") or "")
                    if sub and sub.id != agent.id and task:
                        yield {"type": "log", "text": f"{agent.id} → {sub.id}"}
                        bits: list[str] = []
                        async for ev in run_turn(
                            sub,
                            task,
                            provider=provider,
                            model=model,
                            allow_mutate=allow_mutate,
                            use_tools=True,
                            cancel=cancel,
                            _depth=_depth + 1,
                        ):
                            yield ev
                            if ev.get("type") == "token":
                                bits.append(str(ev.get("text") or ""))
                        result = {"ok": True, "agent": sub.id, "excerpt": "".join(bits)[:1500]}
                        messages[-1]["content"] = json.dumps(result, ensure_ascii=False)[:8000]
            if code_desk and tools:
                br = next_brake(
                    verified=verified,
                    see_streak=see_streak,
                    names=round_names,
                    args_list=round_args,
                    got_verify=got_verify,
                    got_edit=got_edit,
                    got_fail=got_fail,
                )
                verified = bool(br["verified"])
                see_streak = int(br["see_streak"])
                if br["force_stop"]:
                    tools = []
                    yield {"type": "log", "text": "orchestrator: ferdig — stopper"}
                elif br["nudge"]:
                    messages.append({"role": "user", "content": NUDGE_DONE})
            if (
                code_desk
                and rnd + 1 >= 4
                and not did_mutate
                and names
                and tools
            ):
                names = [n for n in names if n in ("repo_read", "repo_edit", "repo_write", "repo_bash", "repo_git", "preview_serve", "preview_set")]
                tools = openai_tools(names) if (use_tools and act != "use_memory" and names) else []
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "4 tools uten repo_edit. Neste kall: repo_edit på fila du allerede har lest, "
                            "eller svar DONE. Ingen grep/glob mer."
                        ),
                    }
                )
        yield {"type": "token", "text": "(nådde max runder uten svar)"}
