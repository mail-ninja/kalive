#!/usr/bin/env bash
# Persistent journald. Run: sudo bash playbooks/journald-persistent.sh
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/kalived-gate.sh
source "$ROOT/playbooks/lib/kalived-gate.sh"
kalived_require_not_alert

DROP="/etc/systemd/journald.conf.d/99-kalived.conf"
mkdir -p /etc/systemd/journald.conf.d
cat > "$DROP" << 'EOF'
[Journal]
Storage=persistent
SystemMaxUse=500M
MaxRetentionSec=14day
EOF
chmod 644 "$DROP"
mkdir -p /var/log/journal
systemd-tmpfiles --create --prefix /var/log/journal >/dev/null 2>&1 || true
systemctl restart systemd-journald
echo "journald Storage=persistent MaxUse=500M Retention=14d → $DROP"
kalived_changelog "journald-persistent.sh" \
  "- journald persistent 500M/14d ($DROP). Gate: ikke ALERT."
echo "DONE"
