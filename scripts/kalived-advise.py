#!/usr/bin/env python3
"""kalived advisor — SpaceXAI/xAI. Reads redacted verdict only. Never sudo."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("KALIVED_ROOT", Path(__file__).resolve().parent.parent))
PROMPT = ROOT / "prompts" / "advisor.md"
PB_DIR = ROOT / "prompts" / "playbooks"
DEFAULT_MODEL = "grok-4.6"
DEFAULT_BASE = "https://api.x.ai/v1"


def _pb_dirs() -> list[Path]:
    dirs = [PB_DIR]
    data = Path(os.environ.get("KALIVED_DATA", ROOT))
    extra = data / "prompts" / "playbooks"
    if extra.resolve() not in {p.resolve() for p in dirs if p.exists()}:
        dirs.append(extra)
    home = os.environ.get("KALIVED_OWNER_HOME")
    if home:
        dirs.append(Path(home) / "kalived" / "prompts" / "playbooks")
    return dirs


def list_playbooks() -> list[str]:
    names: set[str] = set()
    for d in _pb_dirs():
        if not d.is_dir():
            continue
        names.update(p.stem for p in d.glob("*.md") if p.is_file())
    return sorted(names)


def load_system(playbook: str | None) -> tuple[str, str]:
    """Return (name, system_prompt). Default = prompts/advisor.md (personality)."""
    if not playbook:
        text = PROMPT.read_text(encoding="utf-8") if PROMPT.is_file() else "Du er en hjelpsom assistent. Gjør ditt beste."
        return "default", text
    name = playbook.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,40}", name):
        raise SystemExit("ugyldig playbook-navn")
    aliases = [name]
    if name in ("sec", "soc"):
        aliases = ["signal", name]
    for d in _pb_dirs():
        for a in aliases:
            path = d / f"{a}.md"
            if path.is_file():
                return a, path.read_text(encoding="utf-8")
    raise SystemExit(f"ukjent advisor-playbook: {name} (har: {', '.join(list_playbooks()) or 'ingen'})")

PLAYBOOKS = [
    "sudo kalived-ctl scan",
    "sudo kalived-ctl defs",
    "sudo bash playbooks/aide-init.sh --force",
    "sudo bash playbooks/aide-init.sh --force-alert",
    "sudo bash playbooks/install-kalived-helper.sh",
    "sudo bash playbooks/docker-hygiene.sh --prune",
]


def load_dotenv_env() -> None:
    home = os.environ.get("KALIVED_OWNER_HOME")
    if not home:
        owner = os.environ.get("KALIVED_OWNER") or os.environ.get("SUDO_USER") or os.environ.get("USER")
        home = f"/home/{owner}" if owner and owner != "root" else os.path.expanduser("~")
    path = Path(os.environ.get("KALIVED_AI_ENV", Path(home) / ".config/kalived/env"))
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k in ("XAI_API_KEY", "XAI_BASE_URL", "XAI_MODEL"):
            os.environ.setdefault(k, v)


# Local well-known ports only — not a process dump.
PORT_HINTS = {
    7878: "svl/aegir-pty (loopback)",
    8787: "kalived-api (loopback)",
    45959: "containerd (loopback)",
}


def pick_live_snapshot(status: Path) -> Path | None:
    """Latest real sudo scan — skip fixtures and 'live scan krever root' ERROR."""
    if not status.is_dir():
        return None
    ranked: list[tuple[int, str, Path]] = []
    for p in status.iterdir():
        vp = p / "verdict.json"
        if not vp.is_file():
            continue
        meta: dict[str, str] = {}
        mp = p / "meta.txt"
        if mp.is_file():
            for line in mp.read_text(encoding="utf-8", errors="replace").splitlines():
                if "=" in line:
                    k, _, v = line.partition("=")
                    meta[k.strip()] = v.strip()
        try:
            verd = json.loads(vp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        fixture = meta.get("fixture") == "1"
        sudo = str(verd.get("sudo") or meta.get("sudo") or "0") == "1"
        score = 0
        if fixture:
            score -= 100
        if sudo:
            score += 50
        if verd.get("verdict") == "ERROR" and not sudo:
            score -= 80
        if (p / "hunt_nmap.gnmap").is_file():
            score += 15
        if (p / "hunt_preload.txt").is_file():
            score += 10
        ranked.append((score, p.name, p))
    if not ranked:
        return None
    ranked.sort()
    best = ranked[-1]
    if best[0] < 0:
        return None
    return best[2]


def procs_summary(snapshot: Path) -> dict:
    """Counts + listen owners. No full ps dump."""
    p = snapshot / "hunt_procs_summary.json"
    if not p.is_file():
        note = snapshot / "hunt_ps.txt"
        if note.is_file() and "proc_inventory=0" in note.read_text(encoding="utf-8", errors="replace"):
            return {"status": "disabled"}
        return {"status": "not_run"}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "invalid"}
    kept = raw.get("hidden_kept")
    if kept is None:
        kept = raw.get("hidden_count")
    raw_n = raw.get("hidden_raw")
    if raw_n is None:
        raw_n = raw.get("hidden_count")
    return {
        "status": "ran",
        "visible_count": raw.get("visible_count"),
        "hidden_raw": raw_n,
        "hidden_kept": kept,
        "hidden_count": kept,
        "hidden_pids": (raw.get("hidden_pids") or [])[:12],
        "drop": raw.get("drop") or {},
        "classes": raw.get("classes") or {},
        "listen": (raw.get("listen") or [])[:20],
        "sample_comm": (raw.get("sample_comm") or [])[:30],
    }


def nmap_summary(snapshot: Path) -> dict:
    """Open TCP on 127.0.0.1 only. No gnmap dump, no process list."""
    gnmap = snapshot / "hunt_nmap.gnmap"
    note = snapshot / "hunt_nmap.txt"
    ss = snapshot / "ss_tulpn.txt"
    if note.is_file():
        t = note.read_text(encoding="utf-8", errors="replace")
        if "nmap missing" in t:
            return {"status": "nmap_not_installed", "target": "127.0.0.1", "open_tcp": []}
        if "nmap_localhost=0" in t:
            return {"status": "disabled", "target": "127.0.0.1", "open_tcp": []}
    nmap_ports: list[int] = []
    if gnmap.is_file():
        for line in gnmap.read_text(encoding="utf-8", errors="replace").splitlines():
            for m in re.finditer(r"(\d+)/open/tcp", line):
                nmap_ports.append(int(m.group(1)))
        nmap_ports = sorted(set(nmap_ports))[:40]
    elif not note.is_file():
        return {"status": "not_run", "target": "127.0.0.1", "open_tcp": []}
    ss_ports: list[int] = []
    if ss.is_file():
        for line in ss.read_text(encoding="utf-8", errors="replace").splitlines():
            if "LISTEN" not in line:
                continue
            m = re.search(r"(127\.0\.0\.1|0\.0\.0\.0|\*|\[::1\]|\[::\]):(\d+)", line)
            if m:
                ss_ports.append(int(m.group(2)))
        ss_ports = sorted(set(ss_ports))
    hidden = sorted(set(nmap_ports) - set(ss_ports))
    labeled = [{"port": p, "hint": PORT_HINTS.get(p, "loopback")} for p in nmap_ports]
    vs = "match"
    if hidden:
        vs = "nmap_not_in_ss"
    elif nmap_ports and ss_ports and set(ss_ports) - set(nmap_ports):
        vs = "ss_extra_or_timing"
    elif not nmap_ports and not gnmap.is_file():
        vs = "unknown"
    return {
        "status": "ran",
        "target": "127.0.0.1",
        "open_tcp": labeled,
        "vs_ss": vs,
        "hidden_from_ss": hidden[:20],
    }


def defs_summary(data_root: Path) -> dict:
    """Age of last defs update. No feed dumps."""
    logdir = data_root / "logs" / "defs"
    latest = None
    latest_mtime = 0.0
    if logdir.is_dir():
        for p in logdir.glob("*_update.log"):
            try:
                mt = p.stat().st_mtime
            except OSError:
                continue
            if mt >= latest_mtime:
                latest_mtime = mt
                latest = p.name
    if not latest:
        return {"status": "never", "age_days": None, "stale": True}
    age = max(0, int((time.time() - latest_mtime) / 86400))
    return {"status": "ran", "last_log": latest, "age_days": age, "stale": age >= 7}


def suggested_commands(verdict: dict, defs: dict) -> list[str]:
    """Next steps. CLEAN must not re-scan."""
    v = verdict.get("verdict")
    ids = {f.get("id") for f in (verdict.get("findings") or []) if isinstance(f, dict)}
    if v == "CLEAN":
        if defs.get("stale"):
            return ["sudo kalived-ctl defs"]
        return []
    if v == "WARN":
        cmds: list[str] = []
        if "HELPER-STALE" in ids:
            cmds.append("sudo bash playbooks/install-kalived-helper.sh")
            cmds.append("sudo bash playbooks/aide-init.sh --force")
        elif "FIM-AIDE" in ids:
            cmds.append("sudo bash playbooks/aide-init.sh --force")
        if defs.get("stale"):
            cmds.append("sudo kalived-ctl defs")
        return cmds
    if v == "ALERT":
        return [
            "les snapshot/VERDICT.md (ikke ignorer)",
            "# ikke aide-init, ikke reboot, ikke defs «for å rydde»",
        ]
    if v == "ERROR":
        return ["sudo kalived-ctl scan"]
    return []


def pcap_summary(snapshot: Path) -> dict:
    """lo-burst counts. No packets, no payloads."""
    p = snapshot / "hunt_pcap_summary.json"
    note = snapshot / "hunt_pcap.txt"
    if p.is_file():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"status": "invalid"}
        return {
            "status": "ran",
            "iface": raw.get("iface"),
            "raw_rows": raw.get("raw_rows"),
            "synack_ports": (raw.get("synack_ports") or [])[:20],
            "vs_nmap": raw.get("vs_nmap"),
            "vs_ss": raw.get("vs_ss"),
            "drop": raw.get("drop") or {},
            "classes": raw.get("classes") or {},
        }
    if note.is_file():
        t = note.read_text(encoding="utf-8", errors="replace")
        if "tshark missing" in t:
            return {"status": "tshark_not_installed"}
        if "pcap_localhost=0" in t:
            return {"status": "disabled"}
    return {"status": "not_run"}


def ufw_digest_summary(snapshot: Path) -> dict:
    """Counts only. No journal lines, no full SRC lists."""
    p = snapshot / "ufw_digest.json"
    if not p.is_file():
        return {"status": "not_run"}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "invalid"}
    return {
        "status": "ran",
        "window_h": raw.get("window_h"),
        "lines": raw.get("lines"),
        "block": raw.get("block"),
        "allow": raw.get("allow"),
        "allow_dns_proton": raw.get("allow_dns_proton"),
        "scans": len(raw.get("scans") or []),
        "floods": len(raw.get("floods") or []),
        "hits_listen": len(raw.get("hits_listen") or []),
        "top_block_dpt": (raw.get("top_block_dpt") or [])[:8],
    }


def redact(verdict: dict, snapshot: Path | None = None) -> dict:
    findings = []
    info_n = 0
    for f in verdict.get("findings") or []:
        if not isinstance(f, dict):
            continue
        if f.get("severity") == "INFO":
            info_n += 1
            continue
        findings.append(
            {
                "severity": f.get("severity"),
                "id": f.get("id"),
                "title": (f.get("title") or "")[:240],
            }
        )
    findings = findings[:16]
    data_root = Path(os.environ.get("KALIVED_DATA", ROOT))
    defs = defs_summary(data_root)
    out = {
        "verdict": verdict.get("verdict"),
        "exit_code": verdict.get("exit_code"),
        "stamp": verdict.get("stamp"),
        "sudo": verdict.get("sudo"),
        "findings": findings,
        "info_count": info_n,
        "allowed_commands": PLAYBOOKS,
        "defs": defs,
        "suggested_commands": suggested_commands(verdict, defs),
    }
    if snapshot is not None:
        out["nmap_localhost"] = nmap_summary(snapshot)
        out["procs"] = procs_summary(snapshot)
        out["pcap"] = pcap_summary(snapshot)
        out["ufw_digest"] = ufw_digest_summary(snapshot)
    return out


def thread_path(pb_name: str) -> Path:
    home = os.environ.get("KALIVED_OWNER_HOME") or str(Path.home())
    p = Path(home) / ".config/kalived/memory" / pb_name
    p.mkdir(parents=True, exist_ok=True)
    return p / "thread.json"


def load_thread(path: Path) -> dict:
    if not path.is_file():
        return {"stamp": None, "messages": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"stamp": None, "messages": []}
    if not isinstance(data, dict):
        return {"stamp": None, "messages": []}
    data.setdefault("messages", [])
    return data


def save_thread(path: Path, data: dict) -> None:
    msgs = data.get("messages") or []
    data["messages"] = msgs[-24:]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def chat(system: str, messages: list, model: str, base: str, key: str, temperature: float = 0.8) -> str:
    url = base.rstrip("/") + "/chat/completions"
    body = json.dumps(
        {
            "model": model,
            "temperature": temperature,
            "messages": [{"role": "system", "content": system}] + messages,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:800]
        raise SystemExit(f"xAI HTTP {e.code}: {err}") from e
    except urllib.error.URLError as e:
        raise SystemExit(f"xAI network: {e}") from e
    choices = data.get("choices") or []
    if not choices:
        raise SystemExit(f"xAI empty response: {str(data)[:400]}")
    return (choices[0].get("message") or {}).get("content") or ""


def main() -> int:
    load_dotenv_env()
    args = sys.argv[1:]
    snapshot = None
    extra = []
    dry = False
    playbook = None
    i = 0
    while i < len(args):
        if args[i] == "--snapshot" and i + 1 < len(args):
            snapshot = Path(args[i + 1])
            i += 2
            continue
        if args[i] == "--dry-run":
            dry = True
            i += 1
            continue
        if args[i] in ("--playbook", "--pb") and i + 1 < len(args):
            playbook = args[i + 1]
            i += 2
            continue
        if args[i] == "--list-playbooks":
            print("\n".join(list_playbooks()) or "(ingen)")
            return 0
        if args[i] == "--ask" and i + 1 < len(args):
            extra.append(args[i + 1])
            i += 2
            continue
        i += 1

    pb_name, system = load_system(playbook)
    attach_scan = pb_name != "default"

    if snapshot is None and attach_scan:
        data = Path(os.environ.get("KALIVED_DATA", ROOT))
        status = data / "logs" / "status"
        snapshot = pick_live_snapshot(status)
        if snapshot is None:
            print("ingen live sudo-scan (fixture/ERROR-uten-root ignoreres)", file=sys.stderr)
            return 1
        print(f"(advisor leser {snapshot.name} playbook={pb_name})", file=sys.stderr)
    elif snapshot is not None:
        print(f"(advisor leser {snapshot.name} playbook={pb_name})", file=sys.stderr)

    payload = None
    if snapshot is not None:
        verd_path = snapshot / "verdict.json"
        if not verd_path.is_file():
            print(f"mangler {verd_path}", file=sys.stderr)
            return 1
        verdict = json.loads(verd_path.read_text(encoding="utf-8"))
        payload = redact(verdict, snapshot)

    stamp = (payload or {}).get("stamp") if payload else None
    tpath = thread_path(pb_name)
    thread = load_thread(tpath)
    if attach_scan:
        if payload is None:
            print("signal-playbook krever et snapshot", file=sys.stderr)
            return 1
        if thread.get("stamp") != stamp:
            user = "Siste scan (redacted JSON):\n" + json.dumps(payload, ensure_ascii=False, indent=2)
            if extra:
                user += "\n\nOperator spør:\n" + "\n".join(extra)
            thread["stamp"] = stamp
        else:
            user = "\n".join(extra) if extra else "Fortsett. Ikke gjenta hele diagnosen; vi har allerede denne scannen."
        temp = 0.2
    else:
        user = "\n".join(extra) if extra else "hei"
        temp = 0.9

    if dry:
        if payload is not None:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"playbook": pb_name, "ask": extra}, ensure_ascii=False, indent=2))
        return 0

    key = os.environ.get("XAI_API_KEY") or ""
    if not key.strip():
        print("XAI_API_KEY mangler i ~/.config/kalived/env", file=sys.stderr)
        return 2
    model = os.environ.get("XAI_MODEL") or os.environ.get("CFG_AI_MODEL") or DEFAULT_MODEL
    base = os.environ.get("XAI_BASE_URL") or DEFAULT_BASE
    history = [m for m in (thread.get("messages") or []) if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
    history.append({"role": "user", "content": user})
    text = chat(system, history[-20:], model, base, key, temperature=temp).strip() + "\n"
    history.append({"role": "assistant", "content": text})
    thread["messages"] = history
    try:
        save_thread(tpath, thread)
    except OSError:
        pass
    print(text, end="")
    saved = None
    data_root = Path(os.environ.get("KALIVED_DATA", ROOT))
    dests = []
    if snapshot is not None:
        dests.append(snapshot / "advisor.md")
    dests.extend(
        (
            data_root / "logs" / "advisor.md",
            Path.home() / ".config/kalived/last-advisor.md",
        )
    )
    for dest in dests:
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
            saved = dest
            break
        except OSError:
            continue
    if saved is not None:
        print(f"(lagret {saved})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
