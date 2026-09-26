"""Agent-scoped memory. One root, one namespace per agent_id. Layers optional."""
from __future__ import annotations

import json
import re
import socket
import sqlite3
import uuid
from pathlib import Path

import httpx

from .secrets_store import env_path

AID = re.compile(r"^[a-z][a-z0-9_-]{0,40}$")
ROOT = env_path().parent / "memory"
QDRANT = "http://127.0.0.1:6333"
REDIS_HOST, REDIS_PORT = "127.0.0.1", 6379
MINIO_HOST, MINIO_PORT = "127.0.0.1", 9100
MINIO_USER, MINIO_PASS = "kalived", "kalived-minio"


def check_agent(agent_id: str) -> str:
    if not AID.match(agent_id):
        raise ValueError(f"ugyldig agent_id: {agent_id}")
    return agent_id


def agent_dir(agent_id: str) -> Path:
    p = ROOT / check_agent(agent_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def ns(agent_id: str) -> str:
    return f"kalived:{check_agent(agent_id)}"


def _port_up(port: int, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def _sqlite(agent_id: str) -> Path:
    db = agent_dir(agent_id) / "episodes.sqlite"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE IF NOT EXISTS episodes ("
        "id INTEGER PRIMARY KEY, memory_id TEXT UNIQUE, kind TEXT, payload TEXT, "
        "ts DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )
    cols = {row[1] for row in con.execute("PRAGMA table_info(episodes)")}
    if "memory_id" not in cols:
        con.execute("ALTER TABLE episodes ADD COLUMN memory_id TEXT")
    con.commit()
    con.close()
    return db


def layers(agent_id: str) -> dict:
    check_agent(agent_id)
    d = agent_dir(agent_id)
    coll = "kalived_" + agent_id.replace("-", "_")
    bucket = "kalived-" + agent_id.replace("_", "-")
    return {
        "agent_id": agent_id,
        "ns": ns(agent_id),
        "root": str(d),
        "graph": {
            "engine": "kuzu",
            "path": str(d / "graph.kuzu"),
            "role": "langtids relasjoner (Cypher)",
            "up": _kuzu_ok(d / "graph.kuzu"),
        },
        "vector": {
            "engine": "qdrant",
            "url": QDRANT,
            "collection": coll,
            "role": "semantisk recall",
            "up": _port_up(6333),
        },
        "meta": {
            "engine": "sqlite",
            "path": str(d / "episodes.sqlite"),
            "role": "episode-index",
            "up": True,
        },
        "blob": {
            "engine": "minio",
            "url": f"http://{MINIO_HOST}:{MINIO_PORT}",
            "bucket": bucket,
            "role": "bildeminne / filer",
            "up": _port_up(9100),
        },
        "bus": {
            "engine": "redis",
            "url": f"redis://{REDIS_HOST}:{REDIS_PORT}/0",
            "channel": ns(agent_id),
            "role": "nervesystem (korttids + agent↔agent)",
            "up": _port_up(6379),
        },
    }


def _kuzu_ok(path: Path) -> bool:
    try:
        import kuzu  # noqa: F401
    except ImportError:
        return False
    return path.exists()


def status() -> dict:
    from .agents import all_agents

    return {
        "compose": "docker compose -f cockpit/memory/compose.yml up -d",
        "root": str(ROOT),
        "note": "alt under ~/.config/kalived/memory/<agent_id>/  +  docker-tjenester namespacet kalived:{agent_id}",
        "backends": {
            "kuzu": _kuzu_import(),
            "qdrant": _port_up(6333),
            "redis": _port_up(6379),
            "minio": _port_up(9100),
            "sqlite": True,
        },
        "agents": [layers(a.id) for a in all_agents()],
        "embedder": __import__("app.embedder", fromlist=["status"]).status(),
    }


def _kuzu_import() -> bool:
    try:
        import kuzu  # noqa: F401

        return True
    except ImportError:
        return False


def ensure(agent_id: str) -> dict:
    """Full stack for this agent. Same five layers every time. Never a subset by design."""
    check_agent(agent_id)
    d = agent_dir(agent_id)
    _sqlite(agent_id)
    out: dict = {"agent_id": agent_id, "root": str(d), "ok": [], "skip": []}
    try:
        _graph_init(agent_id)
        out["ok"].append("graph")
    except Exception as e:
        out["skip"].append({"graph": str(e)})
    try:
        _qdrant_ensure(agent_id)
        out["ok"].append("vector")
    except Exception as e:
        out["skip"].append({"vector": str(e)})
    try:
        _minio_ensure(agent_id)
        out["ok"].append("blob")
    except Exception as e:
        out["skip"].append({"blob": str(e)})
    if _port_up(6379):
        out["ok"].append("bus")
    else:
        out["skip"].append({"bus": "redis :6379 nede"})
    out["ok"].append("meta")
    out["layers"] = layers(agent_id)
    return out


def remember_meta(agent_id: str, kind: str, payload: dict, memory_id: str | None = None) -> dict:
    mid = memory_id or str(uuid.uuid4())
    body = dict(payload)
    body.setdefault("memory_id", mid)
    body.setdefault("agent_id", agent_id)
    db = _sqlite(agent_id)
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO episodes (memory_id, kind, payload) VALUES (?, ?, ?)",
        (mid, kind, json.dumps(body, ensure_ascii=False)),
    )
    con.commit()
    eid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.close()
    return {"id": eid, "memory_id": mid, "agent_id": agent_id, "kind": kind, "path": str(db)}


def _payload_text(payload: dict) -> str:
    bits = []
    for k in ("user", "assistant", "text", "path", "name", "excerpt"):
        v = payload.get(k)
        if v:
            bits.append(str(v))
    if not bits:
        bits.append(json.dumps(payload, ensure_ascii=False)[:800])
    return " ".join(bits)


def cheap_vec(text: str) -> list[float]:
    """384-d embedding. Local MiniLM via fastembed; hash fallback."""
    from .embedder import embed_one

    return embed_one(text)


_STOP = {
    "the",
    "and",
    "for",
    "not",
    "med",
    "som",
    "det",
    "den",
    "til",
    "en",
    "er",
    "på",
    "av",
    "og",
    "i",
    "jeg",
    "du",
}


def recall(agent_id: str, query: str, limit: int = 6) -> list[dict]:
    """Keyword sqlite + cheap qdrant. Workspace on disk still wins over this."""
    check_agent(agent_id)
    q = (query or "").strip()
    if not q:
        return list_episodes(agent_id, limit=min(limit, 4))
    tokens = [t for t in re.findall(r"[a-zA-Z0-9_./-]{3,}", q.lower()) if t not in _STOP]
    scored: dict[str, tuple[float, dict]] = {}
    for e in list_episodes(agent_id, limit=80):
        blob = json.dumps(e.get("payload") or {}, ensure_ascii=False).lower()
        score = float(sum(1 for t in tokens if t in blob)) if tokens else 0.2
        mid = str(e.get("memory_id") or e.get("id"))
        scored[mid] = (score, e)
    try:
        vs = vector_search(agent_id, cheap_vec(q), limit=8)
        for i, h in enumerate(vs.get("hits") or []):
            pay = h.get("payload") or {}
            mid = str(pay.get("memory_id") or h.get("id") or "")
            if not mid:
                continue
            bonus = 1.5 - i * 0.1
            if mid in scored:
                s, e = scored[mid]
                scored[mid] = (s + bonus, e)
            else:
                try:
                    scored[mid] = (bonus, get_engram(agent_id, mid))
                except KeyError:
                    pass
    except Exception:
        pass
    ranked = sorted(scored.values(), key=lambda x: -x[0])
    out = []
    for score, e in ranked:
        if score <= 0:
            continue
        item = dict(e)
        item["score"] = round(score, 2)
        out.append(item)
        if len(out) >= limit:
            break
    if not out:
        return list_episodes(agent_id, limit=min(limit, 3))
    return out


def format_recall(hits: list[dict], budget: int = 1600) -> str:
    if not hits:
        return ""
    lines = ["## Minne (tidligere episoder — workspace på disk vinner ved konflikt)"]
    used = 0
    for h in hits:
        p = h.get("payload") or {}
        user = str(p.get("user") or "")[:220]
        asst = str(p.get("assistant") or p.get("excerpt") or p.get("text") or "")[:220]
        kind = h.get("kind") or p.get("kind") or "?"
        line = f"- [{kind}] {user}"
        if asst:
            line += f" → {asst}"
        if used + len(line) > budget:
            break
        lines.append(line)
        used += len(line)
    return "\n".join(lines) if len(lines) > 1 else ""


def remember_engram(
    agent_id: str,
    kind: str,
    payload: dict | None = None,
    vector: list[float] | None = None,
    rel_to: list[str] | None = None,
) -> dict:
    """One UUID into every layer that is up. That id is how stores point at each other."""
    check_agent(agent_id)
    ensure(agent_id)
    mid = str(uuid.uuid4())
    body = dict(payload or {})
    body["memory_id"] = mid
    body["agent_id"] = agent_id
    wrote = ["meta"]
    skipped = []
    remember_meta(agent_id, kind, body, memory_id=mid)
    try:
        graph_node(agent_id, mid, kind, body)
        graph_node(agent_id, f"agent:{agent_id}", "agent", {"agent_id": agent_id})
        graph_edge(agent_id, f"agent:{agent_id}", mid, "OWNS")
        for other in rel_to or []:
            graph_edge(agent_id, mid, other, "REL")
        wrote.append("graph")
    except Exception as e:
        skipped.append({"graph": str(e)[:200]})
    try:
        vec = vector or cheap_vec(_payload_text(body))
        vector_upsert(
            agent_id,
            mid,
            vec,
            {"kind": kind, "memory_id": mid, "agent_id": agent_id, "text": _payload_text(body)[:400]},
        )
        wrote.append("vector")
    except Exception as e:
        skipped.append({"vector": str(e)[:200]})
    try:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        if len(raw) <= 80_000:
            blob_put(agent_id, f"engrams/{mid}.json", raw, "application/json")
            wrote.append("blob")
    except Exception as e:
        skipped.append({"blob": str(e)[:200]})
    try:
        bus_publish(agent_id, json.dumps({"memory_id": mid, "kind": kind, "agent_id": agent_id}))
        wrote.append("bus")
    except Exception as e:
        skipped.append({"bus": str(e)[:200]})
    return {"memory_id": mid, "agent_id": agent_id, "kind": kind, "wrote": wrote, "skip": skipped}


def get_engram(agent_id: str, memory_id: str) -> dict:
    db = _sqlite(agent_id)
    con = sqlite3.connect(db)
    row = con.execute(
        "SELECT id, memory_id, kind, payload, ts FROM episodes WHERE memory_id = ?",
        (memory_id,),
    ).fetchone()
    con.close()
    if not row:
        raise KeyError(memory_id)
    try:
        payload = json.loads(row[3])
    except json.JSONDecodeError:
        payload = {"raw": row[3]}
    return {
        "agent_id": agent_id,
        "memory_id": memory_id,
        "sqlite_id": row[0],
        "kind": row[2],
        "ts": row[4],
        "payload": payload,
        "where": {
            "meta": str(db),
            "graph": f"Entity.id={memory_id}",
            "vector": f"point id or payload.memory_id={memory_id}",
            "blob": f"bucket key prefix {memory_id}/",
            "bus": f"{ns(agent_id)} messages contain memory_id",
        },
    }


def list_episodes(agent_id: str, limit: int = 50) -> list[dict]:
    db = _sqlite(agent_id)
    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT id, memory_id, kind, payload, ts FROM episodes ORDER BY id DESC LIMIT ?",
        (max(1, min(limit, 200)),),
    ).fetchall()
    con.close()
    out = []
    for i, mid, kind, payload, ts in rows:
        try:
            body = json.loads(payload)
        except json.JSONDecodeError:
            body = {"raw": payload}
        out.append({"id": i, "memory_id": mid, "kind": kind, "payload": body, "ts": ts})
    return out


def _graph_conn(agent_id: str):
    import kuzu

    path = agent_dir(agent_id) / "graph.kuzu"
    db = kuzu.Database(str(path))
    return kuzu.Connection(db)


def _graph_init(agent_id: str) -> None:
    conn = _graph_conn(agent_id)
    conn.execute(
        "CREATE NODE TABLE IF NOT EXISTS Entity(id STRING, kind STRING, props STRING, PRIMARY KEY(id))"
    )
    conn.execute(
        "CREATE REL TABLE IF NOT EXISTS Rel(FROM Entity TO Entity, kind STRING, props STRING)"
    )


def graph_node(agent_id: str, node_id: str, kind: str, props: dict) -> dict:
    _graph_init(agent_id)
    conn = _graph_conn(agent_id)
    blob = json.dumps(props, ensure_ascii=False)
    try:
        conn.execute(
            "CREATE (e:Entity {id: $id, kind: $kind, props: $props})",
            {"id": node_id, "kind": kind, "props": blob},
        )
    except Exception:
        conn.execute(
            "MATCH (e:Entity {id: $id}) SET e.kind = $kind, e.props = $props",
            {"id": node_id, "kind": kind, "props": blob},
        )
    return {"agent_id": agent_id, "id": node_id, "kind": kind}


def graph_edge(agent_id: str, src: str, dst: str, kind: str, props: dict | None = None) -> dict:
    _graph_init(agent_id)
    conn = _graph_conn(agent_id)
    blob = json.dumps(props or {}, ensure_ascii=False)
    conn.execute(
        "MATCH (a:Entity {id: $src}), (b:Entity {id: $dst}) "
        "CREATE (a)-[:Rel {kind: $kind, props: $props}]->(b)",
        {"src": src, "dst": dst, "kind": kind, "props": blob},
    )
    return {"agent_id": agent_id, "src": src, "dst": dst, "kind": kind}


def graph_query(agent_id: str, cypher: str) -> dict:
    conn = _graph_conn(agent_id)
    result = conn.execute(cypher)
    rows = []
    try:
        while result.has_next():
            rows.append([_cell(x) for x in result.get_next()])
    except Exception:
        pass
    return {"agent_id": agent_id, "rows": rows[:200]}


def _cell(x):
    try:
        json.dumps(x)
        return x
    except TypeError:
        return str(x)


def _vector_dim() -> int:
    from .embedder import dim

    return dim()


_reindexing: set[str] = set()


def _qdrant_ensure(agent_id: str) -> str:
    if not _port_up(6333):
        raise RuntimeError("qdrant :6333 nede — docker compose -f cockpit/memory/compose.yml up -d")
    coll = layers(agent_id)["vector"]["collection"]
    want = _vector_dim()
    g = httpx.get(f"{QDRANT}/collections/{coll}", timeout=5.0)
    recreate = True
    if g.status_code == 200:
        try:
            size = g.json()["result"]["config"]["params"]["vectors"]["size"]
        except (KeyError, TypeError):
            size = None
        if size == want:
            recreate = False
        else:
            httpx.delete(f"{QDRANT}/collections/{coll}", timeout=10.0)
    if recreate:
        r = httpx.put(
            f"{QDRANT}/collections/{coll}",
            json={"vectors": {"size": want, "distance": "Cosine"}},
            timeout=5.0,
        )
        if r.status_code >= 400 and "already" not in r.text.lower():
            raise RuntimeError(r.text[:300])
        if agent_id not in _reindexing:
            _reindexing.add(agent_id)
            try:
                reindex_vectors(agent_id)
            except Exception:
                pass
            finally:
                _reindexing.discard(agent_id)
    return coll


def reindex_vectors(agent_id: str) -> dict:
    """Re-embed sqlite episodes into Qdrant after dim change."""
    n = 0
    for e in list_episodes(agent_id, limit=200):
        p = e.get("payload") or {}
        mid = str(p.get("memory_id") or e.get("memory_id") or "")
        if not mid:
            continue
        try:
            vector_upsert(
                agent_id,
                mid,
                cheap_vec(_payload_text(p)),
                {"kind": e.get("kind"), "memory_id": mid, "agent_id": agent_id, "text": _payload_text(p)[:400]},
            )
            n += 1
        except Exception:
            continue
    return {"agent_id": agent_id, "reindexed": n}


def vector_upsert(agent_id: str, point_id: str, vector: list[float], payload: dict) -> dict:
    coll = _qdrant_ensure(agent_id)
    want = _vector_dim()
    v = (list(vector) + [0.0] * want)[:want]
    r = httpx.put(
        f"{QDRANT}/collections/{coll}/points?wait=true",
        json={"points": [{"id": point_id if _uuidish(point_id) else None, "vector": v, "payload": payload}]},
        timeout=10.0,
    )
    # qdrant wants uuid or int id — if string not uuid, hash to uuid
    if r.status_code >= 400:
        import hashlib

        hid = str(uuid.UUID(hashlib.md5(point_id.encode()).hexdigest()))
        r = httpx.put(
            f"{QDRANT}/collections/{coll}/points?wait=true",
            json={"points": [{"id": hid, "vector": v, "payload": {**payload, "key": point_id}}]},
            timeout=10.0,
        )
        r.raise_for_status()
        point_id = hid
    return {"agent_id": agent_id, "collection": coll, "id": point_id}


def vector_search(agent_id: str, vector: list[float], limit: int = 8) -> dict:
    coll = _qdrant_ensure(agent_id)
    want = _vector_dim()
    v = (list(vector) + [0.0] * want)[:want]
    r = httpx.post(
        f"{QDRANT}/collections/{coll}/points/search",
        json={"vector": v, "limit": max(1, min(limit, 32)), "with_payload": True},
        timeout=10.0,
    )
    r.raise_for_status()
    return {"agent_id": agent_id, "hits": r.json().get("result") or []}


def _uuidish(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except ValueError:
        return False


def _minio_client():
    from minio import Minio

    return Minio(f"{MINIO_HOST}:{MINIO_PORT}", access_key=MINIO_USER, secret_key=MINIO_PASS, secure=False)


def _minio_ensure(agent_id: str) -> str:
    if not _port_up(9100):
        raise RuntimeError("minio :9100 nede — docker compose -f cockpit/memory/compose.yml up -d")
    bucket = layers(agent_id)["blob"]["bucket"]
    c = _minio_client()
    if not c.bucket_exists(bucket):
        c.make_bucket(bucket)
    return bucket


def blob_put(agent_id: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> dict:
    bucket = _minio_ensure(agent_id)
    import io

    c = _minio_client()
    c.put_object(bucket, key, io.BytesIO(data), length=len(data), content_type=content_type)
    return {"agent_id": agent_id, "bucket": bucket, "key": key, "bytes": len(data)}


def blob_get(agent_id: str, key: str) -> tuple[bytes, str]:
    bucket = _minio_ensure(agent_id)
    c = _minio_client()
    obj = c.get_object(bucket, key)
    try:
        data = obj.read()
        ctype = obj.headers.get("Content-Type") or "application/octet-stream"
    finally:
        obj.close()
        obj.release_conn()
    return data, ctype


def bus_publish(agent_id: str, message: str) -> dict:
    if not _port_up(6379):
        raise RuntimeError("redis :6379 nede — docker compose -f cockpit/memory/compose.yml up -d")
    import redis

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    ch = ns(agent_id)
    n = r.publish(ch, message)
    r.lpush(ch + ":recent", message)
    r.ltrim(ch + ":recent", 0, 99)
    return {"agent_id": agent_id, "channel": ch, "subscribers": n}


def bus_recent(agent_id: str, limit: int = 20) -> dict:
    if not _port_up(6379):
        raise RuntimeError("redis :6379 nede")
    import redis

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    ch = ns(agent_id)
    items = r.lrange(ch + ":recent", 0, max(0, min(limit, 99) - 1))
    return {"agent_id": agent_id, "channel": ch, "recent": items}
