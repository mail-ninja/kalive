"""Chat sessions per project folder (docs/<navn> or apps/<navn>). Disk, not git."""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path

from .secrets_store import env_path

_PROJ = re.compile(r"^(docs|apps)/([^/]+)")
_WS = re.compile(r"^ws/([A-Za-z0-9._-]{1,64})$")
_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def root() -> Path:
    override = os.environ.get("KALIVED_SESSIONS")
    p = Path(override) if override else (env_path().parent / "sessions")
    p.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(p, 0o700)
    except OSError:
        pass
    return p


def project_of(path: str) -> str:
    """docs/mario/index.html → docs/mario. Eksternt workspace → ws/<mappenavn>."""
    s = (path or "").replace("\\", "/").lstrip("./")
    m = _PROJ.match(s)
    if m:
        name = m.group(2)
        if "." not in name:
            return f"{m.group(1)}/{name}"
    if _WS.match(s):
        return s
    from . import workspace as w

    if not w.is_kalived_repo():
        name = w.root().name
        if re.match(r"^[A-Za-z0-9._-]{1,64}$", name) and not name.startswith("."):
            return "ws/" + name
    return ""


def canonical(project: str) -> str:
    p = project_of(project or "")
    if p:
        return p
    s = (project or "").replace("\\", "/").strip("/")
    if _WS.match(s):
        return s
    return project_of(s + "/index.html")


def _key(project: str) -> str:
    p = project_of(project) or (project if _PROJ.match(project or "") or _WS.match(project or "") else "")
    if not p:
        raise ValueError("ugyldig prosjekt")
    return _SAFE.sub("-", p.replace("/", "--"))[:80]


def _dir(agent_id: str, project: str, mkdir: bool = True) -> Path:
    aid = re.sub(r"[^a-z0-9_-]", "", (agent_id or "build").lower())[:40] or "build"
    d = root() / aid / _key(project)
    if mkdir:
        d.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(d.parent, 0o700)
            os.chmod(d, 0o700)
        except OSError:
            pass
    return d


def _index_path(agent_id: str, project: str, mkdir: bool = True) -> Path:
    return _dir(agent_id, project, mkdir=mkdir) / "index.json"


def _sess_path(agent_id: str, project: str, sid: str, mkdir: bool = True) -> Path:
    if not re.match(r"^s_[a-z0-9]{6,32}$", sid or ""):
        raise ValueError("ugyldig session")
    return _dir(agent_id, project, mkdir=mkdir) / (sid + ".json")


def _read_json(p: Path, default):
    if not p.is_file():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(p: Path, obj) -> None:
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=0), encoding="utf-8")
    tmp.replace(p)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _title_from(hist: list) -> str:
    for m in hist or []:
        if isinstance(m, dict) and m.get("role") == "you":
            t = str(m.get("text") or "").strip().replace("\n", " ")
            return (t[:48] + "…") if len(t) > 48 else (t or "samtale")
    return "samtale"


def _meta(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "project": row.get("project"),
        "title": row.get("title") or "samtale",
        "created": row.get("created"),
        "used": row.get("used"),
        "n": int(row.get("n") or len(row.get("hist") or [])),
    }


def list_sessions(agent_id: str, project: str) -> list[dict]:
    p = project_of(project) or project
    idx = _read_json(_index_path(agent_id, p, mkdir=False), [])
    if not isinstance(idx, list):
        idx = []
    rows = [_meta(x) for x in idx if isinstance(x, dict) and x.get("id")]
    rows.sort(key=lambda r: str(r.get("used") or ""), reverse=True)
    return rows


def list_all(agent_id: str) -> list[dict]:
    """Alle prosjekter med samtaler, sist brukt øverst."""
    aid = re.sub(r"[^a-z0-9_-]", "", (agent_id or "build").lower())[:40] or "build"
    base = root() / aid
    if not base.is_dir():
        return []
    groups: list[dict] = []
    for d in base.iterdir():
        if not d.is_dir():
            continue
        idx = _read_json(d / "index.json", [])
        if not isinstance(idx, list):
            continue
        rows = [_meta(x) for x in idx if isinstance(x, dict) and x.get("id") and x.get("project")]
        if not rows:
            continue
        rows.sort(key=lambda r: str(r.get("used") or ""), reverse=True)
        groups.append(
            {
                "project": rows[0]["project"],
                "used": rows[0].get("used") or "",
                "sessions": rows,
            }
        )
    groups.sort(key=lambda g: str(g.get("used") or ""), reverse=True)
    return groups


def get_session(agent_id: str, project: str, sid: str) -> dict:
    p = project_of(project) or project
    body = _read_json(_sess_path(agent_id, p, sid, mkdir=False), None)
    if not isinstance(body, dict) or body.get("id") != sid:
        raise FileNotFoundError("session finnes ikke")
    return body


def create_session(agent_id: str, project: str, title: str = "", hist: list | None = None) -> dict:
    p = project_of(project) or project
    if not project_of(p):
        raise ValueError("ugyldig prosjekt")
    sid = "s_" + uuid.uuid4().hex[:12]
    now = _now()
    hist = list(hist or [])
    body = {
        "id": sid,
        "project": p,
        "title": (title or _title_from(hist) or "samtale")[:80],
        "created": now,
        "used": now,
        "hist": hist[:500],
        "n": len(hist[:500]),
    }
    _write_json(_sess_path(agent_id, p, sid), body)
    idx = list_sessions(agent_id, p)
    idx = [x for x in idx if x.get("id") != sid]
    idx.insert(0, _meta(body))
    _write_json(_index_path(agent_id, p), idx[:80])
    return body


def save_session(agent_id: str, project: str, sid: str, hist: list, title: str | None = None) -> dict:
    p = project_of(project) or project
    body = get_session(agent_id, p, sid)
    body["hist"] = list(hist or [])[:500]
    body["n"] = len(body["hist"])
    body["used"] = _now()
    if title:
        body["title"] = str(title)[:80]
    elif not body.get("title") or body.get("title") == "samtale":
        body["title"] = _title_from(body["hist"])
    _write_json(_sess_path(agent_id, p, sid), body)
    idx = [x for x in list_sessions(agent_id, p) if x.get("id") != sid]
    idx.insert(0, _meta(body))
    _write_json(_index_path(agent_id, p), idx[:80])
    return _meta(body)


def last_from_hist(hist: list | None, n: int = 2) -> list[dict]:
    """you/bot-par for fill_goal. Eldste først."""
    pairs: list[dict] = []
    user = asst = ""
    for m in hist or []:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        text = str(m.get("text") or "")
        if role == "you":
            if user or asst:
                pairs.append({"user": user, "assistant": asst})
            user, asst = text, ""
        elif role == "bot":
            asst = text
    if user or asst:
        pairs.append({"user": user, "assistant": asst})
    return pairs[-max(1, min(int(n or 2), 8)) :]
