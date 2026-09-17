# F-001 — UFW-regler ikke verifisert uten sudo

| | |
|--|--|
| Status | **fixed** (verified 2026-08-10_2321) |
| Severity | medium (informasjonsgap) → closed |
| First seen | 2026-08-10 |
| Closed | 2026-08-10 |

## Observasjon (opprinnelig)

UFW enabled i config men runtime-regler ikke dumpet uten sudo.

## Verifikasjon (2026-08-10_2321)

```
Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), deny (routed)
```

Live nft:

- `INPUT` / `FORWARD` policy **drop** (IPv4 + IPv6)
- `ufw-user-input` / `ufw6-user-input` **tomme** (ingen åpne porter)
- Docker-kjeder til stede, 0 container-trafikk
- NetBIOS/SMB-støy droppes; `[UFW BLOCK]` logging aktiv

Artefakter:

- `logs/ufw/2026-08-10_2321_status.txt`
- `scans/firewall/2026-08-10_2321_nft_summary.md`
- `baselines/firewall_ufw_default_deny.expected`

## Done-kriterium

Regler dumpet og oppsummert — **oppfylt**.
