"""Open VSX marketplace + local VSIX install. Not a VS Code extension host."""
from __future__ import annotations

import io
import json
import os
import re
import stat
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

OPEN_VSX = "https://open-vsx.org"
ALLOW_HOSTS = frozenset({"open-vsx.org", "www.open-vsx.org"})
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.[A-Za-z0-9][A-Za-z0-9._-]*$")
NS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
MAX_VSIX = 32 * 1024 * 1024


def root() -> Path:
    env = os.environ.get("KALIVED_EXTENSIONS")
    if env:
        return Path(env).expanduser().resolve()
    home = os.environ.get("KALIVED_OWNER_HOME") or str(Path.home())
    return Path(home) / ".config" / "kalived" / "extensions"


def registry_path() -> Path:
    return root() / "registry.json"


def _load_reg() -> dict[str, Any]:
    p = registry_path()
    if not p.is_file():
        return {"installed": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"installed": {}}
    if not isinstance(data, dict):
        return {"installed": {}}
    inst = data.get("installed")
    if not isinstance(inst, dict):
        data["installed"] = {}
    return data


def _save_reg(data: dict[str, Any]) -> None:
    d = root()
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, stat.S_IRWXU)
    p = registry_path()
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    tmp.replace(p)
    os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)


def _http_json(url: str, timeout: float = 15) -> dict[str, Any]:
    u = urlparse(url)
    host = (u.hostname or "").lower()
    if u.scheme != "https" or host not in ALLOW_HOSTS:
        return {"error": "bare open-vsx.org"}
    req = Request(url, headers={"User-Agent": "kalived-cockpit", "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except Exception as e:
        return {"error": f"open-vsx: {e}"[:240]}
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return {"error": "open-vsx: ugyldig json"}


def _http_bytes(url: str, timeout: float = 40) -> bytes | dict[str, Any]:
    u = urlparse(url)
    host = (u.hostname or "").lower()
    if u.scheme != "https" or host not in ALLOW_HOSTS:
        return {"error": "bare open-vsx.org"}
    req = Request(url, headers={"User-Agent": "kalived-cockpit"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            final = urlparse(resp.geturl())
            fhost = (final.hostname or "").lower()
            # Open VSX may redirect to a blob host; keep the first hop on open-vsx.org.
            if final.scheme not in ("https",) or (
                fhost not in ALLOW_HOSTS and not fhost.endswith(".blob.core.windows.net")
            ):
                return {"error": "uventet vsix-host"}
            data = resp.read(MAX_VSIX + 1)
    except Exception as e:
        return {"error": f"nedlasting: {e}"[:240]}
    if len(data) > MAX_VSIX:
        return {"error": "vsix for stor"}
    if len(data) < 40:
        return {"error": "tom vsix"}
    return data


def search(query: str, size: int = 16) -> dict[str, Any]:
    q = (query or "").strip()[:80]
    n = max(1, min(int(size or 16), 40))
    url = OPEN_VSX + "/api/-/search?" + urlencode({"query": q or "theme", "size": n})
    data = _http_json(url)
    if data.get("error"):
        return data
    rows = []
    for ext in data.get("extensions") or []:
        if not isinstance(ext, dict):
            continue
        ns = str(ext.get("namespace") or "")
        name = str(ext.get("name") or "")
        files = ext.get("files") if isinstance(ext.get("files"), dict) else {}
        rows.append(
            {
                "id": f"{ns}.{name}" if ns and name else "",
                "namespace": ns,
                "name": name,
                "display": str(ext.get("displayName") or name),
                "version": str(ext.get("version") or ""),
                "description": str(ext.get("description") or "")[:280],
                "download": str(files.get("download") or ""),
                "icon": str(files.get("icon") or ""),
            }
        )
    return {"ok": True, "query": q, "n": len(rows), "total": data.get("totalSize"), "extensions": rows}


def _read_package(zf: zipfile.ZipFile) -> dict[str, Any]:
    names = zf.namelist()
    pkg_name = None
    for cand in ("extension/package.json", "package.json"):
        if cand in names:
            pkg_name = cand
            break
    if not pkg_name:
        for n in names:
            if n.endswith("/package.json") and n.count("/") <= 2:
                pkg_name = n
                break
    if not pkg_name:
        return {"error": "vsix mangler package.json"}
    try:
        pkg = json.loads(zf.read(pkg_name).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"error": "ugyldig package.json"}
    if not isinstance(pkg, dict):
        return {"error": "ugyldig package.json"}
    pub = str(pkg.get("publisher") or pkg.get("namespace") or "")
    name = str(pkg.get("name") or "")
    if not pub or not name:
        return {"error": "package.json mangler publisher/name"}
    eid = f"{pub}.{name}"
    if not ID_RE.match(eid):
        return {"error": f"ugyldig extension-id {eid}"}
    return {
        "id": eid,
        "publisher": pub,
        "name": name,
        "display": str(pkg.get("displayName") or name),
        "version": str(pkg.get("version") or ""),
        "description": str(pkg.get("description") or "")[:400],
        "engines": pkg.get("engines") if isinstance(pkg.get("engines"), dict) else {},
        "contributes": sorted((pkg.get("contributes") or {}).keys())
        if isinstance(pkg.get("contributes"), dict)
        else [],
        "kalived": bool(isinstance(pkg.get("contributes"), dict) and "kalived" in (pkg.get("contributes") or {})),
        "package": pkg_name,
    }


def install_vsix(data: bytes, *, source: str = "file") -> dict[str, Any]:
    if not data or len(data) > MAX_VSIX:
        return {"error": "ugyldig vsix"}
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return {"error": "ikke en vsix/zip"}
    meta = _read_package(zf)
    if meta.get("error"):
        return meta
    dest = root() / meta["id"]
    if dest.exists():
        import shutil

        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    os.chmod(root(), stat.S_IRWXU)
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if name.endswith("/") or ".." in Path(name).parts:
            continue
        # strip extension/ prefix so package.json sits at dest root
        rel = name
        if rel.startswith("extension/"):
            rel = rel[len("extension/") :]
        if not rel or rel.endswith("/"):
            continue
        out = dest / rel
        try:
            out.relative_to(dest)
        except ValueError:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(zf.read(info.filename))
    reg = _load_reg()
    inst = reg.setdefault("installed", {})
    inst[meta["id"]] = {
        "id": meta["id"],
        "version": meta["version"],
        "display": meta["display"],
        "enabled": True,
        "source": source,
        "kalived": meta["kalived"],
        "contributes": meta["contributes"],
        "description": meta["description"],
    }
    _save_reg(reg)
    return {"ok": True, **inst[meta["id"]], "path": str(dest)}


def install_openvsx(namespace: str, name: str, version: str = "") -> dict[str, Any]:
    ns = (namespace or "").strip()
    nm = (name or "").strip()
    if not NS_RE.match(ns) or not NS_RE.match(nm):
        return {"error": "ugyldig namespace/name"}
    ver = (version or "").strip()
    path = f"/api/{ns}/{nm}"
    if ver:
        if not re.match(r"^[A-Za-z0-9._+-]+$", ver):
            return {"error": "ugyldig version"}
        path += "/" + ver
    info = _http_json(OPEN_VSX + path)
    if info.get("error"):
        return info
    files = info.get("files") if isinstance(info.get("files"), dict) else {}
    url = str(files.get("download") or "")
    if not url:
        return {"error": "ingen vsix-url"}
    blob = _http_bytes(url)
    if isinstance(blob, dict):
        return blob
    src = f"open-vsx:{ns}.{nm}@{info.get('version') or ver or 'latest'}"
    return install_vsix(blob, source=src)


def uninstall(eid: str) -> dict[str, Any]:
    if not ID_RE.match(eid or ""):
        return {"error": "ugyldig id"}
    dest = root() / eid
    if dest.exists():
        import shutil

        shutil.rmtree(dest)
    reg = _load_reg()
    inst = reg.setdefault("installed", {})
    inst.pop(eid, None)
    _save_reg(reg)
    return {"ok": True, "id": eid, "removed": True}


def set_enabled(eid: str, enabled: bool) -> dict[str, Any]:
    if not ID_RE.match(eid or ""):
        return {"error": "ugyldig id"}
    reg = _load_reg()
    inst = reg.setdefault("installed", {})
    row = inst.get(eid)
    if not isinstance(row, dict):
        return {"error": "ikke installert"}
    row["enabled"] = bool(enabled)
    _save_reg(reg)
    return {"ok": True, **row}


def list_installed() -> dict[str, Any]:
    reg = _load_reg()
    rows = []
    for eid, row in (reg.get("installed") or {}).items():
        if not isinstance(row, dict):
            continue
        item = dict(row)
        item["id"] = eid
        item["path"] = str(root() / eid)
        rows.append(item)
    rows.sort(key=lambda r: str(r.get("display") or r.get("id") or "").lower())
    return {
        "ok": True,
        "root": str(root()),
        "n": len(rows),
        "extensions": rows,
        "note": "VSIX/Open VSX. Kjører i cockpit bare med contributes.kalived.",
    }
