"""FastAPI routes: every memory layer, always keyed by agent_id."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import memory as mem

router = APIRouter(prefix="/v1/memory", tags=["memory"])


def _aid(agent_id: str) -> str:
    try:
        return mem.check_agent(agent_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


def _layer(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ImportError as e:
        raise HTTPException(503, f"pakke mangler: {e}") from e
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)[:400]) from e


@router.get("")
def overview():
    return mem.status()


@router.post("/{agent_id}/ensure")
def ensure(agent_id: str):
    return _layer(mem.ensure, _aid(agent_id))


@router.get("/{agent_id}")
def bundle(agent_id: str):
    return mem.layers(_aid(agent_id))


class EpisodeIn(BaseModel):
    kind: str = "note"
    payload: dict = Field(default_factory=dict)


@router.post("/{agent_id}/episodes")
def add_episode(agent_id: str, body: EpisodeIn):
    return mem.remember_meta(_aid(agent_id), body.kind, body.payload)


@router.get("/{agent_id}/episodes")
def get_episodes(agent_id: str, limit: int = Query(default=50, ge=1, le=200)):
    return {"agent_id": agent_id, "episodes": mem.list_episodes(_aid(agent_id), limit)}


class EngramIn(BaseModel):
    kind: str = "note"
    payload: dict = Field(default_factory=dict)
    vector: list[float] | None = None
    rel_to: list[str] = Field(default_factory=list)


@router.post("/{agent_id}/engrams")
def add_engram(agent_id: str, body: EngramIn):
    return _layer(mem.remember_engram, _aid(agent_id), body.kind, body.payload, body.vector, body.rel_to)


@router.get("/{agent_id}/engrams/{memory_id}")
def get_engram(agent_id: str, memory_id: str):
    try:
        return mem.get_engram(_aid(agent_id), memory_id)
    except KeyError:
        raise HTTPException(404, "unknown memory_id") from None


class NodeIn(BaseModel):
    id: str
    kind: str = "entity"
    props: dict = Field(default_factory=dict)


class EdgeIn(BaseModel):
    src: str
    dst: str
    kind: str = "rel"
    props: dict = Field(default_factory=dict)


class CypherIn(BaseModel):
    cypher: str


@router.post("/{agent_id}/graph/nodes")
def add_node(agent_id: str, body: NodeIn):
    return _layer(mem.graph_node, _aid(agent_id), body.id, body.kind, body.props)


@router.post("/{agent_id}/graph/edges")
def add_edge(agent_id: str, body: EdgeIn):
    return _layer(mem.graph_edge, _aid(agent_id), body.src, body.dst, body.kind, body.props)


@router.post("/{agent_id}/graph/query")
def query_graph(agent_id: str, body: CypherIn):
    return _layer(mem.graph_query, _aid(agent_id), body.cypher)


class VectorIn(BaseModel):
    id: str
    vector: list[float]
    payload: dict = Field(default_factory=dict)


class VectorSearch(BaseModel):
    vector: list[float]
    limit: int = 8


@router.post("/{agent_id}/vectors")
def upsert_vector(agent_id: str, body: VectorIn):
    return _layer(mem.vector_upsert, _aid(agent_id), body.id, body.vector, body.payload)


@router.post("/{agent_id}/vectors/search")
def search_vector(agent_id: str, body: VectorSearch):
    return _layer(mem.vector_search, _aid(agent_id), body.vector, body.limit)


@router.put("/{agent_id}/blobs/{key:path}")
async def put_blob(agent_id: str, key: str, file: UploadFile = File(...)):
    data = await file.read()
    return _layer(mem.blob_put, _aid(agent_id), key, data, file.content_type or "application/octet-stream")


@router.get("/{agent_id}/blobs/{key:path}")
def get_blob(agent_id: str, key: str):
    data, ctype = _layer(mem.blob_get, _aid(agent_id), key)
    return Response(content=data, media_type=ctype)


class BusIn(BaseModel):
    message: str


@router.post("/{agent_id}/bus")
def publish_bus(agent_id: str, body: BusIn):
    return _layer(mem.bus_publish, _aid(agent_id), body.message)


@router.get("/{agent_id}/bus")
def recent_bus(agent_id: str, limit: int = 20):
    return _layer(mem.bus_recent, _aid(agent_id), limit)
