#!/usr/bin/env bash
# Fixture tests for kalived-scan. Never opens live backdoors.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCAN="$ROOT/scripts/kalived-scan.sh"
CASES="$ROOT/scripts/testdata/cases"
fail=0

checksum_testdata() {
  (cd "$ROOT/scripts/testdata" && find . -type f -print0 | sort -z | xargs -0 sha256sum)
}

before="$(checksum_testdata)"

run_case() {
  local dir="$1"
  local name
  name="$(basename "$dir")"
  echo "[test] $name"
  local exp="$dir/expected_verdict.txt"
  if [[ ! -f "$exp" ]]; then
    echo "  FAIL mangler expected_verdict.txt"
    fail=1
    return
  fi
  local want_v want_e
  want_v="$(grep '^VERDICT=' "$exp" | cut -d= -f2)"
  want_e="$(grep '^EXIT=' "$exp" | cut -d= -f2)"
  local out
  set +e
  out="$("$SCAN" --fixture "$dir" --quiet --skip-hunt 2>/tmp/kalived-test-err.$$)"
  local rc=$?
  set -e
  local got_v
  got_v="$(printf '%s' "$out" | python3 -c "import json,sys; print(json.load(sys.stdin)['verdict'])" 2>/dev/null || echo PARSE_FAIL)"
  echo "  rc=$rc want_e=$want_e verdict=$got_v want=$want_v"
  if [[ "$rc" != "$want_e" || "$got_v" != "$want_v" ]]; then
    echo "  FAIL"
    sed 's/^/  /' /tmp/kalived-test-err.$$ || true
    fail=1
  else
    echo "  OK"
  fi
  if grep -q '^IDS=' "$exp"; then
    local ids
    ids="$(grep '^IDS=' "$exp" | cut -d= -f2)"
    if ! printf '%s' "$out" | grep -q "$ids"; then
      echo "  FAIL mangler ID $ids i verdict.json"
      fail=1
    fi
  fi
}

for d in "$CASES"/*; do
  [[ -d "$d" ]] || continue
  run_case "$d"
done

echo "[test] testdata urørt"
after="$(checksum_testdata)"
if [[ "$before" != "$after" ]]; then
  echo "  FAIL testdata endret"
  fail=1
else
  echo "  OK"
fi

echo "[test] ugyldig config enum → exit 3"
badcfg="$(mktemp)"
printf 'aide_init_policy = "bogus"\n' > "$badcfg"
set +e
KALIVED_CONFIG="$badcfg" "$SCAN" --fixture "$CASES/clean_full_root" --quiet --skip-hunt >/tmp/kalived-test-cfg.$$ 2>/tmp/kalived-test-cfg-err.$$
cfg_rc=$?
set -e
if [[ "$cfg_rc" != "3" ]]; then
  echo "  FAIL rc=$cfg_rc (forventet 3)"
  fail=1
else
  echo "  OK rc=3"
fi
rm -f "$badcfg" /tmp/kalived-test-cfg.$$ /tmp/kalived-test-cfg-err.$$

echo "[test] listen_bind 0.0.0.0 → exit 3"
badcfg="$(mktemp)"
printf 'listen_bind = "0.0.0.0"\n' > "$badcfg"
set +e
KALIVED_CONFIG="$badcfg" "$SCAN" --fixture "$CASES/clean_full_root" --quiet --skip-hunt >/dev/null 2>/tmp/kalived-test-bind-err.$$
bind_rc=$?
set -e
if [[ "$bind_rc" != "3" ]]; then
  echo "  FAIL rc=$bind_rc"
  fail=1
else
  echo "  OK rc=3"
fi
rm -f "$badcfg" /tmp/kalived-test-bind-err.$$

echo "[test] API e2e"
if ! "$ROOT/scripts/tests/api-e2e.sh"; then
  echo "  FAIL api-e2e"
  fail=1
else
  echo "  OK api-e2e"
fi

echo "[test] API health + auth"
apicfg="$(mktemp)"
apitok="$(mktemp)"
printf 'listen_bind = "127.0.0.1"\nlisten_port = 18787\n' > "$apicfg"
printf 'test-token-kalived-api\n' > "$apitok"
set +e
KALIVED_CONFIG="$apicfg" KALIVED_API_TOKEN="$apitok" KALIVED_DATA="$ROOT" \
  python3 "$ROOT/api/server.py" >/tmp/kalived-api-out.$$ 2>/tmp/kalived-api-err.$$ &
api_pid=$!
sleep 0.4
h1="$(curl -s -o /tmp/h1.$$ -w '%{http_code}' http://127.0.0.1:18787/v1/health)"
h2="$(curl -s -o /tmp/h2.$$ -w '%{http_code}' http://127.0.0.1:18787/v1/config)"
h3="$(curl -s -o /tmp/h3.$$ -w '%{http_code}' -H 'Authorization: Bearer test-token-kalived-api' http://127.0.0.1:18787/v1/config)"
kill "$api_pid" 2>/dev/null
wait "$api_pid" 2>/dev/null
set -e
if [[ "$h1" == "200" && "$h2" == "401" && "$h3" == "200" ]]; then
  echo "  OK health=$h1 unauth=$h2 auth=$h3"
else
  echo "  FAIL health=$h1 unauth=$h2 auth=$h3"
  sed 's/^/  /' /tmp/kalived-api-err.$$ || true
  fail=1
fi
rm -f "$apicfg" "$apitok" /tmp/h1.$$ /tmp/h2.$$ /tmp/h3.$$ /tmp/kalived-api-out.$$ /tmp/kalived-api-err.$$

echo "[test] live uten root → exit 3 (ERROR)"
set +e
"$SCAN" --quiet --skip-hunt >/tmp/kalived-test-live.$$ 2>/tmp/kalived-test-live-err.$$
live_rc=$?
set -e
if [[ "$live_rc" != "3" ]]; then
  echo "  FAIL rc=$live_rc (forventet 3 når ikke root)"
  fail=1
else
  echo "  OK rc=3"
fi

rm -f /tmp/kalived-test-err.$$ /tmp/kalived-test-live.$$ /tmp/kalived-test-live-err.$$

if [[ "$fail" -ne 0 ]]; then
  echo "FAILED"
  exit 1
fi
echo "ALL OK"
exit 0
