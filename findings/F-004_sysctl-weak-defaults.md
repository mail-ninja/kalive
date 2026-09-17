# F-004 — Svake kernel sysctl (hardening)

| | |
|--|--|
| Status | **fixed** (99-kalived-hardening.conf 2026-08-13_1028) |
| Severity | medium |
| First seen | 2026-08-10 |

## Observasjon (runtime)

| Key | Verdi | Forventet hardnet | Kommentar |
|-----|-------|-------------------|-----------|
| net.ipv4.ip_forward | 1 | 0 (hvis ikke router) | Docker setter ofte 1 |
| net.ipv4.conf.all.rp_filter | 0 | 1 eller 2 | strict/loose RPF |
| net.ipv4.conf.all.send_redirects | 1 | 0 | |
| kernel.kptr_restrict | 0 | 1 eller 2 | |
| kernel.dmesg_restrict | 0 | 1 | |
| kernel.yama.ptrace_scope | 0 | 1+ | |
| net.ipv4.conf.all.accept_redirects | 0 | 0 | OK |
| fs.suid_dumpable | 0 | 0 | OK |

Ingen egne hardening-filer under `/etc/sysctl.d/` (kun README + cursor-relatert).

## Anbefalt handling

Lag `/etc/sysctl.d/99-kalived-hardening.conf` via playbook (pass på Docker/ip_forward).
Se `playbooks/sysctl-hardening.md` når implementert.

## Done-kriterium

Persistente sysctl-verdier + re-snapshot i `logs/status/`.

## Applied
`/etc/sysctl.d/99-kalived-hardening.conf` via harden-host-sudo.sh
