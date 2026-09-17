#!/usr/bin/env bash
# kalived-scan.sh — ett inngangspunkt for kompromissjekk.
# Live scan KREVER root (sudo ./scripts/kalived-scan.sh).
# Fixture/from-dir trenger ikke root.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/kalived-common.sh
source "$ROOT/scripts/lib/kalived-common.sh"
# shellcheck source=lib/kalived-config.sh
source "$ROOT/scripts/lib/kalived-config.sh"
# shellcheck source=lib/kalived-verdict.sh
source "$ROOT/scripts/lib/kalived-verdict.sh"
# shellcheck source=lib/check-listen.sh
source "$ROOT/scripts/lib/check-listen.sh"
# shellcheck source=lib/check-units.sh
source "$ROOT/scripts/lib/check-units.sh"
# shellcheck source=lib/check-passwd.sh
source "$ROOT/scripts/lib/check-passwd.sh"
# shellcheck source=lib/check-firewall.sh
source "$ROOT/scripts/lib/check-firewall.sh"
# shellcheck source=lib/check-persistence.sh
source "$ROOT/scripts/lib/check-persistence.sh"
# shellcheck source=lib/check-process.sh
source "$ROOT/scripts/lib/check-process.sh"
# shellcheck source=lib/check-outbound.sh
source "$ROOT/scripts/lib/check-outbound.sh"
# shellcheck source=lib/check-network-hygiene.sh
source "$ROOT/scripts/lib/check-network-hygiene.sh"
# shellcheck source=lib/check-audit.sh
source "$ROOT/scripts/lib/check-audit.sh"
# shellcheck source=lib/check-aide.sh
source "$ROOT/scripts/lib/check-aide.sh"
# shellcheck source=lib/check-docker.sh
source "$ROOT/scripts/lib/check-docker.sh"
# shellcheck source=lib/check-kernel.sh
source "$ROOT/scripts/lib/check-kernel.sh"
# shellcheck source=lib/check-rootkit.sh
source "$ROOT/scripts/lib/check-rootkit.sh"

usage() {
  cat << 'EOF'
Bruk: sudo ./scripts/kalived-scan.sh [flagg]

Live scan kjøres alltid som root (produktkontrakt).

  --sudo              tving sudo-re-exec hvis ikke root (default for live)
  --from-dir DIR      evaluer kopi av historisk snapshot (read-only på DIR)
  --fixture DIR       som --from-dir, pluss testmodus (ingen live ss/ps)
  --skip-hunt         hopp over hunt-persistence.sh (sjekker fortsatt snapshot-filer)
  --quiet             banner på stderr, verdict.json på stdout
  --help              denne teksten

Exit: 0 CLEAN, 1 WARN, 2 ALERT, 3 ERROR
EOF
}

FROM_DIR=""
FIXTURE_DIR=""
SKIP_HUNT=0
QUIET=0
WANT_SUDO=1
SCAN_VERSION=6

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    --sudo)
      WANT_SUDO=1
      KALIVED_SUDO=1
      shift
      ;;
    --from-dir)
      FROM_DIR="${2:-}"
      [[ -n "$FROM_DIR" ]] || { echo "mangler DIR til --from-dir" >&2; exit 3; }
      shift 2
      ;;
    --fixture)
      FIXTURE_DIR="${2:-}"
      [[ -n "$FIXTURE_DIR" ]] || { echo "mangler DIR til --fixture" >&2; exit 3; }
      shift 2
      ;;
    --skip-hunt)
      SKIP_HUNT=1
      shift
      ;;
    --quiet)
      QUIET=1
      NO_COLOR=1
      export NO_COLOR
      shift
      ;;
    --accept-alert-suppress)
      shift
      ;;
    *)
      echo "ukjent flagg: $1" >&2
      usage >&2
      exit 3
      ;;
  esac
done

if [[ -n "$FIXTURE_DIR" ]]; then
  WANT_SUDO=0
  KALIVED_FIXTURE=1
  KALIVED_FROM_DIR=1
  FROM_DIR="$FIXTURE_DIR"
fi
if [[ -n "$FROM_DIR" ]]; then
  KALIVED_FROM_DIR=1
fi
export KALIVED_FIXTURE="${KALIVED_FIXTURE:-0}"
export KALIVED_FROM_DIR="${KALIVED_FROM_DIR:-0}"
export KALIVED_SUDO="${KALIVED_SUDO:-0}"

if [[ "$QUIET" == "1" ]]; then
  export KALIVED_BANNER_FD=2
else
  export KALIVED_BANNER_FD=1
fi

DATA="${KALIVED_DATA:-$ROOT}"
STAMP="${KALIVED_STAMP:-$(date +%Y-%m-%d_%H%M%S)}"
OUT="${KALIVED_OUT:-$DATA/logs/status/$STAMP}"
if [[ -z "${KALIVED_OUT:-}" && -e "$OUT" ]]; then
  STAMP="${STAMP}_$$"
  OUT="$DATA/logs/status/$STAMP"
fi
export ROOT DATA STAMP OUT
export KALIVED_DATA="$DATA"

if ! kalived_config_load; then
  mkdir -p "$OUT"
  kalived_init_findings
  add_finding ERROR SCAN "ugyldig config.toml" "se stderr; KALIVED_CONFIG=${KALIVED_CONFIG_PATH:-}" "config"
  KALIVED_SUDO_FLAG=0
  write_verdict_md ERROR 3
  write_verdict_json ERROR 3
  print_banner ERROR
  exit 3
fi
if [[ "$SKIP_HUNT" != "1" && "${CFG_SKIP_HUNT:-0}" == "1" ]]; then
  SKIP_HUNT=1
fi
export CFG_NOTIFY_ON_ALERT CFG_SKIP_ROOTKIT CFG_DEFS_AUTO_UPDATE CFG_VERBOSE

# Live: must be root. Re-exec sudo when possible.
if kalived_is_live; then
  if ! kalived_is_root; then
    if [[ -t 0 ]] && command -v sudo >/dev/null 2>&1; then
      _reexec=("$ROOT/scripts/kalived-scan.sh")
      [[ "$QUIET" == "1" ]] && _reexec+=(--quiet)
      [[ "$SKIP_HUNT" == "1" ]] && _reexec+=(--skip-hunt)
      exec sudo -E -- "${_reexec[@]}"
    fi
    mkdir -p "$OUT"
    kalived_init_findings
    add_finding ERROR SCAN "live scan krever root" \
      "kjør: sudo $ROOT/scripts/kalived-scan.sh" "orchestrator"
    KALIVED_SUDO_FLAG=0
    write_verdict_md ERROR 3
    write_verdict_json ERROR 3
    print_banner ERROR
    exit 3
  fi
  KALIVED_SUDO=1
  KALIVED_SUDO_FLAG=1
else
  KALIVED_SUDO_FLAG=0
fi
export KALIVED_SUDO KALIVED_SUDO_FLAG

mkdir -p "$OUT"

if [[ -n "$FROM_DIR" ]]; then
  if [[ ! -d "$FROM_DIR" ]]; then
    echo "finnes ikke: $FROM_DIR" >&2
    exit 3
  fi
  # DIR is read-only. Copy into fresh OUT.
  src="$(cd "$FROM_DIR" && pwd)"
  if [[ "$src" == "$OUT" ]]; then
    echo "from-dir kan ikke være OUT" >&2
    exit 3
  fi
  cp -a "$src"/. "$OUT"/
  # Drop copied verdict so we write our own; keep evidence files.
  rm -f "$OUT/verdict.json" "$OUT/VERDICT.md" "$OUT/findings.jsonl" "$OUT/scan.log"
fi

kalived_init_findings
kalived_log "[*] kalived-scan stamp=$STAMP out=$OUT fixture=${KALIVED_FIXTURE:-0} sudo=${KALIVED_SUDO_FLAG}"

if kalived_is_live; then
  export KALIVED_OUT="$OUT" KALIVED_STAMP="$STAMP"
  if ! "$ROOT/scripts/collect-baseline.sh"; then
    add_finding ERROR SCAN "collect-baseline.sh feilet" "se scan.log"
  fi
  if [[ -f "$OUT/meta.txt" && ! -f "$OUT/collect_meta.txt" ]]; then
    mv "$OUT/meta.txt" "$OUT/collect_meta.txt"
  fi
  if [[ "$SKIP_HUNT" != "1" ]]; then
    if ! "$ROOT/scripts/hunt-persistence.sh"; then
      add_finding ERROR SCAN "hunt-persistence.sh feilet" "se scan.log"
    fi
    if ! "$ROOT/scripts/keylogscan.sh"; then
      add_finding WARN SCAN "keylogscan.sh feilet" "se scan.log"
    fi
    if [[ "${CFG_DEFS_AUTO_UPDATE:-0}" == "1" ]]; then
      "$ROOT/scripts/update-threat-defs.sh" || add_finding WARN SCAN "defs-update feilet" "se logs/defs"
    fi
    if [[ "${CFG_SKIP_ROOTKIT:-0}" != "1" ]]; then
      if ! "$ROOT/scripts/hunt-rootkit.sh"; then
        add_finding ERROR SCAN "hunt-rootkit.sh feilet" "se scan.log"
      fi
    fi
  fi
fi

# Orchestrator-owned meta.txt (append keys, do not clobber collect fields we moved).
{
  echo "stamp=$STAMP"
  echo "date=$(date -Iseconds)"
  echo "host=$(hostname)"
  echo "user=$(whoami)"
  echo "kalived_scan=1"
  echo "sudo=${KALIVED_SUDO_FLAG}"
  echo "scan_version=$SCAN_VERSION"
  echo "fixture=${KALIVED_FIXTURE:-0}"
  echo "adapted=0"
  echo "config_path=${KALIVED_CONFIG_PATH:-}"
  echo "aide_init_policy=${CFG_AIDE_INIT_POLICY:-}"
  echo "scan_sudo_mode=${CFG_SCAN_SUDO_MODE:-}"
  echo "docker_stop_idle=${CFG_DOCKER_STOP_IDLE:-}"
  echo "listen_bind=${CFG_LISTEN_BIND:-}"
} > "$OUT/meta.txt"
if [[ -f "$OUT/collect_meta.txt" ]]; then
  grep -E '^(boot_id|virt)=' "$OUT/collect_meta.txt" >> "$OUT/meta.txt" || true
fi

if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
  :
else
  add_finding ERROR SCAN "python3 mangler" "påkrevd for verdict.json"
fi

run_mod listen check_listen
run_mod units check_units
run_mod passwd check_passwd
run_mod firewall check_firewall
run_mod persist check_persistence
run_mod process check_process
run_mod outbound check_outbound
run_mod nethyg check_network_hygiene
run_mod audit check_audit
run_mod journald check_journald
run_mod aide check_aide
run_mod dockerhyg check_docker_hygiene
run_mod timer check_timer
run_mod kernel check_kernel
run_mod debsums check_debsums
run_mod dpkgage check_dpkg_age
run_mod rootkit check_rootkit

# PR 2 dummy: SUDO-MISS-INPUT only on live sudo=0 (should not happen — we ERROR earlier).
if kalived_is_live && [[ "${KALIVED_SUDO_FLAG}" == "0" ]]; then
  add_finding WARN SUDO-MISS-INPUT \
    "/dev/input ikke sjekket — kjør med sudo" \
    "live scan uten root" "orchestrator"
fi

VERDICT="$(compute_verdict)"
EXIT_CODE="$(verdict_exit_code "$VERDICT")"
write_verdict_md "$VERDICT" "$EXIT_CODE"
write_verdict_json "$VERDICT" "$EXIT_CODE"
print_banner "$VERDICT"

REPORT="$DATA/reports/${STAMP}_scan.md"
mkdir -p "$DATA/reports"
cp "$OUT/VERDICT.md" "$REPORT" 2>/dev/null || true

_owner="${KALIVED_OWNER:-${SUDO_USER:-}}"
if [[ "$(id -u)" -eq 0 && -n "$_owner" ]]; then
  chown -R "${_owner}:${_owner}" "$OUT" "$REPORT" 2>/dev/null || true
fi

if [[ "$QUIET" == "1" ]]; then
  cat "$OUT/verdict.json"
fi

exit "$EXIT_CODE"
