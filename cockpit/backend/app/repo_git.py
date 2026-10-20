"""Git for the build agent. status/diff/log/commit. Never push."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

from . import workspace as w

ACTIONS = ("status", "diff", "log", "commit")
_MAX_DIFF = 80_000
_MAX_PATHS = 40
_MAX_MSG = 2000


def _git(*args: str, timeout: float = 30) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "NO_COLOR": "1",
    }
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(w.root()),
            capture_output=True,
            text=True,
            timeout=max(2.0, min(float(timeout), 60.0)),
            env=env,
            check=False,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(["git", *args], 127, "", "git ikke funnet")
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "git timeout")
        return subprocess.CompletedProcess(["git", *args], 124, out, err)


def _ensure_repo() -> Path | dict[str, Any]:
    root = w.root()
    gitdir = root / ".git"
    if not gitdir.exists():
        return {"error": f"ikke et git-repo: {root}"}
    return root


def _safe_paths(raw: Any) -> list[str] | dict[str, Any]:
    if raw is None:
        return []
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, list):
        items = [str(x) for x in raw if str(x).strip()]
    else:
        return {"error": "paths må være streng eller liste"}
    if len(items) > _MAX_PATHS:
        return {"error": f"maks {_MAX_PATHS} paths"}
    out: list[str] = []
    for item in items:
        try:
            p = w.safe(item)
        except ValueError as e:
            return {"error": str(e)}
        rel = w.rel_of(p)
        if rel.startswith(".git/") or rel == ".git":
            return {"error": "ikke .git"}
        out.append(rel)
    return out


def _status() -> dict[str, Any]:
    r = _git("status", "--porcelain=v1", "-b")
    if r.returncode != 0:
        return {"error": (r.stderr or r.stdout or "git status feilet")[:400], "action": "status"}
    lines = (r.stdout or "").splitlines()
    branch = ""
    upstream = ""
    ahead = 0
    behind = 0
    files: list[dict[str, str]] = []
    if lines and lines[0].startswith("## "):
        head = lines[0][3:]
        ab = re.search(r"\[ahead (\d+)(?:, behind (\d+))?\]", head)
        if ab:
            ahead = int(ab.group(1))
            behind = int(ab.group(2) or 0)
        bb = re.search(r"\[behind (\d+)\]", head)
        if bb and not ab:
            behind = int(bb.group(1))
        core = re.sub(r"\s*\[.*\]$", "", head).strip()
        if core.startswith("No commits yet on "):
            core = core[len("No commits yet on ") :].strip()
        if "..." in core:
            branch, upstream = core.split("...", 1)
        else:
            branch = core
        lines = lines[1:]
    for line in lines:
        if len(line) < 4:
            continue
        xy, path = line[:2], line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[-1]
        files.append({"xy": xy, "path": path})
    dirty = bool(files)
    summary = branch or "HEAD"
    if upstream:
        summary += f"...{upstream}"
    if ahead:
        summary += f" +{ahead}"
    if behind:
        summary += f" -{behind}"
    if dirty:
        summary += f"  {len(files)} fil" + ("" if len(files) == 1 else "er")
    else:
        summary += "  rent"
    if files:
        summary += "\n" + "\n".join(f"{f['xy']} {f['path']}" for f in files[:40])
    out: dict[str, Any] = {
        "action": "status",
        "branch": branch,
        "upstream": upstream or None,
        "ahead": ahead,
        "behind": behind,
        "dirty": dirty,
        "files": files,
        "n": len(files),
        "summary": summary,
    }
    if files:
        out["path"] = files[0]["path"]
    return out


def _diff(path: str | None = None, staged: bool = False) -> dict[str, Any]:
    base = ["diff", "--no-ext-diff"]
    if staged:
        base.append("--cached")
    rel = None
    tail: list[str] = []
    if path:
        try:
            rel = w.rel_of(w.safe(path))
        except ValueError as e:
            return {"error": str(e), "action": "diff"}
        tail = ["--", rel]
    stat = _git(*base, "--stat", *tail)
    patch = _git(*base, *tail)
    if patch.returncode not in (0, 1):
        return {"error": (patch.stderr or "git diff feilet")[:400], "action": "diff"}
    diff = (patch.stdout or "")[:_MAX_DIFF]
    summary = (stat.stdout or "").strip() or ("ingen diff" if not diff.strip() else "diff")
    out: dict[str, Any] = {
        "action": "diff",
        "staged": bool(staged),
        "diff": diff,
        "summary": summary[:1200],
        "n": diff.count("\n"),
    }
    if rel:
        out["path"] = rel
    return out


def _log(n: int = 12) -> dict[str, Any]:
    n = max(1, min(int(n or 12), 30))
    r = _git("log", f"-n{n}", "--format=%h\t%s\t%an")
    if r.returncode != 0:
        err = (r.stderr or "").strip()
        if "does not have any commits" in err or "your current branch 'master'" in err:
            return {"action": "log", "commits": [], "n": 0, "summary": "ingen commits"}
        return {"error": err[:400] or "git log feilet", "action": "log"}
    commits = []
    for line in (r.stdout or "").splitlines():
        parts = line.split("\t", 2)
        if len(parts) >= 2:
            commits.append({"sha": parts[0], "subject": parts[1], "author": parts[2] if len(parts) > 2 else ""})
    summary = "\n".join(f"{c['sha']}  {c['subject']}" for c in commits) or "ingen commits"
    return {"action": "log", "commits": commits, "n": len(commits), "summary": summary}


def _commit(message: str, paths: list[str], allow_mutate: bool) -> dict[str, Any]:
    if not allow_mutate:
        return {"error": "mutating: huk av «agent får kjøre» i cockpit", "action": "commit"}
    msg = (message or "").strip()
    if len(msg) < 3:
        return {"error": "commit trenger message", "action": "commit"}
    if len(msg) > _MAX_MSG:
        return {"error": f"message maks {_MAX_MSG} tegn", "action": "commit"}
    if paths:
        for rel in paths:
            p = w.safe(rel)
            if not p.exists():
                return {"error": f"finnes ikke: {rel}", "action": "commit"}
            add = _git("add", "--", rel)
            if add.returncode != 0:
                return {"error": (add.stderr or f"git add {rel} feilet")[:400], "action": "commit"}
    staged = _git("diff", "--cached", "--quiet")
    if staged.returncode == 0:
        return {"error": "ingenting staged — oppgi paths eller git add først", "action": "commit"}
    r = _git("-c", "commit.gpgsign=false", "commit", "--no-gpg-sign", "-m", msg, timeout=45)
    if r.returncode != 0:
        return {"error": (r.stderr or r.stdout or "git commit feilet")[:400], "action": "commit"}
    sha = _git("rev-parse", "--short", "HEAD")
    short = (sha.stdout or "").strip()
    first = paths[0] if paths else None
    out: dict[str, Any] = {
        "action": "commit",
        "ok": True,
        "sha": short,
        "message": msg,
        "paths": paths,
        "summary": f"commit {short}  {msg.splitlines()[0][:120]}",
    }
    if first:
        out["path"] = first
    return out


def run(
    action: str,
    *,
    message: str = "",
    paths: Any = None,
    path: str | None = None,
    staged: bool = False,
    n: int = 12,
    allow_mutate: bool = False,
) -> dict[str, Any]:
    act = (action or "status").strip().lower()
    if act == "push":
        return {"error": "nekta: git push — du eier remote", "action": "push"}
    if act not in ACTIONS:
        return {"error": f"ukjent action {act!r}. status|diff|log|commit", "action": act}
    repo = _ensure_repo()
    if isinstance(repo, dict):
        return repo
    if act == "status":
        return _status()
    if act == "diff":
        return _diff(path=path, staged=bool(staged))
    if act == "log":
        return _log(n=n)
    resolved = _safe_paths(paths if paths is not None else path)
    if isinstance(resolved, dict):
        return resolved
    return _commit(message, resolved, allow_mutate=allow_mutate)
