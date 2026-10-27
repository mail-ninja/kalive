#!/usr/bin/env python3
"""Classify AIDE report paths. Scoped freeze is a prefix list — not a full --init."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA = 1
# AIDE 0.19: "f++++++++++++++++++: /path"  or  "f >.... m ..H      : /path"
ENTRY = re.compile(r"^([fld])(?:\++| [^:]*)\s*:\s+(\S.*)$")
FILE_LINE = re.compile(r"^File:\s+(\S.*)$")

DEFAULT_SCOPE = (
    "/etc/sudoers.d/kalived",
    "/usr/local/lib/kalived",
    "/usr/sbin/kalived-ctl",
    "/etc/systemd/system/kalived-watch.service",
    "/etc/systemd/system/kalived-watch.timer",
    "/etc/systemd/system/timers.target.wants/kalived-watch.timer",
)

IDENTITY_EXACT = frozenset(
    {
        "/etc/passwd",
        "/etc/shadow",
        "/etc/group",
        "/etc/gshadow",
        "/etc/sudoers",
        "/etc/ld.so.preload",
        "/usr/bin/sudo",
        "/usr/bin/su",
        "/usr/bin/passwd",
        "/usr/bin/pkexec",
    }
)

_ESC = re.compile(r"\\x([0-9A-Fa-f]{2})")

SEV = {
    "self_sudoers": ("WARN", "FIM-AIDE", "AIDE self_sudoers"),
    "self_helper": ("INFO", "FIM-AIDE", "AIDE self_helper"),
    "snap_proton": ("WARN", "FIM-AIDE", "AIDE snap_proton"),
    "snap_other": ("WARN", "FIM-AIDE", "AIDE snap_other"),
    "identity": ("ALERT", "FIM-AIDE", "AIDE identity"),
    "stale": ("WARN", "FIM-AIDE-STALE", "AIDE stale"),
    "pkg": ("WARN", "FIM-AIDE-PKG", "AIDE pkg"),
    "other": ("WARN", "FIM-AIDE", "AIDE other"),
}

DPKG_EVENT = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?:upgrade|install|configure) ([^:\s]+)"
)
AIDE_HEAD = re.compile(r"^(?:File|Link|Directory):\s+(\S.*)$")
AIDE_MTIME = re.compile(
    r"^ Mtime\s+:\s+.*\|\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?: [+-]\d{4})?)\s*$"
)
AIDE_START = re.compile(
    r"^Start timestamp:\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?: [+-]\d{4})?)"
)
MTIME_LINE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?: [+-]\d{4})?|\d{9,12})\s+(\S.*)$"
)
PKG_SLACK_S = 24 * 3600
BIN_PREFIXES = ("/usr/bin/", "/usr/sbin/", "/bin/", "/sbin/")


def decode_path(raw: str) -> str:
    s = str(raw or "").strip()
    return _ESC.sub(lambda m: chr(int(m.group(1), 16)), s)


def _parse_ts(raw: str) -> float | None:
    s = str(raw or "").strip()
    if not s:
        return None
    if re.fullmatch(r"\d{9,12}", s):
        return float(s)
    s = s.replace("T", " ", 1)
    for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).timestamp()
        except ValueError:
            continue
    return None


def parse_aide_mtimes(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    current = ""
    for raw in text.splitlines():
        hm = AIDE_HEAD.match(raw.rstrip())
        if hm:
            current = decode_path(hm.group(1))
            continue
        mm = AIDE_MTIME.match(raw.rstrip())
        if mm and current:
            ts = _parse_ts(mm.group(1))
            if ts is not None:
                out[current] = ts
    return out


def parse_aide_start(text: str) -> float | None:
    for raw in text.splitlines()[:30]:
        m = AIDE_START.match(raw.rstrip())
        if m:
            return _parse_ts(m.group(1))
    return None


def live_mtime(path: str) -> float | None:
    try:
        return Path(decode_path(path)).lstat().st_mtime
    except OSError:
        return None


def resolve_mtime(path: str, aide_mtime: dict[str, float], extra_mtime: dict[str, float]) -> float | None:
    """AIDE changed-block first; file_mtime.txt / live stat fill Added (no Mtime)."""
    p = decode_path(path)
    if p in aide_mtime:
        return aide_mtime[p]
    if p in extra_mtime:
        return extra_mtime[p]
    return live_mtime(p)


def parse_file_mtime_txt(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for raw in text.splitlines():
        m = MTIME_LINE.match(raw.strip())
        if not m:
            continue
        ts = _parse_ts(m.group(1))
        if ts is None:
            continue
        out[decode_path(m.group(2))] = ts
    return out


def parse_dpkg_log(text: str) -> list[tuple[float, str]]:
    rows: list[tuple[float, str]] = []
    for raw in text.splitlines():
        m = DPKG_EVENT.match(raw.strip())
        if not m:
            continue
        ts = _parse_ts(m.group(1))
        if ts is None:
            continue
        rows.append((ts, m.group(2)))
    return rows


def parse_dpkg_owned(text: str) -> dict[str, str]:
    """dpkg -S lines: 'openssh-server: /etc/ssh/sshd_config'."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "no path found" in line.lower():
            continue
        if ": " not in line:
            continue
        pkg, path = line.split(": ", 1)
        pkg = pkg.split(",", 1)[0].strip().split(":", 1)[0]
        path = decode_path(path)
        if pkg and path.startswith("/"):
            out[path] = pkg
    return out


def parse_debsums_txt(text: str) -> dict[str, str]:
    """'OK /path' or debsums native '/path  OK'."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^(OK|FAILED)\s+(\S.*)$", line)
        if m:
            out[decode_path(m.group(2))] = m.group(1)
            continue
        m = re.match(r"^(.*?)\s+(OK|FAILED)\s*$", line)
        if m:
            out[decode_path(m.group(1).rstrip())] = m.group(2)
    return out


def load_dpkg_context(
    out_dir: Path | None,
) -> tuple[dict[str, str], list[tuple[float, str]], dict[str, float], dict[str, str]]:
    if out_dir is None or not out_dir.is_dir():
        return {}, [], {}, {}
    owned: dict[str, str] = {}
    events: list[tuple[float, str]] = []
    mtimes: dict[str, float] = {}
    debsums: dict[str, str] = {}
    op = out_dir / "dpkg_owned.txt"
    if op.is_file():
        owned = parse_dpkg_owned(op.read_text(encoding="utf-8", errors="replace"))
    for name in ("dpkg.log", "dpkg.log.1", "dpkg_log.txt"):
        lp = out_dir / name
        if lp.is_file():
            events.extend(parse_dpkg_log(lp.read_text(encoding="utf-8", errors="replace")))
    mp = out_dir / "file_mtime.txt"
    if mp.is_file():
        mtimes = parse_file_mtime_txt(mp.read_text(encoding="utf-8", errors="replace"))
    dp = out_dir / "debsums.txt"
    if dp.is_file():
        debsums = parse_debsums_txt(dp.read_text(encoding="utf-8", errors="replace"))
    return owned, events, mtimes, debsums


def pkg_for_path(path: str, owned: dict[str, str]) -> str | None:
    p = decode_path(path)
    if p in owned:
        return owned[p]
    best: str | None = None
    best_n = -1
    for op, pkg in owned.items():
        if classify_path(op) != "identity":
            continue
        if p == op or p.startswith(op.rstrip("/") + "/"):
            if len(op) > best_n:
                best, best_n = pkg, len(op)
    return best


def in_dpkg_window(mtime: float | None, pkg: str | None, events: list[tuple[float, str]]) -> bool:
    if mtime is None or not pkg or not events:
        return False
    for ts, name in events:
        if name == pkg and abs(mtime - ts) <= PKG_SLACK_S:
            return True
    return False


def is_identity_binary(path: str) -> bool:
    """dpkg-owned ELF/bin under PATH; conffiles under /etc stay on mtime-vindu."""
    return decode_path(path).startswith(BIN_PREFIXES)


def pkg_event_in_scan_window(
    pkg: str | None,
    events: list[tuple[float, str]],
    scan_ts: float | None,
) -> bool:
    if not pkg or scan_ts is None or not events:
        return False
    return any(name == pkg and abs(scan_ts - ts) <= PKG_SLACK_S for ts, name in events)


def identity_is_pkg(
    path: str,
    pkg: str | None,
    events: list[tuple[float, str]],
    mtime: float | None,
    scan_ts: float | None,
) -> bool:
    if not pkg:
        return False
    # Binær-mtime er pakkens byggetid. configure/upgrade i scan-vinduet er nok.
    if is_identity_binary(path) and pkg_event_in_scan_window(pkg, events, scan_ts):
        return True
    return in_dpkg_window(mtime, pkg, events)


def debsums_status(path: str, status_map: dict[str, str]) -> str | None:
    p = decode_path(path)
    if p in status_map:
        return status_map[p]
    try:
        real = str(Path(p).resolve())
    except OSError:
        return None
    return status_map.get(real)


def identity_is_stale(path: str, pkg: str | None, status_map: dict[str, str]) -> bool:
    """dpkg-eid + debsums OK + ikke apt-vindu (vindu sjekkes før denne)."""
    if not pkg:
        return False
    return debsums_status(path, status_map) == "OK"


def package_hashes(pkg: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if not pkg:
        return out
    info = Path("/var/lib/dpkg/info")
    for f in (info / f"{pkg}.md5sums", info / f"{pkg}:amd64.md5sums"):
        if not f.is_file():
            continue
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if len(line) < 35:
                continue
            digest, rel = line[:32], line[34:].strip()
            if not re.fullmatch(r"[0-9a-f]{32}", digest):
                continue
            out["/" + rel.lstrip("/")] = digest
    try:
        p = subprocess.run(
            ["dpkg-query", "-W", "-f", "${Conffiles}\n", pkg],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        for line in (p.stdout or "").splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0].startswith("/") and re.fullmatch(r"[0-9a-f]{32}", parts[1]):
                out[parts[0]] = parts[1]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return out


def live_md5(path: str) -> str | None:
    try:
        return hashlib.md5(Path(decode_path(path)).read_bytes()).hexdigest()
    except OSError:
        return None


def write_debsums_txt(paths: list[str], owned_file: Path, dest: Path) -> None:
    owned = {}
    if owned_file.is_file():
        owned = parse_dpkg_owned(owned_file.read_text(encoding="utf-8", errors="replace"))
    cache: dict[str, dict[str, str]] = {}
    lines: list[str] = []
    for raw in paths:
        p = decode_path(raw)
        if not p:
            continue
        pkg = pkg_for_path(p, owned)
        if not pkg:
            continue
        hashes = cache.setdefault(pkg, package_hashes(pkg))
        got = live_md5(p)
        want = hashes.get(p)
        if want is None:
            try:
                want = hashes.get(str(Path(p).resolve()))
            except OSError:
                want = None
        if not got or not want:
            continue
        lines.append(f"{'OK' if got == want else 'FAILED'} {p}")
    dest.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def stale_paths_from_verdict(doc: dict[str, Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for rec in doc.get("findings") or []:
        if not isinstance(rec, dict) or rec.get("id") != "FIM-AIDE-STALE":
            continue
        for line in (rec.get("detail") or "").splitlines():
            p = decode_path(line)
            if p.startswith("/") and p not in seen:
                seen.add(p)
                out.append(p)
    return out


def identity_paths(text: str) -> list[str]:
    return [p for _, p in parse_paths(text) if classify_path(p) == "identity"]


def classify_path(path: str) -> str:
    p = decode_path(path)
    if p == "/etc/sudoers.d/kalived" or p.startswith("/etc/sudoers.d/kalived/"):
        return "self_sudoers"
    if p.startswith("/etc/sudoers.d/"):
        return "identity"
    if p in IDENTITY_EXACT or p == "/etc/ssh" or p.startswith("/etc/ssh/"):
        return "identity"
    low = p.lower()
    if "proton-vpn" in low or "proton_vpn" in low:
        return "snap_proton"
    if re.search(r"snap-snapd-", low) or (
        "snap-" in low and low.endswith(".mount") and "proton" not in low
    ):
        return "snap_other"
    if "snapd.mounts.target" in low and "proton" not in low:
        return "snap_other"
    if p.startswith("/usr/local/lib/kalived") or p == "/usr/sbin/kalived-ctl":
        return "self_helper"
    if "kalived-watch.service" in p or "kalived-watch.timer" in p:
        return "self_helper"
    return "other"


def parse_paths(text: str) -> list[tuple[str, str]]:
    """Return (kind, path) for file/link/dir entries. Skip dir-only mtime noise."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    in_entries = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("Added entries") or line.startswith("Removed entries") or line.startswith(
            "Changed entries"
        ):
            in_entries = True
            continue
        if line.startswith("The attributes of") or line.startswith("End timestamp"):
            in_entries = False
            continue
        m = ENTRY.match(line)
        if m:
            kind, path = m.group(1), decode_path(m.group(2))
            # Directory mtime-only (d =....) is parent noise; added dirs stay.
            if kind == "d" and not line.startswith("d+") and classify_path(path) != "identity":
                continue
            if path not in seen:
                seen.add(path)
                out.append((kind, path))
            continue
        if in_entries:
            continue
        fm = FILE_LINE.match(line)
        if fm:
            path = decode_path(fm.group(1))
            if path not in seen:
                seen.add(path)
                out.append(("f", path))
    return out


def load_scope(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return doc if isinstance(doc, dict) else {}


def scope_path() -> Path | None:
    env = os.environ.get("KALIVED_AIDE_SCOPE")
    if env:
        return Path(env)
    # Fixture scans must not pick up a live overlay from the operator home.
    if os.environ.get("KALIVED_FIXTURE") == "1":
        return None
    home = os.environ.get("KALIVED_OWNER_HOME") or os.environ.get("HOME") or ""
    if home:
        p = Path(home) / ".config" / "kalived" / "aide-scope.json"
        if p.is_file():
            return p
    p = Path("/var/lib/aide/kalived-scope.json")
    return p if p.is_file() else None


def is_frozen(path: str, scope: dict[str, Any]) -> bool:
    if not scope or scope.get("mode") == "all":
        return False
    prefixes = [decode_path(x) for x in (scope.get("prefixes") or [])]
    hashes = scope.get("sha256") or {}
    p = decode_path(path)
    matched = None
    for pre in prefixes:
        if p == pre or p.startswith(pre.rstrip("/") + "/"):
            matched = pre
            break
    if matched is None:
        return False
    want = hashes.get(p) or hashes.get(matched)
    if not want:
        return True
    live = Path(p)
    if not live.is_file():
        return True
    got = hashlib.sha256(live.read_bytes()).hexdigest()
    return got == want


def findings_from_report(
    text: str,
    scope: dict[str, Any] | None = None,
    out_dir: Path | None = None,
) -> list[dict[str, str]]:
    if re.search(r"There are no differences|AIDE found NO|Nothing to do", text, re.I):
        if re.search(r"failed to open|No such file", text, re.I):
            return [
                {
                    "severity": "INFO",
                    "id": "FIM-AIDE",
                    "title": "AIDE-DB mangler ennå",
                    "detail": text[:400],
                    "source": "aide_check.txt",
                }
            ]
        return []
    scope = scope or {}
    owned, events, extra_mtime, debsums = load_dpkg_context(out_dir)
    aide_mtime = parse_aide_mtimes(text)
    scan_ts = parse_aide_start(text)
    buckets: dict[str, list[str]] = defaultdict(list)
    skipped: list[str] = []
    for _kind, path in parse_paths(text):
        cls = classify_path(path)
        if cls == "identity":
            pkg = pkg_for_path(path, owned)
            mtime = resolve_mtime(path, aide_mtime, extra_mtime)
            if identity_is_pkg(path, pkg, events, mtime, scan_ts):
                cls = "pkg"
            elif identity_is_stale(path, pkg, debsums):
                cls = "stale"
        if cls in {"self_sudoers", "self_helper", "stale"} and is_frozen(path, scope):
            skipped.append(path)
            continue
        buckets[cls].append(path)
    recs: list[dict[str, str]] = []
    order = (
        "identity",
        "stale",
        "pkg",
        "self_sudoers",
        "snap_proton",
        "snap_other",
        "other",
        "self_helper",
    )
    for cls in order:
        paths = buckets.get(cls) or []
        if not paths:
            continue
        sev, fid, label = SEV[cls]
        shown = paths[:12]
        extra = f" (+{len(paths) - 12})" if len(paths) > 12 else ""
        title = f"{label}: {', '.join(shown)}{extra}"
        if cls == "self_sudoers":
            title = "AIDE self_sudoers: /etc/sudoers.d/kalived — scoped Confirm fryser kalived, ikke Proton"
        if cls == "self_helper":
            title = f"AIDE self_helper: {len(paths)} stier (timer/helper/ctl)"
        recs.append(
            {
                "severity": sev,
                "id": fid,
                "title": title,
                "detail": "\n".join(paths[:40]),
                "source": "aide_check.txt",
            }
        )
    return recs


def write_scope(dest: Path, prefixes: list[str] | None = None) -> dict[str, Any]:
    import time

    prefs = list(prefixes or DEFAULT_SCOPE)
    hashes: dict[str, str] = {}
    for p in prefs:
        fp = Path(p)
        if not fp.is_file():
            continue
        try:
            hashes[p] = hashlib.sha256(fp.read_bytes()).hexdigest()
        except OSError:
            continue
    doc = {
        "schema": SCHEMA,
        "mode": "scoped",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "prefixes": prefs,
        "sha256": hashes,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(dest)
    os.chmod(dest, 0o600)
    return doc


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: aide_classify.py findings REPORT [SCOPE]", file=sys.stderr)
        print("       aide_classify.py write-scope DEST [prefix...]", file=sys.stderr)
        return 2
    cmd = argv[1]
    if cmd == "write-scope":
        dest = Path(argv[2])
        prefs = argv[3:] or list(DEFAULT_SCOPE)
        write_scope(dest, prefs)
        print(dest)
        return 0
    if cmd == "findings":
        report_p = Path(argv[2])
        report = report_p.read_text(encoding="utf-8", errors="replace")
        scope = load_scope(Path(argv[3]) if len(argv) > 3 else scope_path())
        out_dir = Path(argv[4]) if len(argv) > 4 else report_p.parent
        recs = findings_from_report(report, scope, out_dir)
        print(json.dumps(recs, ensure_ascii=False, indent=2))
        return 0
    print("unknown", cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
