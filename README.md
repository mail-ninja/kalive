# kalived

To rom på én Kali-workstation (`void@kali`).

**Arbeid** skal bli et kodemiljø som faktisk er verdt å sitte i: tydelig kode, filtre, preview av det du bygger, og en samtale med en orchestrator som *gjør* jobben — i ånden av Grok Build / Claude Code, men lokalt, loopback, dine nøkler.

**Hiroshima** er host-SOC: *er maskinen allerede kompromittert?* CLEAN / WARN / ALERT / ERROR. I dag et ærlig burst-system (ss, nmap localhost, tshark lo, rkhunter, AIDE, auditd, `/proc`). I morgen personlig antimalware og lokal sikkerhet som vokser uten å bli EDR-i-skyen.

Dette er **ikke** Huntress, ikke et SIEM, ikke en LAN-skanner, ikke GitHub Pages. Alt lytter på `127.0.0.1`.

Repo: [github.com/mail-ninja/kalive](https://github.com/mail-ninja/kalive) (`git remote kalive`). `origin` peker fortsatt på et eldre `wallE`-tre — ikke bland.

Les mer: [docs/README.md](docs/README.md). Neste bygg (forslag, ikke startet): [docs/NEXT.md](docs/NEXT.md). Operator-kontrakt for scan/API: [docs/SURFACE.md](docs/SURFACE.md).

---

## Slik du fyrer det opp

Cockpit (det du ser):

```bash
bash cockpit/scripts/dev.sh
# UI  http://127.0.0.1:5173
# API http://127.0.0.1:8788/v1/health
```

Minne-docker (qdrant/redis/minio, loopback) — valgfritt, cockpit starter uten:

```bash
sudo systemctl start docker.socket docker.service   # stop-idle kan ha slått den av
docker compose -f cockpit/memory/compose.yml up -d
```

Daglig SOC:

```bash
sudo kalived-ctl scan          # NOPASSWD. Helper/AIDE-init er *ikke* oppvarming.
./scripts/kalived-advise.sh    # råd på siste ekte sudo-scan
```

Gammel SOC-GUI (stdlib, urørt, ikke strangled):

```bash
sudo kalived-ctl api           # http://127.0.0.1:8787
```

Exit scan: `0` CLEAN · `1` WARN · `2` ALERT · `3` ERROR. Sannheten er `echo $?`.

---

## De to rommene (nå)

| Rom | Hvor | Hva det er i dag |
|-----|------|------------------|
| **Arbeid** | `:5173` fanen Arbeid | Chat + kodeteam (`crew` / `forge` / `review` / `term`) + canvas **Monaco** eller **iframe** (`iframe_write`, knapp *spill*) + cockpit-PTY |
| **Hiroshima** | rosa skuff, samme UI | Siste `verdict.json` fra disk, scan via `sudo -n kalived-ctl` (oneshot-jobb), egen PTY. Trenger **ikke** `:8787`. |
| **Settings** | fanen | Skriv nøkler til `~/.config/kalived/env` (0600). UI får aldri full nøkkel tilbake. |

Agenter husker på **`agent_id`**, ikke på provider. Bytt Grok → Mercury: samme graf/episoder. Fem lag: Kuzu, Qdrant, SQLite, MinIO, Redis. Isolasjon = namespace. Ingen LangChain. Ingen Semantic Kernel. Orkestrering = FastAPI + én WebSocket.

`:8787` er den gamle kalived-API (scan/playbooks/root-PTY). Vi wrapper den ikke. Hiroshima på `:8788` leser snapshot og kaller `kalived-ctl`.

---

## Tre trær (ikke bland)

| Tre | Sti | Rolle |
|-----|-----|--------|
| **Git / data** | `~/kalived` | kode, `logs/status/`, findings, reports |
| **Secrets** | `~/.config/kalived/` | `config.toml`, `env`, `api.token`, `memory/<agent_id>/` — **ikke git** |
| **Root-runtime** | `/usr/local/lib/kalived` + `/usr/sbin/kalived-ctl` | det timeren og NOPASSWD kjører. `root:root` |

Live scan **må** være root. NOPASSWD mot home-scripts er en bakdør. `kalived-ctl` er den tynne dispatcher-en (`scan`, `api`, `defs`, `token-fix`).

Etter du **faktisk** endrer scan-kode (ikke daglig ritual):

```bash
sudo bash playbooks/install-kalived-helper.sh
sudo bash playbooks/aide-init.sh --force    # nektes hvis siste scan er ALERT
sudo kalived-ctl scan
```

`HELPER-STALE` = helper bak git. Ikke innbrudd. `--force` hopper ikke over ALERT-gate.

---

## Hva scannen faktisk gjør

1. Collect — porter, UFW/nft, docker, sysctl, suid
2. Persistens — cron, systemd, preload, keys, udev, deleted exe
3. Parallelt: tshark lo-burst + localhost-nmap + rkhunter + hunt-procs. Join: SYN-ACK × nmap-open × ss
4. Sjekker mot baselines → `verdict.json` + norsk banner
5. Første `/proc`−ps-diff er **kandidater**, ikke implantat (fire siler)

Scanner **ikke** LAN, **ikke** telefonen som default, **ikke** egress-deny. INFO hever ikke verdict.

WARN = hygiene. ALERT = noe å løse, ikke whitelist uten evidens i snapshotet.

---

## Hvor vi vil (kort)

Arbeid: tre flater som henger sammen — **kode** (filtre + Monaco, VS Code-følelse uten Theia), **preview** (iframe som viser det du bygger, ikke en tom ramme), **cli** (der planlegging og samtale med orchestratoren skjer, som denne Grok Build-sesjonen). Forslag: [docs/NEXT.md](docs/NEXT.md).

Hiroshima: fra burst-SOC til personlig lokal sikkerhet som faktisk holder — antimalware, persistens, støy vs. funn — uten å sende livet ditt til noens sky. Den er *grei* nå. Den skal bli umulig å ignorere, ikke umulig å forstå.

---

## Mappeguide

| Path | Hva |
|------|-----|
| `cockpit/` | Svelte 5 + FastAPI. [docs/COCKPIT.md](docs/COCKPIT.md) |
| `scripts/kalived-scan.sh` | SOC-orkestrator |
| `scripts/lib/check-*.sh` | detektorer |
| `scripts/kalived-advise.py` | 8787-advisor (`thread.json` per playbook) |
| `prompts/playbooks/` | signal (SOC), forge/review/term/crew (kode), advisor.md (ops) |
| `playbooks/` | muterende install (gate: ikke ALERT) |
| `baselines/` | kjent-godt |
| `findings/` | saker, ikke raw dumps |
| `defs/` | allowlists + IOC + feeds |
| `docs/` | denne historien + kontrakt + neste steg |
| `api/` | gammel `:8787` (urørt stdlib) |

---

## Secrets og modeller

`~/.config/kalived/env` — `XAI_API_KEY` (SpaceXAI / `api.x.ai`, default `grok-4.6`), `INCEPTION_API_KEY`, `HF_TOKEN` (Inference Providers, ikke «alt på Hugging Face»), git-token er **git** ikke chat. Aldri i repoet.

Passord skrives i **xterm**, aldri i chat. `sudo -S` og `echo pw | sudo` er forbudt i tools.

---

## Tester

```bash
./scripts/tests/run.sh
./scripts/tests/api-e2e.sh
```

`logs/` og `reports/*_scan.md` er ikke i git.

---

## Hva vi ikke bygger oppå dette

- Ett tre der alt kjører som void uten root
- NOPASSWD på `~/kalived/scripts`
- GUI som reparser `ss` i stedet for `verdict.json`
- Auto-kille / `ufw disable` / `aide-init --force` etter ALERT
- Full prosessliste til skyen
- LangChain eller Semantic Kernel som «ekte» orkester
- Theia som skall
- Tredje FastAPI «for Hiroshima»
- 0.0.0.0-lyttere
