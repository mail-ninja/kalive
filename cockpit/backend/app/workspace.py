"""Workspace on disk. Default ~/kalived. Never $HOME as root."""
from __future__ import annotations

import difflib
import fcntl
import json
import os
import re
import shlex
import signal
import stat
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

_BLOCK_ROOTS = ("/etc", "/usr", "/root", "/proc", "/sys", "/dev", "/boot", "/run", "/var")
_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_live: Path | None = None


def owner_home() -> Path:
    return Path(os.environ.get("KALIVED_OWNER_HOME") or Path.home()).expanduser().resolve()


def state_path() -> Path:
    env = os.environ.get("KALIVED_WORKSPACES")
    if env:
        return Path(env).expanduser()
    return owner_home() / ".config" / "kalived" / "workspaces.json"


def kalived_repo() -> Path:
    return Path(__file__).resolve().parents[3]


def reset_live() -> None:
    global _live
    _live = None


def _default_root() -> Path:
    env = os.environ.get("KALIVED_WORKSPACE") or os.environ.get("KALIVED_DATA")
    if env:
        return Path(env).expanduser().resolve()
    return (Path.home() / "kalived").resolve()


def _load_state() -> dict:
    p = state_path()
    if not p.is_file():
        return {"current": "", "recents": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"current": "", "recents": []}
    if not isinstance(data, dict):
        return {"current": "", "recents": []}
    rec = data.get("recents")
    if not isinstance(rec, list):
        data["recents"] = []
    return data


def _save_state(data: dict) -> None:
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    tmp.replace(p)
    os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)


def _allow_roots() -> list[Path]:
    roots = [owner_home()]
    extra = os.environ.get("KALIVED_WS_ALLOW")
    if extra:
        try:
            roots.append(Path(extra).expanduser().resolve())
        except OSError:
            pass
    return roots


def check_open(raw: str) -> Path | dict:
    s = (raw or "").strip()
    if not s:
        return {"error": "tom path"}
    try:
        p = Path(s).expanduser().resolve()
    except OSError:
        return {"error": "ugyldig path"}
    if not p.is_dir():
        return {"error": "ikke en mappe"}
    try:
        st = p.stat()
    except OSError:
        return {"error": "kan ikke lese mappa"}
    if st.st_uid != os.getuid():
        return {"error": "ikke din mappe"}
    home = owner_home()
    if p == home:
        return {"error": "ikke hele hjemmekatalogen som workspace"}
    sp = str(p)
    for b in _BLOCK_ROOTS:
        if sp == b or sp.startswith(b + "/"):
            return {"error": "blokkert path"}
    secrets = home / ".config" / "kalived"
    ssh = home / ".ssh"
    gpg = home / ".gnupg"
    for banned in (secrets, ssh, gpg):
        if p == banned or banned in p.parents:
            return {"error": "blokkert path"}
    if not any(p == a or a in p.parents for a in _allow_roots()):
        return {"error": "utenfor hjemmekatalogen"}
    return p


def _browseable(p: Path) -> bool:
    try:
        if not p.is_dir() or p.stat().st_uid != os.getuid():
            return False
    except OSError:
        return False
    home = owner_home()
    if p == home:
        return True
    got = check_open(str(p))
    if isinstance(got, Path):
        return True
    return any(p == a or a in p.parents for a in _allow_roots())


def root() -> Path:
    global _live
    if _live is not None and _live.is_dir():
        return _live
    data = _load_state()
    cur = str(data.get("current") or "").strip()
    if cur:
        got = check_open(cur)
        if isinstance(got, Path):
            _live = got
            return got
    p = _default_root()
    if not p.is_dir():
        raise FileNotFoundError(f"workspace mangler: {p}")
    return p


def is_kalived_repo() -> bool:
    try:
        return root().resolve() == kalived_repo()
    except (OSError, FileNotFoundError):
        return False


def hint_file() -> str:
    r = root()
    for name in ("README.md", "README", "index.html", "index.md"):
        if (r / name).is_file():
            return name
    return ""


def snapshot() -> dict:
    r = root()
    data = _load_state()
    recents = []
    for row in data.get("recents") or []:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        if not path:
            continue
        recents.append(
            {
                "path": path,
                "name": str(row.get("name") or Path(path).name),
                "used": str(row.get("used") or ""),
            }
        )
    kind = "kalived" if is_kalived_repo() else "external"
    name = r.name
    project = "" if kind == "kalived" else ("ws/" + name if _NAME_RE.match(name) and not name.startswith(".") else "")
    return {
        "root": str(r),
        "name": name,
        "kind": kind,
        "project": project,
        "hint": hint_file(),
        "recents": recents[:12],
    }


def open_workspace(raw: str) -> dict:
    global _live
    got = check_open(raw)
    if isinstance(got, dict):
        return got
    _live = got
    data = _load_state()
    recents = [r for r in (data.get("recents") or []) if isinstance(r, dict) and r.get("path") != str(got)]
    recents.insert(0, {"path": str(got), "name": got.name, "used": time.strftime("%Y-%m-%dT%H:%M:%S")})
    data["current"] = str(got)
    data["recents"] = recents[:12]
    _save_state(data)
    return {"ok": True, **snapshot()}


def mkdir_here(rel: str) -> dict:
    name = (rel or "").strip().strip("/")
    if not name or "/" in name or name in (".", "..") or not _NAME_RE.match(name) or name.startswith("."):
        return {"error": "ugyldig mappenavn"}
    try:
        p = safe(name)
    except ValueError as e:
        return {"error": str(e)}
    if p.exists():
        return {"error": "finnes allerede"}
    p.mkdir(mode=0o700)
    return {"ok": True, "path": rel_of(p), "dir": True}


def create_workspace(parent: str, name: str, git: bool = True) -> dict:
    nm = (name or "").strip()
    if not _NAME_RE.match(nm) or nm.startswith("."):
        return {"error": "ugyldig navn"}
    parent_s = (parent or "").strip() or str(owner_home())
    try:
        parent_p = Path(parent_s).expanduser().resolve()
    except OSError:
        return {"error": "ugyldig forelder"}
    if not _browseable(parent_p):
        return {"error": "kan ikke lage workspace der"}
    dest = parent_p / nm
    if dest.exists():
        return {"error": "finnes allerede"}
    dest.mkdir(mode=0o700)
    if git:
        subprocess.run(
            ["git", "init", "-b", "main"],
            cwd=str(dest),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    return open_workspace(str(dest))


def browse(raw: str = "") -> dict:
    home = owner_home()
    s = (raw or "").strip()
    try:
        p = Path(s).expanduser().resolve() if s else home
    except OSError:
        return {"error": "ugyldig path"}
    if not _browseable(p):
        return {"error": "kan ikke liste den mappa"}
    parent = str(p.parent) if p != home and _browseable(p.parent) else ""
    dirs = []
    try:
        kids = sorted(p.iterdir(), key=lambda x: x.name.lower())
    except OSError:
        kids = []
    for c in kids:
        if not c.is_dir() or c.name.startswith("."):
            continue
        if c.name in {".ssh", ".gnupg", "node_modules", "__pycache__", ".venv", "venv"}:
            continue
        openable = isinstance(check_open(str(c)), Path)
        dirs.append({"name": c.name, "path": str(c), "openable": openable})
        if len(dirs) >= 80:
            break
    openable = isinstance(check_open(str(p)), Path)
    return {
        "ok": True,
        "path": str(p),
        "parent": parent,
        "home": str(home),
        "dirs": dirs,
        "openable": openable,
    }


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


def read(rel: str, max_bytes: int = MAX_READ, start_line: int = 1, n_lines: int | None = None) -> dict:
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
    start_line = max(1, int(start_line or 1))
    out = {
        "path": rel_of(p),
        "language": language_of(rel_of(p)),
        "text": text,
        "n": len(text),
        "truncated": truncated,
    }
    if start_line > 1 or n_lines is not None:
        cap = int(n_lines) if n_lines is not None else 250
        cap = max(1, min(cap, 2000))
        lines = text.splitlines(keepends=True)
        chunk = lines[start_line - 1 : start_line - 1 + cap]
        window = "".join(chunk)
        out["text"] = window
        out["n"] = len(window)
        out["start_line"] = start_line
        out["end_line"] = start_line + len(chunk) - 1 if chunk else start_line - 1
        out["total_lines"] = len(lines)
        out["truncated"] = truncated or (start_line - 1 + len(chunk) < len(lines))
    return out


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
    out = {"path": rel_of(p), "n": len(text), "diff": diff[:12000], "wrote": True}
    if str(out["path"]).lower().endswith((".html", ".htm")):
        out["mode"] = "iframe"
    return out


def _headings(s: str) -> list[str]:
    return [ln.rstrip() for ln in s.splitlines() if ln.startswith("#")]


def edit(rel: str, old: str, new: str) -> dict:
    p = safe(rel)
    if not p.is_file():
        raise FileNotFoundError(rel)
    if skipped(p):
        raise ValueError("hoppet over")
    text = p.read_text(encoding="utf-8")
    old, new = old.replace("\r\n", "\n"), new.replace("\r\n", "\n")
    if "\n" not in old and len(old) < 80:
        return {
            "error": "old_string for kort — ta med omliggende linjer (inkl. overskrift) så innsettinga treffer seksjonen, ikke slutten av fila",
            "path": rel_of(p),
        }
    if old not in text:
        return {"error": "old_string ikke funnet", "path": rel_of(p)}
    if text.count(old) > 1:
        return {"error": "old_string treffer mer enn én gang — gjør den unik med mer kontekst", "path": rel_of(p)}
    # appending a brand-new markdown heading at EOF is how we got a second «Etter A»
    stripped = text.rstrip()
    if stripped.endswith(old.rstrip()) and new.startswith(old):
        rest = new[len(old) :].lstrip("\n")
        if rest.startswith("#"):
            return {
                "error": "ikke lim ny overskrift på slutten av fila — utvid eksisterende seksjon; old_string skal inneholde overskriften du redigerer under",
                "path": rel_of(p),
            }
    updated = text.replace(old, new, 1)
    before, after = _headings(text), _headings(updated)
    extra = [h for h in after if after.count(h) > before.count(h) and before.count(h) >= 1]
    if extra:
        return {
            "error": "edit ville duplisert overskrift: " + ", ".join(extra[:5]) + " — rediger inni den eksisterende seksjonen",
            "path": rel_of(p),
        }
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
_TOOLCHAIN = re.compile(
    r"(^|[\s;|&])(npm|npx|bun|pnpm|yarn|cargo|pip3?)\b",
    re.I,
)
_TOOLCHAIN_SCOPE = re.compile(
    r"(?:^|[\s=/])(?:apps|docs)/|--prefix\s+(?:apps|docs)/|-C\s+(?:apps|docs)/",
    re.I,
)


def toolchain_ok(blob: str) -> bool:
    """npm/bun/pip/cargo: in kalived-repo only under apps/ or docs/. External workspace: rot er lov."""
    if not _TOOLCHAIN.search(blob or ""):
        return True
    if not is_kalived_repo():
        return True
    return bool(_TOOLCHAIN_SCOPE.search(blob or ""))
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


def _nb(fd) -> None:
    if fd is None:
        return
    fl = fcntl.fcntl(fd.fileno(), fcntl.F_GETFL)
    fcntl.fcntl(fd.fileno(), fcntl.F_SETFL, fl | os.O_NONBLOCK)


def _read_nb(stream) -> bytes:
    if stream is None:
        return b""
    try:
        return stream.read(8192) or b""
    except (OSError, ValueError):
        return b""


def _redact(s: str) -> str:
    for secret in ("sk-", "API_KEY=", "BEGIN PRIVATE"):
        if secret in s:
            s = s.replace(secret, "«redact»")
    return s


def bash(
    argv: list[str] | None = None,
    line: str | None = None,
    timeout_s: float = 120,
    cancel=None,
    on_chunk=None,
) -> dict:
    """Run one command in workspace. Mutating. No sudo, no git push."""
    if argv and isinstance(argv, list) and any(str(a) for a in argv):
        cmd = [str(a) for a in argv if str(a) != ""]
    elif line and str(line).strip():
        raw = str(line).strip()
        if re.search(r"[|&;<>]", raw):
            cmd = ["/bin/bash", "-c", raw]
        else:
            try:
                cmd = shlex.split(raw, posix=True)
            except ValueError as e:
                return {"error": f"kan ikke parse linje: {e}"}
    else:
        return {"error": "trenger argv eller line"}
    if not cmd:
        return {"error": "tom kommando"}
    blob = " ".join(cmd)
    if _DENY.search(blob):
        return {"error": "nekta: sudo/git push/destruktiv root — PTY til passord, du eier remote", "argv": cmd}
    if not toolchain_ok(blob):
        return {
            "error": "nekta: npm/bun/pip/cargo bare i apps/ eller docs/ (cd apps/<navn> eller --prefix). Ikke workspace-rot.",
            "argv": cmd,
        }
    if re.search(r"(^|[\s;|&])git\s+commit(\s|$)", blob, re.I):
        return {"error": "bruk repo_git action=commit (hake på). Ikke git commit via repo_bash", "argv": cmd}
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
            bufsize=0,
        )
    except FileNotFoundError:
        return {"error": f"ikke funnet: {cmd[0]}", "argv": cmd, "cwd": cwd}
    _nb(proc.stdout)
    _nb(proc.stderr)
    if on_chunk:
        on_chunk("meta", f"$ {' '.join(cmd)}  pid={proc.pid}\n")
    t0 = time.time()
    timed = False
    cancelled = False
    out_b: list[bytes] = []
    err_b: list[bytes] = []

    def drain() -> None:
        chunk = _read_nb(proc.stdout)
        if chunk:
            out_b.append(chunk)
            if on_chunk:
                on_chunk("stdout", _redact(chunk.decode("utf-8", errors="replace")))
        chunk = _read_nb(proc.stderr)
        if chunk:
            err_b.append(chunk)
            if on_chunk:
                on_chunk("stderr", _redact(chunk.decode("utf-8", errors="replace")))

    while proc.poll() is None:
        drain()
        if cancel is not None and getattr(cancel, "is_set", lambda: False)():
            _kill_pg(proc.pid)
            cancelled = True
            break
        if time.time() - t0 > timeout_s:
            _kill_pg(proc.pid)
            timed = True
            break
        time.sleep(0.08)
    drain()
    try:
        rest_out, rest_err = proc.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        _kill_pg(proc.pid)
        rest_out, rest_err = proc.communicate(timeout=2)
    if rest_out:
        out_b.append(rest_out)
        if on_chunk:
            on_chunk("stdout", _redact(rest_out.decode("utf-8", errors="replace")))
    if rest_err:
        err_b.append(rest_err)
        if on_chunk:
            on_chunk("stderr", _redact(rest_err.decode("utf-8", errors="replace")))

    def tail(parts: list[bytes]) -> str:
        s = b"".join(parts).decode("utf-8", errors="replace")
        if len(s) > _TAIL:
            return s[-_TAIL:]
        return _redact(s)

    stdout, stderr = tail(out_b), tail(err_b)
    return {
        "argv": cmd,
        "cwd": cwd,
        "pid": proc.pid,
        "exit_code": proc.returncode,
        "timeout": timed,
        "cancelled": cancelled,
        "stdout_tail": stdout,
        "stderr_tail": stderr,
        "elapsed_s": round(time.time() - t0, 2),
    }


@router.get("")
def info():
    return snapshot()


class OpenIn(BaseModel):
    path: str = ""


class MkdirIn(BaseModel):
    name: str = ""


class CreateIn(BaseModel):
    parent: str = ""
    name: str = ""
    git: bool = True


def _or_err(row: dict):
    if row.get("error"):
        raise HTTPException(400, row["error"])
    return row


@router.get("/browse")
def browse_http(path: str = ""):
    return _or_err(browse(path))


@router.post("/open")
def open_http(body: OpenIn):
    return _or_err(open_workspace(body.path))


@router.post("/mkdir")
def mkdir_http(body: MkdirIn):
    return _or_err(mkdir_here(body.name))


@router.post("/create")
def create_http(body: CreateIn):
    return _or_err(create_workspace(body.parent, body.name, git=body.git))


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
