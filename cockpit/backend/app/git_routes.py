"""HTTP for the cockpit Git tab."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import git_panel as g

router = APIRouter(prefix="/v1/git", tags=["git"])


class PathsIn(BaseModel):
    paths: list[str] = Field(default_factory=list)


class CommitIn(BaseModel):
    message: str = ""
    paths: list[str] = Field(default_factory=list)


class RemoteIn(BaseModel):
    remote: str = ""
    branch: str = ""


class TokenIn(BaseModel):
    token: str = ""


def _or_err(row: dict):
    if row.get("error"):
        raise HTTPException(400, row["error"])
    return row


@router.get("/status")
def git_status():
    return _or_err(g.status())


@router.get("/log")
def git_log(n: int = 12):
    return _or_err(g.log(n=n))


@router.post("/stage")
def git_stage(body: PathsIn):
    return _or_err(g.stage(body.paths, unstage=False))


@router.post("/unstage")
def git_unstage(body: PathsIn):
    return _or_err(g.stage(body.paths, unstage=True))


@router.post("/commit")
def git_commit(body: CommitIn):
    return _or_err(g.commit(body.message, body.paths or None))


@router.post("/push")
def git_push(body: RemoteIn):
    return _or_err(g.push(remote=body.remote, branch=body.branch))


@router.post("/pull")
def git_pull(body: RemoteIn):
    return _or_err(g.pull(remote=body.remote, branch=body.branch))


@router.get("/github")
def git_github():
    return g.github_who()


@router.put("/github")
def git_github_login(body: TokenIn):
    return _or_err(g.github_login(body.token))


@router.delete("/github")
def git_github_logout():
    return g.github_logout()
