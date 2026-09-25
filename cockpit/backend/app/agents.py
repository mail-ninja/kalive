"""Agent registry. Built-ins in code; extras in ~/.config/kalived/agents.json."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from .secrets_store import env_path


class Agent(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,40}$")
    name: str
    description: str = ""
    provider: str = "xai"  # xai | inception
    model: str = ""
    playbook: str | None = None  # prompts/playbooks/<id>.md
    desk: str = "any"  # soc | code | any
    tools: list[str] = Field(default_factory=list)
    builtin: bool = False


SOC_TOOLS = ["ping", "hiroshima_verdict", "hiroshima_scan", "hiroshima_run", "hiroshima_job"]
CODE_TOOLS = ["iframe_write", "preview_set", "canvas_open", "canvas_edit", "canvas_read", "ping", "term_send"]
BUILD_TOOLS = ["repo_glob", "repo_grep", "repo_read", "repo_edit", "repo_bash", "ping"]
CREW_TOOLS = ["ping", "ask_agent", "repo_read"]
TERM_TOOLS = ["ping", "term_send"]
REVIEW_TOOLS = ["ping", "repo_read", "repo_grep"]

BUILTINS = [
    Agent(
        id="dummy",
        name="ops",
        description="Terminal-sec. Henda på xterm, ikke SOC-rapport.",
        provider="xai",
        model="grok-4.6",
        playbook=None,
        desk="any",
        tools=TERM_TOOLS,
        builtin=True,
    ),
    Agent(
        id="signal",
        name="signal",
        description="SOC-dom. Sil 4, ikke innbrudd på støy.",
        provider="xai",
        model="grok-4.6",
        playbook="signal",
        desk="soc",
        tools=SOC_TOOLS,
        builtin=True,
    ),
    Agent(
        id="build",
        name="build",
        description="Repo-loop. Leser og patcher filer på disk i workspace.",
        provider="xai",
        model="grok-4.6",
        playbook="build",
        desk="code",
        tools=BUILD_TOOLS,
        builtin=True,
    ),
    Agent(
        id="forge",
        name="forge",
        description="Kode. Spill/app → iframe_write. Annet → Monaco.",
        provider="xai",
        model="grok-4.6",
        playbook="forge",
        desk="code",
        tools=CODE_TOOLS,
        builtin=True,
    ),
    Agent(
        id="review",
        name="review",
        description="Les canvas. Funn, ikke rewrite.",
        provider="xai",
        model="grok-4.6",
        playbook="review",
        desk="code",
        tools=REVIEW_TOOLS,
        builtin=True,
    ),
    Agent(
        id="term",
        name="term",
        description="Dedikert xterm-agent. Passord der, ikke i chat.",
        provider="xai",
        model="grok-4.6",
        playbook="term",
        desk="code",
        tools=TERM_TOOLS,
        builtin=True,
    ),
    Agent(
        id="crew",
        name="crew",
        description="Kodeteam-dirigent. ask_agent → forge/review/term. Ikke LangChain.",
        provider="xai",
        model="grok-4.6",
        playbook="crew",
        desk="code",
        tools=CREW_TOOLS,
        builtin=True,
    ),
    Agent(
        id="swarm",
        name="sverm",
        description="Alias for crew (gammel stub).",
        provider="xai",
        model="grok-4.6",
        playbook="crew",
        desk="code",
        tools=CREW_TOOLS,
        builtin=True,
    ),
    Agent(
        id="mercury",
        name="Mercury",
        description="Inception Mercury 2.5 — rask chat/tools.",
        provider="inception",
        model="mercury-2.5",
        playbook=None,
        desk="any",
        tools=CODE_TOOLS,
        builtin=True,
    ),
]


def _extra_path() -> Path:
    return env_path().parent / "agents.json"


def _extras() -> list[Agent]:
    p = _extra_path()
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    out: list[Agent] = []
    for item in raw if isinstance(raw, list) else raw.get("agents") or []:
        try:
            a = Agent.model_validate(item)
            a.builtin = False
            out.append(a)
        except Exception:
            continue
    return out


def all_agents() -> list[Agent]:
    seen: set[str] = set()
    out: list[Agent] = []
    for a in [*_extras(), *BUILTINS]:
        if a.id in seen:
            continue
        seen.add(a.id)
        out.append(a)
    return out


def get_agent(agent_id: str) -> Agent | None:
    for a in all_agents():
        if a.id == agent_id:
            return a
    return None


def list_public() -> list[dict]:
    return [a.model_dump() for a in all_agents()]
