"""Provider + model lists. Live /v1/models when a key exists; else fallback."""
from __future__ import annotations

import httpx

from .secrets_store import load_env

PROVIDERS = [
    {
        "id": "xai",
        "label": "xAI",
        "models": ["grok-4.6", "grok-4", "grok-3", "grok-3-mini"],
        "key": "XAI_API_KEY",
        "key_alts": [],
        "base": "https://api.x.ai/v1",
        "base_env": "XAI_BASE_URL",
        "docs": "https://docs.x.ai/docs/overview",
    },
    {
        "id": "inception",
        "label": "Inception",
        "models": ["mercury-2.5", "mercury-2"],
        "key": "INCEPTION_API_KEY",
        "key_alts": [],
        "base": "https://api.inceptionlabs.ai/v1",
        "base_env": "INCEPTION_BASE_URL",
        "docs": "https://docs.inceptionlabs.ai/get-started",
    },
    {
        "id": "huggingface",
        "label": "Hugging Face",
        "models": [
            "meta-llama/Llama-3.1-8B-Instruct:fastest",
            "Qwen/Qwen2.5-7B-Instruct:fastest",
            "openai/gpt-oss-120b:fastest",
        ],
        "key": "HF_TOKEN",
        "key_alts": ["HUGGINGFACE_HUB_TOKEN"],
        "base": "https://router.huggingface.co/v1",
        "base_env": "HF_BASE_URL",
        "docs": "https://huggingface.co/docs/inference-providers/index",
    },
    {
        "id": "perplexity",
        "label": "Perplexity",
        "models": ["sonar", "sonar-pro", "sonar-reasoning"],
        "key": "PERPLEXITY_API_KEY",
        "key_alts": [],
        "base": "https://api.perplexity.ai",
        "base_env": "PERPLEXITY_BASE_URL",
        "docs": "https://docs.perplexity.ai/guides/getting-started",
    },
    {
        "id": "openai",
        "label": "OpenAI",
        "models": ["gpt-4o", "gpt-4.1", "o4-mini"],
        "key": "OPENAI_API_KEY",
        "key_alts": [],
        "base": "https://api.openai.com/v1",
        "base_env": "OPENAI_BASE_URL",
        "docs": "https://platform.openai.com/docs/models",
    },
    {
        "id": "github",
        "label": "GitHub",
        "models": [],
        "key": "GITHUB_TOKEN",
        "key_alts": ["GH_TOKEN"],
        "base": "https://models.github.ai/inference",
        "base_env": "GITHUB_MODELS_BASE_URL",
        "docs": "https://docs.github.com/en/rest",
        "note": "GitHub Models (chat) ble pensjonert 2026-07-30. Tokenet er til repo/gh — ikke inference.",
        "chat": False,
    },
]


def get_provider(pid: str) -> dict | None:
    for p in PROVIDERS:
        if p["id"] == pid:
            return p
    return None


def _key_for(spec: dict, env: dict) -> str:
    for k in [spec.get("key"), *(spec.get("key_alts") or [])]:
        if k and (env.get(k) or "").strip():
            return env[k].strip()
    return ""


def fetch_models(pid: str) -> dict:
    spec = get_provider(pid)
    if not spec:
        return {"id": pid, "models": [], "source": "unknown", "error": "ukjent provider"}
    fallback = list(spec.get("models") or [])
    if spec.get("chat") is False:
        return {
            "id": pid,
            "models": fallback,
            "source": "none",
            "error": spec.get("note"),
            "docs": spec.get("docs"),
        }
    env = load_env()
    key = _key_for(spec, env)
    if not key:
        return {
            "id": pid,
            "models": fallback,
            "source": "fallback",
            "error": f"ingen nøkkel ({spec['key']}) — Settings",
            "docs": spec.get("docs"),
        }
    base = (env.get(spec.get("base_env") or "") or spec["base"]).rstrip("/")
    url = base + "/models"
    try:
        r = httpx.get(url, headers={"Authorization": "Bearer " + key}, timeout=8.0)
        if r.status_code >= 400:
            return {
                "id": pid,
                "models": fallback,
                "source": "fallback",
                "error": f"HTTP {r.status_code}",
                "docs": spec.get("docs"),
            }
        data = r.json()
        rows = data.get("data") if isinstance(data, dict) else data
        ids = []
        for row in rows or []:
            if isinstance(row, dict) and row.get("id"):
                ids.append(str(row["id"]))
            elif isinstance(row, str):
                ids.append(row)
        ids = [i for i in ids if i][:80]
        return {
            "id": pid,
            "models": ids or fallback,
            "source": "live" if ids else "fallback",
            "docs": spec.get("docs"),
        }
    except httpx.HTTPError as e:
        return {
            "id": pid,
            "models": fallback,
            "source": "fallback",
            "error": str(e)[:200],
            "docs": spec.get("docs"),
        }


def public(*, live: bool = True) -> list[dict]:
    out = []
    for p in PROVIDERS:
        item = {
            "id": p["id"],
            "label": p["label"],
            "models": list(p.get("models") or []),
            "docs": p.get("docs"),
            "chat": p.get("chat", True),
            "note": p.get("note"),
        }
        if live:
            fetched = fetch_models(p["id"])
            if fetched.get("models"):
                item["models"] = fetched["models"]
            item["source"] = fetched.get("source")
            if fetched.get("error"):
                item["error"] = fetched["error"]
        out.append(item)
    return out
