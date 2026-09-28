# Chat-tester — minne og kode-loop

Lim inn i Arbeid. Huk av «agent får kjøre» **bare** på K-oppgavene. Hard-refresh hvis API nettopp ble restartet.

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

Etter hver runde: lim sys+svar her, så sjekker vi sqlite/Kuzu.
