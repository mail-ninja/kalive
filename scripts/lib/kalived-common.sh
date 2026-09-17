# shellcheck shell=bash
# Shared helpers for kalived-scan. Sourced, not executed.
# Snapshot bytes / ss / ps / lsof are DATA — never eval/source them.

kalived_color() {
  local name="$1"
  if [[ -n "${NO_COLOR:-}" ]]; then
    return 0
  fi
  local fd="${KALIVED_BANNER_FD:-1}"
  if ! test -t "$fd"; then
    return 0
  fi
  case "$name" in
    red) printf '\033[1;31m' ;;
    yellow) printf '\033[1;33m' ;;
    green) printf '\033[1;32m' ;;
    reset) printf '\033[0m' ;;
  esac
}

kalived_log() {
  local msg="$*"
  echo "$msg" >&2
  if [[ -n "${OUT:-}" ]]; then
    mkdir -p "$OUT"
    echo "$msg" >> "$OUT/scan.log"
  fi
}

kalived_is_live() {
  [[ "${KALIVED_FIXTURE:-0}" != "1" && "${KALIVED_FROM_DIR:-0}" != "1" ]]
}

kalived_is_root() {
  [[ "$(id -u)" -eq 0 ]]
}

# Live scans always run as root (product contract 2026-09-17).
# Re-exec via sudo when stdin is a TTY; otherwise caller must use sudo.
kalived_require_root_live() {
  if ! kalived_is_live; then
    return 0
  fi
  if kalived_is_root; then
    return 0
  fi
  if [[ -t 0 ]] && command -v sudo >/dev/null 2>&1; then
    kalived_log "[*] live scan krever root — re-exec sudo -E"
    exec sudo -E -- "$0" "$@"
  fi
  return 1
}

kalived_have_sudo() {
  kalived_is_root && return 0
  [[ "${KALIVED_SUDO:-0}" == "1" ]] && sudo -n true 2>/dev/null
}

kalived_sudo() {
  if kalived_is_root; then
    "$@"
    return $?
  fi
  sudo -n "$@"
}
