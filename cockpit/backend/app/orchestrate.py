"""When the build loop should stop. Pure. No I/O."""
from __future__ import annotations

from typing import Any

SEE = frozenset({"repo_glob", "repo_grep", "repo_read", "ping", "repo_git"})
EDIT = frozenset({"repo_edit", "repo_write", "iframe_write"})
SHORT_DONE = (
    "Svar på under 8 setninger. DONE / NEEDS_INPUT / BLOCKED. Ingen essay. Ingen nye tools."
)
NUDGE_DONE = (
    "Verifikasjon OK. Hvis oppgaven er ferdig: svar DONE uten tools. "
    "Ett fiks-kall bare hvis noe konkret mangler. Ikke grep/glob mer."
)


def is_see(name: str, args: dict | None = None) -> bool:
    n = str(name or "")
    if n == "repo_git":
        return str((args or {}).get("action") or "status") != "commit"
    return n in SEE


def is_edit(name: str, args: dict | None = None) -> bool:
    n = str(name or "")
    if n == "repo_git":
        return str((args or {}).get("action") or "") == "commit"
    return n in EDIT


def is_verify(name: str, result: dict | None) -> bool:
    if not isinstance(result, dict) or result.get("error"):
        return False
    n = str(name or "")
    if n == "repo_bash":
        return result.get("exit_code") == 0 and not result.get("cancelled")
    if n == "preview_serve":
        return bool(result.get("listening") or result.get("url"))
    if n == "preview_set":
        return bool(result.get("preview") or result.get("url") or result.get("ok"))
    if n == "repo_git" and result.get("ok") and result.get("action") == "commit":
        return True
    return False


def is_fail(name: str, result: dict | None) -> bool:
    if not isinstance(result, dict):
        return False
    n = str(name or "")
    if result.get("error"):
        return n in {"repo_bash", "repo_edit", "repo_write", "preview_serve", "preview_set", "repo_git"}
    if n == "repo_bash":
        code = result.get("exit_code")
        return code not in (0, None) or bool(result.get("timeout"))
    return False


def only_see(names: list[str], args_list: list[dict] | None = None) -> bool:
    if not names:
        return False
    args_list = list(args_list or [])
    while len(args_list) < len(names):
        args_list.append({})
    return all(is_see(n, a) for n, a in zip(names, args_list))


def next_brake(
    *,
    verified: bool,
    see_streak: int,
    names: list[str],
    args_list: list[dict] | None = None,
    got_verify: bool,
    got_edit: bool,
    got_fail: bool,
) -> dict[str, Any]:
    """After one tool-round: maybe nudge, maybe force a short DONE."""
    streak = see_streak
    v = verified
    if got_fail:
        v, streak = False, 0
    elif got_verify:
        v, streak = True, 0
    elif got_edit:
        v, streak = False, 0
    elif v and only_see(names, args_list):
        streak = see_streak + 1
    force = bool(v and streak >= 1)
    nudge = bool(got_verify and not force)
    return {
        "verified": v,
        "see_streak": streak,
        "force_stop": force,
        "nudge": nudge,
    }
