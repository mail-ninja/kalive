# Sec-runde sjekkliste

Bruk denne hver gang. Kryss av og pek til ny snapshot under `logs/status/`.

**Fase 0 (hard gate før AIDE/auditd):** `checklists/phase0-fresh-snapshot.md`  
**Rebuild-plan:** `reports/2026-09-17_rebuild-design.md`

## Kartlegging (alltid)

- [x] Fase 0 collect 2026-09-17_1443 (non-sudo i agent-sesjon; **sudo-scan gjenstår** for G3/G8)
- [ ] `sudo ./scripts/kalived-scan.sh` → ny mappe i `logs/status/`
- [x] TCP LISTEN utenfor localhost: ingen (2026-09-17_1443)
- [x] SSH: masked / inactive (2026-09-17)
- [x] Docker: 0 containers (daemon on — F-005)
- [x] Aktive nettverk 2026-09-17: eth0 192.168.10.73 + ProtonVPN proton0

## Med sudo (når passord tilgjengelig)

- [ ] `sudo ufw status verbose` → `logs/ufw/`
- [ ] `sudo nft list ruleset` eller iptables → `scans/firewall/`
- [ ] `sudo aa-status`
- [ ] `sudo fail2ban-client status` (hvis installert)
- [ ] Evt. `lastb` / auth-feil

## Hardening backlog (fra baseline)

- [x] F-001 UFW-regler verifisert (2026-08-10_2321)
- [x] F-003 AppArmor service enabled (2026-08-11 02:04)
- [x] F-009 Keylogscan clean (2026-08-11 02:07)
- [x] F-004 Sysctl (2026-08-13_1028)
- [x] F-006 Guest-utils (2026-08-13_1028)
- [ ] F-002 fail2ban (hvis remote auth)
- [ ] F-005 Docker policy / prune (stop-when-idle; behold gruppen)
- [ ] F-007 Oppdateringer (WARN hvis dpkg > 30 dager; ingen unattended-upgrades)
- [ ] F-010 Kompromittert telefon-tether (ren nettvei) (`apt update` / full-upgrade dato notert)
- [ ] F-011–F-019 gap-tickets (orkestrator, hunt, outbound, auditd, AIDE, timer, UFW-log, rkhunter, AA-unconfined)

## Periodisk

- [ ] Keylogscan (prosess/autostart/LD_PRELOAD + evt. `sudo lsof /dev/input/event0`)
- [ ] `sudo aa-status` snapshot

## Etter endringer

- [ ] Ny status-snapshot
- [ ] Oppdater findings status
- [ ] Linje i `remediation/CHANGELOG.md`
- [ ] Oppdater baseline hvis ny «kjent god» tilstand
