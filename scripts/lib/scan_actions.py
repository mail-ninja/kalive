"""Post-scan Confirm rows. Rule table owns runnable verbs; agent may rewrite why/rank."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Closed Confirm list. Unknown run from Jev/Mercury is dropped.
CONFIRM_RUNS = frozenset({"aide-init-ack-stale", "isolate-dst", "isolate-undo"})
ALLOWED_RUNS = CONFIRM_RUNS | {None}

DPKG_EXE_PREFIXES = (
    "/usr/bin/",
    "/usr/sbin/",
    "/usr/lib/",
    "/usr/libexec/",
    "/bin/",
    "/sbin/",
    "/lib/",
    "/lib64/",
)
UNPACKAGED_PREFIXES = (
    "/tmp/",
    "/var/tmp/",
    "/dev/shm/",
    "/home/",
    "/root/",
    "/run/",
    "/opt/",
    "memfd:",
)

_EXE = re.compile(r"exe=(\S+)")
HELPER_PTY = "pkexec bash playbooks/install-kalived-helper.sh"
# libbrotli 1.2.1 is the pin; kali-rolling had 1.2.0-4+b2 as of 2026-10-27.
BROTLI_ARCHIVE = "1.2.1 ikke i kali-rolling (sist sett 2026-10-27). Node 24.22.1 er inne."
TEXT_ROW_IDS = frozenset({"travel-harden", "runtime-apt", "helper-pty", "isolate-skip"})

NOISE_IDS = frozenset(
    {
        "FIM-AIDE-PKG",
        "NET-UFW-NOISE",
        "NET-UFW-SCAN",
        "NET-UFW-HIT",
        "NET-UFW-INFO",
        "PCAP-NOISE",
        "PROC-HIDDEN-NOISE",
        "PERS-SUID",
        "ROOT-LSMOD",
        "ROOT-RKH",
    }
)


def _one_line(s: str, n: int = 240) -> str:
    t = " ".join((s or "").split())
    return t[:n]


def _row(
    id: str,
    title: str,
    why: str,
    *,
    run: str | None = None,
    confirm: bool = False,
    text: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if run not in ALLOWED_RUNS:
        run = None
    out: dict[str, Any] = {
        "id": id,
        "title": title,
        "why": _one_line(why),
        "run": run,
        "confirm": bool(confirm and run),
    }
    if text:
        out["text"] = text
    if extra:
        out["extra"] = extra
    return out


def _findings(doc: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rec in doc.get("findings") or []:
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _ids(findings: list[dict[str, Any]]) -> set[str]:
    return {str(r.get("id") or "") for r in findings if r.get("id")}


def _identity_alert(findings: list[dict[str, Any]]) -> bool:
    for r in findings:
        if r.get("id") == "FIM-AIDE" and str(r.get("severity") or "").upper() == "ALERT":
            return True
    return False


def _stale_paths(doc: dict[str, Any]) -> list[str]:
    try:
        from aide_classify import stale_paths_from_verdict
    except ImportError:
        paths: list[str] = []
        seen: set[str] = set()
        for rec in _findings(doc):
            if rec.get("id") != "FIM-AIDE-STALE":
                continue
            for line in (rec.get("detail") or "").splitlines():
                p = line.strip()
                if p.startswith("/") and p not in seen:
                    seen.add(p)
                    paths.append(p)
        return paths
    return list(stale_paths_from_verdict(doc))


def _exe_paths(detail: str) -> list[str]:
    out: list[str] = []
    for m in _EXE.finditer(detail or ""):
        raw = m.group(1).replace("(deleted)", "").strip()
        if raw:
            out.append(raw)
    if "memfd:" in (detail or "") and not any(p.startswith("memfd:") for p in out):
        out.append("memfd:")
    return out


def _is_dpkg_exe(path: str) -> bool:
    p = (path or "").strip()
    if not p or p.startswith("memfd:") or "memfd:" in p:
        return False
    if any(p.startswith(pref) for pref in UNPACKAGED_PREFIXES):
        return False
    return any(p.startswith(pref) for pref in DPKG_EXE_PREFIXES)


def _deleted_kind(findings: list[dict[str, Any]]) -> str | None:
    """'dpkg' if every deleted exe is package-owned; 'unknown' otherwise; None if no finding."""
    hits = [r for r in findings if r.get("id") in ("PROC-DELETED", "PROC-MEMFD")]
    if not hits:
        return None
    unpackaged = False
    saw_path = False
    for r in hits:
        if r.get("id") == "PROC-MEMFD" or "memfd:" in (r.get("detail") or ""):
            unpackaged = True
        paths = _exe_paths(r.get("detail") or "")
        if not paths:
            unpackaged = True
            continue
        for p in paths:
            saw_path = True
            if not _is_dpkg_exe(p):
                unpackaged = True
    if unpackaged or not saw_path:
        return "unknown"
    return "dpkg"


def _exe_names(detail: str) -> list[str]:
    names: list[str] = []
    for p in _exe_paths(detail):
        if p.startswith("memfd:"):
            names.append("memfd")
        else:
            names.append(Path(p).name)
    return names


def _env_class(protocol: dict[str, Any] | None) -> str:
    env = (protocol or {}).get("env") if isinstance(protocol, dict) else None
    if isinstance(env, dict):
        return str(env.get("class") or "").strip()
    return ""


def _env_ssid(protocol: dict[str, Any] | None) -> str:
    env = (protocol or {}).get("env") if isinstance(protocol, dict) else None
    if isinstance(env, dict):
        return str(env.get("ssid") or "").strip()
    return ""


def _travel_harden_row(protocol: dict[str, Any]) -> dict[str, Any]:
    env = _env_class(protocol)
    ssid = _env_ssid(protocol)
    ufw = protocol.get("ufw") if isinstance(protocol.get("ufw"), dict) else {}
    proton_dns = int(ufw.get("allow_dns_proton") or 0)
    net = f"Nett: {ssid}." if ssid else ("Tether." if env == "tether" else "Gjestenett/travel.")
    if proton_dns:
        proton = "Proton-DNS synlig i UFW-vindu."
    else:
        proton = "Proton-tunnel ikke synlig — slå på VPN (snap er installert)."
    why = f"{net} UFW inn er reject. {proton} Isolate av unknown-DNS kutter nett."
    return _row(
        "travel-harden",
        "Sikre uten isolate",
        why,
        text="Proton VPN (snap) · UFW inn reject · mDNS på LAN · ikke isolate DNS",
    )


def actions_from_verdict(
    doc: dict[str, Any] | None,
    protocol: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Closed rows for the post-scan sheet. Nothing here executes."""
    doc = doc if isinstance(doc, dict) else {}
    proto = protocol if isinstance(protocol, dict) else {}
    if not proto and isinstance(doc.get("protocol"), dict):
        proto = doc["protocol"]
    findings = _findings(doc)
    ids = _ids(findings)
    rows: list[dict[str, Any]] = []

    deleted = _deleted_kind(findings)
    if deleted == "unknown":
        names: list[str] = []
        for r in findings:
            if r.get("id") in ("PROC-DELETED", "PROC-MEMFD"):
                names.extend(_exe_names(r.get("detail") or ""))
        label = ", ".join(names[:4]) if names else "ukjent exe"
        rows.append(
            _row(
                "ask-operator",
                "ask_operator",
                f"PROC-DELETED/MEMFD uten dpkg-eierskap ({label}). Ingen isolate, ingen kill fra arket.",
            )
        )
    elif deleted == "dpkg":
        names = []
        for r in findings:
            if r.get("id") == "PROC-DELETED":
                names.extend(_exe_names(r.get("detail") or ""))
        label = ", ".join(names[:4]) if names else "dpkg"
        rows.append(
            _row(
                "close-deleted-dpkg",
                "Lukk — slettet inode etter apt",
                f"{label} er dpkg-eid og holder slettet inode. Ikke kill-pid.",
            )
        )

    ident = _identity_alert(findings)
    if "FIM-AIDE-STALE" in ids and not ident:
        paths = _stale_paths(doc)
        shown = ", ".join(paths[:6]) if paths else "stale identity-stier"
        extra = f" (+{len(paths) - 6})" if len(paths) > 6 else ""
        rows.append(
            _row(
                "ack-stale",
                "Confirm --ack-stale",
                f"FIM-AIDE-STALE: {shown}{extra}. Overlay unionerer (sudo blir værende). Proton urørt.",
                run="aide-init-ack-stale",
                confirm=True,
            )
        )

    env = _env_class(proto)
    if proto.get("isolatable") and env == "home":
        rows.append(
            _row(
                "isolate-dst",
                "Confirm isolate unknown",
                "ukjent dest i ring og env=home.",
                run="isolate-dst",
                confirm=True,
                extra={"family": "unknown"},
            )
        )
    elif env in ("travel", "tether") or proto.get("isolatable"):
        rows.append(_travel_harden_row(proto))

    if proto.get("rollback"):
        rows.append(
            _row(
                "isolate-undo",
                "Confirm undo isolate",
                "rollback-fil finnes.",
                run="isolate-undo",
                confirm=True,
            )
        )

    if "HELPER-STALE" in ids:
        rows.append(
            _row(
                "helper-pty",
                "Helper i PTY",
                "HELPER-STALE: /usr/local henger etter git. ctl har ikke helper.",
                text=HELPER_PTY,
            )
        )

    if "HOST-RUNTIME" in ids:
        recs = [r for r in findings if r.get("id") == "HOST-RUNTIME"]
        blob = " ".join(f"{r.get('title') or ''} {r.get('detail') or ''}" for r in recs)
        if "brotli" in blob.lower() or "1.2.0" in blob:
            why = f"libbrotli1 under pin. {BROTLI_ARCHIVE} Apt full-upgrade henter det ikke."
        else:
            why = _one_line(blob, 160) or "Runtime under pin. Ingen auto-apt."
        rows.append(
            _row(
                "runtime-apt",
                "Brotli: vent på Kali",
                why,
            )
        )

    if not rows:
        verd = str(doc.get("verdict") or "").upper()
        if verd == "CLEAN":
            rows.append(
                _row(
                    "close",
                    "Ingenting å gjøre",
                    "Ingen findings som krever Confirm.",
                )
            )
        elif ident:
            rows.append(
                _row(
                    "close",
                    "Ingen Confirm-handling",
                    "Identity-ALERT stenger aide-init. Findings vises under.",
                )
            )
        else:
            noise = ids <= (NOISE_IDS | {""})
            if noise or not ids:
                rows.append(
                    _row(
                        "close",
                        "Ingenting å gjøre",
                        "Proton/PKG/UFW er synlig i lista, ingen handling.",
                    )
                )
            else:
                rows.append(
                    _row(
                        "close",
                        "Ingen Confirm-handling",
                        "Findings vises under. Ingen rad i allowlisten matcher.",
                    )
                )
    return rows


def port_actions(
    rows: list[dict[str, Any]] | None,
    pick: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Rewrite why on an existing row and/or move it first. Unknown run is dropped."""
    src = [dict(r) for r in (rows or []) if isinstance(r, dict)]
    if not src or not isinstance(pick, dict):
        return src
    run = pick.get("run")
    if run == "":
        run = None
    aid = pick.get("id")
    why = pick.get("why")
    if run not in (None, "") and run not in {r.get("run") for r in src}:
        return src
    idx: int | None = None
    if aid:
        for i, r in enumerate(src):
            if r.get("id") == aid:
                idx = i
                break
    if idx is None and run not in (None, ""):
        for i, r in enumerate(src):
            if r.get("run") == run:
                idx = i
                break
    if idx is None:
        return src
    chosen = dict(src[idx])
    if isinstance(why, str) and why.strip():
        chosen["why"] = _one_line(why)
    rest = [dict(r) for i, r in enumerate(src) if i != idx]
    return [chosen] + rest


def signal_port(
    rows: list[dict[str, Any]] | None,
    doc: dict[str, Any] | None = None,
    protocol: dict[str, Any] | None = None,
    picks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Signal writes why/text on existing rows. Text-only extra rows allowed. Unknown run dropped."""
    out = [dict(r) for r in (rows or []) if isinstance(r, dict)]
    proto = protocol if isinstance(protocol, dict) else {}
    if not proto and isinstance((doc or {}).get("protocol"), dict):
        proto = doc["protocol"]  # type: ignore[index]
    auto: list[dict[str, Any]] = []
    if _env_class(proto) in ("travel", "tether"):
        harden = _travel_harden_row(proto)
        auto.append(
            {
                "id": harden["id"],
                "why": harden["why"],
                "text": harden.get("text"),
                "first": True,
            }
        )
    for pick in list(auto) + list(picks or []):
        if not isinstance(pick, dict):
            continue
        run = pick.get("run")
        if run == "":
            run = None
        if run not in (None, "") and run not in CONFIRM_RUNS:
            continue
        if run not in (None, "") and run not in {r.get("run") for r in out}:
            continue
        aid = pick.get("id")
        idx: int | None = None
        if aid:
            for i, r in enumerate(out):
                if r.get("id") == aid:
                    idx = i
                    break
        if idx is None and run not in (None, ""):
            for i, r in enumerate(out):
                if r.get("run") == run:
                    idx = i
                    break
        why = pick.get("why")
        text = pick.get("text")
        title = pick.get("title")
        if idx is None:
            if run in (None, "") and aid in TEXT_ROW_IDS:
                out.append(
                    _row(
                        str(aid),
                        str(title or aid),
                        str(why or ""),
                        text=str(text) if text else None,
                    )
                )
            continue
        chosen = dict(out[idx])
        if isinstance(why, str) and why.strip():
            chosen["why"] = _one_line(why)
        if isinstance(text, str) and text.strip():
            chosen["text"] = text
        if isinstance(title, str) and title.strip():
            chosen["title"] = title
        if pick.get("first"):
            rest = [dict(r) for i, r in enumerate(out) if i != idx]
            out = [chosen] + rest
        else:
            out[idx] = chosen
    return out
