# F-014 — journald-only, ingen auditd, ingen auth.log

| | |
|--|--|
| Status | **fixed** (2026-09-17_163400) |
| Severity | medium (etterforskning) |
| First seen | 2026-08-11 (dokumentert i login-ips) |

## Observasjon

- `/var/log/auth.log` finnes ikke (journald only) — `reports/2026-08-11_login-ips.md`
- Ingen `auditd`-regler for passwd/sudoers/ssh/ld.so.preload/modul-last
- `btmp` uleselig uten ekstra rettigheter

## Anbefalt handling

journald `Storage=persistent` + auditd mini-regler (PR 6). Krever grønn fase 0-gate.

## Done-kriterium

auditd aktiv med `kalived_*`-nøkler; scan samler `audit_recent.txt`. Lukkes av PR 6.
