# shellcheck shell=bash
# Shared gate for mutating playbooks. Source after ROOT is set.

kalived_latest_scan_dir() {
  local d best="" best_meta=""
  for d in "$ROOT"/logs/status/*/; do
    [[ -f "$d/meta.txt" && -f "$d/verdict.json" ]] || continue
    grep -q '^kalived_scan=1' "$d/meta.txt" 2>/dev/null || continue
    if [[ -z "$best" || "$d" > "$best" ]]; then
      best="$d"
    fi
  done
  printf '%s' "$best"
}

# Exit 2 if latest live verdict is ALERT/ERROR. OK on CLEAN or WARN.
kalived_require_not_alert() {
  local dir verdict
  dir="$(kalived_latest_scan_dir)"
  if [[ -z "$dir" ]]; then
    echo "GATE FAIL: ingen kalived_scan=1 + verdict.json. Kjør sudo ./scripts/kalived-scan.sh først." >&2
    return 2
  fi
  verdict="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('verdict',''))" "$dir/verdict.json" 2>/dev/null || true)"
  echo "GATE: latest=$dir verdict=$verdict"
  case "$verdict" in
    ALERT|ERROR)
      echo "GATE FAIL: siste scan er $verdict — ikke installer auditd/AIDE på denne tilstanden." >&2
      return 2
      ;;
    CLEAN|WARN)
      return 0
      ;;
    *)
      echo "GATE FAIL: uleselig verdict ($verdict)" >&2
      return 2
      ;;
  esac
}

kalived_changelog() {
  {
    echo ""
    echo "### $(date +%Y-%m-%d_%H%M) — $1"
    echo "$2"
  } >> "$ROOT/remediation/CHANGELOG.md"
  if [[ -n "${SUDO_USER:-}" ]]; then
    chown "${SUDO_USER}:${SUDO_USER}" "$ROOT/remediation/CHANGELOG.md" 2>/dev/null || true
  fi
}
