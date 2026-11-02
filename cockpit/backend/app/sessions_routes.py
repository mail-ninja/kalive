"""HTTP for project chat sessions."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from . import sessions as sess
from .memory import check_agent

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


def _aid(agent_id: str) -> str:
    try:
        return check_agent(agent_id or "build")
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


def _proj(project: str) -> str:
    p = sess.canonical(project)
    if not p:
        raise HTTPException(400, "ugyldig prosjekt — docs/<navn> eller apps/<navn>")
    return p


class SessionIn(BaseModel):
    agent: str = "build"
    project: str
    title: str = ""
    hist: list = Field(default_factory=list)


class SessionSave(BaseModel):
    agent: str = "build"
    project: str
    hist: list = Field(default_factory=list)
    title: str = ""


@router.get("")
def list_sessions(project: str | None = Query(default=None), agent: str = Query(default="build")):
    aid = _aid(agent)
    if not project:
        return {"projects": sess.list_all(aid)}
    p = _proj(project)
    return {"project": p, "sessions": sess.list_sessions(aid, p)}


@router.post("")
def create(body: SessionIn):
    p = _proj(body.project)
    try:
        row = sess.create_session(_aid(body.agent), p, title=body.title, hist=body.hist)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return row


@router.get("/{sid}")
def get_one(sid: str, project: str = Query(...), agent: str = Query(default="build")):
    p = _proj(project)
    try:
        return sess.get_session(_aid(agent), p, sid)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(404, str(e)) from e


@router.put("/{sid}")
def save(sid: str, body: SessionSave):
    p = _proj(body.project)
    try:
        return sess.save_session(_aid(body.agent), p, sid, body.hist, title=body.title or None)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(404, str(e)) from e
