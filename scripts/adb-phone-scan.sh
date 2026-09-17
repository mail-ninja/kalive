#!/usr/bin/env bash
# Safe read-only ADB inventory of connected Android phone.
# Usage: ./scripts/adb-phone-scan.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ADB="${ADB:-$ROOT/tools/adb}"
STAMP="$(date +%Y-%m-%d_%H%M)"
OUT="$ROOT/logs/status/${STAMP}_adb_phone"
mkdir -p "$OUT"

if [[ ! -x "$ADB" ]]; then
  echo "adb not found at $ADB" >&2
  exit 1
fi

export ADB
echo "[*] ADB: $($ADB version | head -1)"
$ADB start-server >/dev/null
devs=$($ADB devices | awk 'NR>1 && $2=="device" {print $1}')
unauth=$($ADB devices | awk 'NR>1 && $2=="unauthorized" {print $1}')
if [[ -n "$unauth" ]]; then
  echo "[!] Device unauthorized: $unauth"
  echo "    Unlock phone → Allow USB debugging → re-run"
  $ADB devices -l
  exit 2
fi
if [[ -z "$devs" ]]; then
  echo "[!] No authorized device. Connect USB, enable debugging, Allow."
  $ADB devices -l
  exit 2
fi

echo "[*] Scanning → $OUT"
{
  echo "stamp=$STAMP"
  date -Iseconds
  $ADB devices -l
} > "$OUT/meta.txt"

run() {
  local name="$1"; shift
  echo "  - $name"
  $ADB shell "$@" > "$OUT/$name.txt" 2>&1 || echo "(failed $name)" >> "$OUT/$name.txt"
}

run props getprop
run model 'getprop ro.product.model; getprop ro.product.manufacturer; getprop ro.build.version.release; getprop ro.build.display.id'
run packages_third 'pm list packages -3'
run packages_all 'pm list packages -f'
run packages_system 'pm list packages -s'
run enabled_apps 'pm list packages -e'
run disabled_apps 'pm list packages -d'
run features 'pm list features'
run accessibility 'settings get secure enabled_accessibility_services; dumpsys accessibility | head -c 200000'
run device_admin 'dumpsys device_policy | head -c 150000'
run appops_summary 'appops get --user 0 2>/dev/null | head -c 50000; dumpsys appops 2>/dev/null | head -c 100000'
run running_services 'dumpsys activity services | head -c 200000'
run running_procs 'ps -A 2>/dev/null || ps'
run vpn 'dumpsys connectivity | head -c 100000; dumpsys vpn 2>/dev/null | head -c 50000'
run notification_access 'settings get secure enabled_notification_listeners'
run usage_stats 'dumpsys usagestats 2>/dev/null | head -c 150000'
run installs 'dumpsys package packages | head -c 300000'
run adb_settings 'settings get global adb_enabled; settings get global development_settings_enabled; getprop sys.usb.config; getprop sys.usb.state'
run battery 'dumpsys battery'
run wifi 'dumpsys wifi | head -c 80000'
run netstat 'cat /proc/net/tcp /proc/net/tcp6 2>/dev/null | head -c 50000'

# Third-party package list only names
$ADB shell pm list packages -3 2>/dev/null | sed 's/package://' | sort > "$OUT/third_party_names.txt" || true

# Heuristic flags
{
  echo '=== HEURISTIC FLAGS ==='
  grep -iE 'spy|track|monitor|remote|control|keylog|hidden|stealth|hack|rat\.|metasploit|c2|accessibility|deviceadmin|vpn|proxy|cleaner|boost|master\.wifi|anydesk|teamviewer|rustdesk|quicksupport|scrcpy' \
    "$OUT/third_party_names.txt" "$OUT/packages_third.txt" 2>/dev/null || echo '(no keyword hits in package names)'
  echo '=== ACCESSIBILITY ==='
  cat "$OUT/accessibility.txt" 2>/dev/null | head -40
  echo '=== DEVICE ADMIN head ==='
  head -60 "$OUT/device_admin.txt" 2>/dev/null
} | tee "$OUT/HEURISTICS.txt"

echo "[+] Done: $OUT"
echo "    third-party apps: $(wc -l < "$OUT/third_party_names.txt" 2>/dev/null || echo 0)"
