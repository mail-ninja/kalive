"""Operator git in the cockpit sidebar. Agent repo_git still never pushes."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import repo_git as rg
from . import secrets_store as secrets
from . import workspace as w

TOKEN_KEYS = ("GITHUB_TOKEN", "GH_TOKEN", "GH_ACCESS_TOKEN")
WALLE = re.compile(r"wallE|mail-ninja/wallE", re.I)
GITHUB_API = "https://api.github.com"


def github_token() -> str:
    env = secrets.load_env()
    for k in TOKEN_KEYS:
        v = (env.get(k) or "").strip()
        if v:
            return v
    return ""


def _headers(token: str) -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "kalived-cockpit",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        h["Authorization"] = "Bearer " + token
    return h


def github_who(token: str | None = None) -> dict[str, Any]:
    tok = (token if token is not None else github_token()).strip()
    if not tok:
        return {"ok": False, "login": None, "set": False}
    req = urllib.request.Request(GITHUB_API + "/user", headers=_headers(tok), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            body = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return {"ok": False, "set": True, "error": f"github {e.code}", "login": None}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return {"ok": False, "set": True, "error": str(e)[:200], "login": None}
    login = str(body.get("login") or "")
    return {
        "ok": bool(login),
        "set": True,
        "login": login or None,
        "name": str(body.get("name") or "") or None,
        "hint": secrets._mask("GITHUB_TOKEN", tok).get("hint"),
    }


def github_login(token: str) -> dict[str, Any]:
    tok = (token or "").strip()
    if len(tok) < 8:
        return {"error": "token for kort"}
    who = github_who(tok)
    if not who.get("ok"):
        return {"error": who.get("error") or "ugyldig GitHub-token", **who}
    secrets.put({"GITHUB_TOKEN": tok})
    return {"ok": True, **who, "set": True}


def github_logout() -> dict[str, Any]:
    secrets.put({"GITHUB_TOKEN": None, "GH_TOKEN": None, "GH_ACCESS_TOKEN": None})
    return {"ok": True, "login": None, "set": False}


def _remotes() -> list[dict[str, str]]:
    r = rg._git("remote", "-v")
    seen: dict[str, dict[str, str]] = {}
    for line in (r.stdout or "").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name, url = parts[0], parts[1]
        kind = "fetch"
        if len(parts) >= 3 and "push" in parts[2]:
            kind = "push"
        row = seen.setdefault(name, {"name": name, "fetch": "", "push": ""})
        row[kind] = url
        if not row["fetch"]:
            row["fetch"] = url
        if not row["push"]:
            row["push"] = url
    out = []
    for row in seen.values():
        url = row.get("push") or row.get("fetch") or ""
        row["ssh"] = _is_ssh(url)
        row["github"] = _is_https_github(url) or "github.com:" in url
        row["blocked"] = bool(_blocked(row["name"], url))
        out.append(row)
    return out


def _blocked(name: str, url: str) -> str | None:
    blob = f"{name} {url}"
    if WALLE.search(blob):
        return "nekta: origin/wallE"
    return None


_REMOTE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,40}$")
_REMOTE_URL = re.compile(
    r"^(?:git@[\w.-]+:[\w./-]+(?:\.git)?|https://[\w.-]+/[\w./-]+(?:\.git)?)$"
)


def add_remote(name: str, url: str) -> dict[str, Any]:
    repo = rg._ensure_repo()
    if isinstance(repo, dict):
        return repo
    nm = (name or "").strip()
    u = (url or "").strip()
    if not _REMOTE_NAME.match(nm):
        return {"error": "ugyldig remote-navn"}
    if not _REMOTE_URL.match(u):
        return {"error": "ugyldig remote-url"}
    blocked = _blocked(nm, u)
    if blocked:
        return {"error": blocked}
    if any(r["name"] == nm for r in _remotes()):
        return {"error": f"remote {nm} finnes"}
    r = rg._git("remote", "add", nm, u)
    if r.returncode != 0:
        return {"error": (r.stderr or r.stdout or "git remote add feilet")[:400], "action": "remote-add"}
    st = status()
    st["ok"] = True
    st["action"] = "remote-add"
    st["remote"] = nm
    st["summary"] = f"la til {nm} → {u}"
    return st


def status() -> dict[str, Any]:
    repo = rg._ensure_repo()
    if isinstance(repo, dict):
        return {
            "ok": False,
            "repo": False,
            "error": repo.get("error") or "ikke et git-repo",
            "branch": "",
            "files": [],
            "remotes": [],
            "github": github_who(),
        }
    st = rg._status()
    if st.get("error"):
        return st
    st["repo"] = True
    st["remotes"] = _remotes()
    st["github"] = github_who()
    return st


def init() -> dict[str, Any]:
    root = w.root()
    if (root / ".git").exists():
        st = status()
        st["ok"] = True
        st["repo"] = True
        st["action"] = "init"
        st["summary"] = "allerede et git-repo"
        return st
    r = rg._git("init", "-b", "main")
    if r.returncode != 0:
        return {"error": (r.stderr or r.stdout or "git init feilet")[:400], "action": "init"}
    st = status()
    st["ok"] = True
    st["repo"] = True
    st["action"] = "init"
    st["summary"] = "git init -b main i " + str(root)
    return st


def stage(paths: list[str], *, unstage: bool = False) -> dict[str, Any]:
    repo = rg._ensure_repo()
    if isinstance(repo, dict):
        return repo
    resolved = rg._safe_paths(paths)
    if isinstance(resolved, dict):
        return resolved
    if not resolved:
        return {"error": "oppgi paths"}
    if unstage:
        r = rg._git("restore", "--staged", "--", *resolved)
        act = "unstage"
    else:
        r = rg._git("add", "--", *resolved)
        act = "stage"
    if r.returncode != 0:
        return {"error": (r.stderr or r.stdout or f"git {act} feilet")[:400], "action": act}
    st = rg._status()
    st["ok"] = True
    st["action"] = act
    st["paths"] = resolved
    return st


def commit(message: str, paths: list[str] | None = None, *, all_files: bool = False) -> dict[str, Any]:
    """Operator commit from the Git tab. Not the agent tool."""
    repo = rg._ensure_repo()
    if isinstance(repo, dict):
        return repo
    msg = (message or "").strip()
    if len(msg) < 3:
        return {"error": "commit trenger message"}
    if all_files:
        add = rg._git("add", "-A")
        if add.returncode != 0:
            return {"error": (add.stderr or "git add feilet")[:400]}
    elif paths:
        resolved = rg._safe_paths(paths)
        if isinstance(resolved, dict):
            return resolved
        add = rg._git("add", "--", *resolved)
        if add.returncode != 0:
            return {"error": (add.stderr or "git add feilet")[:400]}
    staged = rg._git("diff", "--cached", "--quiet")
    if staged.returncode == 0:
        return {"error": "ingenting staged"}
    r = rg._git("-c", "commit.gpgsign=false", "commit", "--no-gpg-sign", "-m", msg, timeout=45)
    if r.returncode != 0:
        return {"error": (r.stderr or r.stdout or "git commit feilet")[:400]}
    sha = (rg._git("rev-parse", "--short", "HEAD").stdout or "").strip()
    st = rg._status()
    st["ok"] = True
    st["action"] = "commit"
    st["sha"] = sha
    st["message"] = msg
    st["summary"] = f"commit {sha}  {msg.splitlines()[0][:120]}"
    return st


def _is_https_github(url: str) -> bool:
    try:
        u = urlparse(url)
    except Exception:
        return False
    return u.scheme in ("http", "https") and (u.hostname or "").lower() in {"github.com", "www.github.com"}


def _is_ssh(url: str) -> bool:
    s = (url or "").strip()
    return s.startswith("git@") or s.startswith("ssh://")


_ASKPASS_SH = """#!/bin/sh
case "$1" in
  *[Uu]sername*) echo x-access-token ;;
  *) printf '%s\\n' "$KALIVED_GIT_ASKPASS_TOKEN" ;;
esac
"""


def _git_auth(*args: str, url: str, timeout: float = 60) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    extra: list[str] = []
    tmp: str | None = None
    if _is_https_github(url):
        tok = github_token()
        if tok:
            tmpd = tempfile.mkdtemp(prefix="kalived-askpass-")
            tmp = tmpd
            script = Path(tmpd) / "askpass"
            script.write_text(_ASKPASS_SH, encoding="utf-8")
            os.chmod(tmpd, 0o700)
            os.chmod(script, 0o700)
            env["GIT_ASKPASS"] = str(script)
            env["SSH_ASKPASS"] = str(script)
            env["GIT_ASKPASS_REQUIRE"] = "force"
            env["KALIVED_GIT_ASKPASS_TOKEN"] = tok
            extra = ["-c", "credential.helper="]
    argv = ["git", *extra, *args]
    try:
        return subprocess.run(
            argv,
            cwd=str(w.root()),
            capture_output=True,
            text=True,
            timeout=max(5.0, min(float(timeout), 90.0)),
            env=env,
            check=False,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(argv, 127, "", "git ikke funnet")
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "git timeout")
        return subprocess.CompletedProcess(argv, 124, out, err)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def _remote_url(name: str) -> tuple[str, str] | dict[str, Any]:
    name = (name or "").strip()
    if not name or not re.match(r"^[A-Za-z0-9._-]+$", name):
        return {"error": "ugyldig remote"}
    rows = {r["name"]: r for r in _remotes()}
    row = rows.get(name)
    if not row:
        return {"error": f"ukjent remote {name}"}
    url = row.get("push") or row.get("fetch") or ""
    blocked = _blocked(name, url)
    if blocked:
        return {"error": blocked, "remote": name, "url": url}
    return name, url


def push(remote: str = "", branch: str = "") -> dict[str, Any]:
    repo = rg._ensure_repo()
    if isinstance(repo, dict):
        return repo
    if not remote:
        names = [r["name"] for r in _remotes()]
        remote = "kalive" if "kalive" in names else (names[0] if names else "")
    got = _remote_url(remote)
    if isinstance(got, dict):
        return got
    name, url = got
    if _is_https_github(url) and not github_token():
        return {"error": "logg inn med GitHub-token først", "remote": name}
    br = (branch or "").strip()
    if br and not re.match(r"^[A-Za-z0-9._/-]+$", br):
        return {"error": "ugyldig branch"}
    args = ["push", "-u", name]
    if br:
        args.append(br)
    r = _git_auth(*args, url=url, timeout=70)
    if r.returncode != 0:
        return {"error": (r.stderr or r.stdout or "git push feilet")[:600], "action": "push", "remote": name}
    st = rg._status()
    st["ok"] = True
    st["action"] = "push"
    st["remote"] = name
    st["summary"] = (r.stderr or r.stdout or "pushet").strip()[:400]
    return st


def pull(remote: str = "", branch: str = "") -> dict[str, Any]:
    repo = rg._ensure_repo()
    if isinstance(repo, dict):
        return repo
    if not remote:
        names = [r["name"] for r in _remotes()]
        remote = "kalive" if "kalive" in names else (names[0] if names else "")
    got = _remote_url(remote)
    if isinstance(got, dict):
        return got
    name, url = got
    if _is_https_github(url) and not github_token():
        return {"error": "logg inn med GitHub-token først", "remote": name}
    br = (branch or "").strip()
    args = ["pull", "--ff-only", name]
    if br:
        if not re.match(r"^[A-Za-z0-9._/-]+$", br):
            return {"error": "ugyldig branch"}
        args.append(br)
    r = _git_auth(*args, url=url, timeout=70)
    if r.returncode != 0:
        return {"error": (r.stderr or r.stdout or "git pull feilet")[:600], "action": "pull", "remote": name}
    st = rg._status()
    st["ok"] = True
    st["action"] = "pull"
    st["remote"] = name
    st["summary"] = (r.stdout or r.stderr or "pullet").strip()[:400]
    return st


def log(n: int = 12) -> dict[str, Any]:
    repo = rg._ensure_repo()
    if isinstance(repo, dict):
        return repo
    return rg._log(n=n)
