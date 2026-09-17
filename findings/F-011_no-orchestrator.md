# F-011 — Ingen auto-diff / orkestrator

| | |
|--|--|
| Status | open |
| Severity | medium (operativt: 5 uker uten runde) |
| First seen | 2026-09-17 (gap kjent siden 2026-08-10) |

## Observasjon

`scripts/collect-baseline.sh` dumper tilstand, men sammenligner ikke mot `baselines/`.
`ALERT_non_localhost_tcp.txt` er en rå `ss`-dump uten severity, uten aggregert verdict, uten
exit-kode. Operatoren må tolke `ss`/`ps` selv.

## Anbefalt handling

`scripts/kalived-scan.sh` + auto-diff (PR 2–3 i `reports/2026-09-17_rebuild-design.md`).

## Done-kriterium

Ett inngangspunkt som printer CLEAN/WARN/ALERT og skriver `verdict.json`. Lukkes av PR 3.
