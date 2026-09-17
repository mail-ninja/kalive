# F-018 — Ingen rkhunter / chkrootkit

| | |
|--|--|
| Status | **fixed** (2026-09-17_180808 CLEAN; Kali-allowlist + vendor cron disabled) |
| Severity | low–medium (etter FIM) |
| First seen | 2026-08-10 (`reports/2026-08-10_baseline-security.md` §12) |

## Observasjon

Ingen signaturbasert rootkit-scan. Baseline-rapporten listet dette som senere runde.
Kali har høy forventet støy (packet sniffers, dev-tools).

## Anbefalt handling

rkhunter + chkrootkit med Kali-whitelist **etter** AIDE (PR 10 / fase 8).
Ikke ALERT på kjente Kali-warnings.

## Done-kriterium

Første dokumenterte kjøring + whitelist. Lukkes av PR 10 (rootkit-delen).
