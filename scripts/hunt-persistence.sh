#!/usr/bin/env bash
# Write hunt_*.txt into $KALIVED_OUT. Live only. Files are DATA.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${KALIVED_OUT:?KALIVED_OUT required}"
mkdir -p "$OUT"

if [[ "${KALIVED_FIXTURE:-0}" == "1" || "${KALIVED_FROM_DIR:-0}" == "1" ]]; then
  exit 0
fi

echo "[*] hunt-persistence → $OUT" >&2

{
  echo "=== user crontabs ==="
  for u in root void postgres; do
    echo "-- $u --"
    crontab -u "$u" -l 2>&1 || true
  done
  echo "=== /etc/cron.d ==="
  ls -la /etc/cron.d 2>/dev/null || true
  echo "=== cron.d contents ==="
  grep -rHve '^#' -e '^$' /etc/cron.d 2>/dev/null || true
  echo "=== /etc/cron.{hourly,daily,weekly,monthly} ==="
  ls /etc/cron.hourly /etc/cron.daily /etc/cron.weekly /etc/cron.monthly 2>/dev/null || true
  echo "=== anacron ==="
  ls -la /etc/anacrontab /var/spool/anacron 2>/dev/null || true
  echo "=== at ==="
  atq 2>/dev/null || echo 'atq failed/empty'
} > "$OUT/hunt_cron.txt" 2>&1 || true

{
  echo "=== /etc/systemd/system (non-symlink-to-usr) ==="
  find /etc/systemd/system /etc/systemd/user -type f \( -name '*.service' -o -name '*.timer' \) 2>/dev/null | sort
  echo "=== user systemd ==="
  find /home -maxdepth 4 -path '*/.config/systemd/user/*.service' -o -path '*/.config/systemd/user/*.timer' 2>/dev/null | sort
  echo "=== ExecStart in extra unit files ==="
  find /etc/systemd/system /etc/systemd/user /home -maxdepth 5 \( -path '*/systemd/user/*.service' -o -path '*/systemd/system/*.service' \) -type f 2>/dev/null | while read -r u; do
    grep -H '^ExecStart' "$u" 2>/dev/null || true
  done
  echo "=== FragmentPath extras ==="
  while IFS= read -r unit; do
    [[ -z "$unit" ]] && continue
    fp="$(systemctl show -p FragmentPath --value "$unit" 2>/dev/null || true)"
    [[ -z "$fp" ]] && continue
    case "$fp" in
      /lib/systemd/*|/usr/lib/systemd/*|/usr/lib/systemd/user/*) continue ;;
    esac
    echo "$unit $fp"
  done < <(systemctl list-unit-files --type=service,timer --no-legend --no-pager 2>/dev/null | awk '{print $1}')
} > "$OUT/hunt_systemd.txt" 2>&1 || true

{
  echo "=== /etc/xdg/autostart ==="
  ls -la /etc/xdg/autostart 2>/dev/null || true
  echo "=== user autostart ==="
  find /home -maxdepth 3 -path '*/.config/autostart/*' 2>/dev/null | sort
  echo "=== Exec= ==="
  grep -H '^Exec=' /etc/xdg/autostart/*.desktop /home/*/.config/autostart/*.desktop 2>/dev/null || true
} > "$OUT/hunt_autostart.txt" 2>&1 || true

{
  echo "=== /etc/udev/rules.d ==="
  ls -la /etc/udev/rules.d 2>/dev/null || true
  echo "=== RUN=/PROGRAM= ==="
  grep -HEn 'RUN=|PROGRAM=' /etc/udev/rules.d/* 2>/dev/null || echo none
} > "$OUT/hunt_udev.txt" 2>&1 || true

{
  echo "=== ld.so.preload ==="
  if [[ -e /etc/ld.so.preload ]]; then
    echo "PRESENT"
    cat /etc/ld.so.preload
  else
    echo "absent"
  fi
  echo "=== LD_PRELOAD ==="
  _uids="0"
  if [[ -n "${SUDO_USER:-}" ]]; then
    _uids="$_uids $(id -u "$SUDO_USER" 2>/dev/null || true)"
  fi
  for _uid in $_uids; do
    for pid in $(pgrep -u "$_uid" 2>/dev/null || true); do
      [[ -f "/proc/$pid/exe" && -r "/proc/$pid/environ" ]] || continue
      envtxt="$(tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null || true)"
      pre="$(printf '%s\n' "$envtxt" | grep '^LD_PRELOAD=' || true)"
      [[ -n "$pre" ]] || continue
      cmd="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
      echo "PID $pid uid=$_uid $pre :: $cmd"
    done
  done
} > "$OUT/hunt_preload.txt" 2>&1 || true

{
  echo "=== authorized_keys ==="
  for h in /root /home/*; do
    [[ -d "$h" ]] || continue
    f="$h/.ssh/authorized_keys"
    echo "-- $f --"
    if [[ -f "$f" ]]; then
      wc -l "$f"
      grep -vE '^\s*#|^\s*$' "$f" || echo '(no key material)'
    else
      echo absent
    fi
  done
} > "$OUT/hunt_authkeys.txt" 2>&1 || true

{
  echo "=== rc.local ==="
  if [[ -e /etc/rc.local ]]; then cat /etc/rc.local; else echo absent; fi
  echo "=== profile.d grep ==="
  grep -RInE 'curl|wget|ncat|nc |python -c|base64' /etc/profile.d /etc/profile 2>/dev/null || echo none
  echo "=== shell rc grep ==="
  grep -nE 'curl|wget|ncat|nc |python -c|base64' /root/.zshrc /root/.bashrc /home/*/.zshrc /home/*/.bashrc 2>/dev/null || echo none
} > "$OUT/hunt_rc.txt" 2>&1 || true

{
  echo "=== extra SUID outside collect paths ==="
  find /usr/local /opt /home /tmp /var/tmp /dev/shm -perm -4000 -type f 2>/dev/null || true
} > "$OUT/hunt_suid_extra.txt" 2>&1 || true

{
  if command -v getcap >/dev/null 2>&1; then
    getcap -r /usr/local /opt /home 2>/dev/null | head -c 200000 || true
  else
    echo 'getcap missing'
  fi
} > "$OUT/hunt_caps.txt" 2>&1 || true

{
  echo "=== docker ps -a ==="
  docker ps -a 2>/dev/null || true
  echo "=== inspect (ports/privileged/mounts/restart) ==="
  ids="$(docker ps -aq 2>/dev/null || true)"
  if [[ -z "$ids" ]]; then
    echo "running_or_stopped=0"
  else
    docker inspect --format '{{.Name}} privileged={{.HostConfig.Privileged}} restart={{.HostConfig.RestartPolicy.Name}} ports={{json .HostConfig.PortBindings}} sock={{range .Mounts}}{{.Source}}->{{.Destination}};{{end}}' $ids 2>/dev/null || true
  fi
  echo -n "daemon="
  systemctl is-active docker 2>/dev/null || true
} > "$OUT/hunt_docker.txt" 2>&1 || true

{
  echo "=== deleted/memfd exe ==="
  for exe in /proc/[0-9]*/exe; do
    [[ -e "$exe" || -L "$exe" ]] || continue
    pid="${exe#/proc/}"
    pid="${pid%/exe}"
    target="$(readlink "$exe" 2>/dev/null || true)"
    [[ -n "$target" ]] || continue
    case "$target" in
      *'(deleted)'*|memfd:*)
        cmd="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
        echo "pid=$pid exe=$target cmd=$cmd"
        ;;
    esac
  done
} > "$OUT/hunt_deleted.txt" 2>&1 || true

ps auxww > "$OUT/hunt_ps.txt" 2>/dev/null || true

{
  lsof /dev/input/event* 2>/dev/null || echo 'lsof failed'
} > "$OUT/hunt_input.txt" 2>&1 || true

{
  echo "=== estab proc ==="
  # pid comm cmdline cwd exe for PIDs that appear in ss_established
  python3 - "$OUT/ss_established.txt" << 'PY' || true
import os, re, sys
path = sys.argv[1]
if not os.path.isfile(path):
    raise SystemExit(0)
text = open(path, encoding="utf-8", errors="replace").read()
pids = set(re.findall(r'pid=(\d+)', text))
for pid in sorted(pids, key=int):
    base = f"/proc/{pid}"
    def read(p):
        try:
            return open(p, "r", encoding="utf-8", errors="replace").read().strip()
        except Exception:
            return ""
    cmd = read(f"{base}/cmdline").replace("\x00", " ")
    comm = read(f"{base}/comm")
    try:
        cwd = os.readlink(f"{base}/cwd")
    except Exception:
        cwd = "?"
    try:
        exe = os.readlink(f"{base}/exe")
    except Exception:
        exe = "?"
    print(f"pid={pid} comm={comm} cwd={cwd} exe={exe} cmd={cmd}")
PY
} > "$OUT/hunt_estab_proc.txt" 2>&1 || true

echo "[+] hunt-persistence done" >&2
