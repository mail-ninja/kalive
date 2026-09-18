# shellcheck shell=bash
# UFW packet digest (sil 4). Policy is check-firewall.sh. Do not ALERT on line count.

check_ufw_digest() {
  [[ "${CFG_UFW_DIGEST:-1}" == "1" ]] || return 0
  local d="$OUT/ufw_digest.json"
  if [[ ! -f "$d" ]]; then
    if kalived_is_live; then
      add_finding INFO NET-UFW-NOISE "ufw_digest.json mangler (ingen 24t-journal i snapshotet)" "" "ufw_digest.json"
    fi
    return 0
  fi
  local py
  py="$(command -v python3 || command -v python || true)"
  [[ -n "$py" ]] || return 0
  local sev id title detail source
  while IFS=$'\t' read -r sev id title detail source || [[ -n "${sev:-}" ]]; do
    [[ -z "${sev:-}" ]] && continue
    add_finding "$sev" "$id" "$title" "${detail//\\n/$'\n'}" "$source"
  done < <("$py" - "$d" << 'PY'
import json, sys

try:
    s = json.load(open(sys.argv[1], encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    raise SystemExit(0)

def emit(sev, fid, title, detail, source):
    def clean(x):
        return str(x or "").replace("\t", " ").replace("\n", "\\n")
    print("\t".join([sev, fid, clean(title), clean(detail), clean(source)]))

lines = int(s.get("lines") or 0)
scans = s.get("scans") or []
floods = s.get("floods") or []
hits = s.get("hits_listen") or []
top = s.get("top_block_dpt") or []
block = int(s.get("block") or 0)
allow = int(s.get("allow") or 0)

if hits:
    bits = []
    for h in hits[:8]:
        bits.append("src=%s dpt=%s in=%s %s" % (h.get("src"), h.get("dpt"), h.get("in"), h.get("action")))
    emit("WARN", "NET-UFW-HIT",
         "UFW %d treff mot lyttende port utenfra (ikke lo)" % len(hits),
         "; ".join(bits), "ufw_digest.json")
if scans or floods:
    emit("INFO", "NET-UFW-SCAN",
         "UFW: %d scan-kilder, %d flood (deny in gjør jobben)" % (len(scans), len(floods)),
         "top_block_dpt=%s" % top[:8], "ufw_digest.json")
elif lines:
    emit("INFO", "NET-UFW-NOISE",
         "UFW 24t: %d linjer (block=%d allow=%d) — støy, ikke angrep" % (lines, block, allow),
         "top_block_dpt=%s" % top[:8], "ufw_digest.json")
PY
)
}
