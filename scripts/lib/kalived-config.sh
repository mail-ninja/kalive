# shellcheck shell=bash
# Load ~/.config/kalived/config.toml (or KALIVED_CONFIG). Safe subset via tomllib.

# systemd oneshot has no HOME (set -u). Prefer owner getent, then KALIVED_OWNER_HOME.
kalived_owner_home() {
  local home="" uid
  uid="$(id -u)"
  if [[ "$uid" -eq 0 && -n "${SUDO_USER:-}" ]]; then
    home="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
  elif [[ "$uid" -eq 0 && -n "${KALIVED_OWNER:-}" ]]; then
    home="$(getent passwd "$KALIVED_OWNER" | cut -d: -f6)"
  fi
  if [[ -z "$home" && -n "${KALIVED_OWNER_HOME:-}" ]]; then
    home="${KALIVED_OWNER_HOME}"
  fi
  if [[ -z "$home" && -n "${HOME:-}" ]]; then
    home="${HOME}"
  fi
  if [[ -z "$home" ]]; then
    home="$(getent passwd "$(id -un)" | cut -d: -f6)"
  fi
  printf '%s' "$home"
}

kalived_config_path() {
  if [[ -n "${KALIVED_CONFIG:-}" ]]; then
    printf '%s' "$KALIVED_CONFIG"
    return 0
  fi
  printf '%s' "$(kalived_owner_home)/.config/kalived/config.toml"
}

# Non-root owner for chown. Never default a personal username.
kalived_owner_name() {
  local owner="${KALIVED_OWNER:-${SUDO_USER:-}}"
  if [[ -z "$owner" || "$owner" == "root" ]]; then
    if [[ "$(id -u)" -ne 0 ]]; then
      owner="$(id -un)"
    else
      owner=""
    fi
  fi
  printf '%s' "$owner"
}

# Timer has KALIVED_OWNER, no SUDO_USER. Never leave secrets root:root.
kalived_chown_owner_dir() {
  local dest="$1"
  local owner
  owner="$(kalived_owner_name)"
  if [[ -z "$owner" || "$owner" == "root" ]]; then
    echo "WARN: skip chown $dest (owner=${owner:-empty})" >&2
    return 0
  fi
  if ! id -u "$owner" >/dev/null 2>&1; then
    echo "WARN: skip chown, unknown owner $owner" >&2
    return 0
  fi
  chown -R "${owner}:${owner}" "$dest"
}

# Single file: owner:owner 0600 (Falco jsonl/txt/err; cockpit must read).
kalived_chown_owner_0600() {
  local f="$1"
  local owner
  owner="$(kalived_owner_name)"
  [[ -e "$f" ]] || return 0
  if [[ -z "$owner" || "$owner" == "root" ]]; then
    echo "WARN: skip chown $f (owner=${owner:-empty})" >&2
    return 0
  fi
  if ! id -u "$owner" >/dev/null 2>&1; then
    echo "WARN: skip chown, unknown owner $owner" >&2
    return 0
  fi
  chown "${owner}:${owner}" "$f"
  chmod 0600 "$f"
}

# Sets CFG_* exports. Returns 3 on invalid enum/bind.
kalived_config_load() {
  local path py
  path="$(kalived_config_path)"
  export KALIVED_CONFIG_PATH="$path"
  py="$(command -v python3 || command -v python || true)"
  if [[ -z "$py" ]]; then
    echo "python3 required for config" >&2
    return 3
  fi
  local out
  if ! out="$("$py" - "$path" << 'PY'
import os, sys, shlex
path = sys.argv[1]
defaults = {
    "aide_init_policy": "allow_known_warn",
    "scan_sudo_mode": "prompt",
    "docker_stop_idle": True,
    "timer_enabled": True,
    "ai_enabled": False,
    "ai_model": "grok-4.6",
    "ai_after_scan": True,
    "listen_bind": "127.0.0.1",
    "listen_port": 8787,
    "apparmor_enforce_selected": False,
    "verbose": False,
    "notify_on_alert": True,
    "skip_hunt": False,
    "skip_rootkit": False,
    "defs_auto_update": False,
    "nmap_localhost": True,
    "nmap_port_spec": "-",
    "helper_stale_check": True,
    "aide_watch_helper": True,
    "proc_inventory": True,
    "proc_hidden_check": True,
    "proc_ioc_check": True,
    "pcap_localhost": True,
    "pcap_duration_s": 8,
    "pcap_max_packets": 4000,
    "nmap_svc_probe": True,
    "ufw_digest": True,
    "web_terminal": True,
}
enums = {
    "aide_init_policy": {"clean_only", "allow_known_warn", "always_prompt"},
    "scan_sudo_mode": {"prompt", "helper", "never"},
}
data = dict(defaults)
loaded = {}
if path and os.path.isfile(path):
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore
    with open(path, "rb") as f:
        loaded = tomllib.load(f) or {}
    if not isinstance(loaded, dict):
        print("CONFIG ERROR: root must be a table", file=sys.stderr)
        sys.exit(3)
    for k, v in loaded.items():
        if k in defaults:
            data[k] = v
for k, allowed in enums.items():
    if data[k] not in allowed:
        print(f"CONFIG ERROR: {k}={data[k]!r} not in {sorted(allowed)}", file=sys.stderr)
        sys.exit(3)
bind = str(data["listen_bind"])
if bind not in ("127.0.0.1", "::1", "localhost"):
    print(f"CONFIG ERROR: listen_bind={bind!r} must be loopback", file=sys.stderr)
    sys.exit(3)
port = int(data["listen_port"])
if not (1 <= port <= 65535):
    print(f"CONFIG ERROR: listen_port={port}", file=sys.stderr)
    sys.exit(3)
spec = str(data["nmap_port_spec"]).strip()
if spec not in ("-", "") and not all(c.isdigit() or c in "-," for c in spec):
    print(f"CONFIG ERROR: nmap_port_spec={spec!r} (only digits, comma, hyphen, or '-')", file=sys.stderr)
    sys.exit(3)
# never a host/CIDR
if "/" in spec or spec.lower() in ("any", "all"):
    print("CONFIG ERROR: nmap_port_spec is ports not targets", file=sys.stderr)
    sys.exit(3)
data["nmap_port_spec"] = spec or "-"
try:
    dur = int(data["pcap_duration_s"])
except (TypeError, ValueError):
    print("CONFIG ERROR: pcap_duration_s must be int", file=sys.stderr)
    sys.exit(3)
if not (1 <= dur <= 30):
    print(f"CONFIG ERROR: pcap_duration_s={dur} (1-30)", file=sys.stderr)
    sys.exit(3)
data["pcap_duration_s"] = dur
try:
    mx = int(data["pcap_max_packets"])
except (TypeError, ValueError):
    print("CONFIG ERROR: pcap_max_packets must be int", file=sys.stderr)
    sys.exit(3)
if not (1 <= mx <= 20000):
    print(f"CONFIG ERROR: pcap_max_packets={mx} (1-20000)", file=sys.stderr)
    sys.exit(3)
data["pcap_max_packets"] = mx

def b(v):
    return "1" if v in (True, "true", "1", 1) else "0"

def q(v):
    return shlex.quote(str(v))
print(f"CFG_AIDE_INIT_POLICY={q(data['aide_init_policy'])}")
print(f"CFG_SCAN_SUDO_MODE={q(data['scan_sudo_mode'])}")
print(f"CFG_DOCKER_STOP_IDLE={b(data['docker_stop_idle'])}")
print(f"CFG_TIMER_ENABLED={b(data['timer_enabled'])}")
print(f"CFG_AI_ENABLED={b(data['ai_enabled'])}")
print(f"CFG_AI_MODEL={q(data['ai_model'])}")
print(f"CFG_AI_AFTER_SCAN={b(data['ai_after_scan'])}")
print(f"CFG_LISTEN_BIND={q(bind)}")
print(f"CFG_LISTEN_PORT={port}")
print(f"CFG_APPARMOR_ENFORCE={b(data['apparmor_enforce_selected'])}")
print(f"CFG_VERBOSE={b(data['verbose'])}")
print(f"CFG_NOTIFY_ON_ALERT={b(data['notify_on_alert'])}")
print(f"CFG_SKIP_HUNT={b(data['skip_hunt'])}")
print(f"CFG_SKIP_ROOTKIT={b(data['skip_rootkit'])}")
print(f"CFG_DEFS_AUTO_UPDATE={b(data['defs_auto_update'])}")
print(f"CFG_NMAP_LOCALHOST={b(data['nmap_localhost'])}")
print(f"CFG_NMAP_PORT_SPEC={q(data['nmap_port_spec'])}")
print(f"CFG_HELPER_STALE_CHECK={b(data['helper_stale_check'])}")
print(f"CFG_AIDE_WATCH_HELPER={b(data['aide_watch_helper'])}")
print(f"CFG_PROC_INVENTORY={b(data['proc_inventory'])}")
print(f"CFG_PROC_HIDDEN_CHECK={b(data['proc_hidden_check'])}")
print(f"CFG_PROC_IOC_CHECK={b(data['proc_ioc_check'])}")
print(f"CFG_PCAP_LOCALHOST={b(data['pcap_localhost'])}")
print(f"CFG_PCAP_DURATION_S={data['pcap_duration_s']}")
print(f"CFG_PCAP_MAX_PACKETS={data['pcap_max_packets']}")
print(f"CFG_NMAP_SVC_PROBE={b(data['nmap_svc_probe'])}")
print(f"CFG_UFW_DIGEST={b(data['ufw_digest'])}")
print(f"CFG_WEB_TERMINAL={b(data['web_terminal'])}")
if "watch_timer" in loaded:
    print(f"CFG_WATCH_TIMER={b(loaded['watch_timer'])}")
PY
)"; then
    return 3
  fi
  CFG_WATCH_TIMER=""
  eval "$out"
  export CFG_AIDE_INIT_POLICY CFG_SCAN_SUDO_MODE CFG_DOCKER_STOP_IDLE \
    CFG_TIMER_ENABLED CFG_AI_ENABLED CFG_AI_MODEL CFG_AI_AFTER_SCAN CFG_LISTEN_BIND \
    CFG_LISTEN_PORT CFG_APPARMOR_ENFORCE CFG_VERBOSE CFG_NOTIFY_ON_ALERT \
    CFG_SKIP_HUNT CFG_SKIP_ROOTKIT CFG_DEFS_AUTO_UPDATE \
    CFG_NMAP_LOCALHOST CFG_NMAP_PORT_SPEC CFG_HELPER_STALE_CHECK CFG_AIDE_WATCH_HELPER \
    CFG_PROC_INVENTORY CFG_PROC_HIDDEN_CHECK CFG_PROC_IOC_CHECK \
    CFG_PCAP_LOCALHOST CFG_PCAP_DURATION_S CFG_PCAP_MAX_PACKETS CFG_NMAP_SVC_PROBE \
    CFG_UFW_DIGEST CFG_WEB_TERMINAL CFG_WATCH_TIMER
  return 0
}
