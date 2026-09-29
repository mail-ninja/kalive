# Hiroshima-protokollen

Spekk 2026-09-29. Ingen kode i denne fila. Scan-sannhet er fortsatt `logs/status/<stamp>/verdict.json`. Cockpit er klient.

Kalived er to rom: Arbeid (kode) og Hiroshima (host-SOC på én Kali-laptop). Hiroshima er ikke SIEM, Huntress, LAN-scanner eller sky-EDR.

## Operatorvedtak (2026-09-29, Trondheim)

1. **Miljøklasse auto-merkes.** Ny SSID / ny default-rute / ny DNS blir `env_shift` og vises i skuffen. ALERT krever dual-source eller hard artefakt oppå det.
2. **Falco etter H4.** Auditd + eksisterende huntere først. Én eBPF-sensor (Falco, container-regler av) når rolling egress-watch er grønn.
3. **Denne fila er H0.** H1-porten og H2-ringen er i treet 2026-09-29.

SSID **Gal** (wlan0 `10.125.19.203/24`, IPv6 `2001:2020:8351:7f87::/64`) er **delt nett fra operatorens telefon**. Klasse: `tether`. Ikke campus, ikke `travel`.

---

## Hva protokollen er

```
rå evidens (lokalt, privilegert via kalived-ctl)
    → deterministiske siler 1–4 + baseline + miljøklasse
        → kort digest (JSON, felter)
            → Jev porter (noise | env_shift | candidate | alert_family)
                → Mercury-2.5 bare på candidate / alert_family
                    → Grok / signal bare når Jev sier review
                        → kalived-ctl utfører, operator Confirm
```

Samme `decide()`-adapter som minnet. Andre spørsmål. Policy i kode. Modellen skriver aldri prompt, eier aldri `sudo`, ser aldri payload.

Jev er **porten** (som `act=use_memory` i Arbeid). Mercury er **kortlista**. `signal` er **aktøren som forklarer**. `build` patche *kalived-kode*. ctl kjører playbooks.

Parallell betyr Jevs speculative fan-out: én `state`, mange typed questions i samme kall. Ikke en sverm av nye agenter.

---

## Ærlig tak

Målet er en host så nær innsynsfri som en laptop kan være: trackere på *verten*, keyloggere, rootkits, malware, bakdører. Taket er ærlig:

- Nettleser-cookies og HTTPS-trackere eies av Brave/uBO. tshark ser SNI, ikke cookie-jar.
- Skjult LKM som lyver i `/proc` krever uavhengig evidens (AIDE på vmlinuz, taint, bpf).
- Firmware ligger utenfor v1.
- Telefon som gateway (F-010, iQOO) er operasjonell risiko. Tether hever hygiene-gulv til WARN-klasse `env_shift`/`tether`. ALERT på *PCen* krever fortsatt dual-source eller hard artefakt.

UFO-bar for ALERT: **to uavhengige domener** (prosess · persistens · nett · dns · fim/rootkit · identitet · pcap) **eller** én sil-4 med hard artefakt (memfd/deleted + nett, fake kworker + userspace-exe, preload, extra UID 0, nmap≠ss bekreftet av tshark).

---

## Arbeidseksempel: Gal 2026-09-29

Live scan `logs/status/2026-09-29_112349`:

| Felt | Verdi |
|---|---|
| verdict | WARN exit 1 |
| nett | wlan0 UP, NM `Gal` 802-11-wireless |
| IPv4 | 10.125.19.203/24 |
| operator | delt nett fra telefon |
| UFW 24t | 16017 linjer, block=459, allow=3428 — `NET-UFW-NOISE` |
| pcap lo | raw=28, vs_nmap=match, vs_ss=match — `PCAP-NOISE` |
| hidden | raw=3 kept=0 — `PROC-HIDDEN-NOISE` |
| AIDE | helper/prompts mtime + systemd wants — `FIM-AIDE` WARN |
| rkhunter | pakke installert, output mangler denne scannen — sensorfeil, INFO `ROOT-RKH` |
| SSH | masked / inactive |

Protokoll-forventning på dette digestet (H1-testen):

- `class=env_shift` (tether) eller `noise` på UFW/pcap/hidden-støy.
- `ours=ja` på python → xAI / Brave / cockpit-loopback.
- `dual=nei`.
- `playbook` ∈ {`install-kalived-helper` + `aide-init --force`, `none`} for AIDE-helper-drift. Ikke isolate, ikke scan-på-nytt etter CLEAN-aktig støy.
- Scan-verdict WARN **blir stående** (disk er sannhet). Protokollen *forklarer* den, den overskriver den ikke.

Overlay-frø (ikke git): `Gal` → `tether`. Heuristikk alene ville gjettet `travel` (nettet er `10.125.19.0/24`, ikke klassisk 192.168.43.0/24 Android-hotspot). Operator overstyrer; fila husker.

---

## Lag

### 0 — Sensorer (lokalt, root via ctl)

Allerede i treet: AIDE, auditd-mini, UFW over nftables, tshark 4.6.6 lo-burst, rkhunter 1.4.6, chkrootkit 0.59, nmap-lo, hunt-procs, keylogscan, outbound-allow, ufw_digest, defs/IOC.

tshark er **evidens-burst** (8 s, SYN-ACK på `lo`, `-T fields`, aldri pcapng til advisor). Se [strategy-nmap-tshark-proc.md](../playbooks/strategy-nmap-tshark-proc.md). Always-on `tshark -i any` er forkastet der: persondata, Proton-støy.

Kontinuerlig logger (H4): rolling egress-watch på `connect()` (auditd + `ss -tnp` + conntrack), felter + pid, ringbuffer under `~/.config/kalived/hiroshima/` modus 0600. Suricata IDS på *aktiv* uplink er H6, valgfri. Zeek / Security Onion er SOC-apparat, ikke denne laptopen.

### 1 — Siler og baseline (kode)

Sil 1–4 som i dag. `baselines/machine/outbound_proc.allow` (grok, brave, firefox, NetworkManager, …). Proton NS `10.2.0.1`. Loopback-porter 8787 / 5173 / 6333 / 6379 / 9100 / 45959 / 7878. DNS-familie. Miljøklasse (under).

Jev ser **det som overlevde silene**, som et kort digest. TypeSafe: filtrer først; stor irrelevant `state` senker nøyaktighet. Jev teller ikke, sammenligner ikke datoer, behandler ikke state som fiendtlig.

### 2 — Digest

Bygg på `scripts/kalived-advise.py` (allerede redigert: findings-id, procs-tall, nmap vs ss, pcap-tall, ufw_digest-tall, suggested_commands). Utvid med:

```json
{
  "stamp": "2026-09-29_112349",
  "verdict": "WARN",
  "env": {
    "class": "tether",
    "ssid": "Gal",
    "iface": "wlan0",
    "src": "overlay",
    "first_seen": false
  },
  "findings": [{"severity": "WARN", "id": "FIM-AIDE"}],
  "procs": {"hidden_raw": 3, "hidden_kept": 0},
  "pcap": {"vs_nmap": "match", "vs_ss": "match"},
  "ufw": {"block": 459, "hits_listen": 0},
  "candidates": [
    {"id": "c1", "pid": 0, "exe": "python3", "dst_family": "xAI", "sil": "NET-ESTAB"}
  ]
}
```

Aldri: pakke-payload, pcapng, full URL, journal-linjer, API-nøkler, raw `ps`. DNS-qname og SNI hashes eller allowlist-familie (`xAI`, `Proton`, `Mozilla`, `unknown`). Fiendtlige strenger (DNS, prosessnavn) i feltet `untrusted_sensor_text` med merkelapp i state.

Digestet lander på disk ved siden av `verdict.json` som `protocol.json` (H1). GUI leser begge.

### 3 — Jev-port (`decide()`)

Én evaluate per vindu, `classify_turn`-stil: timeout 4 s, ingen 429-retry, ingen andre URL. Mercury bare hvis `class ∈ {candidate, alert_family}`. Rules kjører alltid og kan veto.

| Primitive | id | Alternativer / betydning |
|---|---|---|
| Choice | `class` | `noise` / `env_shift` / `candidate` / `alert_family` |
| Noul | `ours` | er dette vårt (xAI / Proton / cockpit / Brave / NM)? |
| Noul | `dual` | finnes to uavhengige evidens-domener? |
| Score | `severity` | 1–5; kode mapper til CLEAN/WARN/ALERT-*forslag* |
| Choice | `playbook` | id fra `playbooks/` + `none` + `ask_operator` |

Rules-veto (kan ikke bli `noise`): memfd/deleted+nett, fake kworker+userspace-exe, `ld.so.preload`, extra UID 0, nmap≠ss ∧ tshark SYN-ACK samme port. Persist-gulv 0.75 som `_probe.html` på minnesiden.

Jev 1.13 jaggedness som gjelder oss: stor støyende state, adversarial content i DNS/SNI, telling av UFW-linjer (tell i kode), dato på stamp (parse i kode). LogInject / TypeSafe: state er data, ikke fiende — derfor merkelapp + deterministisk sil *foran*.

Kilde logges `src=jev+rules|mercury+rules|rules` som i Arbeid.

### 4 — Mercury

`mercury-2.5`, temperatur 0.5, `max_tokens` 1500, 8–12 kandidatlinjer. Svar JSON:

```json
{"family": "c2|fim|hygiene|tether|self", "why": "…", "missing_evidence": "…", "playbook": "isolate-dst|none"}
```

Ingen prosa-essay inn i GUI. Ingen pakker.

### 5 — signal / Grok

Bare når `class` er `candidate` eller `alert_family`, eller operator åpner Hiroshima-chatten. Playbook [signal.md](../prompts/playbooks/signal.md): korreler, foreslå Confirm-kommandoer, aldri whitelist ALERT uten evidens. Xterm for passord.

### 6 — Aktør

Playbooks bak Confirm. Gate = siste `kalived_scan=1` verdict ≠ ALERT/ERROR (som [SURFACE.md](SURFACE.md) §5). LLM eier aldri `sudo`. Nye playbooks i H3: `isolate-dst` (ufw/nft outbound deny til én dst, rollback), `kill-pid` (exe-match fra snapshot).

`build` endrer kalived-treet. `signal` foreslår. ctl utfører. Etter mutasjon: ny scan, AIDE-gate som i dag.

---

## Miljøklasse

Fil (hemmeligheter-treet, 0600, ikke git): `~/.config/kalived/env_class.toml`

```toml
# auto-merk + operator-retag
[ssid.Gal]
class = "tether"
note = "telefon-hotspot 2026-09-29"

[ssid.HomeExample]
class = "home"
```

Klasser: `home` | `travel` | `tether`.

Auto-merk ved første treff:

| Heuristikk | Klasse |
|---|---|
| `usb0` (eller `enx*`) er default-rute | `tether` |
| DHCP/subnet 192.168.43.0/24, 192.168.137.0/24, 172.20.10.0/28 | `tether` |
| SSID i overlay | overlay vinner |
| ellers ny SSID / ny gw / ny DNS | `travel` |

Første treff: skriv overlay med gjettet klasse, sett `first_seen=true`, vis i skuffen. Operator kan retagge (H3 UI). Gal er allerede `tether` i spekken; H3 seeder overlay.

`tether` er F-010-familien: telefonen er gateway. Hygiene-gulv WARN/`env_shift`. Sensitive logins over kjent-kompromittert telefon forblir F-010-råd, ikke ny ALERT-fabrikk.

UFW-blokk-støy på delt telefon-nett er default deny-in som jobber, ikke angrep, med mindre `hits_listen>0`.

---

## Capture og host-stack

| Lag | Behold | Løft |
|---|---|---|
| tshark | lo-burst, felter, dual-source mot nmap/ss | H4: valgfri 30 s uplink-burst *on demand* via ctl, fortsatt felter |
| Brannmur | UFW operatorflate, nft motor | Isolation via ctl. Ingen iptables-omskriving. |
| fail2ban | ut så lenge SSH er masked | Hvis SSH åpnes: nøkler, `PasswordAuthentication no`, fail2ban med nftables-backend |
| CrowdSec | ut | CTI forlater boksen, krasjer innsynsmålet |
| rkhunter/chkrootkit/debsums | én siler, kjent-ondt | Sannhet for ukjent: AIDE + auditd + (H5) Falco. Manglende rkhunter-output = sensorfeil, ikke innbrudd |
| ClamAV | ut som default | For mye FP på Kali-workstation |
| Wazuh / osquery | ut i v1 | For tungt / feil form |
| Falco | H5 | Host, container-regler av. memfd-exec, write `ld.so.preload`, shell fra nettleser, connect utenfor allow-familie |
| Suricata | H6 valgfri | IDS på aktiv uplink, eve.json alerts, ingen pcap-dump |
| Zeek | ut | Egen boks hvis vi noen gang vil ha conn.log-historie |

Kontinuerlig Jev på pakkestrøm er forkastet: Gateway-429 (bevist i cockpiten), TypeSafe jaggedness på stor state, prompt-injection i DNS/SNI (LogInject opptil 88 % ASR), payload/SNI til Vercel+Inception er innsyn, PCAP-LM viser at `tshark -V` sprenger vindu, agentic-pcap-benker er offline forensics (~43 investigations/t).

---

## Minne og graf

Samme fem backends. `agent_id=signal`. Ingen sjette agent. UUID-spine som [MEMORY.md](MEMORY.md). `verdict.json` er scan-sannhet. Minne er fortelling og korrelasjon.

| kind | Hva |
|---|---|
| `decide` | port-rad (hoppes i recall, som i dag) |
| `finding` | sil-4 / candidate som overlevde |
| `digest` | kort protocol.json-pek |
| `playbook_run` | Confirm + resultat |
| `env_shift` | ny SSID/rute/DNS |

Kanter (H2):

```
agent:signal --OWNS--> {memory_id}
proc:{exe} --CONNECTED--> dst:{family}
finding --ABOUT--> proc:… | path:… | flow:…
finding --CORRELATED--> finding     # dual-source
scan:{stamp} --USED--> detector:{name}
```

Recall i Hiroshima: «har vi sett denne exe mot denne dst-familien før?». MiniLM på kort tekst (`python ESTAB xAI:443`), ikke på pcap.

---

## Personvern

Loopback-UI. Capture er host-nivå via ctl. Secrets i `~/.config/kalived/` 0600.

Det som *kan* forlate maskinen i H1+: redigert digest til Jev (Vercel Gateway / TypeSafe) og, på candidate, samme korte JSON til Mercury (Inception). Felter: stamp, class, finding-ider, pid/exe, dst-familie, porter, tellinger. Ikke payload, ikke pcap, ikke full qname/SNI uten hashing/familie, ikke journal.

`ai_enabled=false` i config skal hoppe over live Jev/Mercury og bruke rules. Timer-scan skriver digest + rules-port uten sky.

---

## Faser

Hver fase er selvstendig testbar. UFO-bar: synlig resultat, DONE uten WS-kutt, minne som hjelper neste tur, loopback, ingen payload ut, ctl for root. Scan-kjernen røres ikke «fordi UI».

### H0 — Spekk (denne fila)

Levert 2026-09-29. Tester: [CHAT-TESTS.md](CHAT-TESTS.md) avsnitt H.

### H1 — Porten på eksisterende scan

**I treet 2026-09-29.** Etter `kalived-ctl scan` (cockpit-jobb ferdig) og ved `GET /v1/hiroshima/verdict` (cache hvis `protocol.json` er nyere enn `verdict.json`; `?port=true` tvinger): digest → `decide()` (Jev 1×4s, ingen Mercury, rules-fallback) → `logs/status/<stamp>/protocol.json` → engram i `signal` (`kind=decide`). Skuffen viser `class`, `env.class`, SSID, `src`, playbook og `sensor_gaps`.

Filer: `cockpit/backend/app/hiroshima_decide.py`, hook i `decide.py`, reap/GET i `hiroshima.py`, `hiroshima_verdict` i `tools.py`, rad i `Hiroshima.svelte`, fixture `scripts/tests/protocol_h1.py`.

Env: seed `Gal→tether`; valgfri overlay `~/.config/kalived/env_class.toml` (0600, ikke git). Live mot `2026-09-29_112349`: `class=env_shift`, `env.class=tether`, `ssid=Gal`, `src=rules`, `playbook=aide-init`, `dual=0.08`, scan-verdict WARN urørt, ROOT-RKH/TAINT i `sensor_gaps`.

Ikke: live capture, Falco, ny agent, auto-ban.

Paste: **H1** i CHAT-TESTS.

### H2 — Kandidat-ring + graf

**I treet 2026-09-29.** Objekter fra sil 4 + ESTAB + DNS + AIDE + PCAP-EXTRA lander i `protocol.ring` (exe, dst-familie, port, sil — aldri IP/cmd). Kuzu: `proc:{exe} --CONNECTED--> dst:{family}`, `scan:{stamp} --USED--> detector:{id}`, digest `--ABOUT-->` detector. `seen` er Kuzu-oppslag («sett denne exe→dst før?»).

Mercury-2.5 (egen gren, 8–12 ringlinjer) bare når `class ∈ {candidate, alert_family}`. Svar: `{family, why, missing_evidence, playbook}`. Gal/`env_shift` hopper over Mercury. Engrams i `signal`: `digest` og `env_shift` (recall), `decide` (hoppes), `finding` for WARN/ALERT.

Filer: `hiroshima_decide.py` (ring, mercury, graph), `memory.py` (`entity_id`, `graph_linked`), `Hiroshima.svelte` (ring-rad), fixture `scripts/tests/protocol_h2.py`.

Live mot `2026-09-29_112349`: ring med ESTAB-flows (browser/loopback/cockpit) + FIM-AIDE + private DNS, `mercury=null`, `firefox-esr CONNECTED browser`.

Paste: **H2** i CHAT-TESTS.

### H3 — Miljøklasse + isolasjon

Les/skriv `env_class.toml`. Seed `Gal=tether`. Skuffen viser klasse. Playbook `isolate-dst` + `kill-pid`. Retag i UI.

### H4 — Rolling egress-watch

systemd-oneshot / auditd `connect` + periodisk `ss`. Ringbuffer 0600. Vindu → ett digest → ett `decide()`. tshark-burst beholdes for dual-source. Fortsatt felter.

### H5 — Falco på host

Etter H4 grønn. Container-regler av. Alerts inn i samme kandidat-ring.

### H6 — Suricata IDS (valgfri)

eve.json på aktiv uplink hvis H4/H5 misser kjente signaturer. Ingen pcap-dump. Zeek ut.

---

## Key Decisions

| # | Vedtak | Hvorfor |
|---|---|---|
| 1 | Sensorer eier strømmen; Jev porter digest | Jev er System One, 429 på andre kall, injection i pakkefelt, innsyn |
| 2 | Mercury bare på candidate/alert_family | Samme lean-regel som `classify_turn` |
| 3 | `signal` namespace, ingen ny agent | Isolasjon allerede testet (M4); sverm er avvist i Arbeid |
| 4 | `verdict.json` forblir scan-sannhet; `protocol.json` er forklaring | GUI finner ikke opp detektorer |
| 5 | Auto-merk miljø; ALERT krever dual-source | Trondheim/Gal skal ikke rope innbrudd |
| 6 | Gal = `tether` | Operator: delt telefon-nett. F-010-familie |
| 7 | UFW + nft, ikke iptables-omskriving | nft er motoren; UFW er operatorflaten |
| 8 | fail2ban/CrowdSec ut mens SSH er masked | Ingen jail; CrowdSec sender CTI ut |
| 9 | Falco = H5, etter H4 | Én eBPF-sensor når watch virker |
| 10 | Playbooks + Confirm, aldri LLM-sudo | Tre trær, NOPASSWD bare ctl |
| 11 | Parallell = Jev-spørsmål på én state | TypeSafe fan-out, ikke agent-crew |
| 12 | Timer skriver rules-port uten sky når `ai_enabled=false` | Loopback-først |

---

## PR-plan

| PR | Tittel | Filer | Avhenger |
|---|---|---|---|
| 0 | Spekk Hiroshima-protokoll | `docs/HIROSHIMA.md`, CHAT-TESTS, NOW, KART, NEXT, JEV, README | — |
| 1 | H1 port på scan-digest | `hiroshima.py`, `decide.py`, `hiroshima_decide.py`, `Hiroshima.svelte`, fixture | 0 — i treet 2026-09-29 |
| 2 | H2 kandidat + graf | `memory.py` kanter, signal-engrams, Mercury-gren | 1 — i treet 2026-09-29 |
| 3 | H3 env_class + isolate-dst | `env_class.toml` schema, playbook, skuff-retag | 1 |
| 4 | H4 egress-watch | ctl-binær/script, ringbuffer, timer-oneshot | 1–2 |
| 5 | H5 Falco host-regler | playbook install, JSON→kandidat | 4 |
| 6 | H6 Suricata (valgfri) | playbook, eve-ingest | 4 |

Hver PR mergebar alene. Scan-scripts i `/usr/local` oppdateres bare via `install-kalived-helper.sh` etter git-endring.

---

## Hva vi ikke gjør

- Kontinuerlig Jev/Mercury på rå pcap
- Nye agenter (`hiroshima`-agent, swarm)
- CrowdSec, Wazuh, Zeek på denne laptopen
- iptables-rewrite, fail2ban mens SSH er masked
- Auto-ban / auto-kill fra modell
- Strangle `:8787`
- Payload eller pcapng til sky
- Love 100 % tracker-/rootkit-fri
- Røre scan-kjernen fordi UI vil ha live-grafer

---

## Åpne (ikke blokkere H1)

- Retag-UI for SSID: H3.
- Hash vs familie for SNI: H4.
- `ai_enabled` default for interaktiv scan vs timer: behold config-default `false` for timer; cockpit-H1 kan kalle `decide()` når Gateway-nøkkel finnes (samme som minne-gaten).

Når H2 er i treet: neste kode er **H3** (env_class.toml + isolate-dst + retag).
