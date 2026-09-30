"""Cockpit view of ~/.config/kalived/config.toml plus live systemd timers."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
_LIB = str(REPO / "scripts" / "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import kalived_config as kc  # type: ignore  # noqa: E402

SCHEMA: list[dict[str, Any]] = [
    {
        "name": "watch_timer",
        "type": "bool",
        "group": "hiroshima",
        "label": "Egress-watch hvert 5. min",
        "help": "Valgfri. systemd kalived-watch.timer. Av hopper over sampling; Confirm watch i skuffen virker fortsatt.",
    },
    {
        "name": "timer_enabled",
        "type": "bool",
        "group": "scan",
        "label": "Ukentlig full-scan",
        "help": "systemd kalived-scan.timer. systemd er sannhet; huken skriver config og prøver ctl.",
    },
    {
        "name": "pcap_localhost",
        "type": "bool",
        "group": "sensorer",
        "label": "tshark lo-burst",
        "help": "8 s SYN-ACK på lo under scan. Ikke -i any.",
    },
    {
        "name": "pcap_duration_s",
        "type": "int",
        "group": "sensorer",
        "label": "tshark-varighet (s)",
        "min": 1,
        "max": 30,
    },
    {
        "name": "nmap_localhost",
        "type": "bool",
        "group": "sensorer",
        "label": "nmap localhost",
        "help": "TCP-scan kun 127.0.0.1.",
    },
    {
        "name": "ufw_digest",
        "type": "bool",
        "group": "sensorer",
        "label": "UFW 24t-digest",
    },
    {
        "name": "proc_inventory",
        "type": "bool",
        "group": "sensorer",
        "label": "Prosesinventar",
    },
    {
        "name": "proc_hidden_check",
        "type": "bool",
        "group": "sensorer",
        "label": "Skjulte PID (sil 4)",
    },
    {
        "name": "proc_ioc_check",
        "type": "bool",
        "group": "sensorer",
        "label": "Prosess-IOC-navn",
    },
    {
        "name": "helper_stale_check",
        "type": "bool",
        "group": "sensorer",
        "label": "WARN hvis helper er bak git",
    },
    {
        "name": "notify_on_alert",
        "type": "bool",
        "group": "sensorer",
        "label": "Varsle ved ALERT",
    },
    {
        "name": "verbose",
        "type": "bool",
        "group": "sensorer",
        "label": "Verbose scan-logg",
    },
    {
        "name": "ai_enabled",
        "type": "bool",
        "group": "ai",
        "label": "Jev/Mercury etter scan",
        "help": "Timer skriver rules uten sky når av. Nøkler ligger under Nøkler, ikke her.",
    },
    {
        "name": "ai_after_scan",
        "type": "bool",
        "group": "ai",
        "label": "Port etter interaktiv scan",
    },
    {
        "name": "docker_stop_idle",
        "type": "bool",
        "group": "vert",
        "label": "Stopp docker.socket ved 0 containere",
    },
    {
        "name": "defs_auto_update",
        "type": "bool",
        "group": "vert",
        "label": "rkhunter --update før live scan",
        "help": "Tregt, trenger nett.",
    },
    {
        "name": "aide_init_policy",
        "type": "enum",
        "group": "vert",
        "label": "AIDE re-init",
        "choices": ["clean_only", "allow_known_warn", "always_prompt"],
    },
    {
        "name": "scan_sudo_mode",
        "type": "enum",
        "group": "vert",
        "label": "Scan-eskalering",
        "choices": ["prompt", "helper", "never"],
        "help": "Live scan krever fortsatt root. helper = kalived-ctl.",
    },
    {
        "name": "skip_rootkit",
        "type": "bool",
        "group": "svekker",
        "label": "Hopp over rkhunter/chkrootkit",
        "help": "Svekker scannen. Denne maskinen er mistenkt — hold av med mindre du vet hvorfor.",
        "danger": True,
    },
    {
        "name": "skip_hunt",
        "type": "bool",
        "group": "svekker",
        "label": "Hopp over hunt-siler",
        "help": "Svekker scannen.",
        "danger": True,
    },
    {
        "name": "listen_bind",
        "type": "text",
        "group": "låst",
        "label": "API bind",
        "readonly": True,
        "help": "Alltid loopback.",
    },
    {
        "name": "listen_port",
        "type": "int",
        "group": "låst",
        "label": "gammel SOC-port",
        "readonly": True,
    },
]

GROUPS = [
    ("hiroshima", "Hiroshima"),
    ("scan", "Scan-timer"),
    ("sensorer", "Sensorer"),
    ("ai", "Modell-port"),
    ("vert", "Vert"),
    ("svekker", "Svekker scannen"),
    ("låst", "Låst"),
]


def _unit(name: str) -> dict[str, str]:
    def one(cmd: str) -> str:
        try:
            p = subprocess.run(
                ["systemctl", "is-" + cmd, name],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return (p.stdout or p.stderr or "").strip() or ("enabled" if p.returncode == 0 else "disabled")
        except (OSError, subprocess.TimeoutExpired):
            return "unknown"

    return {"enabled": one("enabled"), "active": one("active")}


def live() -> dict[str, Any]:
    return {
        "watch_timer": _unit("kalived-watch.timer"),
        "scan_timer": _unit("kalived-scan.timer"),
    }


def status() -> dict[str, Any]:
    data = kc.load()
    present = set(data.pop("_present", []) or [])
    live_u = live()
    if "watch_timer" not in present:
        data["watch_timer"] = live_u["watch_timer"]["enabled"] in ("enabled", "static", "alias")
    values = {k: data[k] for k in kc.DEFAULTS if k in data}
    return {
        "path": str(kc.config_path()),
        "mode": oct(kc.config_path().stat().st_mode & 0o777) if kc.config_path().is_file() else None,
        "values": values,
        "live": live_u,
        "schema": SCHEMA,
        "groups": [{"id": i, "label": l} for i, l in GROUPS],
        "readonly": sorted(kc.READONLY),
    }


def _ctl(verb: str) -> dict[str, Any]:
    ctl = "/usr/sbin/kalived-ctl"
    if not os.path.isfile(ctl):
        ctl = "/usr/local/sbin/kalived-ctl"
    try:
        p = subprocess.run(
            ["sudo", "-n", ctl, verb],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "hint": str(e)[:160]}
    out = ((p.stdout or "") + (p.stderr or ""))[-400:]
    if p.returncode == 0:
        return {"ok": True, "out": out}
    hint = "sudo bash playbooks/install-nopasswd-ctl.sh"
    if "password" in (p.stderr or "").lower() or p.returncode == 1:
        return {"ok": False, "hint": hint, "out": out}
    return {"ok": False, "hint": out or hint}


def put(updates: dict[str, Any]) -> dict[str, Any]:
    raw = kc._raw()
    cur = kc.load()
    live_u = live()
    live_w = live_u["watch_timer"]["enabled"] in ("enabled", "enabled-runtime", "static", "alias")
    if "watch_timer" not in raw:
        cur["watch_timer"] = live_w
    old_w = bool(cur.get("watch_timer"))
    old_s = bool(cur.get("timer_enabled"))
    full = {k: cur[k] for k in kc.DEFAULTS}
    full.update(updates)
    data = kc.validate(full)
    kc.write(data)
    data.pop("_present", None)
    ctl_runs: list[dict[str, Any]] = []
    if "watch_timer" in updates and bool(data.get("watch_timer")) != old_w:
        verb = "watch-timer-on" if data.get("watch_timer") else "watch-timer-off"
        ctl_runs.append({"verb": verb, **_ctl(verb)})
    if "timer_enabled" in updates and bool(data.get("timer_enabled")) != old_s:
        verb = "scan-timer-on" if data.get("timer_enabled") else "scan-timer-off"
        ctl_runs.append({"verb": verb, **_ctl(verb)})
    st = status()
    st["ctl"] = ctl_runs
    return st
