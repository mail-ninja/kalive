"""Follow-up continuity and gap-fill for the build loop. Pure. No I/O."""
from __future__ import annotations

import re
from typing import Any

_ANAPHOR = re.compile(
    r"\b(den|det|klonen|klone|samme|fortsett|igjen|denne|huket|haken|oppgaven)\b",
    re.I,
)
_GIT_CLONE = re.compile(
    r"("
    r"\bgit\s+clone\b"
    r"|clone\s+https?://"
    r"|https?://[^\s]+/(?:\.git)?"
    r"|git@[\w.-]+:"
    r"|\brepo-url\b"
    r"|\bklone\s+(repoet|repositoriet|git)\b"
    r")",
    re.I,
)
_GIT_ASK = re.compile(r"(repo-url|git clone|hvilken repo|github\.com|gitlab\.)", re.I)
_PRODUCT_HINT = re.compile(
    r"\b(pac-?man|crack-?man|mario|tetris|snake|pong|breakout|flappy|spill|app|klone|prototype|demo|kanban)\b",
    re.I,
)
_BLOCKED = re.compile(r"\bBLOCKED\b", re.I)
_HAKE = re.compile(r"\b(huket|haken|agent får kjøre|den er huket)\b", re.I)
_VAGUE = re.compile(
    r"(detaljene er opp til deg|kjør på|bare bygg|fyll inn|som du vil)",
    re.I,
)
_BUILD = re.compile(r"\b(lag |bygg |skriv |lag en|bygg en|make )\b", re.I)
_DOCS_SUB = re.compile(r"\b(undermappe|under\s+docs|i docs|docs-mappa|docs/)\b", re.I)
_SLUG = re.compile(
    r"\b(pac-?man|crack-?man|mario|tetris|snake|pong|breakout|flappy|kanban|todo)\b",
    re.I,
)
_APE = re.compile(
    r"^\s*(?:ok[,.]?\s+|please\s+)?(?:lag(?:\s+en|\s+et)?|bygg(?:\s+en|\s+et)?|skriv|make)\s+(.+?)\s*$",
    re.I,
)
_BARE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_-]{1,24})!+\s*$")
_FILLER = re.compile(r"\b(en|et|ei|klone|klonen|spill|spillet|app|appen|prototype|demo)\b", re.I)

GAMES = {
    "tetris": "fallende tetrominoer, rotasjon, linjerydding, neste brikke, poeng, økende fart, game over. Piltaster/WASD.",
    "snake": "rutenett, slangen vokser, mat, vegg/hale dreper, poeng, piltaster.",
    "pong": "to padler, ball, poeng, piltaster / W S.",
    "breakout": "padle, ball, klosser, liv, poeng.",
    "pacman": "labyrint, prikker, spøkelser, power, poeng. Brettet må kunne vinnes (alle prikker nåbare).",
    "crackman": "labyrint, piller, fiender, poeng. Brettet må kunne vinnes.",
    "mario": "side-scroller, tyngdekraft, hopp, fiender, mynter, mål/flagg som kan nås.",
    "flappy": "hopp, rør, poeng, gravitasjon, space/klikk.",
    "kanban": "HTML-tavle, kolonner, kort, localStorage.",
}


def _norm_slug(raw: str) -> str:
    s = (raw or "").lower().replace("-", "")
    if s in {"pacman", "crackman"}:
        return s
    return s


def _slug(text: str) -> str | None:
    m = _SLUG.search(text or "")
    if not m:
        return None
    return _norm_slug(m.group(1)) or None


def _ape_noun(q: str) -> str | None:
    m = _APE.match(q or "")
    if m:
        noun = _FILLER.sub(" ", m.group(1))
        noun = re.sub(r"[!?.,]+$", "", noun).strip()
        noun = re.sub(r"\s+", " ", noun)
        return noun or None
    m2 = _BARE.match(q or "")
    if m2:
        return m2.group(1)
    return None


def is_ape(q: str) -> bool:
    q = str(q or "").strip()
    if not q or looks_like_git_clone(q):
        return False
    if _BARE.match(q) and _slug(q):
        return True
    if _APE.match(q) and len(q) <= 80:
        return True
    return bool(_BUILD.search(q) and len(q) <= 48)


def is_anaphor(text: str) -> bool:
    return bool(_ANAPHOR.search(text or ""))


def looks_like_git_clone(text: str) -> bool:
    return bool(_GIT_CLONE.search(text or ""))


def fill_goal(user: str, prior: list[dict] | None = None) -> dict[str, Any]:
    """Resolve this turn against the last chats. Fill path/scope when the prompt is thin."""
    q = str(user or "").strip()
    prior = [p for p in (prior or []) if isinstance(p, dict)]
    last = prior[-1] if prior else {}
    prior_user = str(last.get("user") or "")
    prior_asst = str(last.get("assistant") or "")
    ape = is_ape(q)
    noun = _ape_noun(q) if ape else None
    slug = _slug(q) or ( _slug(noun) if noun else None )
    if not slug and noun:
        tok = re.sub(r"[^a-z0-9]+", "", noun.lower())
        if 3 <= len(tok) <= 24:
            slug = tok
    if not slug and not ape:
        slug = _slug(prior_user)
    git = looks_like_git_clone(q)
    product = bool((_PRODUCT_HINT.search(q) or slug in GAMES or ape) and not git)
    if not product and slug and not git:
        product = True
    blocked = bool(_BLOCKED.search(prior_asst))
    retry = bool(blocked and (_HAKE.search(q) or is_anaphor(q)))
    follow = bool(prior_user and (is_anaphor(q) or retry) and not ape)
    vague = bool(ape or _VAGUE.search(q) or (_BUILD.search(q) and len(q) < 220))
    docs_sub = bool(_DOCS_SUB.search(q) or (not ape and _DOCS_SUB.search(prior_user)))

    path = ""
    if product and slug and not git:
        path = f"docs/{slug}/index.html"

    kind = "fresh"
    if retry:
        kind = "retry_mutate"
    elif follow:
        kind = "followup"
    elif ape:
        kind = "ape"
    elif vague and product:
        kind = "gapfill"

    goal = q
    if ape and slug:
        goal = (
            f"Lag et spillbart {slug} i {path or 'docs/' + slug + '/index.html'}. "
            f"HTML på disk, iframe-preview, tastatur, vinn/tap, HUD. "
            f"Operator skrev bare: {q}"
        )
    elif follow and prior_user:
        extra = []
        if slug:
            extra.append(slug)
        if path:
            extra.append("i " + path)
        if docs_sub and path:
            extra.append("mappe under docs/")
        suffix = (" (" + ", ".join(extra) + ")") if extra else ""
        goal = f"{prior_user.strip()} — fortsett{suffix}. Denne turen: {q}"

    hints: list[str] = []
    if ape:
        hints.append(
            "Ape-prompt: det er hele oppgaven. Fyll kode, styring, vinn/tap, HUD, iframe. "
            "Ikke spør. Ikke les NOW/NEXT/README."
        )
    if product and not git:
        hints.append(
            "Dette er en produktklone i workspace, ikke git clone. "
            "Ikke spør om repo-URL."
        )
    if retry:
        hints.append(
            "Forrige tur var BLOCKED på haken. Skriv samme fil med repo_write nå. "
            "Ikke ritual-les README/NOW/NEXT."
        )
    if path:
        hints.append(f"Skriv {path} (lag mappa om den mangler). HTML på disk åpner preview.")
    mech = GAMES.get(slug or "")
    if mech:
        hints.append("Sjanger: " + mech)
    if (vague or ape) and product:
        hints.append(
            "Fyll hull selv: ferdig spillbart artifact, poeng, tastatur, iframe-preview. "
            "Ikke NEEDS_INPUT for smak."
        )
    if follow or retry:
        hints.append("«den»/«klonen»/«huket av» peker på forrige tur, ikke en ny oppgave.")

    write_now = bool(retry or ape or (product and (vague or follow) and not git))
    return {
        "goal": goal[:1200],
        "kind": kind,
        "path": path,
        "slug": slug or "",
        "hints": hints,
        "write_now": write_now,
        "product_not_git": bool(product and not git),
        "retry_mutate": retry,
        "followup": follow,
        "ape": ape,
    }


def prior_messages(prior: list[dict] | None, intent: dict | None = None) -> list[dict[str, str]]:
    """One previous user/assistant pair, sanitized so a bad NEEDS_INPUT cannot stick."""
    intent = intent or {}
    if intent.get("ape"):
        return []
    prior = [p for p in (prior or []) if isinstance(p, dict)]
    if not prior:
        return []
    last = prior[-1]
    user = str(last.get("user") or "").strip()[:1500]
    asst = str(last.get("assistant") or "").strip()
    if not user:
        return []
    if intent.get("product_not_git") and _GIT_ASK.search(asst):
        asst = (
            "Forrige tur misforsto «klone» som git clone. "
            "Fortsett produktklonen. Ikke spør om URL."
        )
    elif _BLOCKED.search(asst):
        asst = asst[:500]
    else:
        asst = asst[:800] or "(ingen svar)"
    return [
        {"role": "user", "content": user},
        {"role": "assistant", "content": asst},
    ]


def format_intent(intent: dict | None) -> str:
    if not isinstance(intent, dict) or not intent.get("goal"):
        return ""
    title = "Ape-prompt — utfylt" if intent.get("ape") else "Oppgave (utfylt fra denne og forrige tur)"
    lines = ["## " + title]
    lines.append("Mål: " + str(intent.get("goal") or "")[:500])
    path = str(intent.get("path") or "")
    if path:
        lines.append("Fil: " + path)
    for h in intent.get("hints") or []:
        lines.append("- " + str(h))
    if intent.get("write_now"):
        lines.append("Skriv fila nå. Maks 4 see-tools.")
    return "\n".join(lines)
