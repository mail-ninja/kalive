# Fase 0 — ferskt snapshot (hard gate)

Kjør dette **før** nye detektorer, AIDE eller host-muterende playbooks.
Siste fulle runde før rebuild: 2026-08-13. Design: `reports/2026-09-17_rebuild-design.md`.

Ingen nye detektorer her — bare eksisterende scripts + manuelle sjekker.
Hvis **noen** G1–G10 feiler: **stopp rebuild**, etterforsk, ikke «aksepter» innbrudd i baselines.

**Live collect og scan kjøres alltid med sudo** (produktkontrakt 2026-09-17). Non-sudo er bare rest/fallback.

## Kommandoer (i rekkefølge)

```bash
cd /home/void/kalived

# A+B. Collect som root (ufw/nft/aa-status inkludert)
sudo ./scripts/collect-baseline.sh
# Noter STAMP-mappen som skrives (logs/status/YYYY-MM-DD_HHMM/)
# Fallback uten TTY: ./scripts/collect-baseline.sh (mangler G3 live-regler)

# C. Keylogscan uten og med sudo
./scripts/keylogscan.sh
KALIVED_SUDO=1 ./scripts/keylogscan.sh

# D. Manuelle sjekker (inntil hunt-persistence.sh finnes)
STAMP=$(date +%Y-%m-%d_%H%M%S)
MAN="logs/status/${STAMP}_phase0_manual"
mkdir -p "$MAN"
{
  echo "=== deleted exe ==="
  find /proc -maxdepth 2 -name exe -ls 2>/dev/null | grep -i deleted || echo none
  echo "=== ld.so.preload ==="
  if [ -e /etc/ld.so.preload ]; then cat /etc/ld.so.preload; else echo absent; fi
  echo "=== ssh ==="
  systemctl is-active ssh; systemctl is-enabled ssh 2>&1 || true
  echo "=== authorized_keys void ==="
  wc -l ~/.ssh/authorized_keys 2>/dev/null || echo none
  echo "=== uid0 ==="
  awk -F: '$3==0 {print}' /etc/passwd
  echo "=== non-localhost TCP ==="
  ss -tlnp | awk 'NR>1 {print}' | grep -vE '127\.0\.0\.1:|\[::1\]:' || echo OK none
} | tee "$MAN/manual.txt"

# G8: ALLE event*-noder (ikke bare event0/8). upowerd forventes på lid/power (event2).
sudo sh -c "lsof /dev/input/event* 2>/dev/null | tee $MAN/lsof_input.txt"
sudo sh -c "crontab -l 2>&1 | tee $MAN/root_cron.txt; ls -la /etc/cron.d /var/spool/cron/crontabs | tee -a $MAN/root_cron.txt"
sudo sh -c "test -f /root/.ssh/authorized_keys && echo EXISTS || echo absent" | tee "$MAN/root_keys.txt"
```

## Etter kjøring

1. Rapport: `reports/YYYY-MM-DD_phase0-fresh-snapshot.md` (executive verdict-tabell).
2. Oppdater `inventory/host.md` (kernel, disk, nett, guest-utils **disabled** siden 2026-08-13_1028).
3. Kryss `checklists/sec-round.md`.
4. Linje i `remediation/CHANGELOG.md`: «fase 0 snapshot, ingen systemendring».
5. Hvis G1–G10 pass: freeze `baselines/machine/SOURCE.txt` + `prev_snapshot.txt` fra sudo-collect-mappen. Ikke utvid allowlists fra et ALERT-host.

## G1–G10 — «god nok til å gå videre»

Alle må være sanne. Dette er ALERT-klasse med *dagens* verktøy.

| Gate | Kriterium |
|------|-----------|
| G1 | Ingen TCP LISTEN på `0.0.0.0` / LAN / `::` / `*` |
| G2 | `ssh` inactive og masked (eller minst inactive+disabled) |
| G3 | UFW active, default deny incoming, tomme user-regler (sudo-dump) |
| G4 | `/etc/ld.so.preload` fraværende/tom |
| G5 | Ingen `authorized_keys` med nøkler for void/root |
| G6 | Ingen ekstra UID 0 i `/etc/passwd` |
| G7 | Ingen deleted executables (modulo kjent browser-FP dokumentert) |
| G8 | `lsof /dev/input/event*`: COMMAND ⊆ {systemd-logind / systemd-l, Xorg, upowerd}. Tastatur-noder (event0/event8) er ALERT-sensitive; lid/power (`upowerd`) er allowlistet. Ukjent holder på **hvilken som helst** event* stopper rebuild |
| G9 | `last`/journal: 0 remote logins siden forrige runde |
| G10 | Ingen åpenbar reverse-shell-prosess i established (bash/ncat/python mot ikke-localhost) |

Hvis sudo mangler: G3 og G8 er **uverifisert**, ikke grønne. Muterende playbooks (auditd/AIDE/rkhunter/UFW-logging) skal ikke kjøres.

## WARN som **ikke** stopper rebuild

docker.socket oppe, dangling images, F-007 ingen notert full-upgrade, F-010 usb0/tether default route, AppArmor unconfined-antall, `run-vmblock-fuse.mount` enabled, `vmware-user-suid-wrapper` SUID, spice-vdagent user unit.
