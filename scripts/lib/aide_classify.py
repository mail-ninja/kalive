#!/usr/bin/env python3
"""Classify AIDE report paths. Scoped freeze is a prefix list — not a full --init."""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
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
    "other": ("WARN", "FIM-AIDE", "AIDE other"),
}


def decode_path(raw: str) -> str:
    s = str(raw or "").strip()
    return _ESC.sub(lambda m: chr(int(m.group(1), 16)), s)


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
    import hashlib

    got = hashlib.sha256(live.read_bytes()).hexdigest()
    return got == want


def findings_from_report(text: str, scope: dict[str, Any] | None = None) -> list[dict[str, str]]:
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
    buckets: dict[str, list[str]] = defaultdict(list)
    skipped: list[str] = []
    for _kind, path in parse_paths(text):
        cls = classify_path(path)
        if cls in {"self_sudoers", "self_helper"} and is_frozen(path, scope):
            skipped.append(path)
            continue
        buckets[cls].append(path)
    recs: list[dict[str, str]] = []
    order = ("identity", "self_sudoers", "snap_proton", "snap_other", "other", "self_helper")
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
    import hashlib
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
        report = Path(argv[2]).read_text(encoding="utf-8", errors="replace")
        scope = load_scope(Path(argv[3]) if len(argv) > 3 else scope_path())
        recs = findings_from_report(report, scope)
        print(json.dumps(recs, ensure_ascii=False, indent=2))
        return 0
    print("unknown", cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
