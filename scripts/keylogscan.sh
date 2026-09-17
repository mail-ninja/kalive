#!/usr/bin/env bash
# Lightweight keylogger / input-grab indicators (mostly non-root).
# Usage: ./scripts/keylogscan.sh
# Optional: KALIVED_SUDO=1 for lsof on /dev/input + aa-status

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="${KALIVED_STAMP:-$(date +%Y-%m-%d_%H%M)}"
if [[ -n "${KALIVED_OUT:-}" ]]; then
  OUT="$KALIVED_OUT"
else
  OUT="$ROOT/logs/status/${STAMP}_keylogscan"
fi
mkdir -p "$OUT"

echo "[*] Keylogscan → $OUT"
if [[ -z "${KALIVED_OUT:-}" ]]; then
  {
    echo "stamp=$STAMP date=$(date -Iseconds) user=$(whoami)"
  } > "$OUT/meta.txt"
fi

{
  echo '### packages'
  dpkg -l 2>/dev/null | grep -iE 'logkeys|keylog' || echo none
  echo '### process names'
  ps auxww | grep -iE 'keylog|logkeys|pynput|pyxhook|evtest|logkey' \
    | grep -v grep | grep -v 'scripts/keylogscan.sh' | grep -v 'keylog_summary.txt' || echo none
  echo '### LD_PRELOAD (readable procs)'
  found=0
  _uids="$(id -u)"
  if [[ -n "${SUDO_USER:-}" ]]; then
    _uids="$_uids $(id -u "$SUDO_USER" 2>/dev/null || true)"
  fi
  for _uid in $_uids; do
  for pid in $(pgrep -u "$_uid" 2>/dev/null); do
    [[ -f "/proc/$pid/exe" && -r "/proc/$pid/environ" ]] || continue
    envtxt="$(tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null || true)"
    pre="$(printf '%s\n' "$envtxt" | grep '^LD_PRELOAD=' || true)"
    [[ -n "$pre" ]] || continue
    if echo "$pre" | grep -qv libmozsandbox; then
      echo "PID $pid: $pre :: $(tr '\0' ' ' < /proc/$pid/cmdline 2>/dev/null || true)"
      found=1
    fi
  done
  done
  [ "$found" = 0 ] && echo 'none (excl. firefox mozsandbox)'
  echo '### ld.so.preload'
  if [ -e /etc/ld.so.preload ]; then cat /etc/ld.so.preload; else echo 'absent'; fi
  echo '### cron'
  crontab -l 2>&1 || true
  echo '### autostart grep'
  grep -riE 'keylog|logkeys|pynput|evtest' \
    "$HOME/.config/autostart" /etc/xdg/autostart 2>/dev/null || echo none
  echo '### non-localhost TCP'
  ss -tln | awk 'NR>1 {print $4}' | grep -vE '127\.0\.0\.1:|\[::1\]:' || echo 'OK none'
} | tee "$OUT/${KALIVED_OUT:+keylog_}summary.txt"

if [[ "${KALIVED_SUDO:-0}" == "1" || "$(id -u)" -eq 0 ]]; then
  LSOF_OUT="$OUT/lsof_event0.txt"
  [[ -n "${KALIVED_OUT:-}" ]] && LSOF_OUT="$OUT/keylog_lsof_event0.txt"
  if [[ "$(id -u)" -eq 0 ]]; then
    lsof /dev/input/event0 2>/dev/null > "$LSOF_OUT" || true
    # aa-status allerede i collect når orkestrert
    if [[ -z "${KALIVED_OUT:-}" ]]; then
      aa-status > "$OUT/aa_status.txt" 2>/dev/null || true
    fi
  else
    sudo -n lsof /dev/input/event0 2>/dev/null > "$LSOF_OUT" || true
  fi
fi

echo "[+] Done. Review $OUT/${KALIVED_OUT:+keylog_}summary.txt"
