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
_GREET = re.compile(r"^\s*(yo|halla|hallo|hei+|hi+|hey|sup|god\s+morgen|god\s+kveld)\b", re.I)
_KINDS = ("fact", "artifact", "noise", "decision")
_MUTATE_TOOLS = frozenset({"repo_edit", "repo_bash", "iframe_write"})


def jev_key() -> str:
    env = load_env()
    return (
        env.get("AI_GATEWAY_API_KEY")
        or env.get("VERCEL_API_KEY")
        or env.get("OPENROUTER_API_KEY")
        or env.get("TYPESAFE_API_KEY")
        or ""
    ).strip()


def decide(
    state: Any,
    questions: dict[str, dict],
    *,
    jev_attempts: int = 3,
    jev_timeout: float = 8.0,
    jev_second_url: bool = True,
    use_mercury: bool = True,
) -> dict:
    """Jev first; fallback Mercury-2.5 + rules veto. Last resort: rules only."""
    rules = {qid: _rule_one(state, qid, spec) for qid, spec in questions.items()}
    live = None
    src = "rules"
    key = jev_key()
    if key:
        try:
            live = _jev_http(
                state,
                questions,
                key,
                attempts=jev_attempts,
                timeout=jev_timeout,
                second_url=jev_second_url,
            )
            if live:
                src = "jev"
        except Exception:
            live = None
    if live is None and use_mercury:
        try:
            live = _mercury_http(state, questions)
            if live:
                src = "mercury"
        except Exception:
            live = None
    if live:
        return {"source": src + "+rules", "answers": _merge_rules(state, rules, live)}
    return {"source": "rules", "answers": rules}


def _query_of(state: Any) -> str:
    if isinstance(state, dict):
        return str(state.get("query") or "")
    return str(state or "")


def _hit_answers(hits: list) -> bool:
    for h in hits or []:
        if not isinstance(h, dict):
            continue
        if (h.get("kind") or "") != "chat":
            continue
        asst = str(h.get("assistant") or "")
        sal = str(h.get("salience") or h.get("salience_kind") or "")
        if len(asst) > 40 and sal in ("", "artifact", "fact"):
            return True
    return False


def _merge_rules(state: Any, rules: dict, live: dict) -> dict:
    """Mutate cannot skip disk. Ask-questions with a chat-answer cannot skip memory."""
    out = dict(live)
    q = _query_of(state)
    st = state if isinstance(state, dict) else {}
    hits = st.get("hits") or []
    act = (out.get("act") or {}).get("choice")
    if _MUTATE.search(q) and act == "use_memory":
        base = dict(out.get("act") or {})
        base["choice"] = "both"
        base["veto"] = "rules-mutate"
        out["act"] = base
    elif (
        _ASK.search(q)
        and not _MUTATE.search(q)
        and _hit_answers(hits)
        and act == "read_disk"
    ):
        base = dict(out.get("act") or {})
        base["choice"] = "use_memory"
        base["veto"] = "rules-answered"
        out["act"] = base
    for qid, rans in rules.items():
        if qid.startswith("keep_") and qid not in out:
            out[qid] = rans
    return out


def _mercury_http(state: Any, questions: dict[str, dict]) -> dict[str, dict] | None:
    env = load_env()
    key = (env.get("INCEPTION_API_KEY") or "").strip()
    if not key:
        return None
    base = (env.get("INCEPTION_BASE_URL") or "https://api.inceptionlabs.ai/v1").rstrip("/")
    payload = {"state": state, "questions": questions}
    r = httpx.post(
        base + "/chat/completions",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        json={
            "model": "mercury-2.5",
            "temperature": 0.5,
            "max_tokens": 1500,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return ONLY a JSON object keyed by question id. "
                        "noul/boolean: {\"noul\": 0-1, \"confidence\": 0-1}. "
                        "choice: {\"choice\": \"<one criteria key>\", \"confidence\": 0-1}. "
                        "No markdown, no extra keys."
                    ),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)[:8000]},
            ],
        },
        timeout=20.0,
    )
    r.raise_for_status()
    content = (((r.json().get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.S)
        if not m:
            return None
        data = json.loads(m.group(0))
    if not isinstance(data, dict):
        return None
    out: dict[str, dict] = {}
    for qid, ans in data.items():
        if not isinstance(ans, dict):
            continue
        d: dict[str, Any] = {"source": "mercury", "confidence": float(ans.get("confidence") or 0.5)}
        if ans.get("noul") is not None:
            d["noul"] = float(ans["noul"])
        if ans.get("choice") is not None:
            d["choice"] = str(ans["choice"])
        if ans.get("score") is not None:
            d["score"] = float(ans["score"])
        out[qid] = d
    return out or None


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


def _jev_http(
    state: Any,
    questions: dict[str, dict],
    key: str,
    *,
    attempts: int = 3,
    timeout: float = 8.0,
    second_url: bool = True,
) -> dict[str, dict] | None:
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
    targets = [
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
    import time

    n_try = max(1, int(attempts))
    urls = targets if second_url else targets[:1]
    for url, body in urls:
        for attempt in range(n_try):
            try:
                r = httpx.post(url, headers=headers, json=body, timeout=timeout)
                if r.status_code == 429:
                    last_err = 429
                    if attempt + 1 >= n_try:
                        break
                    time.sleep(0.6 * (attempt + 1))
                    continue
                if r.status_code >= 400:
                    last_err = r.status_code
                    break
                parsed = _parse_jev_answers(r.json() if r.content else {})
                if parsed:
                    return parsed
                break
            except Exception as e:
                last_err = e
                break
    if last_err:
        raise RuntimeError(str(last_err)[:120])
    return None


def _tool_names(state: dict) -> list[str]:
    names: list[str] = []
    for t in state.get("tools") or []:
        if isinstance(t, str):
            names.append(t)
        elif isinstance(t, dict) and t.get("name"):
            names.append(str(t.get("name")))
    return names


def _rule_one(state: Any, qid: str, spec: dict) -> dict:
    typ = (spec.get("type") or "noul").lower()
    st = state if isinstance(state, dict) else {"query": str(state)}
    query = str(st.get("query") or st.get("user") or "")
    hits = st.get("hits") or []
    names = _tool_names(st)
    asst = str(st.get("assistant") or "")
    note = str(st.get("note") or "")
    err = str(st.get("error") or "")
    blob = f"{query} {asst}".lower()
    if typ == "noul" and qid == "persist_hot":
        noul = 0.45
        if any(n in _MUTATE_TOOLS for n in names) or "_probe.html" in blob:
            noul = 0.9
        elif _ASK.search(query) and len(asst) > 40:
            noul = 0.75
        elif _GREET.search(query) and not names:
            noul = 0.15
        elif "ws-disconnect" in note or err:
            noul = 0.55 if names else 0.2
        return {"noul": noul, "confidence": 0.6, "source": "rules"}
    if typ == "choice" and qid == "kind":
        if any(n in _MUTATE_TOOLS for n in names) or "_probe.html" in blob:
            choice = "artifact"
        elif _GREET.search(query) and not names:
            choice = "noise"
        elif "ws-disconnect" in note and len(asst) < 40:
            choice = "noise"
        elif _ASK.search(query):
            choice = "fact"
        else:
            choice = "fact" if asst else "noise"
        return {"choice": choice, "confidence": 0.65, "source": "rules"}
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
        if _MUTATE.search(query):
            choice = "both" if hits else "read_disk"
        elif _ASK.search(query) and _hit_answers(hits):
            choice = "use_memory"
        elif not hits or top < 1.5:
            choice = "read_disk"
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
                "salience": p.get("salience_kind"),
                "paths": (p.get("paths") or ([p.get("path")] if p.get("path") else []))[:3],
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


def _finalize_salience(st: dict, out: dict) -> dict:
    answers = out.get("answers") or {}
    kind = str((answers.get("kind") or {}).get("choice") or "fact")
    if kind not in _KINDS:
        kind = "fact"
    try:
        persist = float((answers.get("persist_hot") or {}).get("noul") or 0.5)
    except (TypeError, ValueError):
        persist = 0.5
    persist = max(0.0, min(1.0, persist))
    names = _tool_names(st)
    blob = f"{st.get('query') or st.get('user') or ''} {st.get('assistant') or ''}".lower()
    veto = ""
    if any(n in _MUTATE_TOOLS for n in names) or "_probe.html" in blob:
        if kind == "noise":
            kind = "artifact"
        persist = max(persist, 0.75)
        veto = "artifact"
    return {
        "source": out.get("source") or "rules",
        "kind": kind,
        "persist_hot": round(persist, 2),
        "veto": veto,
    }


def classify_turn(state: dict | None = None) -> dict:
    """One decide() after the answer: salience for the final chat engram, never per tool."""
    st = dict(state or {})
    if "query" not in st:
        st["query"] = st.get("user") or ""
    questions = {
        "persist_hot": {
            "type": "noul",
            "instructions": (
                "Should later turns easily recall this episode? High for durable facts "
                "and files written on disk; low for greetings, empty disconnects, chatter."
            ),
        },
        "kind": {
            "type": "choice",
            "instructions": "What is this episode?",
            "criteria": {
                "fact": "A durable answer (what/where/which) worth recalling",
                "artifact": "A file, probe, edit, or bash result on disk",
                "decision": "A policy/choice about how to work, not a world fact",
                "noise": "Greeting, stall, empty disconnect, or throwaway chatter",
            },
        },
    }
    # Gate already spent the Jev budget this turn; a second call is usually 429
    # plus Mercury (8–20s). One short evaluate, then rules+veto.
    out = decide(
        st,
        questions,
        jev_attempts=1,
        jev_timeout=4.0,
        jev_second_url=False,
        use_mercury=False,
    )
    return _finalize_salience(st, out)
