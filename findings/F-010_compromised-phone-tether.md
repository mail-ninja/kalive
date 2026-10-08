# F-010 — Telefon som gateway (tether)

| | |
|--|--|
| Status | open — operational risk |
| Severity | high (network trust) |
| First seen | 2026-08-13 |

## Observasjon

PC har brukt telefon-hotspot / USB-tether som default-rute. En kompromittert eller uærlig telefon-gw er `tether` / `env_shift` i Hiroshima-porten, ikke automatisk innbrudd på PC-en.

## Risiko

Kompromittert gateway kan MITM, DNS-hijack, levere skadevare, sniffe ukryptert trafikk.

## Handling

1. Ikke tether via en telefon du ikke stoler på.
2. Bytt kritiske passord fra nett du stoler på.
3. PC harden via `playbooks/harden-host-sudo.sh`.
4. Prefer HTTPS/HSTS på sensitive logins over tether.
5. Overlay: merk hotspot-SSID som `tether` via Hiroshima-skuffen (`PUT /v1/hiroshima/env`).
