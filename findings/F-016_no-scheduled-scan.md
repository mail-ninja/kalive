# F-016 — Ingen tidsstyrt scan (5-ukers gap)

| | |
|--|--|
| Status | **fixed** (timer enabled, neste 2026-09-21 00:10 CEST) |
| Severity | medium (operativt) |
| First seen | 2026-09-17 |

## Observasjon

Siste fulle runde 2026-08-13, neste 2026-09-17. `checklists/sec-round.md` krever manuell
disiplin som åpenbart svikter. Ingen systemd-timer.

## Anbefalt handling

Opt-in user-timer (PR 8). Default **disabled** til operator har sett én live scan.
`SuccessExitStatus=1 2` slik WARN/ALERT ikke ser ut som unit-failure.

## Done-kriterium

Timer enabled **eller** eksplisitt accepted risk dokumentert.
