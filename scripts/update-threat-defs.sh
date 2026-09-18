#!/usr/bin/env bash
# Update threat definition sources. Extensible via defs/feeds.d/*.feed
# Local git IOC = ALERT-grunnlag. Remote cache = WARN inntil det merges i git.
# Aldri eval av nedlastet innhold. Nyheter er aldri ALERT-grunnlag.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${KALIVED_DATA:-$ROOT}"
STAMP="$(date +%Y-%m-%d_%H%M%S)"
LOG="$DATA/logs/defs/${STAMP}_update.log"
CACHE="$ROOT/defs/cache"
mkdir -p "$DATA/logs/defs" "$CACHE"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

{
  echo "=== update-threat-defs $STAMP ==="
  echo "defs VERSION=$(cat "$ROOT/defs/VERSION" 2>/dev/null || echo '?')"
} | tee "$LOG"

# --- local pack: always refresh cache copies of git IOC (no network) ---
sync_local_pack() {
  echo "[feed] local-ioc type=local-pack"
  local n=0
  shopt -s nullglob
  for f in "$ROOT/defs/ioc/"*.txt; do
    [[ -f "$f" ]] || continue
    install -m 644 "$f" "$CACHE/$(basename "$f").local"
    n=$((n + 1))
  done
  for f in "$ROOT/defs/kali-allow/"*.txt; do
    [[ -f "$f" ]] || continue
    install -m 644 "$f" "$CACHE/$(basename "$f").allow"
    n=$((n + 1))
  done
  echo "  copied $n git-lists → $CACHE"
}

ingest_http() {
  local id="$1" url="$2" kind="$3"
  local dest="$CACHE/${id}.remote.txt"
  local tmp
  tmp="$(mktemp)"
  echo "  GET $url"
  if ! curl -fsSL --max-time 45 --retry 1 -A "kalived-defs/1" "$url" -o "$tmp"; then
    echo "  FAIL curl $id"
    rm -f "$tmp"
    return 0
  fi
  python3 - "$tmp" "$dest" "$kind" << 'PY' || true
import os, re, sys
src, dest, kind = sys.argv[1:4]
raw = open(src, encoding="utf-8", errors="replace").read().splitlines()
out = []
if kind == "url-ioc":
    for line in raw:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.search(r"https?://([^/:]+)", line, re.I)
        host = (m.group(1) if m else line).lower().rstrip(".")
        if re.match(r"^[a-z0-9][a-z0-9.-]{1,250}$", host) and "." in host:
            out.append(host)
elif kind == "text-lines":
    for line in raw:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._/-]{1,80}$", line):
            out.append(line.lower())
# unique, cap
seen = set()
uniq = []
for x in out:
    if x in seen:
        continue
    seen.add(x)
    uniq.append(x)
    if len(uniq) >= 8000:
        break
os.makedirs(os.path.dirname(dest), exist_ok=True)
with open(dest, "w", encoding="utf-8") as f:
    f.write("# remote cache — WARN in checkers, never eval\n")
    f.write("\n".join(uniq) + ("\n" if uniq else ""))
print("  wrote %d tokens → %s" % (len(uniq), dest))
PY
  rm -f "$tmp"
}

run_feed() {
  local f="$1"
  local id type enabled url
  id="$(grep -E '^id=' "$f" | head -1 | cut -d= -f2-)"
  type="$(grep -E '^type=' "$f" | head -1 | cut -d= -f2-)"
  enabled="$(grep -E '^enabled=' "$f" | head -1 | cut -d= -f2-)"
  url="$(grep -E '^url=' "$f" | head -1 | cut -d= -f2- || true)"
  [[ "$enabled" == "1" ]] || { echo "[skip] $id ($type)"; return 0; }
  echo "[feed] $id type=$type"
  case "$type" in
    rkhunter)
      if command -v rkhunter >/dev/null 2>&1; then
        rkhunter --update || echo "rkhunter --update failed"
      else
        echo "rkhunter not installed"
      fi
      ;;
    local-pack)
      sync_local_pack
      ;;
    url-ioc)
      [[ -n "$url" ]] || { echo "  missing url="; return 0; }
      ingest_http "$id" "$url" url-ioc
      ;;
    text-lines)
      [[ -n "$url" ]] || { echo "  missing url="; return 0; }
      ingest_http "$id" "$url" text-lines
      ;;
    json-cve|yara|news)
      echo "  skip type=$type (news/cve is context, never ALERT-grunnlag)"
      ;;
    *)
      echo "  unknown type $type — ignored (no eval)"
      ;;
  esac
}

if command -v rkhunter >/dev/null 2>&1; then
  _rkconf=""
  for _c in "$ROOT/playbooks/rkhunter.conf.local" \
            "$ROOT/config/rkhunter.conf.local" \
            "${KALIVED_DATA:-}/playbooks/rkhunter.conf.local"; do
    [[ -f "$_c" ]] && _rkconf="$_c" && break
  done
  if [[ -n "$_rkconf" ]]; then
    install -m 644 "$_rkconf" /etc/rkhunter.conf.local
    echo "rkhunter.conf.local ← $_rkconf"
  else
    echo "WARN: rkhunter.conf.local not in helper/playbooks — skip install, fortsetter --update"
  fi
fi

sync_local_pack | tee -a "$LOG"

# Parallel: rkhunter + enabled HTTP feeds
_pids=()
_run_bg() {
  local f="$1"
  local type enabled
  type="$(grep -E '^type=' "$f" | head -1 | cut -d= -f2-)"
  enabled="$(grep -E '^enabled=' "$f" | head -1 | cut -d= -f2-)"
  [[ "$enabled" == "1" ]] || { echo "[skip] $(grep -E '^id=' "$f" | head -1 | cut -d= -f2-) ($type)" | tee -a "$LOG"; return 0; }
  [[ "$type" == "local-pack" ]] && return 0
  ( run_feed "$f" ) | tee -a "$LOG" &
  _pids+=($!)
}

shopt -s nullglob
for feed in "$ROOT/defs/feeds.d/"*.feed; do
  _run_bg "$feed"
done
for _p in "${_pids[@]+"${_pids[@]}"}"; do
  wait "$_p" || echo "WARN: feed pid $_p failed" | tee -a "$LOG"
done

python3 - "$CACHE" "$STAMP" "$ROOT/defs/VERSION" << 'PY' || true
import json, os, sys, time, hashlib
cache, stamp, verp = sys.argv[1:4]
files = {}
for name in sorted(os.listdir(cache)):
    p = os.path.join(cache, name)
    if not os.path.isfile(p):
        continue
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    files[name] = {"sha256": h, "bytes": os.path.getsize(p)}
ver = open(verp, encoding="utf-8").read().strip() if os.path.isfile(verp) else "?"
json.dump({"stamp": stamp, "defs_version": ver, "files": files, "unix": int(time.time())},
          open(os.path.join(cache, "MANIFEST.json"), "w", encoding="utf-8"), indent=2)
print("MANIFEST.json files=%d" % len(files))
PY

echo "allowlists: $ROOT/defs/kali-allow/"
echo "DONE" | tee -a "$LOG"
if [[ -n "${SUDO_USER:-}" ]]; then
  chown -R "${SUDO_USER}:${SUDO_USER}" "$DATA/logs/defs" "$CACHE" 2>/dev/null || true
fi
