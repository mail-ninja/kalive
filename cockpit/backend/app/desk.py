"""Arbeid-canvas: last snapshot so agents can read what the UI shows."""
from __future__ import annotations

import html as htmlmod
import threading

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

_lock = threading.Lock()
_state: dict = {
    "path": "untitled.md",
    "language": "markdown",
    "text": "// cockpit editor — monaco\n",
    "mode": "monaco",  # monaco | iframe
    "preview": "",
    "rev": 0,
}

router = APIRouter(prefix="/v1/desk", tags=["desk"])


def looks_html(text: str = "", path: str = "", language: str = "") -> bool:
    t = (text or "").lstrip().lower()
    lang = (language or "").lower()
    p = (path or "").lower()
    if lang in ("html", "htm"):
        return True
    if p.endswith((".html", ".htm")):
        return True
    return t.startswith("<!doctype html") or t.startswith("<html") or "<canvas" in t[:4000]


def snapshot() -> dict:
    with _lock:
        return dict(_state)


def apply(update: dict) -> dict:
    with _lock:
        if "path" in update and isinstance(update["path"], str):
            _state["path"] = update["path"][:240] or "untitled.md"
        if "language" in update and isinstance(update["language"], str):
            _state["language"] = update["language"][:40] or "markdown"
        if "text" in update and isinstance(update["text"], str):
            _state["text"] = update["text"][:400_000]
        if update.get("mode") in ("monaco", "iframe"):
            _state["mode"] = update["mode"]
        if "preview" in update and isinstance(update["preview"], str):
            _state["preview"] = update["preview"][:400_000]
        _state["rev"] = int(_state.get("rev") or 0) + 1
        return dict(_state)


def preview_body() -> tuple[str | None, str]:
    """Return (redirect_url | None, html)."""
    s = snapshot()
    prev = (s.get("preview") or "").strip()
    text = s.get("text") or ""
    if prev.startswith("http://127.0.0.1") or prev.startswith("https://127.0.0.1") or prev.startswith("http://localhost"):
        return prev, ""
    src = prev if looks_html(prev) else text
    if looks_html(src, s.get("path") or "", s.get("language") or ""):
        return None, src
    escaped = htmlmod.escape(src[:50_000] or "(tom canvas)")
    return None, (
        "<!doctype html><meta charset=utf-8><body style='margin:0;background:#0d1117;color:#c9d1d9;"
        "font:14px ui-monospace,monospace;padding:1rem'>"
        "<p style='color:#8b949e'>Ikke HTML — forge må <code>preview_set</code> med en HTML-fil "
        "(spill/app), ikke .py-spec i Monaco.</p><pre>"
        + escaped
        + "</pre></body>"
    )


@router.get("/preview")
def preview():
    loc, body = preview_body()
    if loc:
        return RedirectResponse(loc, status_code=302)
    return HTMLResponse(body, headers={"Cache-Control": "no-store"})


class PlayIn(BaseModel):
    text: str | None = None
    path: str | None = None
    language: str | None = None


@router.post("/play")
def play(body: PlayIn | None = None):
    s = snapshot()
    text = (body.text if body and body.text is not None else None) or s.get("preview") or s.get("text") or ""
    path = (body.path if body and body.path else None) or s.get("path") or "index.html"
    lang = (body.language if body and body.language else None) or s.get("language") or ""
    if looks_html(text, path, lang):
        return apply({"text": text, "preview": text, "mode": "iframe", "language": "html", "path": path})
    return apply({"text": text, "mode": "iframe", "path": path})
