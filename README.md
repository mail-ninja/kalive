# kalived

Lokalt kodemiljø og personlig host-SOC på samme laptop. Ett UI. Bare loopback.

**Arbeid** er rommet du sitter i: samtale som leser og patcher filer på disk, tre og Monaco, preview av det som ble bygget, PTY når du selv skal taste. Agenten jobber i workspace. Nøklene dine. Ingen sky-IDE.

**Hiroshima** svarer på det andre spørsmålet: *er denne maskinen allerede kompromittert?* Burst-scan og valgfri rullende egress-watch. CLEAN / WARN / ALERT / ERROR. Sensorene eier sannheten. Modellene porterer og forklarer. Du Confirm-er isolate og kill.

Dette er ikke Huntress, ikke SIEM, ikke LAN-skanner og ikke sky-EDR. Alt lytter på `127.0.0.1`.

```
┌─────────────────────────────────────────────────────────────┐
│  Arbeid                              │  Hiroshima (skuff)   │
│  cli · tre · Monaco · preview · PTY  │  verdict · ring      │
│  build-agent mot workspace           │  Confirm-playbooks   │
└─────────────────────────────────────────────────────────────┘
         Vite :5173  →  FastAPI :8788  →  kalived-ctl (root)
```

---

## Ambisjon

Lista er bevisst høy.

1. **Et kodemiljø det er verdt å sitte i.** Grok Build-følelse uten å sende repoet til en sky-IDE. Du skriver hva som skal skje. Orchestratoren planlegger, leser, viser diff, kjører test, oppdaterer preview, stopper. Samme vindu. Dine nøkler. Din disk.
2. **En vert så nær innsynsfri som en laptop kan være.** Trackere på *verten*, keyloggere, rootkits, malware, bakdører. Finn dem. Fjern dem. Late ikke som EDR-i-skyen.

Det er destinasjonen. v1 er ærlig om taket og om avstanden dit.

**Arbeid i dag:** loopen virker. Klikk-telleren (`docs/_probe.html`) og minne-statuslinjen er kjørt gjennom den: les → patch → `repo_bash` → HTML-preview. Det er fortsatt et stykke unna UFO-editoren — tre flater som føles som *ett* sted å sitte, preview som følger en lokal app, cli som planlegger og stopper rent.

**Hiroshima i dag:** burst-scan, Falco 8 s, scoped AIDE-freeze, opt-in 5-min egress-watch. Den *ser*. Den rydder ikke alene.

v1-taket:

- Nettleser-cookies og HTTPS-trackere eies av nettleseren og uBlock. Watch ser familie og port, ikke cookie-jar.
- Et skjult LKM som lyver i `/proc` krever uavhengig evidens (AIDE, taint, Falco).
- Firmware ligger utenfor v1.
- Telefon som gateway er operasjonell risiko på *nettet*. Det er `tether` / `env_shift`, ikke automatisk innbrudd på PC-en.

ALERT krever to uavhengige evidens-domener **eller** én hard artefakt (memfd/deleted + nett, fake kworker, `ld.so.preload`, extra UID 0, nmap≠ss bekreftet av tshark).

Baseline-filer under `baselines/machine/` er merkelapper for forventet støy, ikke attest på rent host. Alt mistenkelig skal synes og kunne fjernes.

Leserekkefølge: denne fila → [docs/NOW.md](docs/NOW.md) → [docs/HIROSHIMA.md](docs/HIROSHIMA.md). Neste bygg: [docs/NEXT.md](docs/NEXT.md).

---

## Hvor koden er (2026-10)

| Flate | I treet |
|-------|---------|
| Arbeid | Agentkonsoll (`build`), mappetre, Monaco på disk, `repo_*` + `repo_bash`, HTML-preview, PTY-skuff, MiniLM + Jev-gate |
| Hiroshima H0–H5 | Scan, digest-port, ring + Kuzu-graf, miljøklasse, Confirm-playbooks, 5-min egress-watch, Falco host-burst |
| Settings | Maskin (`config.toml`) og nøkler (`env` 0600) |
| H6 Suricata | Valgfri, ikke påbegynt |
| Port C | Sandbox-VM, tale, mobil — destinasjon |

---

## Stack

| Lag | Hva |
|-----|-----|
| UI | Svelte 5 + Vite `127.0.0.1:5173` |
| API | FastAPI / uvicorn `127.0.0.1:8788`, én WebSocket |
| Eldre SOC-API | stdlib `:8787` (`sudo kalived-ctl api`) — urørt |
| Chat | SpaceXAI / xAI, default `grok-4.6` |
| Port | TypeSafe **Jev** (Vercel AI Gateway) → Inception **Mercury-2.5** på candidate → rules |
| Embeddings | lokal MiniLM 384-d |
| Minne | Kuzu, Qdrant, SQLite, MinIO, Redis — namespace per `agent_id` |
| Sensorer | AIDE, auditd-connect, UFW over nft, rkhunter, chkrootkit, nmap lo, tshark lo-burst, hunt-procs, Falco host-burst |
| Watch | `ss` ESTAB + `ausearch -k kalived_connect` → felter i `~/.config/kalived/hiroshima/` 0600 |
| Root | `/usr/sbin/kalived-ctl` → `/usr/local/lib/kalived` (`root:root`) |

Ingen LangChain. Ingen Semantic Kernel. Orkestrering = FastAPI + tools + `decide()`.

---

## Tre trær

| Tre | Sti | Rolle |
|-----|-----|--------|
| Git / data | workspace (`~/kalived` som default) | kode, `logs/status/`, findings |
| Secrets | `~/.config/kalived/` | `config.toml`, `env`, `api.token`, `env_class.toml`, minne, watch — **ikke git**, 0600/0700 |
| Root-runtime | `/usr/local/lib/kalived` + `/usr/sbin/kalived-ctl` | det timer og NOPASSWD kjører |

Live scan må være root. NOPASSWD mot home-scripts er en bakdør. NOPASSWD er bare `kalived-ctl`-verb. Helper oppdateres med passord:

```bash
sudo bash playbooks/install-kalived-helper.sh
sudo bash playbooks/install-nopasswd-ctl.sh   # nye ctl-verb
sudo bash playbooks/aide-init.sh --force      # scoped: kalived-filer, ikke VPN-snap
sudo kalived-ctl scan
```

`HELPER-STALE` betyr at helper ligger bak git. Ikke innbrudd.

---

## Start

Cockpit (Vite + API; minne-compose hvis Docker kjører):

```bash
cd ~/kalived && bash cockpit/scripts/up.sh
# UI  http://127.0.0.1:5173
# API http://127.0.0.1:8788/v1/health
```

Minne-docker (Qdrant / Redis / MinIO, loopback) — sqlite og Kuzu lever uten:

```bash
sudo systemctl start docker.socket docker.service
docker compose -f cockpit/memory/compose.yml up -d
```

Daglig SOC:

```bash
sudo kalived-ctl scan
```

Exit: `0` CLEAN · `1` WARN · `2` ALERT · `3` ERROR. Sannheten er `echo $?` og `logs/status/<stamp>/verdict.json`. `protocol.json` forklarer; den overskriver ikke.

Watch (opt-in):

```bash
sudo bash playbooks/install-watch-timer.sh
sudo kalived-ctl watch
```

Eldre SOC-GUI: `sudo kalived-ctl api` → `http://127.0.0.1:8787`.

`kalived-ctl`: `scan` `api` `defs` `token-fix` `aide-init` `rkhunter-setup` `isolate-dst` `isolate-undo` `kill-pid` `watch` `uplink-burst` `falco-burst` `watch-timer-on/off` `scan-timer-on/off`. Ingen ekstra argv.

---

## De to rommene

| Rom | Hvor | Hva |
|-----|------|-----|
| **Arbeid** | `:5173` | `build`-loop: konsoll, tre, Monaco, iframe, `repo_bash`, PTY |
| **Hiroshima** | skuff | `verdict.json` + `protocol.json` + ring + watch. Scan/watch/isolate bak Confirm |
| **Settings** | fanen | Maskin → `config.toml`. Nøkler → `env` 0600. UI får aldri full nøkkel tilbake |

Agenter husker på `agent_id`. `build` eier repo-loopen. `signal` forklarer SOC.

**Minne, én runde:** MiniLM henter → Jev (ellers Mercury, ellers rules) velger `keep`/`act` → Grok svarer → samme `decide()` merker engramet. [docs/MEMORY.md](docs/MEMORY.md), [docs/JEV.md](docs/JEV.md).

**Hiroshima-protokoll:** sensorer → siler + miljøklasse → digest → Jev (`noise` \| `env_shift` \| `candidate` \| `alert_family`) → Mercury bare på candidate/alert → `signal` forklarer → ctl etter Confirm. Payload, pcap, full URL, SNI og journal går ikke til skyen.

Miljøklasse (`home` / `travel` / `tether`) settes av overlay og heuristikk, ikke av signal-agenten. Telefon-hotspot er `tether`. Nytt hotell-SSID er `travel`. Begge blir `env_shift` i porten.

---

## Scan og watch

Scan (oneshot): collect → persistens → tshark lo + nmap localhost + rkhunter/chkrootkit + `/proc` + Falco-burst → baselines → `verdict.json`. Fire siler. INFO hever ikke. Scanner ikke LAN og ikke telefonen.

Watch (rullende): `connect()`-audit + `ss` ESTAB. Vindu: exe, dest-familie, port, n, `unmapped`. Aldri IP/SNI/cmd. python/shell mot unknown = `alert_family`. Isolate bruker dest-IP fra siste **scan**-snapshot.

Falco: host-regler i `defs/falco-host.yaml` (ikke stock). `engine.kind=modern_ebpf`. Burst ~8 s. Tom jsonl = ingen finding. Falco alene = WARN/candidate. Falco + FIM eller Falco + nett = ALERT. Dual leser høyeste severity per funn-id. Pakke mangler = INFO, scan hever ikke. Ingen always-on unit.

WARN er hygiene (AIDE etter egen install, gammel lsmod-freeze, kjent chkrootkit-støy, VPN-snap). ALERT er noe å løse.

---

## Secrets og modeller

`~/.config/kalived/env` — `XAI_API_KEY`, `INCEPTION_API_KEY`, `AI_GATEWAY_API_KEY` (Jev), `HF_TOKEN`. Git-token er git, ikke chat. Aldri i repoet.

Passord skrives i **xterm**. `sudo -S` og `echo pw | sudo` er forbudt i tools.

---

## Tester

```bash
./scripts/tests/run.sh
python3 scripts/tests/protocol_h1.py
python3 scripts/tests/protocol_h3.py
python3 scripts/tests/protocol_h4.py
cockpit/backend/.venv/bin/python3 scripts/tests/protocol_h2.py
python3 scripts/tests/protocol_h5.py
```

Paste-tester: [docs/CHAT-TESTS.md](docs/CHAT-TESTS.md). `logs/` er ikke i git.

---

## Docs

| Fil | |
|-----|--|
| [docs/README.md](docs/README.md) | kart |
| [docs/NOW.md](docs/NOW.md) | hvor vi er |
| [docs/NEXT.md](docs/NEXT.md) | neste bygg (Arbeid-editor, valgfri H6) |
| [docs/HIROSHIMA.md](docs/HIROSHIMA.md) | SOC-protokoll H0–H6 |
| [docs/SURFACE.md](docs/SURFACE.md) | scan-kontrakt, CLI, findings |
| [docs/COCKPIT.md](docs/COCKPIT.md) | `:5173` / `:8788` |
| [docs/MEMORY.md](docs/MEMORY.md) · [docs/JEV.md](docs/JEV.md) | minne-gate |
| [docs/CHAT-TESTS.md](docs/CHAT-TESTS.md) | paste-tester |

---

## Mappeguide

| Path | Hva |
|------|-----|
| `cockpit/` | Svelte 5 + FastAPI |
| `scripts/kalived-scan.sh` | SOC-orkestrator |
| `scripts/kalived-watch.sh` | egress-sample |
| `scripts/kalived-falco.sh` | host-burst |
| `scripts/lib/check-*.sh` | detektorer |
| `prompts/playbooks/` | signal / build / forge / … |
| `playbooks/` | muterende install (gate: ikke ALERT) |
| `baselines/` | kjent-godt — merkelapp, ikke rent-host |
| `defs/` | allowlists, IOC, Falco-yaml |
| `api/` | eldre `:8787` |

---

## Hva vi ikke bygger oppå dette

- Ett tre der alt kjører som vanlige bruker uten root
- NOPASSWD på workspace-scripts
- GUI som reparser `ss` i stedet for `verdict.json`
- Auto-kille / auto-ban / LLM-sudo
- Full prosessliste, pcap eller journal til skyen
- LangChain / Semantic Kernel / Theia
- Tredje FastAPI «for Hiroshima»
- CrowdSec, Wazuh, Zeek, fail2ban mens SSH er masked
- Always-on `tshark -i any`
- 0.0.0.0-lyttere
- Love 100 % tracker- og rootkit-fri

Apache-2.0. Se [LICENSE](LICENSE).
