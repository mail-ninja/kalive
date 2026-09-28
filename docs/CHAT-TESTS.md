# Chat-tester — minne og kode-loop

Lim inn i Arbeid mot **build**. Huk av «agent får kjøre» bare på K-oppgavene. Hard-refresh UI først (API ble restartet).

Skriv opp: `minne-gate` (treff, act, src, ms), tools, om svaret er rett, `minne-skriv` (kind, persist, src, ms).

## M — hukommelse (ingen hake)

**M1 — regresjon**
```
hva var probe-appen?
```
Forvent: `docs/_probe.html`, ingen `repo_read`, `act=use_memory` eller `both`. Sys viser `Nms recall Nms decide`.

**M2 — fil-kontekst (graf)**
```
hvilken fil hører probe-appen til, og ble den skrevet eller bare lest?
```
Forvent: `docs/_probe.html`, skrevet (`repo_edit` / EDITED). Ikke en vegg av NOW.md.

**M3 — støy**
```
yo
```
Forvent: kort hilsen. `minne-skriv: noise` med lav persist, eller i hvert fall ikke en probe-essay.

**M4 — isolasjon** (bytt agent til `signal`, så tilbake til build)
```
hva var probe-appen?
```
På **signal**: ingen treff / ikke `_probe.html`. På **build**: samme som M1.

## K — kode, så minne (hake på)

Ikke en ny telleapp. Én synlig greie i **kalived selv**, så vi spør etterpå om den.

**K1 — bygg (hake på)**
```
Legg en diskret statuslinje i Arbeid (cockpit/web) som henter GET /v1/memory og viser om sqlite, qdrant, kuzu, redis, minio er oppe. Norsk etikett «Minne». Ikke ny agent, ikke ny side. Så vis i UI.
```
Forvent: `repo_read` av eksisterende Svelte, `repo_edit` på rett fil, fil på disk, preview/UI viser linjen. DONE uten WS-kutt.

**K2 — husk (hake av)**
```
hva er minne-statuslinjen vi nettopp la inn, og i hvilken fil?
```
Forvent: treff på den nye fila, ingen ritual-README, svar som matcher K1.

**K3 — bash på det du bygde (hake på)**
```
Kjør en kjapp sjekk med repo_bash at GET http://127.0.0.1:8788/v1/memory returnerer backends.kuzu og backends.qdrant true. Vis output.
```

## Hva vi leser ut

| Symptom | Betydning |
|---|---|
| M1 feil / ritual-read | gaten eller MiniLM |
| M2 treffer probe men ikke fila | graf `ABOUT` brukes ikke i prompt ennå (forventet til vi tar graph-hop) |
| M3 dumper probe | salience/støyfilter |
| M4 signal vet om probe | namespace-lekkasje |
| K1 dør i WS / feil fil | kode-loop |
| K2 glemmer K1 | skriving/recall av ny feature |

Etter M+K: si ifra, så leser vi sqlite/Kuzu sammen.
