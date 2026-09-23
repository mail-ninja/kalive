# Tilbakemelding på «ærlig arkitekturkritikk»

Kilde: `~/Downloads/Kalive ærlig arkitekturkritikk og anbefalt vei videre.md` (2026-09-24).  
Dette er **ikke** en byggestart. Det er svar før neste kode.

Kort: **det matcher det vi driver med.** To rom, `verdict.json` som sannhet, tre trær, mutasjon bak menneske, loopback, ikke SIEM/EDR/Theia. Kritikken av den flate toppbaren og Monaco-uten-disk er treffsikker — vi har sett den live (`snake.py` i buffer, `python snake.py` mot home). Ambisjonsnivået er **høyt på riktig akse** (kontroll, evidens, én komplett loop). Der det blir omvei er **nye leverandører og nye produkter før loopen virker**.

---

## Ambisjon

Skyhøyt bør bety: en agent som planlegger, leser repoet, viser diff, får ja, kjører test, oppdaterer preview, stopper — og en SOC som aldri later som den har drept noe den ikke kan bevise. Det er høyere enn «flere modeller i dropdown».

Kritikk-teksten treffer det. 90-dagersplanen treffer det *også*, men pakker inn Jev, Groq, NIM, ElevenLabs, FindingV2, signert audit-kjede og panic mode i samme kvartal. Det er høyt på **bredde**. Vi vil ha høyt på **dybde i én loop**, så bredde.

Behold destinasjonen. Ikke start kvartalet med adaptere.

---

## Matcher treet?

| Påstand i kritikken | I kalived nå |
|---|---|
| To rom Arbeid / Hiroshima | Ja. Hiroshima er skuff, ikke iframe av `:8787`. |
| `verdict.json` er GUI-sannhet | Ja. Cockpit leser disk. |
| Tre trær git / secrets / helper | Ja. |
| Mutasjon bak hake | Grovsmed: én checkbox «agent får kjøre». Ikke policy-gateway. |
| Canvas ≠ workspace | Ja. `iframe_write` / Monaco-buffer. Ingen `repo_read`. |
| Tool-navn lekker i toppbar | Ja. Hele `TOOLS`-lista vises. |
| `crew` / `swarm` / `forge` / `term` | Finnes. `swarm` er alias. Ingen `build`. Ingen sandbox-runner. |
| Prompt registry | Nei. Playbooks er markdown-filer. |
| Jev / Groq / NIM | Nei. Catalog: xAI, Inception, HF, Perplexity, OpenAI (GitHub chat pensjonert). |
| Finding v2 / panic mode | Nei. Verdict-schema 1, CLEAN/WARN/ALERT/ERROR. |
| Mobil | Bevisst ute. Playbooks for telefon er egne. |

Produktløftet i kritikken er godt. Behold det. Internt navn forblir **kalived** (repo, ctl, paths). **Kalive** er git-remote. Ikke rebrand i UI ennå.

---

## Inn — dette er destinasjonen

1. **Policy/approval-gateway** mellom modell og tool. Modellen foreslår; kode sier allow / review / deny. Haken vi har er v0 av dette.
2. **Én vertikal loop** (oppgave → plan → les → diff → godkjenning → isolert kjøring → review → preview → stopp). Dette *er* cli-flaten. Ikke flere agenter først.
3. **Tre paneler i Arbeid:** agentkonsoll (samtale/plan/tools), workspace (tre + Monaco på disk), preview (iframe fra godkjent bygg). PTY er skuff, «ikke agent».
4. **Navn:** agentkonsoll, workspace, preview, PTY. `crew`/`swarm` → orchestrator når vi rører UI. `build` som repo-loop. `policy-gate` er **ikke** en LLM.
5. **Prompt-kompilering fra versjonerte blokker**, ikke agenter som omskriver hverandre. Jev (hvis det blir med) fyller felt, ikke systemprompt.
6. **Tale er I/O**, ikke en agent. Groq Whisper som første STT *etter* tekstloopen. TTS sist.
7. **Hiroshima som deteksjon → evidens → vurdering → containment → reverserbar remediation.** DNS som familie, ikke én test. Finding-schema v2. Aldri «kill all».
8. **Mobil er companion**, etter Linux v1.
9. **Porter:** byggeloop uten å forlate Kalive; ingen root/secrets/utenfor-workspace via tools; hver run har spor; ny bruker skjønner oppgave + diff + verdict.

Det er skyhøyt. Det skal stå.

---

## Ut — eller langt bak i køen

| Ting | Hvorfor ut av neste bygg |
|---|---|
| Jev som uke 9-krav | Riktig *rolle* (rask, typet beslutning). Feil *binding* før vi har målt en regelbaseline. Community-API (`/v1/systemone` vs `/v1/decisions`) er ikke contract-testet her. Adapter-plass, ikke avhengighet. |
| Prompt-telefon Mercury→Grok | Enig, ut. For alltid, ikke «senere». |
| Ubegrenset swarm | `swarm` i UI er støy. Én orchestrator, to workere. |
| Fem STT-leverandører | Groq Whisper først. Resten når push-to-talk faktisk brukes. |
| NVIDIA NIM i uke 7–8 | Verdig *senere* (data som ikke skal ut). Ikke før `ProviderAdapter` og én loop. |
| ElevenLabs / diarization | Når vi har møter i PTY. Ikke nå. |
| Signert audit-kjede + panic mode i samme 12-ukersblokk som cli | Panic mode er billig og bør inn tidlig (stopp AI-kall). Signert kjede er Hiroshima-kvalitet, eget løp. |
| Tre brukerprofiler (enkel/bygger/operatør) | Riktig slutt-UX. I v1: skjul tool-lista og putt provider i «Kjøredetaljer». Profiler som CSS-lag etter loopen. |
| iOS/Android-paritet | Enig, ut. Companion etter Linux v1. |
| Flere minnelag | Vi har fem. Ikke flere. Mål recall/sletting på det som finnes. |
| DSPy/GEPA i produksjon | Offline, hvis noensinne. |

---

## Motforslag / kompromiss

Behold arkitekturen i kritikken. **Klem 90 dager til én bevis-port, så påfyll.**

### Port A — «én uke i eget repo» (før alt annet)

Mål: du kan beskrive en liten feature i Kalive, se plan, se filer, godkjenne diff, se test/preview, og få `DONE` — uten å forlate `:5173`.

Rekkefølge (samme som [NEXT.md](NEXT.md), strammet med kritikken):

1. Skjul tool-lista. Topp: workspace-navn, profil, **stopp**. Agentkonsoll = venstre chat, med plan + tool-kort + sluttstatus.
2. Agent `build`. Tools: `repo_glob` / `repo_grep` / `repo_read` mot default `~/kalived`.
3. Workspace-tre + Monaco **på disk** (ikke canvas-buffer). Save er fil.
4. `repo_edit` + diff-kort + haken (v0 av gateway: path i workspace, ingen `sudo -S`).
5. Preview bare fra det som faktisk ligger på disk eller loopback etter godkjenning.
6. Stopp. Bruk det på kalived selv. Først da bash/sandbox.

PTY forblir skuff. Passord der. Hiroshima urørt i denne porten unntatt at **panic** (stopp WS-loop + eksterne kall) er en knapp, ikke et uke-11-prosjekt.

### Port B — etter at A er kjedelig å rose

- `repo_bash` med timeout, cwd=workspace, egress av som *default* (ikke «full sandbox-VM» først; deretter boble hvis vi trenger den).
- `ProviderAdapter` + profiler Fast/Build/Review. Groq inn som adapter (chat *og* Whisper). xAI og Mercury allerede der.
- Jev **kun** hvis vi har logg av routing-beslutninger å slå den mot. Ellers if/else + later adapter.
- Hiroshima: Finding v2 + DNS-familie + fixtures, **egne commits**, ikke i samme uke som Groq.

### Port C — destinasjon, ikke sprint

Sandbox-runner med mount, NIM lokalt, ElevenLabs, companion-app, signert snapshot-kjede, containment-playbooks. Skyhøyt. Etter A og B.

---

## Svar på åpne spørsmål i NEXT.md

Kritikken avgjør dem:

| Spørsmål | Svar |
|---|---|
| Workspace-rot | Default `~/kalived`, velgbar. Aldri `$HOME` som rot. |
| Cli vs chat | **Agentkonsoll erstatter venstre chat i Arbeid.** Ikke tredje canvas-knapp. |
| Preview av cockpiten selv | Nei i port A. |
| `build` vs `forge` | **`build` eier repo-loopen.** `forge` kan dø eller bli «canvas/preview-worker». Ikke begge med samme tools. |

---

## Groq Whisper

Ja — som **mikrofon → tekst inn i agentkonsollen**. Ikke som egen agent. Ikke før port A. Første adapter Groq `whisper-large-v3` / turbo, samme secrets-mønster som xAI (`GROQ_API_KEY` i `env`, hint i Settings). xAI STT er plan B (vi har allerede nøkkel). OpenAI/ElevenLabs etter at push-to-talk er i bruk.

---

## Hiroshima, kort

Kritikken er bedre enn «legg til rogue DNS-sjekk». Familie av resolver / NAT / hosts / persistens, evidens før tiltak, reverserbart. Det er skyhøyt og **riktig**. Det er også lett å bruke tre uker på schema uten at ALERT blir lettere å stole på.

Kompromiss: neste Hiroshima-PR er **støy vi allerede kjenner** (python-ESTAB mot Cloudflare/xAI, self-noise) *eller* én DNS-familie-detektor med fixture — ikke FindingV2 + signert logg + panic + tidslinje i samme sleng. Panic-knappen i cockpit er Arbeid, ikke scan-kjernen.

Scan-scripts røres ikke «fordi UI».

---

## Hva jeg ville strøket i 90-dagersplanen hvis vi skal holde lista høy

- Uke 1–2: frys **navn og to schemaer** (`RunEvent`, `ApprovalRequest`). Ikke alle fem. Tool-matrise som tabell i docs, implementert som kode i port A for `repo_*` bare.
- Uke 9–10 Jev: blir «hvis port A har n>20 kjøringer å sammenligne».
- Uke 7–8: preview fra disk/loopback (allerede v0) + Groq-adapter. Ikke NIM.
- Uke 11–12: én Hiroshima-detektor + fixtures. Ikke hele kvalitetsløftet.

Da er 90 dager fortsatt ambisiøst: en cockpit du *jobber i*, med evidens og stopp — ikke en vegg av leverandører.

---

## Anbefalt neste setning når du er klar

«Kjør port A. Ingen Jev, ingen Whisper, ingen FindingV2 i samme runde.»

Inntil den setningen: ikke mer produktkode. Dette dokumentet + [NEXT.md](NEXT.md) + kilden i Downloads er nok å være uenig i.
