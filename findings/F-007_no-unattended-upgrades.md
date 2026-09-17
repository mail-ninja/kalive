# F-007 — Ingen unattended-upgrades / auto-patch

| | |
|--|--|
| Status | scan-WARN hvis dpkg.log > 30 dager; ingen unattended-upgrades (Kali rolling) |
| Severity | low–medium (Kali rolling = manuell disiplin) |
| First seen | 2026-08-10 |

## Observasjon

- Pakke `unattended-upgrades` ikke funnet.
- Siste dpkg-aktivitet i logg rundt **2026-08-07** (inkl. ufw install).
- Kali rolling oppdateres typisk manuelt (`apt update && apt full-upgrade`).

## Anbefalt handling

Enten periodisk manuell upgrade (sjekkliste) eller begrenset auto-security setup.
Ikke slå på aggressiv auto-upgrade blindt på Kali (breaking changes).

## Done-kriterium

Sjekkliste-punkt + dato for siste full upgrade i inventory/rapport.
