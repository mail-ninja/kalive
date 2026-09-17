# F-015 — Ingen AIDE / filintegritet

| | |
|--|--|
| Status | **fixed** (2026-09-17_163400) — AIDE NO differences, 218 entries |
| Severity | medium |
| First seen | 2026-09-17 (gap kjent som «senere runde» siden 2026-08-10) |

## Observasjon

Ingen FIM. En rootkit som bytter `ps`/`ss`/`ls` fanges ikke av navnegrep.
`suid.txt` dumps, men auto-diff'es ikke.

## Anbefalt handling

AIDE init **etter** fase 0 G1–G10 + fersk CLEAN (eller config `aide_init_policy`).
Aldri `aideinit` på ALERT-host. PR 7.

## Done-kriterium

AIDE-DB i `/var/lib/aide` (root:root) og scan kjører `aide --check` når DB finnes.
