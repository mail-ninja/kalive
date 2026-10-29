"""When the build loop should stop. Pure. No I/O."""
from __future__ import annotations

from typing import Any

SEE = frozenset({"repo_glob", "repo_grep", "repo_read", "ping", "repo_git"})
EDIT = frozenset({"repo_edit", "repo_write", "iframe_write"})
WRITE_KEEP = frozenset(
    {"repo_write", "repo_edit", "repo_bash", "preview_serve", "preview_set", "repo_git"}
)
SEE_CAP = 4
WRITE_NUDGE_AT = 3
SHORT_DONE = (
    "Svar på under 8 setninger. DONE / NEEDS_INPUT / BLOCKED. Ingen essay. Ingen nye tools."
)
NUDGE_DONE = (
    "Verifikasjon OK. Hvis oppgaven er ferdig: svar DONE uten tools. "
    "Ett fiks-kall bare hvis noe konkret mangler. Ikke grep/glob mer."
)
NUDGE_WRITE = (
    "Du har lest nok. Skriv fila nå med repo_write (ny fil) eller repo_edit (patch). "
    "Ikke glob/grep/read mer. Ikke spør om git-URL med mindre operator sa git clone. "
    "Fyll hull selv: mappe, filnavn, ferdig artifact + preview."
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
    see_only_count: int = 0,
) -> dict[str, Any]:
    """After one tool-round: maybe nudge, maybe force a short DONE, maybe force a write."""
    streak = see_streak
    v = verified
    see_n = int(see_only_count or 0)
    seeing = only_see(names, args_list)
    if got_fail:
        v, streak, see_n = False, 0, 0
    elif got_verify:
        v, streak, see_n = True, 0, 0
    elif got_edit:
        v, streak, see_n = False, 0, 0
    elif seeing:
        see_n = see_n + 1
        if v:
            streak = see_streak + 1
    else:
        see_n = 0
    force = bool(v and streak >= 1)
    nudge = bool(got_verify and not force)
    write_nudge = bool((not v) and see_n >= WRITE_NUDGE_AT and not force)
    see_cap_hit = bool((not v) and see_n >= SEE_CAP and not force)
    return {
        "verified": v,
        "see_streak": streak,
        "see_only_count": see_n,
        "force_stop": force,
        "nudge": nudge,
        "write_nudge": write_nudge,
        "see_cap_hit": see_cap_hit,
    }
