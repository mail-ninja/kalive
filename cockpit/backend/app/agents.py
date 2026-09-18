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
    tools: list[str] = Field(default_factory=list)
    builtin: bool = False


BUILTINS = [
    Agent(
        id="dummy",
        name="ops",
        description="Terminal-sec. Henda på xterm, ikke SOC-rapport.",
        provider="xai",
        model="grok-4.6",
        playbook=None,
        tools=["ping"],
        builtin=True,
    ),
    Agent(
        id="signal",
        name="signal",
        description="SOC-dom. Sil 4, ikke innbrudd på støy.",
        provider="xai",
        model="grok-4.6",
        playbook="signal",
        tools=["ping"],
        builtin=True,
    ),
    Agent(
        id="swarm",
        name="sverm",
        description="Flere agenter i parallell (stub til loop er wired).",
        provider="xai",
        model="grok-4.6",
        playbook=None,
        tools=["ping"],
        builtin=True,
    ),
    Agent(
        id="mercury",
        name="Mercury",
        description="Inception Mercury 2.5 — rask chat/tools.",
        provider="inception",
        model="mercury-2.5",
        playbook=None,
        tools=["ping"],
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
