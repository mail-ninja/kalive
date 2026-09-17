#!/usr/bin/env bash
# Install ~/.config/kalived/config.toml from example if missing.
# Run: sudo bash playbooks/install-config.sh   (or uten sudo som void)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="${SUDO_USER:-$(id -un)}"
HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"
DEST_DIR="${HOME_DIR}/.config/kalived"
DEST="${DEST_DIR}/config.toml"
EXAMPLE="$ROOT/config/kalived.toml.example"
mkdir -p "$DEST_DIR"
if [[ -f "$DEST" ]]; then
  echo "finnes allerede: $DEST (ikke overskrevet)"
else
  cp "$EXAMPLE" "$DEST"
  echo "opprettet $DEST"
fi
chmod 700 "$DEST_DIR"
ENVF="${DEST_DIR}/env"
ENVEX="$ROOT/config/env.example"
if [[ ! -f "$ENVF" ]]; then
  cp "$ENVEX" "$ENVF"
  echo "opprettet $ENVF  ← lim inn XAI_API_KEY her"
fi
chmod 600 "$ENVF" "$DEST"
if [[ "$(id -u)" -eq 0 ]]; then
  chown -R "${USER_NAME}:${USER_NAME}" "$DEST_DIR"
fi
echo "DONE"
echo "Config: $DEST"
echo "Advisor-nøkkel: $ENVF  (chmod 600, ikke git)"
