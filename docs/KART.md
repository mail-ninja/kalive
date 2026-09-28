# Kart — kode-delen (2026-09-26)

Dagens jobb: **måle og dokumentere**, ikke spre features. Hiroshima-protokoll og «sett sammen crew/modeller» venter til kode-loopen er ærlig beskrevet.

UI: http://127.0.0.1:5173/ · API: :8788 · minne-docker: startes med `sudo systemctl start docker` + `bash cockpit/scripts/up.sh`.

## Uferdige mål fra tidligere — gjør vi dem først?

| Rest | Blokkerer kartlegging? | Vedtak |
|---|---|---|
| Port A / B / MiniLM-embedder | Nei — **levert** | La ligge |
| Tool-engrams dumper hele filer (støy i recall) | Nei | Notert som minne-tuning |
| Chip-rad build/forge/review/term/crew | Nei, forvirrer UX | Rydd når vi banker UI |
| WS kutt midt i runde | Delvis fikset (singleton, ingen `--reload`) | Overvåk i testene |
| Hiroshima Jev/tshark/Mercury | Nei | Neste *runde*, ikke i dag |
| `repo_edit` treffer feil seksjon | Guard inne (`eeed752`) | Verifiser i UI-test |

**Konklusjon:** ingen rest som må kodes før testing. Stack opp, så kart.

---

## 1. Minnestack — som bygd

Fem lag, alle namespacet `kalived:{agent_id}`. Join-nøkkel: **engram UUID**.

| Lag | Motor | Port/sti | Rolle i dag |
|---|---|---|---|
| meta | sqlite | `~/.config/kalived/memory/<id>/episodes.sqlite` | episode-index, nøkkelord-recall |
| graph | Kuzu | `.../graph.kuzu` | node + `OWNS` agent→engram |
| vector | Qdrant | `:6333` coll `kalived_<id>` | 384-d MiniLM, cosine |
| blob | MinIO | `:9100` bucket `kalived-<id>` | JSON-kopi av engram |
| bus | Redis | `:6379` kanal `kalived:<id>` | publish etter skriving |

**Embedder:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (fastembed/ONNX, lokal, norsk+engelsk). Override `KALIVED_EMBED_MODEL`. Første last ~220 MB.

**Gaten:** før `run_turn` → `recall()` (sqlite-tokens + Qdrant kNN) → inn i systemprompt. Etter svar → `remember_engram` for `chat` og hver `tool`. Disk vinner ved konflikt.

**Isolasjon:** `recall('signal', …)` ser ikke `build`s episoder. Testet.

### Ønsket slutt (UFO)

- Semantikk som faktisk hjelper neste oppgave, ikke «topp 6 tilfeldige tool-JSON».
- Korte engrams: user + handling + path, ikke hele fila.
- Graf: fil `[:Path]--EDITED-->` episode, agent `ASKED` agent.
- Redis som nervesystem mellom `build` og `review` (ikke bare logg).
- Sletting / TTL / «glem denne runden».
- Embedder lastes én gang, synlig i `/v1/memory`.

### Test 2026-09-26 (denne økta)

Uten docker: sqlite+kuzu oppe; qdrant/redis/minio **nede** til du kjører sudo docker.

| # | Test | Resultat |
|---|---|---|
| M1 | backends uten docker | sqlite+kuzu true; qdrant/redis/minio false |
| M2 | `remember_engram` uten docker | skrev `meta+graph` (forventet) |
| M3 | `recall` nøkkelord `kartleggingstest` | treff i build |
| M4 | isolasjon signal | 0 lekkasje |
| M5 | 5 lag + MiniLM ranking | **kjør på nytt når compose er oppe** (gårsdagens kjøring: 5/5 lag, A/B ranking, 384-d, isolasjon) |

Gårsdagens full-stack (docker oppe): scan-query → Hiroshima-fakta på topp; monaco-query → vs-dark på topp. Svakhet: gamle `tool`-rader med hele filer som #2/#3.

---

## 2. Kode-UI — som bygd

```
Arbeid
  venstre  agentkonsoll (build default) + live stdout under kjøring
  høyre    mappetre (lazy) + Monaco på disk / iframe-preview
  PTY      skuff, «ikke agent»
Hiroshima  skuff, verdict fra disk
```

**Loop:** du skriver oppgave → WS `chat/user` → minne-gate → tools (`repo_*`, `repo_bash`) → diff/kort → `DONE`. Haken = mutasjon. Stopp = avbryt loop + bash pgid.

**Hva som skjer hvis du ber om «en liten app» i dag**

| Steg | I dag | Hull (UFO) |
|---|---|---|
| Plan | Modellen kan skrive kuler | Ofte leser den 16 docs først (bedre etter playbook-tak) |
| Skriv filer | `repo_edit` / `text=` på disk | Feil seksjon uten kontekst — *guard* inne, trenger UI-bevis |
| Ny fil | `repo_edit` med `text=` på ny path | Ingen «ny fil»-knapp; agent må treffe path |
| Kjør | `repo_bash` cwd workspace, 120 s | Ingen langlivet `npm run dev` (timeout). Preview av *ny* Vite-app krever PTY/`up.sh` |
| Se | iframe = HTML på disk (`/v1/workspace/raw`) | Auto-hopp til preview etter `repo_edit` av `.html` (delvis: operator trykker preview) |
| Test | `python3 -m pytest` hvis det finnes | Ingen standard app-mal |
| Husk | korte tool-engrams (etter 2026-09-27) | Gamle episoder er fortsatt støyete |
| Team | **build** synlig; resten i kjøredetaljer | crew/forge/review/term finnes, ikke i chip-rad |

**Happy path 2026-09-27:** «lag en teller i HTML» → `docs/_probe.html` på disk + iframe. Klikk 0→3 verifisert i headless Chromium. Statisk HTML er i boks. Ekte Svelte-app er fortsatt PTY + `:5173`.

### Test 2026-09-26 (API, samme tools som UI)

| # | Test | Resultat |
|---|---|---|
| C1 | glob `NOW.md` / tree `cockpit/scripts` | pass (`up.sh` synlig) |
| C2 | `repo_edit` uten hake | avvist |
| C3 | `repo_bash` `print("kart-test")` | exit 0 |
| C4 | `sudo` / `git push` | nektet |
| C5 | UI «liten app» E2E | **PASS 2026-09-27** — se under |

### Manuell UI 2026-09-27 (alle tre: PASS)

Kilde: `build` sqlite episoder 55–63 + disk + Chromium mot `GET /v1/workspace/raw?path=docs/_probe.html`.

| # | Prompt | Hva som skjedde | Disk / UI |
|---|---|---|---|
| U1 | `repo_bash` teller 0–4 med `sleep 0.3` | 1 tool, exit 0, stdout `0\n1\n2\n3\n4\n`, 1,53 s, pid 539960. Live-vindu. Ingen timeout. | PASS |
| U2 | Sett linje under «Neste hopp» i `docs/NOW.md` | `repo_read` + `repo_edit`. Diff: én linje **inni** seksjonen, ingen ny `##`. | `Kart 2026-09-26: minne+UI målt.` under Neste hopp. PASS |
| U3 | `docs/_probe.html` klikk-teller, vis iframe | glob (én tom, én docs/*) + `repo_edit` ny fil 73 linjer / 1793 B. DONE uten WS-kutt. | Fil på disk. Preview: Probe / Klikk / 0. Headless klikk 0→3. PASS |

Hull som **ikke** slo ut: haken var på; edit traff seksjon; HTML landet i workspace (ikke bare canvas-buffer). Én tom glob i U3 — støy, ikke stopp.

---

## 3. Når er kode-delen «i boks» nok til Hiroshima?

Minimum, UFO-ærlig:

1. **Én happy path:** oppgave → færre enn 6 tools → fil på disk på rett sted → bash-test grønn eller HTML i preview → DONE uten WS-kutt. **GRØNN 2026-09-27** (U1–U3).
2. **Minne som hjelper:** neste spørsmål treffer forrige feature, ikke 4× `repo_read`-JSON. **GRØNN 2026-09-28** — `src=jev+rules` `act=both`, ingen tools, `_probe.html`.
3. **Én synlig agent i Arbeid** (`build`). Resten i kjøredetaljer. **GRØNN** (chip-rad = build).
4. **Dokumenterte nei:** ingen sudo, ingen push, ingen 0.0.0.0. **GRØNN** (C4).

Når 2 er grønt i UI: Hiroshima-protokoll (Jev-port, tshark-evidens, Mercury-klassifisering). **2 er grønt.** Jev på *skriving* (salience, ikke per tool): [MEMORY.md](MEMORY.md).

---

## 4. Neste

1. Verifiser minne etter korte engrams: «hva var probe-appen?» skal treffe `_probe.html`, ikke en vegg av NOW.md.
2. Auto-preview når `repo_edit` skriver `.html`.
3. Jev: se [JEV.md](JEV.md). Anbefaling: `decide()`-adapter nå; live TypeSafe når nøkkel finnes. Hiroshima bruker samme adapter.
