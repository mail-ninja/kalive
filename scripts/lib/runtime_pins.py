"""HOST-RUNTIME: local version pins + php-fpm/apache listeners. No CVE API, no apt."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

LISTEN_COMMS = ("php-fpm", "apache2", "httpd", "apache")
INTERP_NAMES = ("node", "nodejs", "php", "php-fpm", "bun", "deno")
COCKPIT_PORTS = frozenset({"5173", "8788"})


def parse_ver(raw: str) -> tuple[int, ...]:
    s = str(raw or "").strip().lstrip("vV")
    if not s:
        return (0,)
    head = s.split("-", 1)[0].split("+", 1)[0].split("~", 1)[0]
    nums = [int(x) for x in re.findall(r"\d+", head)[:4]]
    return tuple(nums) if nums else (0,)


def ver_ge(have: str, need: str) -> bool:
    h, n = parse_ver(have), parse_ver(need)
    length = max(len(h), len(n))
    h = h + (0,) * (length - len(h))
    n = n + (0,) * (length - len(n))
    return h >= n


def node_ok(raw: str, pins: dict[str, Any]) -> bool:
    series = (pins.get("node") or {}).get("series") or []
    if not raw or not series:
        return True
    major = parse_ver(raw)[0]
    floor = None
    for row in series:
        if not isinstance(row, dict):
            continue
        m = int(row.get("major") or 0)
        mn = str(row.get("min") or "")
        if major == m:
            floor = mn
            break
        if major >= 24 and m == 24:
            floor = mn
    if floor is None:
        return False
    return ver_ge(raw, floor)


def brotli_ok(raw: str, pins: dict[str, Any]) -> bool:
    need = str((pins.get("brotli") or {}).get("min") or "")
    if not raw or not need:
        return True
    return ver_ge(raw, need)


def load_pins(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return obj if isinstance(obj, dict) else {}


def load_versions(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(obj, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in obj.items():
        if isinstance(v, str):
            out[str(k)] = v.strip()
    return out


def _comm_from_ss(line: str) -> str:
    m = re.search(r'users:\(\("([^"]+)",pid=', line)
    return (m.group(1) if m else "").lower()


def php_apache_listeners(ss_text: str) -> list[str]:
    hits: list[str] = []
    for raw in (ss_text or "").splitlines():
        line = raw.strip()
        if not line or "LISTEN" not in line:
            continue
        comm = _comm_from_ss(line)
        if comm.startswith("php-fpm") or comm in LISTEN_COMMS:
            hits.append(line[:240])
    return hits


def findings_from_snapshot(out_dir: Path, pins_path: Path) -> list[dict[str, str]]:
    pins = load_pins(pins_path)
    vers = load_versions(out_dir / "runtime_versions.json")
    recs: list[dict[str, str]] = []
    misses: list[str] = []
    node = vers.get("node") or ""
    brotli = vers.get("brotli") or ""
    if node and pins and not node_ok(node, pins):
        misses.append(f"node {node} < 22.23.4 / 24.22.1")
    if brotli and pins and not brotli_ok(brotli, pins):
        misses.append(f"brotli {brotli} < 1.2.1")
    if misses:
        detail_bits = list(misses)
        for key in ("openssl", "ca_certificates", "chromium"):
            if vers.get(key):
                detail_bits.append(f"{key}={vers[key]}")
        recs.append(
            {
                "severity": "WARN",
                "id": "HOST-RUNTIME",
                "title": "Runtime under pin: " + "; ".join(misses),
                "detail": "\n".join(detail_bits),
                "source": "runtime_versions.json",
            }
        )
    ss_path = out_dir / "ss_tulpn.txt"
    ss_text = ss_path.read_text(encoding="utf-8", errors="replace") if ss_path.is_file() else ""
    listens = php_apache_listeners(ss_text)
    if listens:
        recs.append(
            {
                "severity": "WARN",
                "id": "HOST-RUNTIME",
                "title": f"php-fpm/apache lytter ({len(listens)})",
                "detail": "\n".join(listens),
                "source": "ss_tulpn.txt",
            }
        )
    return recs
