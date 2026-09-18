# shellcheck shell=bash

check_docker_hygiene() {
  local marker="$OUT/docker_stop_idle.txt"
  local sock="$OUT/docker_socket.txt"
  local units="$OUT/sec_units.txt"
  if [[ -f "$marker" ]]; then
    local active=""
    if [[ -f "$sock" ]]; then
      active="$(tr -d ' \n' < "$sock")"
    elif [[ -f "$units" ]]; then
      active="$(grep 'docker.socket:' "$units" | awk '{print $NF}' || true)"
    fi
    if [[ "$active" == "active" ]]; then
      if [[ -f "$OUT/docker_ps.txt" ]] && grep -qE 'qdrant|redis|minio' "$OUT/docker_ps.txt"; then
        return 0
      fi
      if [[ -f "$OUT/docker_ps.txt" ]] && ! grep -qE '^[a-f0-9]{12}' "$OUT/docker_ps.txt"; then
        add_finding WARN PERS-DOCKER "docker.socket kjører med 0 containere (stop-idle er satt)" \
          "sudo systemctl disable --now docker.socket docker.service" "docker_socket.txt"
      fi
    fi
  fi
}

check_timer() {
  local f="$OUT/timer_enabled.txt"
  if [[ ! -f "$f" || ! -s "$f" ]]; then
    add_finding INFO LOG-TIMER "kalived-scan.timer ikke i snapshotet" "" "timer_enabled.txt"
    return 0
  fi
  if grep -qx 'enabled' "$f"; then
    return 0
  fi
  if grep -qE 'disabled|not-found|masked' "$f"; then
    add_finding INFO LOG-TIMER "ukentlig timer ikke enabled (opt-in)" "$(cat "$f")" "timer_enabled.txt"
  fi
}
