#!/usr/bin/env bash
# Isolated API e2e (own port, own token). Does not need a running GUI or live 8787.
# Usage: ./scripts/tests/api-e2e.sh
# Optional: ./scripts/tests/api-e2e.sh --live   (hits 127.0.0.1:8787 with real token)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
fail=0
ok() { echo "  OK $*"; }
bad() { echo "  FAIL $*"; fail=1; }

code() { curl -sS -o "$2" -w '%{http_code}' "${@:3}" "$1"; }

if [[ "${1:-}" == "--live" ]]; then
  BASE="http://127.0.0.1:8787"
  _owner="${SUDO_USER:-$(id -un)}"
  if [[ "$(id -u)" -eq 0 && "$_owner" == "root" ]]; then
    _owner=void
  fi
  _home="$(getent passwd "$_owner" | cut -d: -f6)"
  _tokf="${_home}/.config/kalived/api.token"
  if [[ ! -r "$_tokf" ]]; then
    echo "Kan ikke lese $_tokf (eier/modus). Kjør: sudo kalived-ctl token-fix" >&2
    echo "Eller: sudo chown ${_owner}:${_owner} $_tokf && chmod 600 $_tokf" >&2
    exit 1
  fi
  TOK="$(tr -d '\n' < "$_tokf")"
  echo "[live] $BASE token=$_tokf"
else
  BASE="http://127.0.0.1:18787"
  cfg="$(mktemp)"
  tokf="$(mktemp)"
  printf 'listen_bind = "127.0.0.1"\nlisten_port = 18787\n' > "$cfg"
  printf 'e2e-token-please-ignore\n' > "$tokf"
  TOK="e2e-token-please-ignore"
  echo "[isolated] $BASE"
  _e2elog="$(mktemp)"
  _e2eerr="$(mktemp)"
  KALIVED_CONFIG="$cfg" KALIVED_API_TOKEN="$tokf" KALIVED_DATA="$ROOT" KALIVED_ROOT="$ROOT" \
    python3 "$ROOT/api/server.py" >"$_e2elog" 2>"$_e2eerr" &
  APIPID=$!
  cleanup() { kill "$APIPID" 2>/dev/null || true; wait "$APIPID" 2>/dev/null || true; rm -f "$cfg" "$tokf" "$_e2elog" "$_e2eerr"; }
  trap cleanup EXIT
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    curl -sf -o /dev/null "$BASE/v1/health" && break
    sleep 0.15
  done
fi

AUTH=(-H "Authorization: Bearer $TOK")
TMP=$(mktemp -d)

echo "[1] unauth"
c=$(code "$BASE/" "$TMP/root.json")
[[ "$c" == "200" ]] && ok "GET / $c" || bad "GET / $c"
c=$(code "$BASE/v1/health" "$TMP/health.json")
[[ "$c" == "200" ]] && ok "GET /v1/health $c" || bad "health $c"
c=$(code "$BASE/v1/config" "$TMP/unauth.json")
[[ "$c" == "401" ]] && ok "GET /v1/config unauth $c" || bad "config unauth $c"
c=$(code "$BASE/v1/verdict/latest" "$TMP/unauth2.json")
[[ "$c" == "401" ]] && ok "verdict unauth $c" || bad "verdict unauth $c"

echo "[2] auth GET"
c=$(code "$BASE/v1/config" "$TMP/config.json" "${AUTH[@]}")
[[ "$c" == "200" ]] && grep -q listen_bind "$TMP/config.json" && ok "config" || bad "config $c"
c=$(code "$BASE/v1/verdict/latest" "$TMP/verdict.json" "${AUTH[@]}")
[[ "$c" == "200" || "$c" == "404" ]] && ok "verdict $c" || bad "verdict $c"
c=$(code "$BASE/v1/snapshots" "$TMP/snaps.json" "${AUTH[@]}")
[[ "$c" == "200" ]] && ok "snapshots $c" || bad "snapshots $c"
c=$(code "$BASE/v1/findings" "$TMP/find.json" "${AUTH[@]}")
[[ "$c" == "200" ]] && ok "findings $c" || bad "findings $c"
c=$(code "$BASE/v1/defs/feeds" "$TMP/feeds.json" "${AUTH[@]}")
[[ "$c" == "200" ]] && grep -q rkhunter "$TMP/feeds.json" && ok "feeds" || bad "feeds $c"
c=$(code "$BASE/v1/playbooks" "$TMP/pb.json" "${AUTH[@]}")
[[ "$c" == "200" ]] && grep -q aide-init "$TMP/pb.json" && ok "playbooks list" || bad "playbooks $c"
c=$(code "$BASE/openapi.yaml" "$TMP/oa.yaml")
[[ "$c" == "200" ]] && grep -q 'kalived local API' "$TMP/oa.yaml" && ok "openapi.yaml" || bad "openapi $c"

echo "[3] confirm-gate + mutating"
c=$(curl -sS -o "$TMP/noconfirm.json" -w '%{http_code}' "${AUTH[@]}" \
  -H 'Content-Type: application/json' -d '{}' \
  -X POST "$BASE/v1/playbooks/aide-init")
[[ "$c" == "400" ]] && ok "playbook without confirm $c" || bad "noconfirm $c $(cat "$TMP/noconfirm.json")"
c=$(curl -sS -o "$TMP/badpb.json" -w '%{http_code}' "${AUTH[@]}" \
  -H 'Content-Type: application/json' -d '{"confirm":true}' \
  -X POST "$BASE/v1/playbooks/not-a-real-book")
[[ "$c" == "404" ]] && ok "unknown playbook $c" || bad "unknown pb $c"
c=$(curl -sS -o "$TMP/defs.json" -w '%{http_code}' "${AUTH[@]}" \
  -H 'Content-Type: application/json' -d '{}' \
  -X POST "$BASE/v1/defs/update")
# isolated e2e is not root → 403; --live as root API → 200
if [[ "${1:-}" == "--live" ]]; then
  [[ "$c" == "200" || "$c" == "403" ]] && ok "defs/update $c" || bad "defs $c"
else
  [[ "$c" == "403" ]] && ok "defs/update not-root $c" || bad "defs expected 403 got $c $(cat "$TMP/defs.json")"
fi
c=$(curl -sS -o "$TMP/ai.json" -w '%{http_code}' "${AUTH[@]}" \
  -H 'Content-Type: application/json' -d '{}' \
  -X POST "$BASE/v1/ai/advise")
[[ "$c" == "501" ]] && ok "ai/advise stub $c" || bad "ai $c"
c=$(curl -sS -o "$TMP/put.json" -w '%{http_code}' "${AUTH[@]}" \
  -H 'Content-Type: application/json' -d '{"listen_bind":"0.0.0.0"}' \
  -X PUT "$BASE/v1/config")
[[ "$c" == "400" ]] && ok "PUT bind 0.0.0.0 rejected $c" || bad "put bind $c $(cat "$TMP/put.json")"

rm -rf "$TMP"
echo
if [[ "$fail" -ne 0 ]]; then
  echo "API E2E FAILED"
  exit 1
fi
echo "API E2E OK"
exit 0
