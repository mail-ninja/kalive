#!/usr/bin/env bash
# Gate Falco host-burst: modern_ebpf, ingen always-on unit, ingen gRPC/web, container-regler av.
# Apt kjøres IKKE her — printer kommando hvis pakken mangler.
# Run: sudo bash playbooks/install-falco-host.sh
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/kalived-gate.sh
source "$ROOT/playbooks/lib/kalived-gate.sh"
kalived_require_not_alert || {
  echo "GATE: siste scan er ALERT/ERROR — ikke installer Falco på denne tilstanden." >&2
  exit 2
}

if [[ ! -f /sys/kernel/btf/vmlinux ]]; then
  echo "GATE: modern_ebpf krever BTF. Mangler /sys/kernel/btf/vmlinux." >&2
  exit 2
fi
echo "BTF: /sys/kernel/btf/vmlinux ok" >&2

install -d -m 755 /etc/kalived
install -m 644 "$ROOT/defs/falco-host.yaml" /etc/kalived/falco-host.yaml
install -m 644 "$ROOT/defs/falco.yaml" /etc/kalived/falco.yaml
mkdir -p /usr/local/lib/kalived/defs
install -m 644 "$ROOT/defs/falco-host.yaml" /usr/local/lib/kalived/defs/falco-host.yaml
install -m 644 "$ROOT/defs/falco.yaml" /usr/local/lib/kalived/defs/falco.yaml

# Never enable a listener. Disable vendor units if the package already landed.
systemctl disable --now falco.service falco-modern-bpf.service falcoctl-artifact-follow.service 2>/dev/null || true
systemctl mask falco.service 2>/dev/null || true

if ! command -v falco >/dev/null 2>&1; then
  cat >&2 << 'EOF'
Falco ligger ikke i Kali-apt. Når operator sier ja (tredjeparts-repo + pakke):

  curl -fsSL https://falco.org/repo/falcosecurity-packages.asc | sudo gpg --dearmor -o /usr/share/keyrings/falco-archive-keyring.gpg
  echo "deb [signed-by=/usr/share/keyrings/falco-archive-keyring.gpg] https://download.falco.org/packages/deb stable main" | sudo tee /etc/apt/sources.list.d/falcosecurity.list
  sudo apt-get update -y
  sudo env FALCO_FRONTEND=noninteractive FALCO_DRIVER_CHOICE=none FALCOCTL_ENABLED=no apt-get install -y falco
  sudo systemctl disable --now falco.service falco-modern-bpf.service falco-kmod.service falcoctl-artifact-follow.service
  sudo systemctl mask falco.service falco-modern-bpf.service falcoctl-artifact-follow.service

Ikke enable unit. Ikke gRPC/web. Burst:

  sudo kalived-ctl falco-burst

Regler ligger i defs/falco-host.yaml (ikke stock falco_rules.yaml).
EOF
  kalived_changelog "install-falco-host.sh" \
    "- regler kopiert. falco-pakke mangler — apt ikke kjørt. units disable/mask forsøkt."
  echo "DONE (falco absent, regler på plass)" >&2
  exit 0
fi

echo "burst bruker $ROOT/defs/falco.yaml (ingen stock rules_files, /etc/falco urørt)" >&2

kalived_changelog "install-falco-host.sh" \
  "- Falco host-burst. modern_ebpf. ingen unit enable. regler i /etc/kalived/falco-host.yaml."
echo "DONE. Burst: sudo kalived-ctl falco-burst" >&2
