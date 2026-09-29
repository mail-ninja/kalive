# Minne — skriving, uthenting, Jev

Slik det **faktisk** kjører 2026-09-28. Start: `bash cockpit/scripts/up.sh` (docker for Qdrant/Redis/MinIO).

## Fem lag, én UUID

Hver episode får `memory_id`. Det er limet. Ingen synk-tabell, ingen utenlandsk nøkkel på tvers av motorer: **samme streng** er sqlite-rad, Kuzu-node, Qdrant-punkt, MinIO-nøkkel `engrams/<id>.json`, Redis-melding.

| Lag | Motor | Rolle | Join |
|---|---|---|---|
| meta | sqlite `episodes.sqlite` | hva som skjedde (payload, salience, `paths`, `turn_id`) | `memory_id` |
| graph | Kuzu `graph.kuzu` | *hvordan* det henger (fil, runde, agent) | node `id = memory_id` eller `path:…` |
| vector | Qdrant `:6333` | *hva det ligner* (MiniLM 384-d) | point id = `memory_id` |
| blob | MinIO `:9100` | JSON-kopi | `engrams/<memory_id>.json` |
| bus | Redis `:6379` | siste 100 UUID-er | melding inneholder `memory_id` |

Isolasjon: `agent_id` (egen sqlite/kuzu/collection/bucket/kanal). `build` ser ikke `signal`. Disk vinner ved konflikt med minne.

Kuzu-kanter kopieres **ikke** inn i Qdrant. Vektorer er likhet, ikke topologi. Konteksten til en relasjon ligger på kanten: `props.memory_id` (episoden som skapte den) og `props.turn_id` (samme chat-runde). Sqlite får en denormalisert `paths[]` så `recall()` ser fila uten Cypher.

```
agent:build --OWNS--> {memory_id}
path:docs/_probe.html --EDITED|READ|RAN|MENTIONED--> {memory_id}
{memory_id} --ABOUT--> path:docs/_probe.html
{chat_id} --USED--> {tool_id}          # samme turn_id
```

**Embedder:** `paraphrase-multilingual-MiniLM-L12-v2` (lokal fastembed/ONNX). `KALIVED_EMBED_MODEL` overstyrer.

## Hva som skjer i en runde

```
du skriver
    → recall() MiniLM + sqlite  (kandidater; hopp over decide-logger og støy)
    → decide() Jev, ellers Mercury-2.5, ellers rules
         keep (noul) per treff · act = use_memory | read_disk | both
    → Grok ser minne-blokk; use_memory fjerner tools
         (ask + eksisterende chat-svar tvinger use_memory; grep/read hoppes i recall)
    → svar + korte tool-engrams (uten Jev)
    → DONE
    → decide() én gang til på slutt-engramet: kind + persist_hot
```

Logg: `minne-gate: N treff (beste X) act=… src=jev+rules|mercury+rules|rules`.
Etter svaret: `minne-skriv: fact|artifact|noise|decision persist=0–1 src=…`.

Verifisert uthenting 2026-09-28 08:26: `src=jev+rules` `act=both` `n=4`, ingen tools, riktig `_probe.html`.

Hiroshima bruker **samme adapter** med annet question-sett, namespace `signal`. Spekk: [HIROSHIMA.md](HIROSHIMA.md). `kind=decide` hoppes i recall der også.

## Brukes Jev/Mercury på skriving *og* uthenting?

**Samme `decide()`-adapter begge veier.** MiniLM finner like episoder. Jev (ellers Mercury, ellers rules) sier hva som *betyr noe*.

| Sted | Jev/Mercury | Hvorfor |
|---|---|---|
| Uthenting | **ja** | keep/act — «er dette relevant *nå*?» |
| Slutt-engram (chat) | **ja, én gang** | salience / kind: fact vs støy |
| Hvert `repo_read` | **nei** | for tregt; korte engrams holder |
| MiniLM-vektor | **nei** | Jev rangerer ikke embeddings |
| Hiroshima-port (H1+) | **ja, én gang per scan-vindu** | `class` / `ours` / `dual` / `playbook` på redigert digest. Se [HIROSHIMA.md](HIROSHIMA.md) |

Skrive-policy: Noul `persist_hot` + Choice `kind` = `fact|artifact|noise|decision`. `noise` lagres likevel, men `recall()` dropper den når `persist_hot < 0.35`. Mutasjon og `_probe.html` kan ikke merkes `noise` (rules-veto, persist minst 0.75). `kind=decide`-logger (selve gaten) går ikke inn i prompten.

Hiroshima senere: samme `decide()`, andre questions (støy / kandidat / ALERT).

## Ønsket slutt

- `src=jev+rules` som normal, Mercury når 429, rules når begge nede.
- Recall uten ritual-README.
- Skriv: korte, taggede engrams. Ingen vegg av fil-JSON.
- TTL / «glem denne runden».
- Graf: fil `--EDITED-->` episode. **I treet:** `ABOUT` / `EDITED` / `READ` / `USED`, `turn_id` på runden, `paths[]` i sqlite. TTL / «glem» gjenstår.
