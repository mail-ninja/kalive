# Chat-tester — minne, kode-loop, Hiroshima

Lim inn i Arbeid (M/K) eller Hiroshima-skuffen (H). H2-chat: agentkonsollen, agent `signal`, hake av. Huk av «agent får kjøre» **bare** på K-oppgavene. Hard-refresh hvis API nettopp ble restartet.

Skriv opp: `minne-gate` (treff, act, src, ms), tools, om svaret er rett, `minne-skriv` (kind, persist, src, ms).

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

Chip-raden viser `build`. Agent velges under **kjøredetaljer**.

**M4a** — velg `signal`:
```
hva var probe-appen?
```
Forvent: `minne-gate: ingen treff` **eller** treff uten `_probe.html`.

**M4b** — sett agent tilbake til `build`, samme spørsmål. Forvent: samme som M1. Hvis M4a visste om proben, er namespace ødelagt.

---

## K — kode, så minne

Ikke en ny telleapp. Én synlig greie **i kalived**, så vi spør etterpå.

### K1 — bygg statuslinjen (hake **på**)

```
Legg en diskret statuslinje i Arbeid med etiketten «Minne». Den skal GET /v1/memory (samme origin/proxy som resten av cockpit) og vise fem prikker eller ja/nei for sqlite, qdrant, kuzu, redis, minio. Bruk eksisterende Svelte. Ikke ny agent, ikke ny side, ikke Hiroshima. Etter edit: fila på disk, linjen synlig i UI uten hard-refresh hvis Vite HMR tar den.
```

Forvent: `repo_read` / `repo_edit` av den Svelte-fila — ikke README. Mutasjon bare med haken. DONE uten WS-kutt.

### K2 — husk K1 (hake **av**)

```
hva er minne-statuslinjen vi nettopp la inn, og i hvilken fil ligger den?
```
Forvent: treff på Svelte-fila fra K1, `act=use_memory` eller `both`.

### K3 — bash (hake **på**, valgfritt)
```
Kjør repo_bash: curl -sf http://127.0.0.1:8788/v1/memory | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('backends'))"
```
Forvent: live stdout, backends-objekt, exit 0.

Pipe må være `line` (bash -c), ikke `argv` der `|` blir et ekstra curl-argument.

### P1 — HTML-preview (ingen hake)

Klikk `docs/_probe.html` i treet. Forvent: iframe med klikk-teller, ikke Monaco. Etter `repo_edit` av en `.html` (hake på) skal fliken **preview** slå seg på.

---

## H — Hiroshima-protokoll

Spekk: [HIROSHIMA.md](HIROSHIMA.md). Lim i **Hiroshima-skuffen** (ikke Arbeid), agent `signal` hvis chat. Ingen hake på H1.

**H1 — port på dagens digest**

Åpne Hiroshima. Last siste verdict. Forvent:

- `class` ∈ {`noise`, `env_shift`, `candidate`, `alert_family`} i tråd med spekken (UFW-støy + lo-pcap-match er ikke `alert_family` alene).
- `src=jev+rules` (eller `mercury+rules` / `rules` hvis Gateway 429).
- Scan-verdict blir stående. Protokollen overskriver den ikke.
- `logs/status/<stamp>/protocol.json` finnes. Ingen pcap-payload (`frame.time` / http.host).

Fail: `alert_family` på bare `NET-UFW-NOISE` + FIM-helper-mtime.

**H2 — tether er ikke innbrudd**

På et nett merket `tether` (telefon som gateway) eller `travel` (ny SSID):
```
hva slags nett er dette, og er maskinen kompromittert?
```
Forvent: `env_shift` / `tether` eller `travel`. Ikke ALERT bare fordi SSID er ny. Dual-source nei med mindre Falco+FIM/nett eller hard artefakt. Fail: IP eller cmd i ring-raden.

**H3 — isolasjon signal**

I Arbeid, agent `build`:
```
hva sa siste hiroshima-protokoll om miljøklassen?
```
Forvent: ingen lekkasje av `protocol.json`-engrams fra `signal`. `build` kan ha *docs/HIROSHIMA.md* fra git — det er fil, ikke SOC-minne.

**H3b — retag + Confirm**

Skuffen: dropdown env `home|travel|tether` + **retag**. `isolate unknown` skjult mens ringen bare har browser/loopback/xAI/private. Fail: isolate mot firefox/grok. Fail: retag uten 0600-fil i `~/.config/kalived/env_class.toml`.

**Settings — watch-timer**

Settings → Maskin: huke **Egress-watch hvert 5. min**. Fail: huke av men timer fortsetter å skrive nytt window.ts. Fail: `listen_bind` redigerbar til 0.0.0.0.

**H4b — watch**

Skuffen: `watch N · unknown U · unmapped M`. Knapp **watch** og **uplink 30s**. Unmapped kan være høy (browser mot offentlig dest) — synlig, ikke ALERT. Fail: IP eller SNI i watch-linjen. Fail: `window.json` `root:root` (skal være eier 0600). Fail: `Chrome_ChildIOT` / `tokio-rt-worker` som unknown (skal være browser/xAI).

**H4c — scoped aide-init**

Confirm aide-init fryser kalived-filer, **ikke** VPN-snap / udev / snapd-mount — de skal fortsatt ligge som WARN etter Confirm.

**H5 — Falco host-burst**

Knapp **falco 8s**. Etter burst: `hunt_falco.jsonl` under stamp (ny stamp hvis standalone). Tom jsonl = ingen finding. Falco alene = WARN / `candidate`. Falco + FIM eller Falco + nett = ALERT. Fail: cmdline/SNI/pcap/IP i digest. Fail: filer under `hiroshima/` fra Falco. Fail: ERROR når pakke mangler (INFO «falco absent»).

**H4 — payload-vegg**

```
python3 -c "import json,pathlib; p=sorted(pathlib.Path('logs/status').glob('*/protocol.json'))[-1]; d=json.loads(p.read_text()); print(p, 'payload' in str(d).lower())"
```
Forvent: `False` for payload.

---

## Hva vi leser ut

| Symptom | Betydning |
|---|---|
| M1 ritual-read | gaten / MiniLM |
| M2 uten filnavn | minne har probe, ikke path |
| M3 dumper probe | salience |
| M4a kjenner `_probe.html` | namespace-lekkasje |
| K1 feil fil / WS-kutt | kode-loop |
| K2 glemmer K1 | skriving/recall |
