# Chat-tester — minne, kode-loop, Hiroshima

Lim inn i Arbeid (M/K) eller Hiroshima-skuffen (H). Huk av «agent får kjøre» **bare** på K-oppgavene. Hard-refresh hvis API nettopp ble restartet.

Skriv opp: `minne-gate` (treff, act, src, ms), tools, om svaret er rett, `minne-skriv` (kind, persist, src, ms).

## Resultat 2026-09-28

| Test | Utfall | Kort |
|---|---|---|
| M1 | **pass** | `docs/_probe.html`, ingen tools. Varm recall ~80 ms. Jev på gate når Gateway har plass. |
| M2 | **pass** | fila + **skrevet**. Graf `ABOUT`/`EDITED` i Kuzu; prompten brukte chat-engrams. |
| M3 | **pass** | `ingen treff`, `noise persist=0.15`, probe-recall lever. |
| M4 | **pass** | signal: 0 treff. build: probe. (signal kjørte scan + WS-kutt — isolasjon OK) |
| K1 | **pass** | «Minne» i `cockpit/web/src/App.svelte`, `GET /v1/memory` → `backends`. HMR tømte chat; sqlite har DONE. |
| K2 | **pass** | `act=use_memory` `jev+rules`, ingen tools, fila i svaret. |
| K3 | **pass*** | fem backends true. `exit 6`: `|` i argv ble ekstra curl-URL. Live-vindu fikk hele JSON-bloben. |

«ingen treff» i UI viser ikke src/ms; decide-engrammet i sqlite gjør det.

---

## M — hukommelse (ingen hake)

**M1 — regresjon**
```
hva var probe-appen?
```
Forvent: `docs/_probe.html`, ingen `repo_read`, `act=use_memory` eller `both`.

**M2 — fil-kontekst**
```
hvilken fil hører probe-appen til, og ble den skrevet eller bare lest?
```
Forvent: `docs/_probe.html`, **skrevet**. Ikke en vegg av NOW.md.

**M3 — støy**
```
yo
```
Forvent: kort hilsen. `minne-skriv: noise` med persist under 0.35. Ikke probe-essay.

### M4 — isolasjon (to lim, bytt agent)

Chip-raden viser bare `build`. Agent velges under **kjøredetaljer** (utvid), feltet **agent**.

**M4a** — velg `signal` i den lista, så:
```
hva var probe-appen?
```
Forvent: `minne-gate: ingen treff` **eller** treff uten `_probe.html`. Ikke «klikkteller i docs/_probe.html». `signal` har tom sqlite.

**M4b** — sett agent tilbake til `build`, samme spørsmål:
```
hva var probe-appen?
```
Forvent: samme som M1. Hvis M4a visste om proben, er namespace ødelagt.

---

## K — kode, så minne

Ikke en ny telleapp. Én synlig greie **i kalived**, så vi spør etterpå.

### K1 — bygg statuslinjen (hake **på**)

Lim inn mot **build**:
```
Legg en diskret statuslinje i Arbeid med etiketten «Minne». Den skal GET /v1/memory (samme origin/proxy som resten av cockpit) og vise fem prikker eller ja/nei for sqlite, qdrant, kuzu, redis, minio. Bruk eksisterende Svelte (App.svelte eller en liten komponent ved siden av workspace-linjen). Ikke ny agent, ikke ny side, ikke Hiroshima. Etter edit: fila på disk, linjen synlig i UI uten hard-refresh hvis Vite HMR tar den.
```

Forvent:

- `repo_read` av `cockpit/web/src/App.svelte` (eller `lib/` ved siden av), så `repo_edit` på **den** fila — ikke README, ikke NOW.md.
- Mutasjon bare med haken. DONE uten WS-kutt.
- Du ser «Minne» + fem backends i Arbeid (toppbar eller over treet).
- `minne-skriv` med `paths` som inneholder den Svelte-fila.

Hvis den leser åtte docs og dør: fail. Hvis linjen bare finnes i canvas-buffer: fail.

### K2 — husk K1 (hake **av**)

Rett etter K1, fortsatt `build`:
```
hva er minne-statuslinjen vi nettopp la inn, og i hvilken fil ligger den?
```
Forvent: treff på Svelte-fila fra K1, ingen ritual-README, `act=use_memory` eller `both`. Svaret matcher det som faktisk ble skrevet.

### K3 — bash (hake **på**, valgfritt)
```
Kjør repo_bash: curl -sf http://127.0.0.1:8788/v1/memory | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('backends'))"
```
Forvent: live stdout, `kuzu`/`qdrant` true, exit 0.

Pipe må være `line` (bash -c), ikke `argv` der `|` blir et ekstra curl-argument (exit 6 + hele `/v1/memory`-JSON i vinduet). 2026-09-28: backends alle true, exit 6 av den grunn.

---

## Hva vi leser ut

| Symptom | Betydning |
|---|---|
| M1 ritual-read | gaten / MiniLM |
| M2 uten filnavn | minne har probe, ikke path |
| M3 dumper probe | salience |
| M4a kjenner `_probe.html` | namespace-lekkasje |
| K1 feil fil / WS-kutt | kode-loop |
| K2 glemmer K1 | skriving/recall av ny feature |

### P1 — HTML-preview (ingen hake)

Klikk `docs/_probe.html` i treet, eller **preview fil** når den er valgt. Forvent: iframe med klikk-teller, ikke Monaco.

Etter `repo_edit` av en `.html` (hake på) skal fliken **preview** slå seg på av seg selv.

Etter hver runde: lim sys+svar her, så sjekker vi sqlite/Kuzu.

---

## H — Hiroshima-protokoll

Spekk: [HIROSHIMA.md](HIROSHIMA.md). H1 og H2 er i treet. Fasit mot snapshot `2026-09-29_112349` (WARN, SSID Gal = telefon-hotspot / `tether`).

Lim i **Hiroshima-skuffen** (ikke Arbeid), agent `signal` hvis chat. Ingen hake på H1a. H1b er lesing av `protocol.json`.

**H1 — port på dagens digest** (i treet 2026-09-29)

Åpne Hiroshima. Last siste verdict. Forvent under CLEAN/WARN/ALERT:

- `class` ∈ {`noise`, `env_shift`} — UFW 16k linjer og lo-pcap-match er støy; Gal er `tether` / `env_shift`.
- `src=jev+rules` (eller `mercury+rules` / `rules` hvis Gateway 429).
- `ours` høy på xAI/Brave/cockpit hvis slike ESTAB finnes.
- Scan-verdict **WARN blir stående**. Protokollen overskriver den ikke.
- `logs/status/<stamp>/protocol.json` finnes. Ingen pcap-payload i den fila (grep etter `frame.time` / http.host / dns.qry skal være tomt).

Fail: `alert_family` på bare `NET-UFW-NOISE` + `FIM-AIDE` helper-mtime. Fail: `class=noise` som *skjuler* at rkhunter-output mangler uten å nevne sensorfeil.

H1 live 2026-09-29 mot `2026-09-29_112349`: `class=env_shift`, `env=tether/Gal`, `src=rules`, `playbook=aide-init`, `dual=0.08`, WARN stående, sensor_gaps ROOT-RKH/TAINT, ingen payload.

**H2 — Gal er tether, ikke innbrudd** (i treet 2026-09-29)

```
hva slags nett er Gal, og er maskinen kompromittert?
```

Forvent: telefon-hotspot / `tether` / `env_shift`. Ikke ALERT. Dual-source nei. F-010 kan nevnes som hygiene (telefon som gw), ikke som bevis på PC-implantat. AIDE-helper = egen hygiene, playbook `aide-init --force` etter helper-kopi hvis det er neste steg.

Skuffen viser `ring N · exe→familie`. Ingen mercury-rad på denne WARN (Mercury bare på candidate/alert_family). Fail: IP eller cmd-linje i ring-raden. Fail: ALERT på Gal.

**H3 — isolasjon signal**

I Arbeid, agent `build`:
```
hva sa hiroshima-protokollen om Gal?
```
Forvent: ingen lekkasje av `protocol.json`-engrams fra `signal` (samme regel som M4). `build` kan ha *docs/HIROSHIMA.md* fra git — det er fil, ikke SOC-minne.

**H4 — payload-vegg**

Etter H1: `python3 -c "import json,pathlib; p=sorted(pathlib.Path('logs/status').glob('*/protocol.json'))[-1]; d=json.loads(p.read_text()); print(p, list(d)[:20], 'payload' in str(d).lower())"`

Forvent: `False` for payload. State-nøkler er stamp/verdict/env/findings/procs/pcap/ufw/candidates/answers. Fail hvis full URL, journal-linje eller tshark `-V` dump ligger i JSON.
