# F-005 — Docker root-ekvivalent + image-rot

| | |
|--|--|
| Status | **accepted (gruppe) + mitigated** (2026-09-17_165742: docker.socket inactive, timer enabled) |
| Severity | medium (gruppe) / low (images) |
| First seen | 2026-08-10 |

## Observasjon

- Operator er i **docker**-gruppen → praktisk root-ekvivalent (socket access).
- Docker daemon kan kjøre med dangling images og gamle prosjekt-lag.
- Bridges: `docker0` og prosjekt-nett (linkdown når idle).
- `net.ipv4.ip_forward=1` typisk pga. Docker.

## Risiko

Kompromittert brukerkonto = host root via Docker. Disk/forvirring fra dangling images.

## Anbefalt handling

1. Bevisst beslutning: beholde docker-gruppe (praktisk) vs. rootless/sudo docker.
2. Rydde: `docker image prune` / fjerne ubrukte aegir-lag (etter bekreftelse).
3. Hold containers unexposed (`127.0.0.1` bind) når de kjøres.

## Done-kriterium

Dokumentert aksept **eller** endret tilgangsmodell; image-rydd logget i remediation.
