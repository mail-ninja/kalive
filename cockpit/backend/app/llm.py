"""Stream chat from env keys. Tool loop for Hiroshima commands. Never log secrets."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx

from .agents import Agent
from .catalog import get_provider
from .hiroshima import MAX_ROUNDS
from .secrets_store import load_env
from .tools import call_tool, openai_tools

_REPO = Path(__file__).resolve().parents[3]


def _system_prompt(agent: Agent) -> str:
    extra = (
        "\n\nDu er i cockpit-Hiroshima. Tools: hiroshima_verdict, hiroshima_scan, hiroshima_run, hiroshima_job, ping. "
        f"Maks {MAX_ROUNDS} runder. Jobber er ONESHOT: start → vent ferdig → STOPP. "
        "Ikke start ny scan når den er done. Ikke loop. Rutinescan er cron (kalived-scan.timer), ikke deg. "
        "Etter hiroshima_scan: poll hiroshima_job til status=done/timeout, deretter svar operator og slutt. "
        "Passord skrives aldri i chat — bare i xterm. Scan/defs krever «agent får kjøre»."
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
) -> AsyncIterator[dict[str, Any]]:
    key, url, model_id = _endpoint(agent, provider, model)
    pid = (provider or agent.provider or "xai").lower()
    if not key:
        raise RuntimeError(f"ingen nøkkel for provider={pid} — lim inn i Settings")
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _system_prompt(agent)},
        {"role": "user", "content": user_text},
    ]
    tools = openai_tools() if use_tools else []
    async with httpx.AsyncClient(timeout=120.0) as client:
        for rnd in range(MAX_ROUNDS):
            last = rnd == MAX_ROUNDS - 1 or not tools
            body: dict[str, Any] = {"model": model_id, "messages": messages, "stream": last}
            if tools and not last:
                body["tools"] = tools
                body["tool_choice"] = "auto"
            if last:
                async with client.stream("POST", url, headers=_headers(key), json=body) as resp:
                    if resp.status_code >= 400:
                        err = (await resp.aread()).decode("utf-8", "replace")[:400]
                        raise RuntimeError(f"{pid} HTTP {resp.status_code}: {err}")
                    async for line in resp.aiter_lines():
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
                            yield {"type": "token", "text": str(delta)}
                return
            resp = await client.post(url, headers=_headers(key), json=body)
            if resp.status_code >= 400:
                raise RuntimeError(f"{pid} HTTP {resp.status_code}: {resp.text[:400]}")
            choice = ((resp.json().get("choices") or [{}])[0]) or {}
            msg = choice.get("message") or {}
            calls = msg.get("tool_calls") or []
            text = msg.get("content") or ""
            if not calls:
                if text:
                    yield {"type": "token", "text": str(text)}
                return
            messages.append({"role": "assistant", "content": text or "", "tool_calls": calls})
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
                yield {"type": "tool", "name": name, "args": args, "round": rnd + 1}
                result = call_tool(name, args, allow_mutate=allow_mutate)
                yield {"type": "tool_result", "name": name, "result": result, "round": rnd + 1}
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
        yield {"type": "token", "text": "(nådde max runder uten svar)"}
