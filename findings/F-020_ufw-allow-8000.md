# F-020 — UFW ALLOW IN 8000 fra Anywhere

| | |
|--|--|
| Status | **fixed** (2026-09-17_151255) |
| Severity | medium (policy-hull; ingenting lytter *nå*) |
| First seen | 2026-09-17_145806 (sudo-scan) |
| Closed | 2026-09-17 — `sudo ufw delete allow 8000` (v4+v6) |

## Observasjon

August-baseline (`baselines/firewall_ufw_default_deny.expected`, verifisert 2026-08-10_2321 og 2026-08-13_1034): **tomme user-regler**, ingen eksplisitte allow-porter.

Sudo-scan 2026-09-17_145806:

```
To                         Action      From
8000                       ALLOW IN    Anywhere
8000 (v6)                  ALLOW IN    Anywhere (v6)
```

Live nft `ufw-user-input` / `ufw6-user-input`:

```
tcp dport 8000 counter packets 0 bytes 0 accept
udp dport 8000 counter packets 0 bytes 0 accept
```

Tellerne er **0 pakker** — hullet er åpent, men ubrukt i denne booten. `ss` viser **ingen** LISTEN på :8000 (bare `127.0.0.1:45959` containerd).

## Risiko

Inngående TCP/UDP 8000 fra internett/LAN er tillatt. Default INPUT er fortsatt drop for alt *annet*. Hvis noe senere binder `:8000` på 0.0.0.0, er det nåbart uten ny UFW-endring.

## Anbefalt handling

Hvis du ikke bevisst åpnet 8000:

```bash
sudo ufw delete allow 8000
sudo ufw status verbose
```

Hvis det er bevisst (dev-server): bind til `127.0.0.1:8000` og begrens UFW til localhost, eller dokumenter i `baselines/machine/` som akseptert.

## Done-kriterium

User-regler tomme igjen **eller** 8000 dokumentert som accepted i baseline. Scan skal ALERT-e på udokumentert ALLOW IN.

## Verifisert 2026-09-17_151255

- `ufw_status.txt`: active, deny in, **ingen ALLOW-linjer**
- nft `ufw-user-input` / `ufw6-user-input`: **tomme**
- Ingen `dport 8000` i nft
- `check-firewall.sh` fyrte ikke (tom findings.jsonl)
