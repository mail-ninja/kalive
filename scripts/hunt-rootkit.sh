#!/usr/bin/env bash
# Kernel + rkhunter/chkrootkit/debsums dumps. Live only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${KALIVED_OUT:?}"
mkdir -p "$OUT"
if [[ "${KALIVED_FIXTURE:-0}" == "1" || "${KALIVED_FROM_DIR:-0}" == "1" ]]; then
  exit 0
fi
echo "[*] hunt-rootkit → $OUT" >&2

cat /proc/sys/kernel/tainted > "$OUT/kernel_taint.txt" 2>/dev/null || echo '?' > "$OUT/kernel_taint.txt"
lsmod > "$OUT/lsmod.txt" 2>/dev/null || true
{
  echo "=== /proc/net/tcp ==="
  cat /proc/net/tcp 2>/dev/null || true
  echo "=== /proc/net/tcp6 ==="
  cat /proc/net/tcp6 2>/dev/null || true
} > "$OUT/proc_net_tcp.txt" 2>&1 || true

if command -v bpftool >/dev/null 2>&1; then
  bpftool prog show > "$OUT/hunt_bpf.txt" 2>&1 || true
else
  echo 'bpftool missing' > "$OUT/hunt_bpf.txt"
fi

if command -v debsums >/dev/null 2>&1; then
  debsums -c sudo passwd login systemd libc6 coreutils util-linux \
    openssh-client openssh-server bash 2>&1 | head -c 100000 \
    > "$OUT/hunt_debsums.txt" || true
  [[ -s "$OUT/hunt_debsums.txt" ]] || echo 'debsums clean (listed pkgs)' > "$OUT/hunt_debsums.txt"
else
  echo 'debsums missing' > "$OUT/hunt_debsums.txt"
fi

if [[ -f /var/log/dpkg.log ]]; then
  stat -c '%Y %y' /var/log/dpkg.log > "$OUT/dpkg_log_mtime.txt" 2>/dev/null || true
fi

if command -v chkrootkit >/dev/null 2>&1; then
  chkrootkit -q > "$OUT/hunt_chkrootkit.txt" 2>&1 || true
  [[ -s "$OUT/hunt_chkrootkit.txt" ]] || echo 'chkrootkit: no output (typically clean)' > "$OUT/hunt_chkrootkit.txt"
else
  echo 'chkrootkit missing' > "$OUT/hunt_chkrootkit.txt"
fi

if command -v rkhunter >/dev/null 2>&1; then
  rkhunter --check --skip-keypress --report-warnings-only --nocolors \
    > "$OUT/hunt_rkhunter.txt" 2>&1 || true
  [[ -s "$OUT/hunt_rkhunter.txt" ]] || echo 'rkhunter: no warnings' > "$OUT/hunt_rkhunter.txt"
else
  echo 'rkhunter missing' > "$OUT/hunt_rkhunter.txt"
fi

echo "[+] hunt-rootkit done" >&2
