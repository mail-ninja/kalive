# F-012 — Persistensjakt ikke repetérbar

| | |
|--|--|
| Status | implemented (2026-09-17) — venter live sudo-scan |
| Severity | medium |
| First seen | 2026-09-17 (one-shot 2026-08-13) |

## Observasjon

Persistens (cron, systemd-user, `ld.so.preload`, authorized_keys, deleted execs) ble sjekket
én gang i `reports/2026-08-13_hermetic-kali-and-cep1er.md` /
`logs/status/2026-08-13_1019_hermetic/persistence.txt`. Ingen `scripts/hunt-persistence.sh`.

## Anbefalt handling

Gjenbrukbart hunt-script koplet inn i `kalived-scan.sh` (PR 4).

## Done-kriterium

Hunt kjører som del av scannen og diff'er mot `baselines/machine/`. Lukkes av PR 4.
