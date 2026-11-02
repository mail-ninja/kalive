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
_ITERATE = re.compile(
    r"\b(gjør|fiks|legg til|oppdater|endre|patch|bedre|styggere|vanskeligere|pentere|zoom|boost)\b",
    re.I,
)
_SITE = re.compile(r"\b(webside|nettside|website|youtube|feed|blogg|portal|side)\b", re.I)
_PROJECT = re.compile(
    r"\b(3d|three\.?js|phaser|pixi|vite|npm|bun|cargo|svelte|pwa|motor|tjeneste|\bapi\b)\b",
    re.I,
)
_EXISTING_PATH = re.compile(r"\b((?:docs|apps)/[A-Za-z0-9][\w.-]*(?:/index\.html)?)", re.I)
_HYPHEN = re.compile(r"\b([a-z][a-z0-9]+(?:-[a-z0-9]+)+)\b")

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


def _folder_slug(q: str, noun: str | None) -> str | None:
    s = _slug(q) or (_slug(noun) if noun else None)
    if s:
        return s
    text = (noun or q or "").lower()
    m = _HYPHEN.search(text)
    if m:
        name = re.sub(r"-(videoer|videos|webside|nettside|side|klone|spill)$", "", m.group(1))
        if name in {"docs-mappa", "undermappe", "repo-url"} or name.startswith("docs-"):
            name = ""
        if name:
            return name[:40]
    if noun:
        tok = re.sub(r"[^a-z0-9]+", "-", noun.lower())
        tok = re.sub(r"-+", "-", tok).strip("-")
        if 3 <= len(tok) <= 40:
            return tok
    return None


def _norm_dir(p: str) -> str:
    s = (p or "").strip().rstrip("/")
    if s.endswith("/index.html"):
        s = s[: -len("/index.html")]
    return s


def _match_existing(slug: str, existing: list[str] | None) -> str:
    key = (slug or "").lower().replace("-", "")
    if not key:
        return ""
    for e in existing or []:
        name = _norm_dir(str(e)).split("/")[-1].lower().replace("-", "")
        if name == key or key in name or name in key:
            return _norm_dir(str(e))
    return ""


def _path_in_text(*texts: str) -> str:
    for t in texts:
        m = _EXISTING_PATH.search(t or "")
        if m:
            return _norm_dir(m.group(1))
    return ""


def fill_goal(
    user: str,
    prior: list[dict] | None = None,
    existing: list[str] | None = None,
) -> dict[str, Any]:
    """Resolve this turn against the last chats. Fill path/scope when the prompt is thin."""
    q = str(user or "").strip()
    prior = [p for p in (prior or []) if isinstance(p, dict)]
    last = prior[-1] if prior else {}
    prior_user = str(last.get("user") or "")
    prior_asst = str(last.get("assistant") or "")
    ape = is_ape(q)
    noun = _ape_noun(q) if ape else None
    slug = _folder_slug(q, noun)
    git = looks_like_git_clone(q)
    blocked = bool(_BLOCKED.search(prior_asst))
    retry = bool(blocked and (_HAKE.search(q) or is_anaphor(q)))
    iterate_verb = bool(_ITERATE.search(q) and prior_user)
    follow = bool(prior_user and (is_anaphor(q) or retry or iterate_verb) and not ape)
    if (retry or follow) and prior_user:
        ps = _folder_slug(prior_user, None) or _slug(prior_user)
        if ps:
            slug = ps
    elif not slug and not ape:
        slug = _folder_slug(prior_user, None) or _slug(prior_user)
    product = bool((_PRODUCT_HINT.search(q) or slug in GAMES or ape or _SITE.search(q)) and not git)
    if not product and slug and not git:
        product = True
    vague = bool(ape or _VAGUE.search(q) or (_BUILD.search(q) and len(q) < 220))
    site = bool(_SITE.search(q) or _SITE.search(prior_user))
    project = bool(_PROJECT.search(q))
    mix = bool(site and (slug in GAMES or _PRODUCT_HINT.search(q) or re.search(r"\b(rik|penger|mynt|empire)\b", q, re.I)))

    hit = _match_existing(slug or "", existing) if slug else ""
    if follow and not hit:
        hit = _path_in_text(prior_asst, prior_user)
        if hit and existing:
            hit = _match_existing(hit.split("/")[-1], existing) or hit
    iterate = bool(follow and (hit or iterate_verb))

    path = ""
    if iterate and hit:
        path = hit if hit.endswith(".html") else f"{hit}/index.html"
        if hit.startswith("apps/") and not hit.endswith(".html"):
            path = hit
    elif product and slug and not git:
        if project:
            path = f"apps/{slug}/"
        else:
            path = f"docs/{slug}/index.html"

    kind = "fresh"
    if retry:
        kind = "retry_mutate"
    elif iterate or follow:
        kind = "followup"
    elif ape:
        kind = "ape"
    elif vague and product:
        kind = "gapfill"

    goal = q
    if iterate and prior_user:
        goal = f"{prior_user.strip()} — patch {path or hit or 'samme mappe'}. Denne turen: {q}"
    elif ape and slug:
        goal = f"Lag {slug} i {path or 'docs/' + slug + '/'}. Preview i iframe. Operator skrev: {q}"
    elif follow and prior_user:
        goal = f"{prior_user.strip()} — fortsett ({path or slug}). Denne turen: {q}"

    hints: list[str] = []
    if iterate:
        hints.append("Produktet finnes. Patch med repo_edit. Ikke ny klone ved siden av.")
    if ape and not iterate:
        hints.append(
            "Ape-prompt: det er hele oppgaven. Fyll det operatoren sa. "
            "Blanding er lov. Ikke spør. Ikke les NOW/NEXT/README."
        )
    if mix:
        hints.append("Blanding er meningen (f.eks. side + bli rik). Ikke rens vekk den ene.")
    elif site and not (slug in GAMES):
        hints.append("Dette er en side. Spill-HUD bare hvis operatoren ba om det.")
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
    if project and path.startswith("apps/"):
        hints.append(
            f"Tyngre stabel: {path}. Lokal toolchain der (npm/bun/pip/cargo/vendor). "
            "Ikke npm i workspace-roten. Ikke CDN. preview_serve med line på 127.0.0.1."
        )
    elif path:
        if iterate:
            hints.append(f"Patch {path}.")
        else:
            hints.append(f"Skriv {path} (lag mappa om den mangler). HTML på disk åpner preview.")
    mech = GAMES.get((slug or "").replace("-", ""))
    if mech and not site:
        hints.append("Palette (ikke bur): " + mech)
    if (vague or ape) and product and not iterate:
        hints.append("Fyll hull selv. Preview i iframe. Ikke NEEDS_INPUT for smak.")
    if follow or retry:
        hints.append("«den»/«klonen»/«huket av»/«gjør X» peker på forrige tur.")

    write_now = bool(retry or ape or iterate or (product and (vague or follow) and not git))
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
        "iterate": iterate,
        "mix": mix,
        "project": project,
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
