# F-013 — Ingen utgående C2-heuristikk

| | |
|--|--|
| Status | implemented (2026-09-17) — venter live sudo-scan |
| Severity | medium |
| First seen | 2026-09-17 |

## Observasjon

UFW default **allow outgoing**. En reverse shell som bare kobler ut er usynlig mellom
snapshots. Collect tar `ss_established.txt` men ingen auto-vurdering av prosess vs destinasjon.

## Anbefalt handling

NET-ESTAB / PROC-TMPNET / NET-NFT-NAT / NET-DNS i scan (PR 5, read-only).

## Done-kriterium

Scan varsler på uventet established (f.eks. python i `/tmp` mot ikke-localhost). Lukkes av PR 5.
