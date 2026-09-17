# F-019 — AppArmor: mange profiler unconfined / complain

| | |
|--|--|
| Status | open (INFO / hygiene) |
| Severity | info |
| First seen | 2026-08-13 (full-root: 117 lastet, 76 unconfined, 23 complain) |

## Observasjon

AppArmor-**service** er on (F-003 fixed). De fleste desktop-profiler er likevel unconfined.
Enforce-kampanje på Firefox/Xorg er desktop-brudd og **off by default** i denne rebuild.

## Anbefalt handling

Runtime-knapp `apparmor_enforce_selected` (config/GUI, PR 11+). Ikke silent enforce i PR 1–10.

## Done-kriterium

Dokumentert som accepted/INFO, eller operator slår på utvalgte profiler via config.
