#!/usr/bin/env bash
# Host hardening for kalived workstation.
# Run: sudo bash /home/void/kalived/playbooks/harden-host-sudo.sh
# Idempotent-ish. Logs to remediation/.

set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi

STAMP="$(date +%Y-%m-%d_%H%M)"
ROOT="/home/void/kalived"
LOGDIR="$ROOT/logs/status/${STAMP}_harden"
mkdir -p "$LOGDIR" "$ROOT/logs/ufw" "$ROOT/remediation"
exec > >(tee -a "$LOGDIR/harden.log") 2>&1

echo "=== kalived harden $STAMP ==="
date -Iseconds

echo "[1/7] Ensure SSH server stays off"
systemctl disable --now ssh 2>/dev/null || true
systemctl disable --now sshd 2>/dev/null || true
systemctl mask ssh 2>/dev/null || true
systemctl is-active ssh 2>/dev/null || echo "ssh inactive OK"
systemctl is-enabled ssh 2>/dev/null || echo "ssh disabled/masked OK"

echo "[2/7] Disable VM guest tools on bare metal"
systemctl disable --now open-vm-tools.service 2>/dev/null || true
systemctl disable --now vgauth.service 2>/dev/null || true
systemctl disable --now open-vm-tools-desktop.service 2>/dev/null || true
systemctl disable --now virtualbox-guest-utils.service 2>/dev/null || true
systemctl disable --now vboxadd.service 2>/dev/null || true
systemctl disable --now vboxadd-service.service 2>/dev/null || true
# stop helpers if running
pkill -x vmtoolsd 2>/dev/null || true
pkill -x VBoxClient 2>/dev/null || true
pkill -x VBoxService 2>/dev/null || true
systemctl is-enabled open-vm-tools 2>&1 || true
systemctl is-enabled virtualbox-guest-utils 2>&1 || true

echo "[3/7] Disable system xcape autostart"
XCAPE="/etc/xdg/autostart/xcape-super-key-bind.desktop"
if [[ -f "$XCAPE" && ! -f "${XCAPE}.disabled" ]]; then
  mv "$XCAPE" "${XCAPE}.disabled"
  echo "moved $XCAPE -> .disabled"
elif [[ -f "${XCAPE}.disabled" ]]; then
  echo "already disabled"
else
  echo "xcape desktop file not found (ok)"
fi
pkill -x xcape 2>/dev/null || true

echo "[4/7] Sysctl hardening (Docker-safe: leave ip_forward alone if docker active)"
SYSCTL_FILE="/etc/sysctl.d/99-kalived-hardening.conf"
cat > "$SYSCTL_FILE" << 'EOF'
# kalived host hardening — do not set ip_forward here (Docker may need 1)
# Kernel pointer / debug
kernel.kptr_restrict = 1
kernel.dmesg_restrict = 1
kernel.yama.ptrace_scope = 1
# Network
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv6.conf.all.accept_source_route = 0
net.ipv4.tcp_syncookies = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.conf.all.log_martians = 1
fs.suid_dumpable = 0
EOF
sysctl --system 2>/dev/null | tail -20 || sysctl -p "$SYSCTL_FILE"
echo "--- selected values ---"
sysctl kernel.kptr_restrict kernel.dmesg_restrict kernel.yama.ptrace_scope \
  net.ipv4.conf.all.rp_filter net.ipv4.conf.all.send_redirects \
  net.ipv4.ip_forward 2>/dev/null || true

echo "[5/7] UFW: re-assert default deny + enable logging"
ufw default deny incoming
ufw default allow outgoing
ufw default deny routed
ufw logging low
ufw --force enable
ufw status verbose | tee "$ROOT/logs/ufw/${STAMP}_status.txt"

echo "[6/7] AppArmor on + status dump"
systemctl enable --now apparmor
aa-status 2>/dev/null | tee "$LOGDIR/aa_status.txt" | head -40

echo "[7/7] Snapshot ports / services"
ss -tulpn | tee "$LOGDIR/ss_tulpn.txt"
systemctl is-enabled open-vm-tools virtualbox-guest-utils ssh apparmor ufw 2>&1 | tee "$LOGDIR/units.txt" || true

# changelog
{
  echo ""
  echo "### $STAMP — harden-host-sudo.sh"
  echo "- SSH disabled/masked"
  echo "- open-vm-tools + virtualbox-guest-utils disabled"
  echo "- xcape system autostart disabled"
  echo "- sysctl $SYSCTL_FILE applied"
  echo "- UFW deny-in reasserted"
  echo "- AppArmor ensure enabled"
  echo "- Log: logs/status/${STAMP}_harden/"
} >> "$ROOT/remediation/CHANGELOG.md"

chown -R void:void "$ROOT/logs" "$ROOT/remediation/CHANGELOG.md" 2>/dev/null || true

echo ""
echo "=== DONE ==="
echo "Review: $LOGDIR"
echo "Optional next: fail2ban only if you enable SSH; docker group is still a local risk."
echo "PHONE: if tether device is compromised, prefer clean network or phone reset before trusting traffic."
