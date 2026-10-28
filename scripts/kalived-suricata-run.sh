#!/usr/bin/env bash
# Start Suricata IDS on the active uplink (proton0 / wlan0). Never lo, never IPS queue.
# Unit: systemd/kalived-suricata.service. Playbook copies this to /usr/local.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
CONF="${KALIVED_SURICATA_YAML:-/etc/kalived/suricata.yaml}"
[[ -f "$CONF" ]] || CONF="$ROOT/defs/suricata.yaml"
LOCAL_RULES="${KALIVED_SURICATA_RULES:-/etc/kalived/suricata-local.rules}"
[[ -f "$LOCAL_RULES" ]] || LOCAL_RULES="$ROOT/defs/suricata-local.rules"
ET_RULES="/var/lib/suricata/rules/suricata.rules"

iface_up() {
  local d="$1"
  [[ -n "$d" && "$d" != "lo" ]] || return 1
  local p="/sys/class/net/$d"
  [[ -d "$p" ]] || return 1
  [[ "$(cat "$p/operstate" 2>/dev/null || true)" == "up" ]]
}

pick_iface() {
  if iface_up proton0; then
    printf '%s\n' proton0
    return 0
  fi
  local dev=""
  dev="$(ip -o route show default 2>/dev/null | awk '{for (i=1;i<NF;i++) if ($i=="dev") {print $(i+1); exit}}')"
  if iface_up "${dev:-}"; then
    printf '%s\n' "$dev"
    return 0
  fi
  if iface_up wlan0; then
    printf '%s\n' wlan0
    return 0
  fi
  if iface_up eth0; then
    printf '%s\n' eth0
    return 0
  fi
  return 1
}

if ! command -v suricata >/dev/null 2>&1; then
  echo "suricata absent — playbooks/install-suricata-host.sh printer apt" >&2
  exit 75
fi

IFACE=""
IFACE="$(pick_iface || true)"
if [[ -z "$IFACE" || "$IFACE" == "lo" ]]; then
  echo "ingen aktiv uplink (wlan0/proton0) — venter" >&2
  exit 75
fi

args=(-c "$CONF" --af-packet="$IFACE")
if [[ ! -f "$ET_RULES" ]]; then
  args+=(-S "$LOCAL_RULES")
fi

echo "[*] suricata IDS AF_PACKET iface=$IFACE (ikke IPS, ikke lo)" >&2
exec suricata "${args[@]}"
