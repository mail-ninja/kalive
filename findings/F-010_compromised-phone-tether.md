# F-010 — Kompromittert telefon som gateway (tether)

| | |
|--|--|
| Status | open — operational risk |
| Severity | high (network trust) |
| First seen | 2026-08-13 |

## Observasjon

Bruker rapporterer iQOO hacket live. PC har brukt telefon-hotspot/USB-tether for inet.
Snapshot 2026-08-13: `usb0` 192.168.57.162, gw 192.168.57.4.

## Risiko

Kompromittert gateway kan MITM, DNS-hijack, levere skadevare, sniffe ukryptert trafikk.

## Handling

1. Factory reset / ikke bruk den telefonen til tether før ren.
2. Bytt kritiske passord fra rent nett.
3. PC harden via `playbooks/harden-host-sudo.sh`.
4. Prefer HTTPS, HSTS, pin kritiske tjenester; unngå sensitive logins over tether til den telefonen.
