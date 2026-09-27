"""Typed decisions. Same question shapes as TypeSafe Jev (Choice/Score/Noul).

A: deterministic rules. Live Jev is B — only if OPENROUTER_API_KEY / TYPESAFE_API_KEY.
Policy stays in this file. The model never writes the prompt.
"""
from __future__ import annotations

import re
from typing import Any

from .secrets_store import load_env

KEEP_MIN = 0.6
_MUTATE = re.compile(
    r"\b(skriv|edit|patch|kjør|bash|lag |bygg|commit|slett|fjern|repo_edit|repo_bash)\b",
    re.I,
)
_ASK = re.compile(r"\b(hva|hvor|hvilken|hvem|hvordan|was|what|where|which)\b", re.I)


def jev_key() -> str:
    env = load_env()
    return (env.get("OPENROUTER_API_KEY") or env.get("TYPESAFE_API_KEY") or "").strip()


def decide(state: Any, questions: dict[str, dict]) -> dict:
    """answers[id] = {choice|score|noul, confidence, source}."""
    src = "rules"
    # B later: if jev_key(): try HTTP, src="jev"
    answers = {qid: _rule_one(state, qid, spec) for qid, spec in questions.items()}
    return {"source": src, "answers": answers}


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
