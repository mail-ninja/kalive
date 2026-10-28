#!/usr/bin/env bash
# Gate Suricata IDS: AF_PACKET på aktiv uplink, ingen IPS, ingen pcap-fil, ingen web-UI.
# Apt kjøres IKKE her — printer kommando og stopper.
# Run: sudo bash playbooks/install-suricata-host.sh
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/kalived-gate.sh
source "$ROOT/playbooks/lib/kalived-gate.sh"
kalived_require_not_alert || {
  echo "GATE: siste scan er ALERT/ERROR — ikke installer Suricata på denne tilstanden." >&2
  exit 2
}

install -d -m 755 /etc/kalived
install -m 644 "$ROOT/defs/suricata.yaml" /etc/kalived/suricata.yaml
install -m 644 "$ROOT/defs/suricata-local.rules" /etc/kalived/suricata-local.rules
mkdir -p /usr/local/lib/kalived/defs /usr/local/lib/kalived/scripts
install -m 644 "$ROOT/defs/suricata.yaml" /usr/local/lib/kalived/defs/suricata.yaml
install -m 644 "$ROOT/defs/suricata-local.rules" /usr/local/lib/kalived/defs/suricata-local.rules
install -m 755 "$ROOT/scripts/kalived-suricata-run.sh" /usr/local/lib/kalived/scripts/kalived-suricata-run.sh
install -m 755 "$ROOT/scripts/kalived-suricata.sh" /usr/local/lib/kalived/scripts/kalived-suricata.sh
if [[ -f "$ROOT/systemd/kalived-suricata.service" ]]; then
  install -m 644 "$ROOT/systemd/kalived-suricata.service" /etc/systemd/system/kalived-suricata.service
  systemctl daemon-reload 2>/dev/null || true
fi

# Apt og enable kjører ikke her — printer og stopper.
cat >&2 << 'EOF'
Suricata IDS (ikke IPS). AF_PACKET på wlan0/proton0. Ingen nfqueue, ingen pcap-fil, ingen 0.0.0.0.

Når operator sier ja apt:

  sudo apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y suricata suricata-update
  sudo suricata-update enable-source et/open
  sudo suricata-update
  sudo systemctl enable --now kalived-suricata.service

Ikke enable i denne playbooken. Burst er feil tak — unit mens lenken er oppe.
Lokal regel: defs/suricata-local.rules (ingen exploit-payload). ET Open via suricata-update.
EOF

kalived_changelog "install-suricata-host.sh" \
  "- yaml/regler/unit kopiert. apt ikke kjørt. unit ikke enable."
echo "DONE (apt ikke kjørt, unit ikke enable)" >&2
exit 0
