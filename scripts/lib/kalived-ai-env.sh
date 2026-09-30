# shellcheck shell=bash
# Load advisor secrets from ~/.config/kalived/env (not from git).
kalived_ai_env_load() {
  local home="" uid
  uid="$(id -u)"
  if [[ "$uid" -eq 0 && -n "${SUDO_USER:-}" ]]; then
    home="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
  elif [[ "$uid" -eq 0 && -n "${KALIVED_OWNER:-}" ]]; then
    home="$(getent passwd "$KALIVED_OWNER" | cut -d: -f6)"
  fi
  if [[ -z "$home" && -n "${KALIVED_OWNER_HOME:-}" ]]; then
    home="${KALIVED_OWNER_HOME}"
  fi
  if [[ -z "$home" && -n "${HOME:-}" ]]; then
    home="${HOME}"
  fi
  if [[ -z "$home" ]]; then
    home="$(getent passwd "$(id -un)" | cut -d: -f6)"
  fi
  local f="${KALIVED_AI_ENV:-$home/.config/kalived/env}"
  [[ -f "$f" ]] || return 0
  # Only KEY=VALUE lines; no source/eval of arbitrary script.
  local line key val
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" == \#* ]] && continue
    key="${line%%=*}"
    val="${line#*=}"
    case "$key" in
      XAI_API_KEY|XAI_BASE_URL|XAI_MODEL)
        export "$key=$val"
        ;;
    esac
  done < "$f"
}
