# Jev (TypeSafe) — research og anbefaling (2026-09-27)

**A+B-skall i treet:** `decide.py` + Settings **Vercel AI Gateway (Jev)**. Uten nøkkel: `src=rules`. Med `AI_GATEWAY_API_KEY`: `POST …/typesafe/v1/systemone` modell `typesafe-ai/jev`, faller tilbake til rules ved feil.

Du skrev «safetype»; produktet heter **TypeSafe**. Modellen heter **Jev** (`jev-1.13` / `jev-latest`). Lansert 15. sep 2026. Kahneman System 1: rask beslutning, ikke essay.

## Hva Jev er

Ikke en chat-modell. Du sender **state** (tekst/JSON) + **typed questions**. Du får tall tilbake, aldri prosa.

| Primitive | Spørsmål | Svar |
|---|---|---|
| **Choice** | velg én av opptil 255 | vinner + fordeling + confidence |
| **Score** | plassér på 2–10 nivåer du definerer | score + fordeling |
| **Noul** | ja/nei | sannsynlighet 0–1 + confidence |

Latens typisk **70–500 ms**. Pris i OpenRouter-katalogen ca. **$0,042 / M input**, output gratis (ingen tokens å telle). Endepunkter: TypeSafe `POST …/v1/systemone` eller OpenRouter Decisions `POST https://openrouter.ai/api/alpha/decisions` / System One. **Ingen åpne vekter.** Kjører hos dem, ikke i docker hos oss.

Passer når svaret er **lukket og gjentas**: rute, ranger, slå av/på, eskaler. Passer **ikke** når du trenger begrunnelse, kode, eller flerhopps-resonnering.

## Stemmer det på minne-gaten?

**Delvis ja, på jobben — ikke som erstatning for MiniLM.**

| Oppgave | Hvem |
|---|---|
| «Hvilke episoder *ligner* spørsmålet?» | MiniLM + sqlite (vektor/nøkkelord). Det gjør vi. |
| «Av disse N, hvilke skal inn i Grok-konteksten?» | **Jev Noul/Score.** Det er System One. |
| «Trenger vi README, eller holder minnet?» | **Jev Choice:** `answer_from_memory` / `read_disk` / `ask_operator` |

Siste test («hva var probe-appen?») viste at **terskelen vi kodet i dag allerede kan treffe**: 4 treff, ingen ritual-lesing, riktig svar. Jev ville ikke ha *funnet* proben. Den ville **godkjent** at treffene er nok, og sagt nei til `repo_read`.

Uavhengige tester (AIMLAPI m.fl.): Jev er **midt på treet i accuracy**, vinner på **pris og fart**. Svakest når den skal *grade* kvalitet. Prompt injection kan flytte svaret; TypeSafe sier selv at state ikke behandles som fiendtlig. Pydantic: Jev **ved siden av** deterministiske sjekker, ikke i stedet.

## Hiroshima senere

Samme kontrakt, andre spørsmål:

- Choice: `noise` / `candidate` / `alert_family` på tshark-digest
- Noul: «er dette vårt eget python→Cloudflare (xAI)?»
- Score: hvor høyt skal verdikten
- Mercury klassifiserer fort; Jev **porter**; Grok bare ved review

Én adapter, to policy-sett (kode vs SOC). Ikke to integrasjoner.

## Anbefaling: **adapter nå, live Jev når nøkkel + baseline**

Ikke gjør OpenRouter til hard avhengighet (loopback-først, tre trær, vi har ikke `OPENROUTER_API_KEY` i env i dag).

**Bygg slik:**

1. `cockpit/backend/app/decide.py` — `decide(state, questions) -> answers`. I dag: deterministisk (score-cutoff vi nettopp satte). I morgen: HTTP til Jev hvis `OPENROUTER_API_KEY` eller `TYPESAFE_API_KEY` finnes.
2. **Første kallsted:** etter `recall()`, før prompt. State = query + topp-kandidater (korte). Questions:
   - Noul `keep` per treff: «er dette nyttig for *dette* spørsmålet?»
   - Choice `act`: `use_memory` / `read_disk` / `both`
3. **Policy i kode:** `keep < 0.6` → dropp; `act=use_memory` → ingen tools i første runde; logg avgjørelsen som engram `kind=decide`.
4. **Ikke:** la Jev skrive systemprompt, velge filer, eller kjøre bash. Ikke send hele `_probe.html` som state (støy senker Jev — filtrer først, TypeSafe advarer).
5. **Hiroshima:** samme `decide()`, annet question-sett, når du forklarer protokollen.

Mål: 20 loggede `decide`-rader med menneskelig «enig/uenig». Først da er Jev-live bedre enn if/else.

## Hva vi *ikke* gjør i samme sleng

- Ny chat-provider i dropdown
- LangChain TypeSafeClassifier
- Jev som «sikkerhetsagent» som later som den er SOC
- Bytte ut MiniLM

Logg: `minne-gate: N treff … act=use_memory|read_disk|both src=rules`. `act=use_memory` fjerner tools den runden.

## Beslutning jeg vil ha fra deg

**A.** Adapter-skall + deterministisk keep/act (ingen nøkkel, kan merges nå).  
**B.** A + live OpenRouter/TypeSafe når du limer nøkkel i Settings.  
**C.** Vent til Hiroshima-runden, minne-gaten forblir score-cutoff.

Anbefaling: **A nå, B når nøkkelen ligger i env.** Det er «før heller enn senere» uten å gjøre Kalive avhengig av et 12 dager gammelt hosted API.
