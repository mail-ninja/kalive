"""Write-only secrets: ~/.config/kalived/env mode 0600. Never return full secret values."""
from __future__ import annotations

import os
import re
import stat
from pathlib import Path

KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")

PROVIDERS = [
    {
        "id": "xai",
        "label": "xAI / Grok",
        "docs": "https://docs.x.ai/docs/overview",
        "keys": [
            {"name": "XAI_API_KEY", "secret": True, "label": "API-nøkkel"},
            {"name": "XAI_BASE_URL", "secret": False, "label": "Base URL", "placeholder": "https://api.x.ai/v1"},
            {"name": "XAI_MODEL", "secret": False, "label": "Modell", "placeholder": "grok-4.6"},
        ],
    },
    {
        "id": "inception",
        "label": "Inception / Mercury",
        "docs": "https://docs.inceptionlabs.ai/get-started",
        "keys": [
            {"name": "INCEPTION_API_KEY", "secret": True, "label": "API-nøkkel"},
            {
                "name": "INCEPTION_BASE_URL",
                "secret": False,
                "label": "Base URL",
                "placeholder": "https://api.inceptionlabs.ai/v1",
            },
            {"name": "INCEPTION_MODEL", "secret": False, "label": "Modell", "placeholder": "mercury-2.5"},
        ],
    },
    {
        "id": "github",
        "label": "GitHub",
        "docs": "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens",
        "keys": [
            {"name": "GITHUB_TOKEN", "secret": True, "label": "Token (repo)"},
            {"name": "GH_TOKEN", "secret": True, "label": "gh CLI-alias"},
        ],
    },
    {
        "id": "x",
        "label": "X (Twitter)",
        "docs": "https://docs.x.com/fundamentals/authentication/overview",
        "keys": [
            {"name": "X_BEARER_TOKEN", "secret": True, "label": "Bearer"},
            {"name": "X_API_KEY", "secret": True, "label": "API key"},
            {"name": "X_API_SECRET", "secret": True, "label": "API secret"},
            {"name": "X_ACCESS_TOKEN", "secret": True, "label": "Access token"},
            {"name": "X_ACCESS_TOKEN_SECRET", "secret": True, "label": "Access secret"},
        ],
    },
]

SECRET_KEYS = {k["name"] for p in PROVIDERS for k in p["keys"] if k["secret"]}
KNOWN = {k["name"] for p in PROVIDERS for k in p["keys"]}
KNOWN |= {"OPENAI_API_KEY", "ANTHROPIC_API_KEY"}


def env_path() -> Path:
    home = os.environ.get("KALIVED_OWNER_HOME") or str(Path.home())
    override = os.environ.get("KALIVED_AI_ENV")
    if override:
        return Path(override)
    return Path(home) / ".config" / "kalived" / "env"


def _parse(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        k = k.strip()
        if KEY_RE.match(k):
            out[k] = v
    return out


def _is_secret(key: str) -> bool:
    return key in SECRET_KEYS or key.endswith("_KEY") or key.endswith("_TOKEN") or key.endswith("_SECRET")


def _mask(key: str, val: str) -> dict:
    secret = _is_secret(key)
    if not val:
        return {"set": False, "secret": secret, "hint": None}
    if not secret:
        return {"set": True, "secret": False, "hint": val}
    hint = val[:3] + "…" + val[-4:] if len(val) > 8 else "••••"
    return {"set": True, "secret": True, "hint": hint}


def status() -> dict:
    p = env_path()
    data = _parse(p.read_text(encoding="utf-8")) if p.is_file() else {}
    names = sorted(set(KNOWN) | set(data))
    return {
        "path": str(p),
        "exists": p.is_file(),
        "mode": oct(p.stat().st_mode & 0o777) if p.is_file() else None,
        "providers": PROVIDERS,
        "keys": {k: _mask(k, data.get(k, "")) for k in names},
    }


def put(updates: dict[str, str | None]) -> dict:
    """None/empty = delete. Missing keys in body are unchanged. Comments kept."""
    p = env_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    raw = p.read_text(encoding="utf-8") if p.is_file() else ""
    data = _parse(raw)
    for k, v in updates.items():
        if not KEY_RE.match(k):
            raise ValueError(f"ugyldig nøkkel: {k}")
        if v is None or v == "":
            data.pop(k, None)
        else:
            if "\n" in v or "\r" in v:
                raise ValueError("verdi kan ikke ha linjeskift")
            data[k] = v

    seen: set[str] = set()
    out_lines: list[str] = []
    if raw:
        for line in raw.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                out_lines.append(line)
                continue
            k = s.partition("=")[0].strip()
            if not KEY_RE.match(k):
                out_lines.append(line)
                continue
            if k not in data:
                continue  # deleted
            out_lines.append(f"{k}={data[k]}")
            seen.add(k)
    else:
        out_lines = [
            "# ~/.config/kalived/env — cockpit Settings. chmod 600. Ikke git-add.",
        ]
    for k in sorted(data):
        if k not in seen:
            out_lines.append(f"{k}={data[k]}")

    tmp = p.with_suffix(".env.tmp")
    tmp.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    tmp.replace(p)
    os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
    return status()
