# shellcheck shell=bash

check_helper_stale() {
  [[ "${CFG_HELPER_STALE_CHECK:-1}" == "1" ]] || return 0
  kalived_is_live || return 0
  local prefix="/usr/local/lib/kalived"
  local src="${KALIVED_DATA:-$ROOT}"
  # When scan runs from helper, ROOT is prefix; DATA is git tree.
  if [[ "$ROOT" == "$prefix" ]]; then
    src="${KALIVED_DATA:-/home/void/kalived}"
  fi
  if [[ ! -d "$prefix/scripts" ]]; then
    add_finding INFO HELPER-STALE "helper-prefix mangler (kjør install-kalived-helper.sh)" "" "helper"
    return 0
  fi
  if [[ ! -d "$src/scripts" ]]; then
    return 0
  fi
  local py
  py="$(command -v python3 || command -v python || true)"
  [[ -n "$py" ]] || return 0
  local diff
  diff="$("$py" - "$src" "$prefix" << 'PY'
import glob, hashlib, os, sys
src, prefix = sys.argv[1], sys.argv[2]
# Same set as install-kalived-helper.sh — not scripts/tests/
patterns = [
    "scripts/*.sh",
    "scripts/*.py",
    "scripts/lib/*.sh",
    "scripts/lib/*.py",
    "prompts/*",
    "playbooks/rkhunter.conf.local",
    "api/server.py",
    "api/static/*",
    "api/openapi.yaml",
]
rel = []
for pat in patterns:
    for p in glob.glob(os.path.join(src, pat)):
        if os.path.isfile(p):
            rel.append(os.path.relpath(p, src))
rel = sorted(set(rel))
mismatch = []
missing = []
for r in rel:
    a = os.path.join(src, r)
    b = os.path.join(prefix, r)
    if not os.path.isfile(b):
        missing.append(r)
        continue
    def h(p):
        hsh = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hsh.update(chunk)
        return hsh.hexdigest()
    if h(a) != h(b):
        mismatch.append(r)
print("mismatch=" + ",".join(mismatch[:12]))
print("missing=" + ",".join(missing[:12]))
PY
)"
  local mis miss
  mis="$(echo "$diff" | grep '^mismatch=' | cut -d= -f2-)"
  miss="$(echo "$diff" | grep '^missing=' | cut -d= -f2-)"
  if [[ -n "$mis" || -n "$miss" ]]; then
    add_finding WARN HELPER-STALE \
      "helper /usr/local/lib/kalived er bak git-treet. sudo bash playbooks/install-kalived-helper.sh" \
      "changed=${mis:-none} missing=${miss:-none}" "helper"
  fi
}
