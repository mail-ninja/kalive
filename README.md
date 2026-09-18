# kalived

Lokalt **host-sikkerhetssystem** for én Kali-workstation (`void@kali`). Målet er å svare: *er maskinen allerede kompromittert?* — med et tydelig **CLEAN / WARN / ALERT / ERROR**, ikke en haug `ss`-dumper du må tolke selv.

Dette er **ikke** et SIEM, ikke Huntress/EDR, og ikke en LAN-skanner. Det er et burst-innsamlingssystem: korte kjøringer av `ss`, nmap (localhost), rkhunter, AIDE, auditd, **ps/`/proc`/pstree/lsof**, så en SpaceXAI-advisor som syr **redacted** funn sammen.

Repo: [github.com/mail-ninja/wallE](https://github.com/mail-ninja/wallE)

---

## Slik du bruker det (daglig)

```bash
sudo kalived-ctl scan          # daglig (NOPASSWD). Helper/AIDE-init er *ikke* oppvarming.
./scripts/kalived-advise.sh    # råd på siste *ekte* sudo-scan (trenger ikke root)
sudo kalived-ctl api           # loopback API + GUI http://127.0.0.1:8787
./scripts/tests/run.sh         # fixture-tester, ingen sudo
```

Exit: `0` CLEAN · `1` WARN · `2` ALERT · `3` ERROR. Sannheten er `echo $?`, ikke snapshot-lista.

WARN = hygiene (helper gammel, AIDE etter *vår* filendring). ALERT = noe å løse, ikke whitelist uten evidens.

---

## Arkitektur (ikke bland trærne)

| Tre | Sti | Rolle |
|-----|-----|--------|
| **Git / data** | `~/kalived` | kode du redigerer, `logs/status/`, `findings/`, reports |
| **Secrets** | `~/.config/kalived/` | `config.toml`, `env` (`XAI_API_KEY`), `api.token` — **ikke git** |
| **Root-runtime** | `/usr/local/lib/kalived` + `/usr/sbin/kalived-ctl` | det timeren og NOPASSWD kjører. `root:root` |

Live scan **må** være root (AIDE, UFW, `lsof`, `/dev/input`). NOPASSWD mot `~/kalived/scripts` er en bakdør. `kalived-ctl` er den tynne, låste dispatcher-en (`scan`, `api`, `defs`, `token-fix`).

Etter du **faktisk** endrer kode (ikke daglig ritual):

```bash
sudo bash playbooks/install-kalived-helper.sh   # trenger passord
sudo bash playbooks/aide-init.sh --force        # nektes hvis siste scan er ALERT
sudo kalived-ctl scan
```

`--force` re-baseliner FIM etter kjent endring. Det hopper **ikke** over ALERT-gate; `--force-alert` er nødventil. `HELPER-STALE` = helper bak git-treet. Ikke innbrudd.

---

## Hva scannen faktisk gjør

1. **Collect** — porter, UFW/nft, docker, sysctl, suid, …
2. **Persistens** — cron, systemd, preload, keys, udev, deleted exe
3. **Parallelt:** **tshark lo-burst** + localhost-**nmap** (`127.0.0.1`, `-sV` hoppes på kjente lo-porter) + **rkhunter** + **hunt-procs**. Join: SYN-ACK × nmap-open × ss. UFW: policy i `check-firewall`; 24t-pakker som `ufw_digest.json` (ikke rå journal).
4. **Sjekker** mot baselines → `verdict.json` + norsk banner
5. **Advisor** (hvis `ai_enabled`, TTY) — SpaceXAI, redacted kontekst

Den scanner **ikke** LAN, **ikke** telefonen (ADB-playbooks er egne), **ikke** egress-deny.

---

## Mappeguide

| Path | Hva |
|------|-----|
| `scripts/kalived-scan.sh` | orkestrator |
| `scripts/hunt-*.sh` | innsamlere |
| `scripts/lib/check-*.sh` | detektorer (ALERT/WARN) |
| `scripts/kalived-advise.py` | advisor |
| `scripts/testdata/cases/` | fixture-tester |
| `playbooks/` | muterende install (gate: ikke ALERT, unntatt `--force`) |
| `baselines/` | kjent-god (porter, suid, lsmod, AIDE checksum) |
| `findings/F-00x_*.md` | **saker** (open/fixed/accepted) — ikke raw dumps |
| `logs/status/<stamp>/` | evidens per runde (gitignored) |
| `defs/` | allowlists + IOC + feeds (`kalived-ctl defs`) |
| `config/kalived.toml.example` | mal for `~/.config/kalived/config.toml` |
| `docs/SURFACE.md` | flagg, finding-IDs, API-ruter |
| `prompts/advisor.md` | default personlighet (løs prat) |
| `prompts/playbooks/signal.md` | SOC-dom (sil 4). `advise --playbook signal` |
| `cockpit/` | Svelte-cockpit + FastAPI (agenter). Plan: `cockpit/PLAN.md`. SOC-GUI = skuffen Hiroshima. |

---

## Config og API

`~/.config/kalived/config.toml` — samme nøkler i CLI og `GET`/`PUT /v1/config`. Nye funksjoner **skal** ha nøkkel her.

Eksempler: `nmap_localhost`, `proc_inventory`, `proc_hidden_check`, `proc_ioc_check`, `helper_stale_check`, `ai_enabled`, `listen_bind` (kun loopback).

API: `sudo kalived-ctl api` → `http://127.0.0.1:8787`. Token: `~/.config/kalived/api.token`. OpenAPI: `api/openapi.yaml`. Muterende POST krever at API-prosessen er root.

Advisor-nøkkel: `~/.config/kalived/env` (`XAI_API_KEY`). Aldri i git. Advisor får **ikke** sudo og **ikke** full `ps`/`ss`/nmap `-oN`.

---

## Hva du *ikke* bør planlegge oppå dette

- Ett Linux-bruker-tre der alt kjører som void uten root
- NOPASSWD på home-script
- GUI som reparser `ss` i stedet for `verdict.json`
- Auto-kille prosesser / auto-`ufw disable`
- Huntress som «cli-burst» (det er always-on EDR mot deres sky)
- Full prosessliste til skyen
- LAN-sweep som default nmap-mål

GUI = tynn HTML mot eksisterende API. tshark = senere, kort cap, egen config-nøkkel.

---

## Tester og git

```bash
./scripts/tests/run.sh
./scripts/tests/api-e2e.sh          # isolert
./scripts/tests/api-e2e.sh --live   # mot kjørende API
```

`logs/` og `reports/*_scan.md` er ikke i git. Push: `git push origin main` (repo `mail-ninja/wallE`).
