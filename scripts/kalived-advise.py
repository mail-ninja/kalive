#!/usr/bin/env python3
"""kalived advisor — SpaceXAI/xAI. Reads redacted verdict only. Never sudo."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("KALIVED_ROOT", Path(__file__).resolve().parent.parent))
PROMPT = ROOT / "prompts" / "advisor.md"
DEFAULT_MODEL = "grok-4.6"
DEFAULT_BASE = "https://api.x.ai/v1"

PLAYBOOKS = [
    "sudo kalived-ctl scan",
    "sudo kalived-ctl defs",
    "sudo bash playbooks/aide-init.sh --force",
    "sudo bash playbooks/install-kalived-helper.sh",
    "sudo bash playbooks/docker-hygiene.sh --prune",
]


def load_dotenv_env() -> None:
    home = os.environ.get("KALIVED_OWNER_HOME")
    if not home:
        owner = os.environ.get("KALIVED_OWNER") or os.environ.get("SUDO_USER") or os.environ.get("USER")
        home = f"/home/{owner}" if owner and owner != "root" else os.path.expanduser("~")
    path = Path(os.environ.get("KALIVED_AI_ENV", Path(home) / ".config/kalived/env"))
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k in ("XAI_API_KEY", "XAI_BASE_URL", "XAI_MODEL"):
            os.environ.setdefault(k, v)


def redact(verdict: dict) -> dict:
    findings = []
    for f in verdict.get("findings") or []:
        if not isinstance(f, dict):
            continue
        findings.append(
            {
                "severity": f.get("severity"),
                "id": f.get("id"),
                "title": (f.get("title") or "")[:240],
            }
        )
    return {
        "verdict": verdict.get("verdict"),
        "exit_code": verdict.get("exit_code"),
        "stamp": verdict.get("stamp"),
        "sudo": verdict.get("sudo"),
        "findings": findings,
        "allowed_commands": PLAYBOOKS,
    }


def chat(system: str, user: str, model: str, base: str, key: str) -> str:
    url = base.rstrip("/") + "/chat/completions"
    body = json.dumps(
        {
            "model": model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:800]
        raise SystemExit(f"xAI HTTP {e.code}: {err}") from e
    except urllib.error.URLError as e:
        raise SystemExit(f"xAI network: {e}") from e
    choices = data.get("choices") or []
    if not choices:
        raise SystemExit(f"xAI empty response: {str(data)[:400]}")
    return (choices[0].get("message") or {}).get("content") or ""


def main() -> int:
    load_dotenv_env()
    args = sys.argv[1:]
    snapshot = None
    extra = []
    dry = False
    i = 0
    while i < len(args):
        if args[i] == "--snapshot" and i + 1 < len(args):
            snapshot = Path(args[i + 1])
            i += 2
            continue
        if args[i] == "--dry-run":
            dry = True
            i += 1
            continue
        if args[i] == "--ask" and i + 1 < len(args):
            extra.append(args[i + 1])
            i += 2
            continue
        i += 1

    if snapshot is None:
        data = Path(os.environ.get("KALIVED_DATA", ROOT))
        status = data / "logs" / "status"
        cands = sorted([p for p in status.iterdir() if (p / "verdict.json").is_file()], key=lambda p: p.name) if status.is_dir() else []
        if not cands:
            print("ingen verdict.json", file=sys.stderr)
            return 1
        snapshot = cands[-1]

    verd_path = snapshot / "verdict.json"
    if not verd_path.is_file():
        print(f"mangler {verd_path}", file=sys.stderr)
        return 1
    verdict = json.loads(verd_path.read_text(encoding="utf-8"))
    payload = redact(verdict)
    system = PROMPT.read_text(encoding="utf-8") if PROMPT.is_file() else "Du er kalived-advisor. Svar på bokmål."
    user = "Siste scan (redacted JSON):\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    if extra:
        user += "\n\nOperator spør:\n" + "\n".join(extra)

    if dry:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    key = os.environ.get("XAI_API_KEY") or ""
    if not key.strip():
        print("XAI_API_KEY mangler i ~/.config/kalived/env", file=sys.stderr)
        return 2
    model = os.environ.get("XAI_MODEL") or os.environ.get("CFG_AI_MODEL") or DEFAULT_MODEL
    base = os.environ.get("XAI_BASE_URL") or DEFAULT_BASE
    text = chat(system, user, model, base, key)
    out = snapshot / "advisor.md"
    out.write_text(text.strip() + "\n", encoding="utf-8")
    print(text.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
