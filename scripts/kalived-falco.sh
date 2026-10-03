#!/usr/bin/env bash
# Host Falco burst (~8s, same window as tshark). Writes hunt_falco.jsonl under a stamp.
# Scan sets KALIVED_OUT. Standalone ctl mints a new stamp (never reuse an old scan).
# Never ~/.config/kalived/hiroshima/. Never Qdrant. Never cmdline/SNI/pcap.
# Confirm: sudo kalived-ctl falco-burst
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
# shellcheck source=lib/kalived-config.sh
source "$ROOT/scripts/lib/kalived-config.sh"

if [[ "$(id -u)" -ne 0 && "${KALIVED_FALCO_DRY:-0}" != "1" ]]; then
  echo "bruk: sudo kalived-ctl falco-burst" >&2
  exit 1
fi

if [[ -n "${KALIVED_OUT:-}" ]]; then
  OUT="$KALIVED_OUT"
else
  STAMP="$(date +%Y-%m-%d_%H%M%S)"
  OUT="${KALIVED_DATA:-$ROOT}/logs/status/$STAMP"
  if [[ -e "$OUT" ]]; then
    OUT="${OUT}_$$"
  fi
fi
mkdir -p "$OUT"
NOTE="$OUT/hunt_falco.txt"
JSONL="$OUT/hunt_falco.jsonl"
RAW="$OUT/hunt_falco_raw.jsonl"
ERR="$OUT/hunt_falco.err"
LIB="$ROOT/scripts/lib/falco_burst.py"
RULES="$ROOT/defs/falco-host.yaml"
CONF="$ROOT/defs/falco.yaml"

# Refuse H4 watch dir.
case "$OUT" in
  */.config/kalived/hiroshima|*/.config/kalived/hiroshima/*)
    echo "GATE: Falco skriver ikke til ~/.config/kalived/hiroshima/" >&2
    exit 2
    ;;
esac

DUR="${FALCO_DUR:-8}"
[[ "$DUR" =~ ^[0-9]+$ ]] || DUR=8
(( DUR >= 1 && DUR <= 30 )) || DUR=8

if [[ "${KALIVED_FALCO_DRY:-0}" == "1" ]]; then
  echo "falco dry duration_s=$DUR" > "$NOTE"
  : > "$JSONL"
  echo "DRY falco-burst → $JSONL" >&2
  echo "DONE" >&2
  exit 0
fi

if ! command -v falco >/dev/null 2>&1; then
  echo "falco missing" > "$NOTE"
  : > "$JSONL"
  echo "[*] falco absent — hopp over burst (playbooks/install-falco-host.sh printer apt)" >&2
  echo "DONE" >&2
  exit 0
fi

if [[ ! -f /sys/kernel/btf/vmlinux ]]; then
  echo "falco missing btf" > "$NOTE"
  : > "$JSONL"
  echo "GATE: modern_ebpf trenger BTF (/sys/kernel/btf/vmlinux)" >&2
  echo "DONE" >&2
  exit 0
fi

TMPCONF="$(mktemp /tmp/kalived-falco.XXXXXX.yaml)"
cleanup() { rm -f "$TMPCONF"; }
trap cleanup EXIT
{
  cat "$CONF"
  echo
  echo "rules_files:"
  echo "  - $RULES"
} > "$TMPCONF"

args=(-c "$TMPCONF" -r "$RULES"
  -o json_output=true
  -o json_include_output_property=false
  -o webserver.enabled=false
  -o grpc.enabled=false
  -o syslog_output.enabled=false
  -o http_output.enabled=false
  -o file_output.enabled=false
  -o stdout_output.enabled=true)
help="$(falco --help 2>&1 || true)"
if grep -q -- '--modern-ebpf' <<<"$help"; then
  args+=(--modern-ebpf)
elif grep -q -- '--modern-bpf' <<<"$help"; then
  args+=(--modern-bpf)
fi

echo "[*] falco host-burst ${DUR}s (ingen stock-rules, ingen gRPC/web)" >&2
set +e
timeout "$((DUR + 3))" falco "${args[@]}" > "$RAW" 2>"$ERR"
rc=$?
set -e

reject=0
if grep -qi 'Undefined macro' "$ERR" 2>/dev/null; then
  reject=1
fi
# 0 = falco exited; 124/143/137 = timeout killed a running burst (expected).
if [[ "$rc" -ne 0 && "$rc" -ne 124 && "$rc" -ne 143 && "$rc" -ne 137 ]]; then
  reject=1
fi
if [[ "$reject" -eq 1 ]]; then
  echo "falco rules rejected rc=$rc" > "$NOTE"
  : > "$JSONL"
  rm -f "$RAW"
  echo "[*] falco rules rejected rc=$rc — se $ERR" >&2
  exit 1
fi

echo "duration_s=$DUR rc=$rc rules=$RULES" > "$NOTE"
python3 "$LIB" aggregate "$RAW" "$JSONL" >/dev/null
rm -f "$RAW"
# raw can contain cmdline from Falco stdout — drop it after aggregate
echo "DONE falco-burst → $JSONL" >&2
exit 0
