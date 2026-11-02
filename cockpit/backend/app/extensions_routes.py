"""HTTP for the Extensions tab (Open VSX / VSIX)."""
from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from . import extensions as ext

router = APIRouter(prefix="/v1/extensions", tags=["extensions"])


class InstallIn(BaseModel):
    namespace: str = ""
    name: str = ""
    version: str = ""
    vsix_b64: str = ""


class EnableIn(BaseModel):
    enabled: bool = True


def _or_err(row: dict):
    if row.get("error"):
        raise HTTPException(400, row["error"])
    return row


@router.get("")
def list_ext():
    return ext.list_installed()


@router.get("/search")
def search_ext(q: str = Query(default=""), size: int = Query(default=16)):
    return _or_err(ext.search(q, size=size))


@router.post("/install")
def install_ext(body: InstallIn):
    if (body.vsix_b64 or "").strip():
        raw = body.vsix_b64.strip()
        if "," in raw and raw.lower().startswith("data:"):
            raw = raw.split(",", 1)[1]
        try:
            data = base64.b64decode(raw, validate=False)
        except Exception as e:
            raise HTTPException(400, f"ugyldig vsix: {e}") from e
        return _or_err(ext.install_vsix(data, source="upload"))
    if body.namespace and body.name:
        return _or_err(ext.install_openvsx(body.namespace, body.name, body.version))
    raise HTTPException(400, "oppgi namespace+name eller vsix_b64")


@router.post("/{eid}/enable")
def enable_ext(eid: str, body: EnableIn):
    return _or_err(ext.set_enabled(eid, body.enabled))


@router.delete("/{eid}")
def remove_ext(eid: str):
    return _or_err(ext.uninstall(eid))
