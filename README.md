# kalived — intern maskinsikkerhet (Kali)

Arbeidsmappe for **lokal/host-sikkerhet** på denne Kali-maskinen.
Hver runde dokumenteres her: status-snapshots, funn, skanninger, playbooks og remediations.
Fremtidige tester sammenlignes mot baselinen.

## Mappestruktur

| Mappe | Formål |
|-------|--------|
| `reports/` | Menneskelesbare tverrsnittsrapporter (baseline + periodiske) |
| `logs/status/` | Rå snapshots (ss, services, sysctl, docker, …) datert `YYYY-MM-DD_HHMM` |
| `logs/auth/` | Auth-/login-utdrag ved behov |
| `logs/ufw/` | UFW-status dumps (krever ofte sudo) |
| `scans/ports/` | Portkartlegginger over tid |
| `scans/services/` | Tjeneste-inventar |
| `scans/firewall/` | Brannmurregler / nft/iptables dumps |
| `baselines/` | «Kjent-god» tilstand for diff (porter, tjenester, sysctl) |
| `findings/` | Enkeltfunn (F-001, …) med status open/fixed/accepted |
| `inventory/` | Maskin-/nettverksinventar |
| `playbooks/` | Gjenbrukbare løsningsoppskrifter (hvordan fikse X) |
| `remediation/` | Logg over hva som ble gjort når (endringslogg) |
| `checklists/` | Rask sjekkliste for neste sec-runde |
| `scripts/` | Automatiserte samlere (non-destructive) |

## Arbeidsflyt (hver runde)

Live scan og baseline **kjøres alltid med sudo**:

```bash
sudo ./scripts/kalived-scan.sh
```

Banner + `verdict.json` (exit 0 CLEAN / 1 WARN / 2 ALERT / 3 ERROR).
Fixture-tester trenger ikke root: `./scripts/tests/run.sh`.

Fallback uten orkestrator: `sudo ./scripts/collect-baseline.sh` etter `checklists/phase0-fresh-snapshot.md`.

Rebuild-plan: `reports/2026-09-17_rebuild-design.md`. Fase 0-gate: `checklists/phase0-fresh-snapshot.md`.  
**Operatorflate (flagg, finding-IDs, playbooks, planlagte API-stier):** `docs/SURFACE.md`.  
**Runtime-config:** `sudo bash playbooks/install-config.sh` → `~/.config/kalived/config.toml` (mal: `config/kalived.toml.example`).  
**API:** `sudo ./scripts/kalived-api.sh` — `http://127.0.0.1:8787` token i `~/.config/kalived/api.token`.

## Begrensninger

- Noen kommandoer (`ufw status`, `iptables`, `aa-status`, `fail2ban-client`, `lsof /dev/input`) krever **sudo**.
- Ikke legg hemmeligheter (passord, private nøkler, PSK, API-nøkler) i denne mappen.

## Første baseline

Se `reports/2026-08-10_baseline-security.md` og `logs/status/2026-08-10_2305/`.
