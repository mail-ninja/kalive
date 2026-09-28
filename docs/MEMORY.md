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
    → recall() MiniLM + sqlite  (kandidater; hopp over decide-logger og støy)
    → decide() Jev, ellers Mercury-2.5, ellers rules
         keep (noul) per treff · act = use_memory | read_disk | both
    → Grok ser minne-blokk; use_memory fjerner tools
    → svar + korte tool-engrams (uten Jev)
    → DONE
    → decide() én gang til på slutt-engramet: kind + persist_hot
```

Logg: `minne-gate: N treff (beste X) act=… src=jev+rules|mercury+rules|rules`.
Etter svaret: `minne-skriv: fact|artifact|noise|decision persist=0–1 src=…`.

Verifisert uthenting 2026-09-28 08:26: `src=jev+rules` `act=both` `n=4`, ingen tools, riktig `_probe.html`.

## Brukes Jev/Mercury på skriving *og* uthenting?

**Samme `decide()`-adapter begge veier.** MiniLM finner like episoder. Jev (ellers Mercury, ellers rules) sier hva som *betyr noe*.

| Sted | Jev/Mercury | Hvorfor |
|---|---|---|
| Uthenting | **ja** | keep/act — «er dette relevant *nå*?» |
| Slutt-engram (chat) | **ja, én gang** | salience / kind: fact vs støy |
| Hvert `repo_read` | **nei** | for tregt; korte engrams holder |
| MiniLM-vektor | **nei** | Jev rangerer ikke embeddings |

Skrive-policy: Noul `persist_hot` + Choice `kind` = `fact|artifact|noise|decision`. `noise` lagres likevel, men `recall()` dropper den når `persist_hot < 0.35`. Mutasjon og `_probe.html` kan ikke merkes `noise` (rules-veto, persist minst 0.75). `kind=decide`-logger (selve gaten) går ikke inn i prompten.

Hiroshima senere: samme `decide()`, andre questions (støy / kandidat / ALERT).

## Ønsket slutt

- `src=jev+rules` som normal, Mercury når 429, rules når begge nede.
- Recall uten ritual-README.
- Skriv: korte, taggede engrams. Ingen vegg av fil-JSON.
- TTL / «glem denne runden».
- Graf: fil `--EDITED-->` episode.
