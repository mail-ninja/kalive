#!/usr/bin/env bash
# Copy scan code root:root to /usr/local/lib/kalived (timer must not ExecStart home).
# Run: sudo bash playbooks/install-kalived-helper.sh
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/kalived-gate.sh
source "$ROOT/playbooks/lib/kalived-gate.sh"
# Helper er script-kopi — ingen ALERT-gate (FP må ikke blokkere oppdatering).
PREFIX=/usr/local/lib/kalived
mkdir -p "$PREFIX/scripts/lib" "$PREFIX/baselines"
cp -a "$ROOT/scripts/"*.sh "$PREFIX/scripts/"
cp -a "$ROOT/scripts/lib/"*.sh "$PREFIX/scripts/lib/"
cp -a "$ROOT/baselines/." "$PREFIX/baselines/"
mkdir -p "$PREFIX/defs"
cp -a "$ROOT/defs/." "$PREFIX/defs/"
mkdir -p "$PREFIX/config" "$PREFIX/api"
cp -a "$ROOT/config/." "$PREFIX/config/"
cp -a "$ROOT/api/." "$PREFIX/api/"
chown -R root:root "$PREFIX"
find "$PREFIX" -type d -exec chmod 755 {} \;
find "$PREFIX" -type f -exec chmod 644 {} \;
chmod 755 "$PREFIX/scripts/"*.sh
# No NOPASSWD on /home/void/kalived.
echo "Helper: $PREFIX (root:root)"
ls -ld "$PREFIX" "$PREFIX/scripts/kalived-scan.sh"
kalived_changelog "install-kalived-helper.sh" \
  "- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home."
echo "DONE"
