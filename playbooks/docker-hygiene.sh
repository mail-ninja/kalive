#!/usr/bin/env bash
# Docker hygiene: stop-idle + optional dangling prune. Keeps docker group.
# Run: sudo bash playbooks/docker-hygiene.sh [--prune] [--no-stop]
# Start later: sudo systemctl start docker
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/kalived-gate.sh
source "$ROOT/playbooks/lib/kalived-gate.sh"
# shellcheck source=../scripts/lib/kalived-config.sh
source "$ROOT/scripts/lib/kalived-config.sh"
kalived_require_not_alert
kalived_config_load || exit 3

PRUNE=0
STOP="${CFG_DOCKER_STOP_IDLE:-1}"
for a in "$@"; do
  case "$a" in
    --prune) PRUNE=1 ;;
    --no-stop) STOP=0 ;;
    --stop) STOP=1 ;;
    *) echo "ukjent: $a" >&2; exit 3 ;;
  esac
done

mkdir -p /etc/kalived
echo "stop-idle=1" > /etc/kalived/docker-stop-idle
chmod 644 /etc/kalived/docker-stop-idle

if [[ "$PRUNE" == "1" ]]; then
  if ! systemctl is-active --quiet docker; then
    systemctl start docker
  fi
  echo "[*] docker image prune (dangling only)"
  docker image prune -f
  docker images | head -20
fi

if [[ "$STOP" == "1" ]]; then
  running="$(docker ps -q 2>/dev/null || true)"
  names="$(docker ps --format '{{.Names}}' 2>/dev/null || true)"
  if echo "$names" | grep -qE 'qdrant|redis|minio'; then
    echo "cockpit memory-stack kjører (qdrant/redis/minio) — hopper over docker-stop"
    STOP=0
  elif [[ -n "$running" ]]; then
    echo "Containere kjører — hopper over stop. Stopp dem selv først." >&2
    echo "$running"
    exit 1
  fi
fi
if [[ "$STOP" == "1" ]]; then
  echo "[*] stop+disable docker.socket + docker.service (0 containers)"
  systemctl disable --now docker.socket docker.service 2>/dev/null || true
  systemctl is-active docker docker.socket 2>&1 || true
fi

echo "void docker-gruppe: $(getent group docker || true)"
kalived_changelog "docker-hygiene.sh" \
  "- F-005: behold docker-gruppe. stop-idle=$STOP prune=$PRUNE. Marker /etc/kalived/docker-stop-idle. Start: systemctl start docker"
echo "DONE"
