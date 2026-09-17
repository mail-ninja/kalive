# shellcheck shell=bash
# UFW user-regler mot hermetisk baseline (tom allow-liste).

check_firewall() {
  local f="$OUT/ufw_status.txt"
  if [[ ! -f "$f" || ! -s "$f" ]]; then
    if kalived_is_live; then
      add_finding WARN SUDO-MISS-UFW "ufw_status.txt mangler eller tom" "forventet ved sudo-collect" "ufw_status.txt"
    else
      add_finding INFO SNAP-MISS "ufw_status.txt ikke i dette snapshotet" "" "ufw_status.txt"
    fi
    return 0
  fi

  if ! grep -qi '^Status: active' "$f"; then
    add_finding ALERT NET-UFW "UFW er ikke active" "$(head -5 "$f")" "ufw_status.txt"
  fi

  local py
  py="$(command -v python3 || command -v python || true)"
  [[ -n "$py" ]] || return 0

  local tmp
  tmp="$(mktemp)"
  "$py" - "$f" "$tmp" << 'PY'
import sys, re
src, dst = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8", errors="replace").read()
allows = []
for line in text.splitlines():
    if re.search(r"ALLOW IN", line, re.I) and not line.strip().startswith("To"):
        allows.append(line.strip())
open(dst, "w", encoding="utf-8").write("\n".join(allows))
PY
  if [[ -s "$tmp" ]]; then
    local rules
    rules="$(cat "$tmp")"
    add_finding ALERT NET-UFW-ALLOW \
      "UFW har ALLOW IN mot baseline (tom user-liste): ${rules//$'\n'/; }" \
      "$rules" "ufw_status.txt"
  fi
  rm -f "$tmp"
  return 0
}
