# shellcheck shell=bash

_snap_or_miss() {
  local f="$1" id="$2" title="$3"
  if [[ -f "$f" ]]; then
    return 0
  fi
  if kalived_is_live; then
    add_finding WARN "$id" "$title" "mangler $f på live scan" "$f"
  else
    add_finding INFO SNAP-MISS "$title" "ikke samlet i dette snapshotet" "$f"
  fi
  return 1
}

check_persistence() {
  local py
  py="$(command -v python3 || command -v python || true)"
  [[ -n "$py" ]] || return 0

  if _snap_or_miss "$OUT/hunt_preload.txt" SUDO-MISS-PRELOAD "preload-dump mangler"; then
    if grep -q '^PRESENT' "$OUT/hunt_preload.txt"; then
      add_finding ALERT PERS-PRELOAD "/etc/ld.so.preload finnes" "$(grep -A5 '^PRESENT' "$OUT/hunt_preload.txt" | head -8)" "hunt_preload.txt"
    fi
    local allow="$ROOT/baselines/machine/preload_allow.txt"
    while IFS= read -r line || [[ -n "$line" ]]; do
      [[ "$line" == PID* ]] || continue
      local ok=0
      if [[ -f "$allow" ]]; then
        while IFS= read -r tok || [[ -n "$tok" ]]; do
          [[ "$tok" == \#* || -z "$tok" ]] && continue
          if echo "$line" | grep -qF "$tok"; then ok=1; break; fi
        done < "$allow"
      fi
      echo "$line" | grep -q libmozsandbox && ok=1
      if [[ "$ok" -eq 0 ]]; then
        add_finding ALERT PERS-PRELOAD "Uventet LD_PRELOAD: $line" "$line" "hunt_preload.txt"
      fi
    done < "$OUT/hunt_preload.txt"
  fi

  if _snap_or_miss "$OUT/hunt_authkeys.txt" SUDO-MISS-ROOTKEYS "authorized_keys-dump mangler"; then
    "$py" - "$OUT/hunt_authkeys.txt" << 'PY'
import sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read()
chunks = text.split("-- ")
keys = []
for ch in chunks:
    if "authorized_keys" not in ch:
        continue
    body = ch.split("\n", 1)[-1]
    for line in body.splitlines():
        s = line.strip()
        if not s or s in ("absent", "(no key material)") or s.startswith("wc ") or s[0].isdigit():
            continue
        if s.startswith("ssh-") or s.startswith("ecdsa-") or s.startswith("sk-") or "AAA" in s:
            keys.append(s[:120])
open(sys.argv[1] + ".keys", "w").write("\n".join(keys))
PY
    if [[ -s "$OUT/hunt_authkeys.txt.keys" ]]; then
      add_finding ALERT PERS-AUTHKEYS "authorized_keys inneholder nøkkelmateriale" \
        "$(cat "$OUT/hunt_authkeys.txt.keys")" "hunt_authkeys.txt"
    fi
    rm -f "$OUT/hunt_authkeys.txt.keys"
  fi

  if _snap_or_miss "$OUT/hunt_cron.txt" SUDO-MISS-ROOTCRON "cron-dump mangler"; then
    if echo "$(cat "$OUT/hunt_cron.txt")" | grep -qiE 'curl[^|]*\|\s*sh|wget[^|]*\|\s*sh|/tmp/.*python|ncat |nc -'; then
      add_finding ALERT PERS-CRON "Cron-jobb ser ut som nedlasting/pipe til shell" \
        "$(grep -iE 'curl|wget|ncat|/tmp' "$OUT/hunt_cron.txt" | head -20)" "hunt_cron.txt"
    fi
  fi

  if _snap_or_miss "$OUT/hunt_suid_extra.txt" SUDO-MISS-SUID "ekstra SUID-dump mangler"; then
    local suid_hits=""
    while IFS= read -r p || [[ -n "$p" ]]; do
      [[ "$p" == /* ]] || continue
      case "$p" in
        */chrome-sandbox|*/chromium-sandbox|*/brave-sandbox)
          add_finding INFO PERS-SUID "Kjent nettleser-sandbox SUID: $p" "$p" "hunt_suid_extra.txt"
          ;;
        *)
          suid_hits+="$p"$'\n'
          ;;
      esac
    done < "$OUT/hunt_suid_extra.txt"
    if [[ -n "$suid_hits" ]]; then
      add_finding ALERT PERS-SUID "SUID utenfor /usr/bin|/sbin (home/tmp/opt/local)" \
        "$suid_hits" "hunt_suid_extra.txt"
    fi
  fi
  local exp="$ROOT/baselines/machine/suid.expected"
  if [[ -f "$OUT/suid.txt" && -f "$exp" ]]; then
    local extra
    extra="$(comm -13 <(sort -u "$exp") <(sort -u "$OUT/suid.txt") || true)"
    if [[ -n "$extra" ]]; then
      add_finding WARN PERS-SUID "Ny SUID i /usr (sannsynlig apt): $extra" "$extra" "suid.txt"
    fi
  fi

  if _snap_or_miss "$OUT/hunt_docker.txt" SNAP-MISS "docker-dump mangler"; then
    if grep -q 'privileged=true' "$OUT/hunt_docker.txt"; then
      add_finding ALERT PERS-DOCKER "Privileged Docker-container" "$(grep privileged=true "$OUT/hunt_docker.txt")" "hunt_docker.txt"
    fi
    if grep -qE '0\.0\.0\.0' "$OUT/hunt_docker.txt"; then
      add_finding ALERT PERS-DOCKER "Docker publiserer mot 0.0.0.0" "$(grep '0.0.0.0' "$OUT/hunt_docker.txt")" "hunt_docker.txt"
    fi
    if grep -q 'docker.sock' "$OUT/hunt_docker.txt"; then
      add_finding ALERT PERS-DOCKER "Container mounter docker.sock" "$(grep docker.sock "$OUT/hunt_docker.txt")" "hunt_docker.txt"
    fi
  fi

  if _snap_or_miss "$OUT/hunt_udev.txt" SNAP-MISS "udev-dump mangler"; then
    if grep -E 'RUN=|PROGRAM=' "$OUT/hunt_udev.txt" | grep -E '/tmp|/home' >/dev/null 2>&1; then
      add_finding ALERT PERS-UDEV "udev-regel kjører noe under /tmp eller /home" \
        "$(grep -E 'RUN=|PROGRAM=' "$OUT/hunt_udev.txt")" "hunt_udev.txt"
    fi
  fi

  if _snap_or_miss "$OUT/hunt_autostart.txt" SNAP-MISS "autostart-dump mangler"; then
    if grep -E '^Exec=' "$OUT/hunt_autostart.txt" | grep -E '/tmp/|/dev/shm/' >/dev/null 2>&1; then
      add_finding ALERT PERS-AUTOSTART "Autostart Exec peker på /tmp" \
        "$(grep Exec= "$OUT/hunt_autostart.txt")" "hunt_autostart.txt"
    fi
  fi

  if _snap_or_miss "$OUT/hunt_rc.txt" SNAP-MISS "rc-dump mangler"; then
    if grep -E 'curl.*\|\s*sh|wget.*\|\s*sh' "$OUT/hunt_rc.txt" >/dev/null 2>&1; then
      add_finding ALERT PERS-RC "Shell rc/profile henter payload til sh" \
        "$(grep -E 'curl|wget' "$OUT/hunt_rc.txt" | head -10)" "hunt_rc.txt"
    fi
  fi

  if _snap_or_miss "$OUT/hunt_systemd.txt" SNAP-MISS "systemd-dump mangler"; then
    local allow="$ROOT/baselines/machine/systemd_allow.txt"
    while IFS= read -r line || [[ -n "$line" ]]; do
      [[ "$line" == *.service* || "$line" == *.timer* ]] || continue
      local base unitfile
      if [[ "$line" == *":ExecStart="* ]]; then
        unitfile="${line%%:ExecStart=*}"
        base="$(basename "$unitfile")"
      else
        base="$(basename "${line%% *}")"
      fi
      if [[ -f "$allow" ]] && grep -qxF "$base" "$allow" 2>/dev/null; then
        continue
      fi
      case "$line" in
        *spice-vdagent*)
          add_finding WARN PERS-SYSTEMD "spice-vdagent enabled på bare metal" "$line" "hunt_systemd.txt"
          ;;
      esac
      if echo "$line" | grep -qE '/tmp/|/dev/shm/|/home/.*/\.' ; then
        add_finding ALERT PERS-SYSTEMD "Systemd-unit utenfor distro med home/tmp-sti: $line" "$line" "hunt_systemd.txt"
      fi
      if echo "$line" | grep -qiE 'ExecStart=.*(curl|wget|ncat|python -c|/tmp/)'; then
        add_finding ALERT PERS-SYSTEMD "ExecStart ser ut som persistens-payload: $line" "$line" "hunt_systemd.txt"
      fi
    done < "$OUT/hunt_systemd.txt"
  fi
}
