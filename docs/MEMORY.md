# Minne — skriving, uthenting, Jev

Start: `bash cockpit/scripts/up.sh` (docker for Qdrant/Redis/MinIO). sqlite og Kuzu lever uten Docker.

## Fem lag, én UUID

Hver episode får `memory_id`. Samme streng er sqlite-rad, Kuzu-node, Qdrant-punkt, MinIO-nøkkel `engrams/<id>.json`, Redis-melding.

| Lag | Motor | Rolle | Join |
|---|---|---|---|
| meta | sqlite `episodes.sqlite` | hva som skjedde (payload, salience, `paths`, `turn_id`) | `memory_id` |
| graph | Kuzu `graph.kuzu` | *hvordan* det henger (fil, runde, agent) | node `id = memory_id` eller `path:…` |
| vector | Qdrant `:6333` | *hva det ligner* (MiniLM 384-d) | point id = `memory_id` |
| blob | MinIO `:9100` | JSON-kopi | `engrams/<memory_id>.json` |
| bus | Redis `:6379` | siste 100 UUID-er | melding inneholder `memory_id` |

Isolasjon: `agent_id` (egen sqlite/kuzu/collection/bucket/kanal). `build` ser ikke `signal`. Disk vinner ved konflikt med minne.

Kuzu-kanter kopieres ikke inn i Qdrant. Vektorer er likhet, ikke topologi. Kanten har `props.memory_id` og `props.turn_id`. Sqlite har denormalisert `paths[]` så `recall()` ser fila uten Cypher.

```
agent:build --OWNS--> {memory_id}
path:docs/_probe.html --EDITED|READ|RAN|MENTIONED--> {memory_id}
{memory_id} --ABOUT--> path:docs/_probe.html
{chat_id} --USED--> {tool_id}
scan:{stamp} --USED--> detector:{id}
proc:{exe} --CONNECTED--> dst:{family}
```

**Embedder:** `paraphrase-multilingual-MiniLM-L12-v2` (lokal fastembed/ONNX). `KALIVED_EMBED_MODEL` overstyrer. Lastes lazy.

## Hva som skjer i en runde

```
du skriver
    → recall() MiniLM + sqlite
    → decide() Jev, ellers Mercury-2.5, ellers rules
         keep (noul) per treff · act = use_memory | read_disk | both
    → Grok ser minne-blokk; use_memory fjerner tools
    → svar + korte tool-engrams (uten Jev)
    → DONE
    → decide() én gang til på slutt-engramet: kind + persist_hot
```

Logg: `minne-gate: N treff (beste X) act=… src=jev+rules|mercury+rules|rules`.
Etter svaret: `minne-skriv: fact|artifact|noise|decision persist=0–1 src=…`.

Hiroshima bruker samme adapter med annet question-sett, namespace `signal`. `kind=decide` hoppes i recall.

## Jev på skriving og uthenting

Samme `decide()` begge veier. MiniLM finner like episoder. Jev (ellers Mercury, ellers rules) sier hva som betyr noe.

| Sted | Jev/Mercury | Hvorfor |
|---|---|---|
| Uthenting | ja | keep/act |
| Slutt-engram (chat) | ja, én gang | salience / kind |
| Hvert `repo_read` | nei | for tregt |
| MiniLM-vektor | nei | Jev rangerer ikke embeddings |
| Hiroshima-port | ja, én gang per vindu | `class` / `ours` / `dual` / `playbook` |

Skrive-policy: Noul `persist_hot` + Choice `kind` = `fact|artifact|noise|decision`. `noise` lagres, men `recall()` dropper den når `persist_hot < 0.35`. Mutasjon og `_probe.html` kan ikke merkes `noise` (rules-veto). `kind=decide`-logger går ikke inn i prompten.

## Ønsket slutt

- `src=jev+rules` som normal, Mercury ved 429, rules når begge nede
- Recall uten ritual-README
- Korte, taggede engrams
- TTL / «glem denne runden»
- Graf: fil `--EDITED-->` episode — **i treet** (`ABOUT` / `EDITED` / `READ` / `USED`). TTL gjenstår
- Hiroshima-tidslinje: stamp → funn → Confirm-playbook, uten å gjøre minne til orakel
