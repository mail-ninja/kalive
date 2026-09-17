# F-002 — fail2ban ikke installert

| | |
|--|--|
| Status | open |
| Severity | low (SSH er av) → medium hvis SSH/åpne tjenester aktiveres |
| First seen | 2026-08-10 |

## Observasjon

Pakken `fail2ban` finnes ikke. SSH-server er for øyeblikket inactive/disabled, så
umiddelbar eksponering for brute-force er lav.

## Anbefalt handling

Hvis SSH eller andre auth-tjenester skal eksponeres:

```bash
sudo apt install fail2ban
sudo systemctl enable --now fail2ban
# jail for sshd + evt. andre
```

Se `playbooks/install-fail2ban.md` (opprettes ved implementering).

## Done-kriterium

fail2ban installert/aktiv **eller** beslutning «accepted risk» dokumentert så lenge
ingen remote auth-tjenester lytter.
