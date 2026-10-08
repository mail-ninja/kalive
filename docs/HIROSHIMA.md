# Hiroshima-protokollen

H0–H5 er i treet og på verten. H6 er valgfri. Scan-sannhet er `logs/status/<stamp>/verdict.json`. Cockpit er klient. Produkt: [../README.md](../README.md).

Hiroshima er host-SOC på én laptop. Ikke SIEM, Huntress, LAN-scanner eller sky-EDR.

## Vedtak

1. **Miljøklasse auto-merkes.** Ny SSID / ny default-rute / ny DNS blir `env_shift` i skuffen. ALERT krever dual-source eller hard artefakt oppå det.
2. **Falco etter watch.** Auditd + huntere først. Én eBPF-sensor (Falco, container-regler av), burst ~8 s, ingen always-on unit.
3. **Baseline er merkelapp.** `outbound_proc.allow` er forventet comm-navn, ikke bevis for rent host. Alt mistenkelig skal synes og kunne fjernes.

## Protokoll

```
rå evidens (lokalt, privilegert via kalived-ctl)
    → deterministiske siler 1–4 + baseline + miljøklasse
        → kort digest (JSON, felter)
            → Jev porter (noise | env_shift | candidate | alert_family)
                → Mercury-2.5 bare på candidate / alert_family
                    → Grok / signal når Jev sier review
                        → kalived-ctl utfører, operator Confirm
```

Samme `decide()`-adapter som minnet. Andre spørsmål. Policy i kode. Modellen skriver aldri prompt, eier aldri `sudo`, ser aldri payload.

Jev er **porten**. Mercury er **kortlista**. `signal` **forklarer**. `build` patche *kalived-kode*. ctl kjører playbooks.

## Ærlig tak

- Nettleser-cookies og HTTPS-trackere eies av nettleser/uBO. tshark ser SNI, ikke cookie-jar.
- Skjult LKM som lyver i `/proc` krever uavhengig evidens (AIDE, taint, Falco).
- Firmware ligger utenfor v1.
- Telefon som gateway er operasjonell risiko. Klasse `tether` hever hygiene til `env_shift`. ALERT på PCen krever fortsatt dual-source eller hard artefakt.

ALERT-bar: **to uavhengige domener** (prosess · persistens · nett · dns · fim/rootkit · identitet · pcap) **eller** én hard artefakt (memfd/deleted + nett, fake kworker + userspace-exe, preload, extra UID 0, nmap≠ss bekreftet av tshark).

## Lag

### 0 — Sensorer (root via ctl)

AIDE, auditd-mini, UFW over nftables, tshark lo-burst (8 s, SYN-ACK, `-T fields`, aldri pcapng til advisor), rkhunter, chkrootkit, nmap-lo, hunt-procs, keylogscan, outbound-allow, ufw_digest, Falco host-burst, defs/IOC.

Always-on `tshark -i any` er forkastet. Suricata på aktiv uplink er H6, valgfri.

Watch (H4): `connect()` (auditd + `ss -tnp`), felter + pid, ringbuffer under `~/.config/kalived/hiroshima/` 0600.

### 1 — Siler og baseline

Sil 1–4. `baselines/machine/outbound_proc.allow`. Kjent VPN-DNS (Proton `10.2.0.1`) er unntak, ikke ALERT. Loopback-porter for cockpit/minne. DNS-familie. Miljøklasse.

Jev ser det som overlevde silene. TypeSafe: filtrer først. Jev teller ikke, parser ikke datoer.

### 2 — Digest

`scripts/kalived-advise.py` + `hiroshima_decide.py`. Kort JSON: stamp, verdict, env, finding-ider, procs-tall, nmap vs ss, pcap-tall, ufw_digest-tall. Aldri pakke-payload, pcapng, full URL, journal, API-nøkler, raw `ps`.

Digestet lander som `protocol.json` ved siden av `verdict.json` når cockpit reaper scan eller `GET /v1/hiroshima/verdict`. GUI leser begge. Verdict overskrives ikke.

### 3 — Jev-port (`decide()`)

Én evaluate per vindu, timeout 4 s, ingen 429-retry. Mercury bare hvis `class ∈ {candidate, alert_family}`. Rules kjører alltid og kan veto.

| Primitive | id | Alternativer |
|---|---|---|
| Choice | `class` | `noise` / `env_shift` / `candidate` / `alert_family` |
| Noul | `ours` | xAI / Proton / cockpit / Brave / NM |
| Noul | `dual` | to uavhengige evidens-domener |
| Score | `severity` | 1–5; kode mapper til forslag, ikke til `verdict.json` |
| Choice | `playbook` | id fra `playbooks/` + `none` + `ask_operator` |

Rules-veto (kan ikke bli `noise`): memfd/deleted+nett, fake kworker+userspace-exe, `ld.so.preload`, extra UID 0, nmap≠ss ∧ tshark SYN-ACK samme port.

Kilde: `src=jev+rules|mercury+rules|rules`.

### 4 — Mercury

`mercury-2.5`, kort JSON: `{family, why, missing_evidence, playbook}`. Ingen prosa-essay. Ingen pakker. Hoppes på `env_shift` / `noise`.

### 5 — signal / Grok

Når `class` er `candidate` eller `alert_family`, eller operator åpner Hiroshima-chatten. Playbook `prompts/playbooks/signal.md`. Aldri whitelist ALERT uten evidens. Xterm for passord.

### 6 — Aktør

Playbooks bak Confirm (to klikk). Gate: siste `kalived_scan=1` verdict ≠ ALERT/ERROR (WARN er lov). LLM eier aldri `sudo`. Dest-IP til isolate kommer fra scan-snapshot, ikke argv.

`build` endrer kalived-treet. `signal` foreslår. ctl utfører. Etter mutasjon: ny scan.

## Miljøklasse

Fil (ikke git, 0600): `~/.config/kalived/env_class.toml`

Klasser: `home` | `travel` | `tether`.

Auto-merk ved første treff:

| Heuristikk | Klasse |
|---|---|
| `usb0` / `enx*` er default-rute | `tether` |
| Klassisk telefon-DHCP (192.168.43/24, 192.168.137/24, 172.20.10/28) | `tether` |
| SSID i overlay | overlay vinner |
| ellers ny SSID / ny gw / ny DNS | `travel` |

Operator retagger i skuffen (`PUT /v1/hiroshima/env`). **Signal-agenten skriver ikke overlay.**

`tether` og `travel` mapper til port-bøtta `env_shift`. UFW-blokk-støy på delt telefon-nett er default deny-in, ikke angrep, med mindre `hits_listen>0`.

## Personvern

Loopback-UI. Secrets i `~/.config/kalived/` 0600.

Det som kan forlate maskinen: redigert digest til Jev, og på candidate samme korte JSON til Mercury. Felter: stamp, class, finding-ider, exe, dst-familie, porter, tellinger. Ikke payload, pcap, full qname/SNI, journal, cmdline, dest-IP.

`ai_enabled=false`: rules-port uten sky. Timer-scan likeså.

## Faser

### H0 — Spekk

Denne fila. Tester: [CHAT-TESTS.md](CHAT-TESTS.md) avsnitt H.

### H1 — Porten

Etter cockpit-scan (jobb ferdig) og ved `GET /v1/hiroshima/verdict`: digest → `decide()` → `protocol.json` → engram i `signal`. Skuffen viser `class`, `env.class`, SSID, `src`, playbook, `sensor_gaps`.

Filer: `hiroshima_decide.py`, `hiroshima.py`, `Hiroshima.svelte`, `scripts/tests/protocol_h1.py`.

### H2 — Ring + graf

Sil 4 + ESTAB + DNS + AIDE + PCAP-EXTRA → `protocol.ring` (exe, dst-familie, port, sil — aldri IP/cmd). Kuzu: `proc:{exe} --CONNECTED--> dst:{family}`, `scan:{stamp} --USED--> detector:{id}`, digest `--ABOUT-->` detector.

Mercury bare på candidate/alert. Engrams: `digest`, `env_shift`, `finding` (WARN/ALERT). `kind=decide` hoppes i recall.

Filer: `protocol_h2.py`.

### H3 — Miljø + isolasjon

Overlay + retag. Confirm: `aide-init` (scoped), `rkhunter-setup`, `isolate-dst`, `isolate-undo`, `kill-pid`. Act-fil `act.json` 0600.

NOPASSWD: `install-kalived-helper.sh` + `install-nopasswd-ctl.sh`.

### H4 — Egress-watch

`sudo kalived-ctl watch` sampler `ss` ESTAB + `ausearch -k kalived_connect`. Vindu: exe, dst-familie, port, n, `unmapped`. python/shell → unknown = `alert_family`. Isolate bruker siste scan-snapshot.

Timer opt-in: `install-watch-timer.sh` eller Settings. Filer chown-es til `KALIVED_OWNER` 0600.

Uplink-burst: tshark på default-rute-iface, max 30 s, `-T fields`, aldri `-i any`.

### H5 — Falco host-burst

`sudo kalived-ctl falco-burst` (~8 s) → `hunt_falco.jsonl` (`rule`, `exe`, `evt.type`, `n`). Tom jsonl = ingen finding. Falco alene = WARN/candidate. Falco + FIM (`FIM-AIDE`/`FIM-DEBSUMS`/`PERS-PRELOAD` på WARN/ALERT) eller Falco + nett = ALERT. Dual leser **høyeste** severity per id (siste INFO-rad overskriver ikke). INFO «falco absent» / «rules rejected» / «engine failed» hever ikke.

Regler: `defs/falco-host.yaml` (ikke stock `falco_rules.yaml`). `spawned_process` definert der. `engine.kind=modern_ebpf` i `defs/falco.yaml`. Units masked. Ingen gRPC/web. Falco skriver ikke Qdrant eller `hiroshima/`. jsonl/txt/err: operator 0600.

Playbook `install-falco-host.sh` printer tredjeparts-apt hvis binær mangler; kjører den ikke. Fixture `protocol_h5.py`.

### H6 — Suricata (valgfri)

eve.json på aktiv uplink. Ingen pcap-dump. Zeek ut.

## Minne

Etter port: `signal`-namespace får `digest` / `env_shift` / én `finding`. Kuzu-kanter over. Falco-burst alene er utenfor `PLAYBOOK_RUNS`. Disk forblir orakel. Tidslinje tvers av stamps er ønsket, ikke bygd.

## Vedtak (kort)

| # | |
|---|---|
| 1 | Sensorer eier strømmen; Jev porter digest |
| 2 | Mercury bare på candidate/alert_family |
| 3 | `signal` namespace, ingen ny SOC-agent |
| 4 | `verdict.json` er sannhet; `protocol.json` forklarer |
| 5 | Auto-merk miljø; ALERT krever dual-source |
| 6 | Telefon-gw = `tether` / `env_shift` |
| 7 | UFW + nft, ikke iptables-omskriving |
| 8 | fail2ban/CrowdSec ut mens SSH er masked |
| 9 | Falco = burst, etter watch |
| 10 | Playbooks + Confirm, aldri LLM-sudo |
| 11 | Timer skriver rules-port uten sky når `ai_enabled=false` |

## Hva vi ikke gjør

- Kontinuerlig Jev/Mercury på rå pcap
- Nye agenter (`hiroshima`-agent, swarm)
- CrowdSec, Wazuh, Zeek på laptopen
- Auto-ban / auto-kill fra modell
- Strangle `:8787`
- Payload eller pcapng til skyen
- Love 100 % tracker-/rootkit-fri
- Røre scan-kjernen fordi UI vil ha live-grafer
- `aide --all` som default Confirm (gjemmer VPN-snap)
