"""Workspace on disk. Default ~/kalived. Never $HOME as root."""
from __future__ import annotations

import difflib
import os
import re
import shlex
import signal
import subprocess
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

SKIP = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "logs",
    ".grok",
}

MAX_READ = 200_000
MAX_MATCH = 80

router = APIRouter(prefix="/v1/workspace", tags=["workspace"])


def root() -> Path:
    env = os.environ.get("KALIVED_WORKSPACE") or os.environ.get("KALIVED_DATA")
    p = Path(env).expanduser().resolve() if env else (Path.home() / "kalived").resolve()
    if not p.is_dir():
        raise FileNotFoundError(f"workspace mangler: {p}")
    return p


def safe(rel: str) -> Path:
    rel = (rel or "").strip().lstrip("/")
    if not rel or rel in (".",):
        return root()
    if ".." in Path(rel).parts or rel.startswith("~") or rel.startswith("/"):
        raise ValueError("ugyldig path")
    base = root()
    p = (base / rel).resolve()
    try:
        p.relative_to(base)
    except ValueError as e:
        raise ValueError("utenfor workspace") from e
    return p


def rel_of(p: Path) -> str:
    return str(p.relative_to(root())).replace("\\", "/")


def skipped(p: Path) -> bool:
    return any(part in SKIP for part in p.relative_to(root()).parts)


def language_of(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {
        ".py": "python",
        ".ts": "typescript",
        ".js": "javascript",
        ".svelte": "html",
        ".html": "html",
        ".css": "css",
        ".md": "markdown",
        ".json": "json",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".sh": "shell",
        ".toml": "ini",
        ".rhai": "rust",
    }.get(ext, "plaintext")


def listdir(rel: str = "") -> list[dict]:
    """One directory. Client expands folders. No dump of reports/*."""
    d = safe(rel) if rel else root()
    if not d.is_dir():
        raise ValueError("ikke mappe")
    out: list[dict] = []
    try:
        kids = sorted(d.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    except OSError:
        return out
    for c in kids:
        if c.name in SKIP:
            continue
        if c.name.startswith(".") and c.name not in {".gitignore", ".env.example"}:
            continue
        if c.suffix in {".pyc", ".pyo"}:
            continue
        try:
            r = rel_of(c)
        except ValueError:
            continue
        out.append({"path": r, "name": c.name, "dir": c.is_dir()})
    return out


def expand_glob(pattern: str) -> str:
    """`agents.py` → `**/agents.py`. Pathlib glob is not recursive without **."""
    pattern = (pattern or "").strip() or "**/*"
    if "**" not in pattern and "/" not in pattern and not pattern.startswith("."):
        return "**/" + pattern
    return pattern


def glob(pattern: str, limit: int = 80) -> list[str]:
    pattern = expand_glob(pattern)
    base = root()
    hits: list[str] = []
    for p in base.glob(pattern):
        if not p.is_file():
            continue
        if skipped(p):
            continue
        hits.append(rel_of(p))
        if len(hits) >= limit:
            break
    return hits


def grep(query: str, glob_pat: str = "**/*", limit: int = MAX_MATCH) -> list[dict]:
    if not query or len(query) > 200:
        raise ValueError("ugyldig søk")
    try:
        rx = re.compile(query)
    except re.error as e:
        raise ValueError(f"regex: {e}") from e
    hits: list[dict] = []
    base = root()
    for p in base.glob(expand_glob(glob_pat or "**/*")):
        if not p.is_file() or skipped(p):
            continue
        if p.stat().st_size > MAX_READ:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append({"path": rel_of(p), "line": i, "text": line[:240]})
                if len(hits) >= limit:
                    return hits
    return hits


def read(rel: str, max_bytes: int = MAX_READ) -> dict:
    p = safe(rel)
    if p.is_dir():
        names = sorted(c.name for c in p.iterdir() if c.name not in SKIP)[:80]
        return {"path": rel_of(p), "dir": True, "entries": names}
    if not p.is_file():
        raise FileNotFoundError(rel)
    if skipped(p):
        raise ValueError("hoppet over")
    data = p.read_bytes()
    truncated = len(data) > max_bytes
    text = data[:max_bytes].decode("utf-8", errors="replace")
    return {
        "path": rel_of(p),
        "language": language_of(rel_of(p)),
        "text": text,
        "n": len(text),
        "truncated": truncated,
    }


def write(rel: str, text: str) -> dict:
    p = safe(rel)
    if p.suffix == "" and text == "":
        raise ValueError("tom path")
    p.parent.mkdir(parents=True, exist_ok=True)
    if skipped(p):
        raise ValueError("hoppet over")
    before = p.read_text(encoding="utf-8") if p.is_file() else ""
    p.write_text(text, encoding="utf-8")
    diff = "\n".join(
        difflib.unified_diff(
            before.splitlines(),
            text.splitlines(),
            fromfile="a/" + rel_of(p),
            tofile="b/" + rel_of(p),
            lineterm="",
        )
    )
    return {"path": rel_of(p), "n": len(text), "diff": diff[:12000], "wrote": True}


def edit(rel: str, old: str, new: str) -> dict:
    p = safe(rel)
    if not p.is_file():
        raise FileNotFoundError(rel)
    if skipped(p):
        raise ValueError("hoppet over")
    text = p.read_text(encoding="utf-8")
    if old not in text:
        return {"error": "old_string ikke funnet", "path": rel_of(p)}
    if text.count(old) > 1:
        return {"error": "old_string treffer mer enn én gang — gjør den unik", "path": rel_of(p)}
    updated = text.replace(old, new, 1)
    return write(rel_of(p), updated)


_DENY = re.compile(
    r"(^|[\s;|&])(sudo|pkexec|doas)(\s|$)"
    r"|sudo\s+-S"
    r"|git\s+push"
    r"|chmod\s+-R\s+777\s+/"
    r"|rm\s+-rf\s+/"
    r"|curl\s+[^\n]*\|\s*(ba)?sh",
    re.I,
)
_TAIL = 200_000


def _kill_pg(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGTERM)
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    time.sleep(0.4)
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def bash(
    argv: list[str] | None = None,
    line: str | None = None,
    timeout_s: float = 120,
    cancel=None,
) -> dict:
    """Run one command in workspace. Mutating. No sudo, no git push."""
    if argv and isinstance(argv, list) and any(str(a) for a in argv):
        cmd = [str(a) for a in argv if str(a) != ""]
    elif line and str(line).strip():
        try:
            cmd = shlex.split(str(line).strip(), posix=True)
        except ValueError as e:
            return {"error": f"kan ikke parse linje: {e}"}
    else:
        return {"error": "trenger argv eller line"}
    if not cmd:
        return {"error": "tom kommando"}
    blob = " ".join(cmd)
    if _DENY.search(blob):
        return {"error": "nekta: sudo/git push/destruktiv root — PTY til passord, du eier remote", "argv": cmd}
    timeout_s = max(1.0, min(float(timeout_s or 120), 600.0))
    cwd = str(root())
    env = {**os.environ, "NO_COLOR": "1", "PYTHONUNBUFFERED": "1"}
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            env=env,
        )
    except FileNotFoundError:
        return {"error": f"ikke funnet: {cmd[0]}", "argv": cmd, "cwd": cwd}
    t0 = time.time()
    timed = False
    cancelled = False
    while proc.poll() is None:
        if cancel is not None and getattr(cancel, "is_set", lambda: False)():
            _kill_pg(proc.pid)
            cancelled = True
            break
        if time.time() - t0 > timeout_s:
            _kill_pg(proc.pid)
            timed = True
            break
        time.sleep(0.15)
    try:
        out, err = proc.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        _kill_pg(proc.pid)
        out, err = proc.communicate(timeout=2)
    def tail(b: bytes | None) -> str:
        s = (b or b"").decode("utf-8", errors="replace")
        if len(s) > _TAIL:
            return s[-_TAIL:]
        return s
    stdout, stderr = tail(out), tail(err)
    for secret in ("sk-", "API_KEY=", "BEGIN PRIVATE"):
        if secret in stdout:
            stdout = stdout.replace(secret, "«redact»")
        if secret in stderr:
            stderr = stderr.replace(secret, "«redact»")
    return {
        "argv": cmd,
        "cwd": cwd,
        "exit_code": proc.returncode,
        "timeout": timed,
        "cancelled": cancelled,
        "stdout_tail": stdout,
        "stderr_tail": stderr,
        "elapsed_s": round(time.time() - t0, 2),
    }


@router.get("")
def info():
    r = root()
    return {"root": str(r), "name": r.name}


@router.get("/tree")
def tree_http(path: str = ""):
    try:
        entries = listdir(path)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    r = root()
    return {"root": str(r), "path": path, "entries": entries}


@router.get("/file")
def file_get(path: str):
    try:
        return read(path)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


class FilePut(BaseModel):
    path: str
    text: str


@router.put("/file")
def file_put(body: FilePut):
    try:
        return write(body.path, body.text)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/raw")
def raw(path: str):
    """Serve a workspace HTML file for iframe preview. No bash."""
    from fastapi.responses import HTMLResponse, PlainTextResponse

    from .desk import looks_html

    try:
        doc = read(path)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    text = doc.get("text") or ""
    if looks_html(text, path, doc.get("language") or ""):
        return HTMLResponse(text, headers={"Cache-Control": "no-store"})
    return PlainTextResponse(text[:20_000], headers={"Cache-Control": "no-store"})
