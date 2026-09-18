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

echo "[test] ufw-digest parser"
tmpu="$(mktemp)"
{
  echo '2026-09-18T01:00:00+02:00 kali kernel: [UFW BLOCK] IN=eth0 OUT= SRC=198.51.100.7 DST=192.0.2.1 PROTO=TCP SPT=1 DPT=1000'
  echo '2026-09-18T01:00:01+02:00 kali kernel: [UFW BLOCK] IN=eth0 OUT= SRC=198.51.100.7 DST=192.0.2.1 PROTO=TCP SPT=1 DPT=1001'
  echo '2026-09-18T01:00:02+02:00 kali kernel: [UFW BLOCK] IN=eth0 OUT= SRC=198.51.100.7 DST=192.0.2.1 PROTO=TCP SPT=1 DPT=1002'
  echo '2026-09-18T01:00:03+02:00 kali kernel: [UFW BLOCK] IN=eth0 OUT= SRC=198.51.100.7 DST=192.0.2.1 PROTO=TCP SPT=1 DPT=1003'
  echo '2026-09-18T01:00:04+02:00 kali kernel: [UFW BLOCK] IN=eth0 OUT= SRC=198.51.100.7 DST=192.0.2.1 PROTO=TCP SPT=1 DPT=1004'
  echo '2026-09-18T01:00:05+02:00 kali kernel: [UFW BLOCK] IN=eth0 OUT= SRC=198.51.100.7 DST=192.0.2.1 PROTO=TCP SPT=1 DPT=1005'
  echo '2026-09-18T01:00:06+02:00 kali kernel: [UFW BLOCK] IN=eth0 OUT= SRC=198.51.100.7 DST=192.0.2.1 PROTO=TCP SPT=1 DPT=1006'
  echo '2026-09-18T01:00:07+02:00 kali kernel: [UFW BLOCK] IN=eth0 OUT= SRC=198.51.100.7 DST=192.0.2.1 PROTO=TCP SPT=1 DPT=1007'
  echo '2026-09-18T01:00:08+02:00 kali kernel: [UFW BLOCK] IN=eth0 OUT= SRC=198.51.100.7 DST=192.0.2.1 PROTO=TCP SPT=1 DPT=1008'
  echo '2026-09-18T01:00:09+02:00 kali kernel: [UFW BLOCK] IN=eth0 OUT= SRC=198.51.100.7 DST=192.0.2.1 PROTO=TCP SPT=1 DPT=1009'
  echo '2026-09-18T01:00:10+02:00 kali kernel: [UFW BLOCK] IN=eth0 OUT= SRC=198.51.100.7 DST=192.0.2.1 PROTO=TCP SPT=1 DPT=1010'
  echo '2026-09-18T01:00:20+02:00 kali kernel: [UFW ALLOW] IN= OUT=proton0 SRC=10.2.0.2 DST=10.2.0.1 PROTO=UDP SPT=1 DPT=53'
  i=0
  while [[ $i -lt 25 ]]; do
    echo "2026-09-18T01:01:00+02:00 kali kernel: [UFW ALLOW] IN= OUT=proton0 SRC=fdeb:446c:912d:8da:: DST=2606:4700:: PROTO=TCP SPT=40000 DPT=443"
    i=$((i + 1))
  done
} > "$tmpu.j"
python3 "$ROOT/scripts/lib/ufw-digest.py" "$tmpu.j" "$tmpu.json"
if python3 -c 'import json,sys; d=json.load(open(sys.argv[1]));
assert d["scans"] and d["scans"][0]["dpts"]>=10, d
assert d["allow_dns_proton"]==1, d
assert not d["hits_listen"], d
assert not d["floods"], d' "$tmpu.json"; then
  echo "  OK digest scan + proton DNS, ingen listen-hit/HTTPS-flood"
else
  echo "  FAIL ufw-digest"
  cat "$tmpu.json" || true
  fail=1
fi
rm -f "$tmpu" "$tmpu.j" "$tmpu.json"

echo "[test] advisor pcap summary"
tmpp="$(mktemp -d)"
printf '{"verdict":"CLEAN","exit_code":0,"stamp":"t","sudo":1,"findings":[]}\n' > "$tmpp/verdict.json"
printf '{"status":"ran","iface":"lo","raw_rows":10,"synack_ports":[8787],"vs_ss":"match","drop":{"scan_self":9}}\n' > "$tmpp/hunt_pcap_summary.json"
python3 "$ROOT/scripts/kalived-advise.py" --dry-run --snapshot "$tmpp" >/tmp/kalived-advise-pcap.$$
if grep -q '"iface": "lo"' /tmp/kalived-advise-pcap.$$ && ! grep -qi 'frame.time' /tmp/kalived-advise-pcap.$$; then
  echo "  OK pcap summary, no packet dump"
else
  echo "  FAIL pcap redact"
  fail=1
fi
rm -rf "$tmpp" /tmp/kalived-advise-pcap.$$

echo "[test] banner sil-tall (CLEAN race)"
set +e
"$SCAN" --fixture "$CASES/clean_hidden_race" --quiet --skip-hunt >/tmp/kalived-ban-out.$$ 2>/tmp/kalived-ban-err.$$
set -e
if grep -q 'hidden_raw=4' /tmp/kalived-ban-err.$$ && grep -q 'kept=0' /tmp/kalived-ban-err.$$ && grep -q 'listen=lo-only' /tmp/kalived-ban-err.$$; then
  echo "  OK banner hidden_raw=4 kept=0"
else
  echo "  FAIL banner"
  sed 's/^/  /' /tmp/kalived-ban-err.$$ || true
  fail=1
fi
rm -f /tmp/kalived-ban-out.$$ /tmp/kalived-ban-err.$$

echo "[test] aide-init --force gates ALERT"
if grep -q -- '--force-alert' "$ROOT/playbooks/aide-init.sh" \
  && grep -q 'kalived_require_not_alert' "$ROOT/playbooks/aide-init.sh" \
  && grep -q 'FORCE_ALERT' "$ROOT/playbooks/aide-init.sh"; then
  echo "  OK --force-alert er egen nøkkel; --force alene skipper ikke ALERT"
else
  echo "  FAIL aide-init gate"
  fail=1
fi

echo "[test] testdata urørt"
after="$(checksum_testdata)"
if [[ "$before" != "$after" ]]; then
  echo "  FAIL testdata endret"
  fail=1
else
  echo "  OK"
fi

echo "[test] advisor playbooks"
if python3 "$ROOT/scripts/kalived-advise.py" --list-playbooks | grep -qx signal \
  && python3 "$ROOT/scripts/kalived-advise.py" --dry-run --ask "YO" | grep -q '"playbook": "default"'; then
  echo "  OK default personality vs signal playbook"
else
  echo "  FAIL advisor playbooks"
  fail=1
fi

echo "[test] advisor dry-run redact"
if python3 "$ROOT/scripts/kalived-advise.py" --dry-run --snapshot "$CASES/clean_full_root" >/tmp/kalived-advise-dry.$$ 2>/tmp/kalived-advise-dry-err.$$; then
  echo "  (no verdict in fixture dir — ok if fails)"
fi
snap=""
for d in "$ROOT"/logs/status/*/verdict.json; do
  dir="${d%/verdict.json}"
  [[ -f "$dir/hunt_nmap.gnmap" ]] || continue
  grep -q '"verdict": "CLEAN"' "$d" || continue
  snap="$dir"
done
if [[ -n "$snap" ]]; then
  python3 "$ROOT/scripts/kalived-advise.py" --dry-run --snapshot "$snap" >/tmp/kalived-advise-dry.$$ 2>/tmp/kalived-advise-dry-err.$$
  if grep -q '"verdict": "CLEAN"' /tmp/kalived-advise-dry.$$ && ! grep -qi 'Ignored State' /tmp/kalived-advise-dry.$$; then
    echo "  OK redacted CLEAN + nmap summary"
  else
    echo "  FAIL redact"
    fail=1
  fi
fi
python3 "$ROOT/scripts/kalived-advise.py" --dry-run --snapshot "$CASES/alert_nmap_hidden" >/tmp/kalived-advise-nmap.$$ 2>/dev/null || true
# fixture dir may lack verdict.json — synthesize nmap via a temp verdict
if [[ ! -f "$CASES/alert_nmap_hidden/verdict.json" ]]; then
  tmpn="$(mktemp -d)"
  cp "$CASES/alert_nmap_hidden/"* "$tmpn/"
  printf '{"verdict":"ALERT","exit_code":2,"stamp":"fixture","sudo":0,"findings":[]}\n' > "$tmpn/verdict.json"
  python3 "$ROOT/scripts/kalived-advise.py" --dry-run --snapshot "$tmpn" >/tmp/kalived-advise-nmap.$$
  rm -rf "$tmpn"
fi
if grep -q '"port": 4444' /tmp/kalived-advise-nmap.$$ && ! grep -qi 'Ignored State' /tmp/kalived-advise-nmap.$$; then
  echo "  OK nmap port 4444 in context, no gnmap dump"
else
  echo "  FAIL nmap summary"
  fail=1
fi
rm -f /tmp/kalived-advise-nmap.$$
tmpc="$(mktemp -d)"
printf '{"verdict":"CLEAN","exit_code":0,"stamp":"t","sudo":1,"findings":[]}\n' > "$tmpc/verdict.json"
python3 "$ROOT/scripts/kalived-advise.py" --dry-run --snapshot "$tmpc" >/tmp/kalived-advise-clean.$$
if grep -q '"suggested_commands"' /tmp/kalived-advise-clean.$$ \
  && python3 -c 'import json,sys; d=json.load(open(sys.argv[1]));
cmds=d.get("suggested_commands") or [];
assert "sudo kalived-ctl scan" not in cmds, cmds' /tmp/kalived-advise-clean.$$; then
  echo "  OK CLEAN suggested_commands uten re-scan"
else
  echo "  FAIL CLEAN re-scan i suggested_commands"
  fail=1
fi
rm -rf "$tmpc" /tmp/kalived-advise-clean.$$
rm -f /tmp/kalived-advise-dry.$$ /tmp/kalived-advise-dry-err.$$

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
