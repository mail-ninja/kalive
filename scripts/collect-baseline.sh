#!/usr/bin/env bash
# Non-destructive status collector for kalived.
# Usage: ./scripts/collect-baseline.sh
# Optional: KALIVED_SUDO=1 ./scripts/collect-baseline.sh   # will prompt sudo for ufw/nft/aa

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${KALIVED_DATA:-$ROOT}"
STAMP="${KALIVED_STAMP:-$(date +%Y-%m-%d_%H%M)}"
OUT="${KALIVED_OUT:-$DATA/logs/status/$STAMP}"
mkdir -p "$OUT" \
  "$DATA/logs/ufw" \
  "$DATA/scans/ports" \
  "$DATA/scans/firewall" \
  "$DATA/scans/services"

# Root live collect always dumps ufw/nft/aa (produktkontrakt: baseline med sudo).
if [[ "$(id -u)" -eq 0 ]]; then
  KALIVED_SUDO=1
fi

echo "[*] Snapshot → $OUT"

META_FILE="$OUT/meta.txt"
if [[ -n "${KALIVED_OUT:-}" ]]; then
  META_FILE="$OUT/collect_meta.txt"
fi
{
  echo "stamp=$STAMP"
  echo "date=$(date -Iseconds)"
  echo "host=$(hostname)"
  echo "user=$(whoami)"
  echo "boot_id=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || true)"
  echo "virt=$(systemd-detect-virt 2>/dev/null || true)"
} > "$META_FILE"

uname -a > "$OUT/uname.txt"
cp /etc/os-release "$OUT/os_release.txt" 2>/dev/null || true
ip -br a > "$OUT/ip_addr.txt" 2>&1 || true
ip route > "$OUT/ip_route.txt" 2>&1 || true
ip -d link > "$OUT/ip_link_detail.txt" 2>&1 || true
cp /etc/resolv.conf "$OUT/resolv.txt" 2>/dev/null || true
ip -6 route > "$OUT/ip6_route.txt" 2>&1 || true
ss -tulpn > "$OUT/ss_tulpn.txt" 2>&1 || true
ss -tpn state established > "$OUT/ss_established.txt" 2>&1 || true
cp "$OUT/ss_tulpn.txt" "$DATA/scans/ports/${STAMP}_ss_tulpn.txt"
systemctl list-units --type=service --state=running --no-pager > "$OUT/services_running.txt" 2>&1 || true
systemctl list-unit-files --type=service --state=enabled --no-pager > "$OUT/services_enabled.txt" 2>&1 || true
cp "$OUT/services_running.txt" "$DATA/scans/services/${STAMP}_running.txt"
systemctl status ufw --no-pager > "$OUT/ufw_service.txt" 2>&1 || true
cat /etc/ufw/ufw.conf > "$OUT/ufw_conf.txt" 2>&1 || true
cat /etc/default/ufw > "$OUT/ufw_default.txt" 2>&1 || true
sysctl -a 2>/dev/null | grep -E 'ip_forward|rp_filter|accept_redirects|send_redirects|kptr_restrict|dmesg_restrict|ptrace_scope|suid_dumpable|accept_source_route|tcp_syncookies|log_martians' \
  > "$OUT/sysctl_security.txt" || true
getent passwd > "$OUT/passwd.txt"
if [[ "$(id -u)" -eq 0 && -n "${SUDO_USER:-}" ]]; then
  groups "$SUDO_USER" > "$OUT/groups.txt" 2>&1 || true
else
  groups > "$OUT/groups.txt"
fi
last -n 30 > "$OUT/last_logins.txt" 2>&1 || true
docker ps -a > "$OUT/docker_ps.txt" 2>&1 || true
docker images > "$OUT/docker_images.txt" 2>&1 || true
nmcli -t con show --active > "$OUT/nm_active.txt" 2>&1 || true
rfkill list > "$OUT/rfkill.txt" 2>&1 || true
find /usr/bin /usr/sbin /bin /sbin -perm -4000 2>/dev/null > "$OUT/suid.txt" || true
grep -vE '^\s*#|^\s*$' /etc/ssh/sshd_config > "$OUT/sshd_config_active.txt" 2>&1 || true
{
  echo -n "ufw enabled: "; systemctl is-enabled ufw 2>&1 || true
  echo -n "ufw active: "; systemctl is-active ufw 2>&1 || true
  echo -n "ssh active: "; systemctl is-active ssh 2>&1 || true
  echo -n "docker active: "; systemctl is-active docker 2>&1 || true
  echo -n "apparmor enabled: "; systemctl is-enabled apparmor 2>&1 || true
  echo -n "fail2ban: "; (command -v fail2ban-client >/dev/null && echo installed || echo missing)
  echo -n "auditd active: "; systemctl is-active auditd 2>&1 || true
  echo -n "docker.socket: "; systemctl is-active docker.socket 2>&1 || true
  echo -n "kalived-scan.timer: "; systemctl is-enabled kalived-scan.timer 2>&1 || true
} > "$OUT/sec_units.txt" 2>&1

# Quick alert: non-localhost TCP listeners
ALERT="$OUT/ALERT_non_localhost_tcp.txt"
if ss -tln | awk 'NR>1 {print $4}' | grep -vE '127\.0\.0\.1:|\[::1\]:' >/dev/null 2>&1; then
  ss -tlnp | tee "$ALERT"
  echo "[!] Non-localhost TCP listeners found — see $ALERT"
else
  echo "OK: no non-localhost TCP listeners" | tee "$ALERT"
fi

if [[ "${KALIVED_SUDO:-0}" == "1" ]]; then
  echo "[*] Collecting sudo-backed firewall/MAC…"
  # Orchestrated scan: files only (ikke dump aa-status til TTY).
  _run() { if [[ "$(id -u)" -eq 0 ]]; then "$@"; else sudo -n "$@"; fi; }
  _run ufw status verbose > "$OUT/ufw_status.txt" 2>&1 || true
  cp "$OUT/ufw_status.txt" "$DATA/logs/ufw/${STAMP}_status.txt" 2>/dev/null || true
  if _run nft list ruleset > "$OUT/nft_ruleset.txt" 2>/dev/null; then
    cp "$OUT/nft_ruleset.txt" "$DATA/scans/firewall/${STAMP}_nft.txt" 2>/dev/null || true
  else
    _run iptables-save > "$OUT/iptables_save.txt" 2>/dev/null || true
  fi
  _run aa-status > "$OUT/aa_status.txt" 2>/dev/null || true
  _run fail2ban-client status > "$OUT/fail2ban.txt" 2>/dev/null || true
  if [[ -f /etc/audit/rules.d/99-kalived.rules ]]; then
    cat /etc/audit/rules.d/99-kalived.rules > "$OUT/audit_rules.txt"
  fi
  if [[ -f /etc/systemd/journald.conf.d/99-kalived.conf ]]; then
    cat /etc/systemd/journald.conf.d/99-kalived.conf > "$OUT/journald_kalived.txt"
  fi
  if [[ -f /etc/kalived/docker-stop-idle ]]; then
    cat /etc/kalived/docker-stop-idle > "$OUT/docker_stop_idle.txt"
  fi
  systemctl is-enabled kalived-scan.timer > "$OUT/timer_enabled.txt" 2>&1 || true
  systemctl is-active docker.socket > "$OUT/docker_socket.txt" 2>&1 || true
  if command -v ausearch >/dev/null 2>&1; then
    : > "$OUT/audit_recent.txt"
    for _k in kalived_id kalived_ssh kalived_preload kalived_persist kalived_udev kalived_mod kalived_ptrace; do
      ausearch -ts recent -k "$_k" >> "$OUT/audit_recent.txt" 2>/dev/null || true
    done
    [[ -s "$OUT/audit_recent.txt" ]] || echo 'ausearch empty/none' > "$OUT/audit_recent.txt"
  fi
  if [[ -f /etc/aide/kalived.conf && -e /var/lib/aide/kalived.db.gz ]]; then
    aide --config /etc/aide/kalived.conf --check > "$OUT/aide_check.txt" 2>&1 || true
  elif [[ -e /var/lib/aide/kalived.db.gz ]]; then
    echo 'db exists but /etc/aide/kalived.conf missing' > "$OUT/aide_check.txt"
  fi
fi

echo "[+] Done: $OUT"
ls -la "$OUT" | tail -n +1
