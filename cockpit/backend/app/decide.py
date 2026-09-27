"""Typed decisions. Same question shapes as TypeSafe Jev (Choice/Score/Noul).

Rules always run. Live Jev via Vercel AI Gateway when AI_GATEWAY_API_KEY is set.
Policy stays in this file. The model never writes the prompt.
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from .secrets_store import load_env

KEEP_MIN = 0.6
_MUTATE = re.compile(
    r"\b(skriv|edit|patch|kjør|bash|lag |bygg|commit|slett|fjern|repo_edit|repo_bash)\b",
    re.I,
)
_ASK = re.compile(r"\b(hva|hvor|hvilken|hvem|hvordan|was|what|where|which)\b", re.I)


def jev_key() -> str:
    env = load_env()
    return (
        env.get("AI_GATEWAY_API_KEY")
        or env.get("VERCEL_API_KEY")
        or env.get("OPENROUTER_API_KEY")
        or env.get("TYPESAFE_API_KEY")
        or ""
    ).strip()


def decide(state: Any, questions: dict[str, dict]) -> dict:
    """answers[id] = {choice|score|noul, confidence, source}."""
    rules = {qid: _rule_one(state, qid, spec) for qid, spec in questions.items()}
    key = jev_key()
    if key:
        try:
            live = _jev_http(state, questions, key)
            if live:
                return {"source": "jev", "answers": live}
        except Exception:
            pass
    return {"source": "rules", "answers": rules}


def _parse_jev_answers(data: dict) -> dict[str, dict] | None:
    raw = data.get("answers") or (data.get("result") or {}).get("answers") or {}
    meta = ((data.get("providerMetadata") or {}).get("typesafe") or {}).get("confidence") or {}
    if not isinstance(raw, dict) or not raw:
        return None
    out: dict[str, dict] = {}
    for qid, ans in raw.items():
        if not isinstance(ans, dict):
            continue
        conf = ans.get("confidence")
        if conf is None and isinstance(meta, dict):
            conf = meta.get(qid) or meta.get("destination")
        d: dict[str, Any] = {"source": "jev", "confidence": float(conf or 0.5)}
        if ans.get("noul") is not None:
            d["noul"] = float(ans["noul"])
        elif ans.get("probability") is not None:
            d["noul"] = float(ans["probability"])
        elif isinstance(ans.get("boolean"), bool):
            d["noul"] = 1.0 if ans["boolean"] else 0.0
        elif ans.get("boolean") is not None:
            d["noul"] = float(ans["boolean"])
        if ans.get("choice") is not None:
            d["choice"] = str(ans["choice"])
        if ans.get("score") is not None:
            d["score"] = float(ans["score"])
        out[qid] = d
    return out or None


def _jev_http(state: Any, questions: dict[str, dict], key: str) -> dict[str, dict] | None:
    """Vercel labs sample uses /v1/evaluate; TypeSafe SDK uses /typesafe/v1/systemone."""
    env = load_env()
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    st = state if isinstance(state, str) else json.dumps(state, ensure_ascii=False)
    qs_eval: dict[str, dict] = {}
    qs_one: dict[str, dict] = {}
    for qid, spec in questions.items():
        typ = spec.get("type") or "noul"
        instr = spec.get("instructions") or qid
        crit = spec.get("criteria")
        one: dict[str, Any] = {"type": typ, "instructions": instr}
        ev: dict[str, Any] = {"type": "boolean" if typ == "noul" else typ, "instructions": instr}
        if crit:
            one["criteria"] = crit
            ev["criteria"] = crit
        qs_one[qid] = one
        qs_eval[qid] = ev
    attempts = [
        (
            "https://ai-gateway.vercel.sh/v1/evaluate",
            {"model": "typesafe-ai/jev", "state": state if not isinstance(state, str) else st, "questions": qs_eval},
        ),
        (
            (env.get("AI_GATEWAY_BASE_URL") or "https://ai-gateway.vercel.sh/typesafe").rstrip("/") + "/v1/systemone",
            {"model": "typesafe-ai/jev", "state": st, "questions": qs_one},
        ),
    ]
    last_err = None
    for url, body in attempts:
        try:
            r = httpx.post(url, headers=headers, json=body, timeout=8.0)
            if r.status_code >= 400:
                last_err = r.status_code
                continue
            parsed = _parse_jev_answers(r.json() if r.content else {})
            if parsed:
                return parsed
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise RuntimeError(str(last_err)[:120])
    return None


def _rule_one(state: Any, qid: str, spec: dict) -> dict:
    typ = (spec.get("type") or "noul").lower()
    st = state if isinstance(state, dict) else {"query": str(state)}
    query = str(st.get("query") or "")
    hits = st.get("hits") or []
    if typ == "noul" and qid.startswith("keep_"):
        try:
            i = int(qid.split("_", 1)[1])
        except ValueError:
            i = -1
        score = 0.0
        if 0 <= i < len(hits):
            score = float(hits[i].get("score") or 0)
        noul = max(0.0, min(1.0, score / 4.0))
        return {"noul": noul, "confidence": min(1.0, 0.4 + noul / 2), "source": "rules"}
    if typ == "choice" and qid == "act":
        kept_scores = [float(h.get("score") or 0) for h in hits]
        top = max(kept_scores) if kept_scores else 0.0
        if not hits or top < 1.5:
            choice = "read_disk"
        elif _MUTATE.search(query):
            choice = "both"
        elif _ASK.search(query) and top >= 2.8:
            choice = "use_memory"
        else:
            choice = "both" if hits else "read_disk"
        return {"choice": choice, "confidence": 0.7 if hits else 0.9, "source": "rules"}
    if typ == "score":
        return {"score": 0.0, "confidence": 0.3, "source": "rules"}
    return {"noul": 0.0, "confidence": 0.3, "source": "rules"}


def gate_recall(query: str, hits: list[dict]) -> tuple[list[dict], dict]:
    """Filter recall hits and choose use_memory | read_disk | both."""
    compact = []
    for i, h in enumerate(hits):
        p = h.get("payload") or {}
        compact.append(
            {
                "i": i,
                "score": h.get("score") or 0,
                "kind": h.get("kind"),
                "user": str(p.get("user") or "")[:200],
                "assistant": str(p.get("assistant") or p.get("text") or "")[:160],
            }
        )
    questions: dict[str, dict] = {
        "act": {
            "type": "choice",
            "instructions": "How should the coding agent use memory vs disk?",
            "criteria": {
                "use_memory": "Memory already answers; do not ritual-read README",
                "read_disk": "Need current files on disk",
                "both": "Memory helps but verify on disk",
            },
        }
    }
    for i in range(len(compact)):
        questions[f"keep_{i}"] = {
            "type": "noul",
            "instructions": "Is this hit useful for answering the query?",
        }
    out = decide({"query": query, "hits": compact}, questions)
    answers = out.get("answers") or {}
    kept: list[dict] = []
    for i, h in enumerate(hits):
        noul = float((answers.get(f"keep_{i}") or {}).get("noul") or 0)
        if noul >= KEEP_MIN:
            item = dict(h)
            item["keep"] = round(noul, 2)
            kept.append(item)
    act = str((answers.get("act") or {}).get("choice") or "read_disk")
    if not kept and act == "use_memory":
        act = "read_disk"
    return kept, {
        "act": act,
        "source": out.get("source") or "rules",
        "n": len(kept),
        "answers": {k: {kk: vv for kk, vv in v.items() if kk != "source"} for k, v in answers.items()},
    }
