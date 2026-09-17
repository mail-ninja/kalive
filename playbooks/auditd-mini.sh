#!/usr/bin/env bash
# Install auditd + kalived mini rules. Run: sudo bash playbooks/auditd-mini.sh
# Rollback: rm /etc/audit/rules.d/99-kalived.rules && augenrules --load
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/kalived-gate.sh
source "$ROOT/playbooks/lib/kalived-gate.sh"
kalived_require_not_alert

export DEBIAN_FRONTEND=noninteractive
if ! command -v auditctl >/dev/null 2>&1; then
  apt-get install -y auditd audispd-plugins
fi
install -m 640 "$ROOT/playbooks/auditd-mini.rules" /etc/audit/rules.d/99-kalived.rules
if command -v augenrules >/dev/null 2>&1; then
  augenrules --load
fi
systemctl enable --now auditd
sleep 1
echo "=== auditctl -l (kalived keys) ==="
auditctl -l 2>/dev/null | grep -E 'kalived_|key=' || auditctl -l 2>/dev/null | tail -20
if auditctl -l 2>/dev/null | grep -q kalived_preload; then
  echo "OK: kalived_preload loaded"
else
  echo "WARN: kalived_preload not visible yet (immutable ruleset? reboot/load)"
fi
if auditctl -l 2>/dev/null | grep -q kalived_usb; then
  echo "FAIL: USB-regel skal være kommentert" >&2
  exit 3
fi
kalived_changelog "auditd-mini.sh" \
  "- auditd + /etc/audit/rules.d/99-kalived.rules (USB/execve kommentert). Gate: ikke ALERT."
echo "DONE"
