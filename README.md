# kalived

Lokalt kodemiljø og personlig host-SOC på én Kali-laptop (`void@kali`). To rom, samme UI, bare loopback.

**Arbeid** er en Grok Build-aktig cockpit: tre, Monaco, preview, agentkonsoll og PTY. Agenten leser og patcher filer på disk.

**Hiroshima** svarer på: *er denne maskinen allerede kompromittert?* Burst-scan + rullende egress-watch. CLEAN / WARN / ALERT / ERROR. Sensorene eier sannheten; modellene porterer og forklarer; du Confirm-er isolate/kill.

Dette er **ikke** Huntress, SIEM, LAN-skanner eller sky-EDR. Alt lytter på `127.0.0.1`.

Repo: [github.com/mail-ninja/kalive](https://github.com/mail-ninja/kalive) (`git remote kalive`). `origin` er et eldre `wallE`-tre — ikke bland.

---

## Mål og ambisjon

UFO-listen er bevisst høy:

1. Et kodemiljø det er verdt å sitte i — samtale som *gjør* jobben, kode og preview som henger sammen, lokalt, dine nøkler.
2. En vert så nær innsynsfri som en laptop kan være: trackere på *verten*, keyloggere, rootkits, malware, bakdører. Finn og fjern. Ikke late som EDR-i-skyen.

Ærlig tak (v1):

- Nettleser-cookies og HTTPS-trackere eies av Brave/uBO. Watch ser familie/port, ikke cookie-jar.
- Skjult LKM som lyver i `/proc` krever uavhengig evidens (AIDE, taint, senere Falco).
- Firmware ligger utenfor v1.
- Telefon som gateway (SSID **Gal**, F-010) er operasjonell risiko på *nettet*, ikke automatisk innbrudd på PC-en.

Denne Kali-en er **forsøkskanin**. Prosjektet startet fordi operator mistenkte kluss. `baselines/machine/` og `outbound_proc.allow` er merkelapper for forventet støy, ikke bevis for rent host. Alt mistenkelig skal synes og kunne fjernes.

ALERT krever to uavhengige evidens-domener **eller** én hard artefakt (memfd/deleted + nett, fake kworker, `ld.so.preload`, extra UID 0, nmap≠ss bekreftet av tshark).

---

## Hvor vi er (2026-10-01)

| Flate | Status |
|-------|--------|
| Arbeid Port A | I treet: agentkonsoll, mappetre, Monaco på disk, minne-gate |
| Arbeid Port B | I treet: `repo_bash`, HTML auto-preview |
| Hiroshima H0–H4 | I treet **og** på verten: scan, Jev-port, ring/graf, env-overlay, Confirm-playbooks, 5-min egress-watch |
| Settings | Maskin (`config.toml`) + Nøkler (`env` 0600) |
| H5 Falco | I treet: host-burst `kalived-ctl falco-burst`, custom yaml, gated playbook. Live pakke venter på apt. |
| H6 Suricata | Valgfri etter H4/H5 |
| Port C | VM / tale / mobil — destinasjon, ikke neste |

Live scan `2026-09-30_093742`: WARN (AIDE sudoers-drop-in, lsmod vs gammel freeze, chkrootkit-støy på Chromium `/tmp`). Gal = `tether` / `env_shift`. Watch-timer enabled, `audit=ok`, vindu `void:void` 0600.

Detaljert «nå»: [docs/NOW.md](docs/NOW.md). Protokoll: [docs/HIROSHIMA.md](docs/HIROSHIMA.md).

---

## Stack

| Lag | Hva |
|-----|-----|
| UI | Svelte 5 + Vite `127.0.0.1:5173` |
| API | FastAPI / uvicorn `127.0.0.1:8788`, én WebSocket |
| Gammel SOC-API | stdlib `:8787` (`sudo kalived-ctl api`) — urørt, ikke strangled |
| Chat | SpaceXAI / xAI `grok-4.6` (default) |
| Port / salience | TypeSafe **Jev** via Vercel AI Gateway → Inception **Mercury-2.5** på candidate → rules |
| Embeddings | lokal MiniLM 384-d (norsk+engelsk), ikke sky |
| Minne | Kuzu, Qdrant, SQLite, MinIO, Redis — namespace `agent_id` |
| Sensorer | AIDE, auditd-connect, UFW over nft, rkhunter, chkrootkit, nmap lo, tshark lo-burst, hunt-procs, Falco host-burst |
| Watch | `ss` ESTAB + `ausearch -k kalived_connect`, felter i `~/.config/kalived/hiroshima/` 0600 |
| Root | `/usr/sbin/kalived-ctl` → `/usr/local/lib/kalived` `root:root` |

Ingen LangChain. Ingen Semantic Kernel. Orkestrering = FastAPI + tools + `decide()`.

---

## Tre trær (ikke bland)

| Tre | Sti | Rolle |
|-----|-----|--------|
| **Git / data** | `~/kalived` | kode, `logs/status/`, findings |
| **Secrets** | `~/.config/kalived/` | `config.toml`, `env`, `api.token`, `env_class.toml`, minne, watch-vindu — **ikke git**, 0600/0700 |
| **Root-runtime** | `/usr/local/lib/kalived` + `/usr/sbin/kalived-ctl` | det timer og NOPASSWD kjører |

Live scan **må** være root. NOPASSWD mot home-scripts er en bakdør. NOPASSWD er bare `kalived-ctl`-verb. Oppdatering av helper krever passord:

```bash
sudo bash playbooks/install-kalived-helper.sh
sudo bash playbooks/install-nopasswd-ctl.sh   # nye ctl-verb
sudo bash playbooks/aide-init.sh --force      # scoped: kalived-filer, ikke Proton; nektes ved ALERT
sudo kalived-ctl scan
```

`HELPER-STALE` = helper bak git. Ikke innbrudd.

---

## Slik du fyrer det opp

Cockpit:

```bash
cd ~/kalived && bash cockpit/scripts/up.sh
# UI  http://127.0.0.1:5173
# API http://127.0.0.1:8788/v1/health
```

Minne-docker (qdrant/redis/minio, loopback) — valgfritt; sqlite/kuzu lever uten:

```bash
sudo systemctl start docker.socket docker.service
docker compose -f cockpit/memory/compose.yml up -d
```

Daglig SOC:

```bash
sudo kalived-ctl scan
```

Watch (opt-in, Settings eller):

```bash
sudo bash playbooks/install-watch-timer.sh    # 5 min
sudo kalived-ctl watch                        # én sample nå
```

Gammel SOC-GUI:

```bash
sudo kalived-ctl api    # http://127.0.0.1:8787
```

Exit scan: `0` CLEAN · `1` WARN · `2` ALERT · `3` ERROR. Sannheten er `echo $?` og `logs/status/<stamp>/verdict.json`. `protocol.json` forklarer; den overskriver ikke.

`kalived-ctl`: `scan` `api` `defs` `token-fix` `aide-init` `rkhunter-setup` `isolate-dst` `isolate-undo` `kill-pid` `watch` `uplink-burst` `watch-timer-on/off` `scan-timer-on/off`.

---

## De to rommene

| Rom | Hvor | Hva |
|-----|------|-----|
| **Arbeid** | `:5173` | `build`-loop: konsoll, tre, Monaco, iframe, `repo_bash`, PTY |
| **Hiroshima** | rosa skuff | `verdict.json` + `protocol.json` + ring + watch. Scan/watch/isolate bak Confirm. Trenger ikke `:8787`. |
| **Settings** | fanen | **Maskin** → `config.toml` (watch-timer, skip_rootkit, …). **Nøkler** → `env` 0600. UI får aldri full nøkkel tilbake. |

Agenter husker på **`agent_id`**. `build` eier repo-loopen. `signal` forklarer SOC. Isolasjon = namespace.

**Minne, én runde:** MiniLM henter → **Jev** (ellers Mercury, ellers rules) velger `keep`/`act` → Grok svarer → **samme `decide()`** merker engramet. [docs/MEMORY.md](docs/MEMORY.md), [docs/JEV.md](docs/JEV.md).

**Hiroshima-protokoll:** sensorer → siler + miljøklasse → digest → Jev (`noise` \| `env_shift` \| `candidate` \| `alert_family`) → Mercury bare på candidate/alert → `signal` forklarer → ctl etter Confirm. Payload, pcap, full URL, SNI og journal går ikke til skyen.

Gal (telefon-hotspot) er `tether`. Det er `env_shift`, ikke ALERT.

---

## Hva scannen og watch gjør

Scan (oneshot): collect → persistens → tshark lo + nmap localhost + rkhunter/chkrootkit + `/proc` → baselines → `verdict.json`. Fire siler. INFO hever ikke verdict. Scanner **ikke** LAN, **ikke** telefonen.

Watch (rullende): `connect()`-audit + `ss` ESTAB. Vindu: exe, dst-familie, port, n, `unmapped`. Aldri IP/SNI/cmd. python/shell mot unknown = `alert_family`. Isolate bruker fortsatt dest-IP fra siste **scan**-snapshot.

WARN = hygiene (AIDE etter egen install, stale lsmod-freeze, kjent chkrootkit-støy). ALERT = noe å løse, ikke whitelist uten evidens i snapshotet.

---

## Secrets og modeller

`~/.config/kalived/env` — `XAI_API_KEY` (SpaceXAI / `api.x.ai`, default `grok-4.6`), `INCEPTION_API_KEY`, `AI_GATEWAY_API_KEY` (Jev), `HF_TOKEN`. Git-token er git, ikke chat. Aldri i repoet.

Passord skrives i **xterm**. `sudo -S` og `echo pw | sudo` er forbudt i tools.

---

## Tester

```bash
./scripts/tests/run.sh
python3 scripts/tests/protocol_h1.py
python3 scripts/tests/protocol_h3.py
python3 scripts/tests/protocol_h4.py
cockpit/backend/.venv/bin/python3 scripts/tests/protocol_h2.py
```

Paste-tester: [docs/CHAT-TESTS.md](docs/CHAT-TESTS.md). `logs/` er ikke i git.

---

## Docs

| Fil | |
|-----|--|
| [docs/README.md](docs/README.md) | kart over docs |
| [docs/NOW.md](docs/NOW.md) | hvor vi er |
| [docs/HIROSHIMA.md](docs/HIROSHIMA.md) | SOC-protokoll H0–H6 |
| [docs/NEXT.md](docs/NEXT.md) | neste bygg (H5, Arbeid-flater) |
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
| `scripts/kalived-watch.sh` | H4 egress-sample |
| `scripts/lib/check-*.sh` | detektorer |
| `prompts/playbooks/` | signal / build / forge / … |
| `playbooks/` | muterende install (gate: ikke ALERT) |
| `baselines/` | kjent-godt — mistenkt på denne verten |
| `defs/` | allowlists + IOC |
| `api/` | gammel `:8787` |

---

## Hva vi ikke bygger oppå dette

- Ett tre der alt kjører som void uten root
- NOPASSWD på `~/kalived/scripts`
- GUI som reparser `ss` i stedet for `verdict.json`
- Auto-kille / auto-ban / LLM-sudo
- Full prosessliste, pcap eller journal til skyen
- LangChain / Semantic Kernel / Theia
- Tredje FastAPI «for Hiroshima»
- CrowdSec, Wazuh, Zeek, fail2ban mens SSH er masked
- Always-on `tshark -i any`
- 0.0.0.0-lyttere
- Love 100 % tracker-/rootkit-fri
