# F-017 — UFW logging low + default allow outgoing

| | |
|--|--|
| Status | implemented (logging medium playbook) — venter sudo-kjøring. Egress-deny fortsatt out of scope |
| Severity | low (logging) / info (egress-policy) |
| First seen | 2026-08-10 (logging low i harden-script) |

## Observasjon

`playbooks/harden-host-sudo.sh` setter `ufw logging low` og `default allow outgoing`.
Inbound er deny (F-001 fixed). Utgående bakdør logges/blokkeres ikke.

## Anbefalt handling

- Read-only UFW-digest i scan (PR 5)
- `ufw logging medium` via gated playbook (PR 6, krever grønn fase 0)
- Full egress deny-by-default er **ikke** i denne rebuild (fase 9 = ingen kode-PR)

## Done-kriterium

Logging medium + digest i scan. Egress-deny forblir out of scope.
