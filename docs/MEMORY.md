# Minne — skriving, uthenting, Jev

Slik det **faktisk** kjører 2026-09-28. Start: `bash cockpit/scripts/up.sh` (docker for Qdrant/Redis/MinIO).

## Fem lag, én UUID

Hver episode får `memory_id`. Alle lag som er oppe får den.

| Lag | Motor | Skrives | Leses |
|---|---|---|---|
| meta | sqlite `~/.config/kalived/memory/<agent>/episodes.sqlite` | alltid | nøkkelord i `recall()` |
| graph | Kuzu `graph.kuzu` | node + `OWNS` | (lite i gaten ennå) |
| vector | Qdrant `:6333` `kalived_<agent>` | MiniLM 384-d | kNN i `recall()` |
| blob | MinIO `:9100` | JSON-kopi | ikke i gaten |
| bus | Redis `:6379` | publish | ikke i gaten |

Isolasjon: `agent_id`. `build` ser ikke `signal`. Disk vinner ved konflikt med minne.

**Embedder:** `paraphrase-multilingual-MiniLM-L12-v2` (lokal fastembed/ONNX). `KALIVED_EMBED_MODEL` overstyrer.

## Hva som skjer i en runde

```
du skriver
    → recall() MiniLM + sqlite  (kandidater)
    → decide() Jev, ellers Mercury-2.5, ellers rules
         keep (noul) per treff · act = use_memory | read_disk | both
    → Grok ser minne-blokk; use_memory fjerner tools
    → svar + tools
    → remember_engram(chat) + korte tool-engrams
```

Logg: `minne-gate: N treff (beste X) act=… src=jev+rules|mercury+rules|rules`.

Verifisert 2026-09-28 08:26: `src=jev+rules` `act=both` `n=4`, ingen tools, riktig `_probe.html`.

## Brukes Jev/Mercury på skriving *og* uthenting?

**I dag: bare uthenting** (etter MiniLM, før prompt). Skriving er deterministisk: all chat + korte tools går i alle fem lag.

**Beste neste steg er samme adapter på skriving — men ikke per tool.** Jev koster 0,1–20 s. 16 tool-runder × Jev = død loop.

| Sted | Jev/Mercury | Hvorfor |
|---|---|---|
| Uthenting | **ja** | keep/act — «er dette relevant *nå*?» |
| Slutt-engram (chat) | **ja, én gang** | salience / kind: fact vs støy |
| Hvert `repo_read` | **nei** | for tregt; korte engrams holder |
| MiniLM-vektor | **nei** | Jev rangerer ikke embeddings |

Skrive-policy (én `decide()` etter svaret): Noul `persist_hot` + Choice `kind` = `fact|artifact|noise|decision`. `noise` lagres likevel, men med lav salience så `recall()` kan droppe den. Mutasjon og `_probe.html`-artifacts skal overleve.

Hiroshima senere: samme `decide()`, andre questions (støy / kandidat / ALERT).

## Ønsket slutt

- `src=jev+rules` som normal, Mercury når 429, rules når begge nede.
- Recall uten ritual-README.
- Skriv: korte, taggede engrams. Ingen vegg av fil-JSON.
- TTL / «glem denne runden».
- Graf: fil `--EDITED-->` episode.
