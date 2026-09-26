"""Local embeddings for the memory gate. ONNX via fastembed — no torch, no extra cloud."""
from __future__ import annotations

import os
import threading

# Multilingual MiniLM (384-d, ~220 MB). Norwegian + English. Override with KALIVED_EMBED_MODEL.
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIM = 384

_lock = threading.Lock()
_model = None
_name: str | None = None
_error: str | None = None


def model_name() -> str:
    return (os.environ.get("KALIVED_EMBED_MODEL") or DEFAULT_MODEL).strip()


def dim() -> int:
    return DIM


def status() -> dict:
    return {"model": model_name(), "dim": DIM, "loaded": _model is not None, "error": _error}


def _load():
    global _model, _name, _error
    with _lock:
        if _model is not None and _name == model_name():
            return _model
        name = model_name()
        from fastembed import TextEmbedding

        _model = TextEmbedding(model_name=name)
        _name = name
        _error = None
        return _model


def embed_one(text: str) -> list[float]:
    """384-d cosine vector. Falls back to padded hash only if fastembed fails."""
    t = (text or "")[:8000] or " "
    try:
        m = _load()
        vec = next(iter(m.embed([t])))
        out = [float(x) for x in vec]
        if len(out) != DIM:
            out = (out + [0.0] * DIM)[:DIM]
        return out
    except Exception as e:
        global _error
        _error = str(e)[:300]
        import hashlib

        h = hashlib.sha256(t.encode("utf-8", errors="replace")).digest()
        # stretch hash to DIM so qdrant schema still matches
        raw = (h * (DIM // len(h) + 1))[:DIM]
        return [b / 255.0 for b in raw]
