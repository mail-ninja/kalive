# Neste bygg — forslag (ikke startet)

Skrevet for å **rådføre** før mer kode. Ingenting her er i treet som ferdig flate.

Retningen: det feteste *lokale* kodemiljøet vi klarer, med Hiroshima som sikkerhetsrom som vokser. Ikke en omvei rundt SOC-kjernen. Ikke et nytt rammeverk.

---

## Tre flater i Arbeid

I dag: chat til venstre, Monaco/iframe + PTY til høyre. Det er for flatt. Målet er tre *tydelige* jobber:

```
┌──────────────────────────┬─────────────────────┐
│  3. cli                  │  1. kode            │
│  samtale + plan + tools  │  filtre + Monaco    │
│  (orchestrator)          │  VS Code-ish, tynt  │
│                          ├─────────────────────┤
│                          │  2. preview         │
│                          │  iframe av bygget   │
└──────────────────────────┴─────────────────────┘
         PTY nederst eller bak «term» — passord der
```

### 1. Kode — filtre + Monaco

Ikke Theia. Ikke full VS Code. En **tydelig** trevisning av workspace (default `~/kalived`, byttbar) og Monaco på fila du står i. Åpne / lagre / diff. Agenten (`build` eller `forge`) leser og patcher *filer på disk*, ikke bare canvas-buffer.

Mindre komplisert enn VS Code betyr: ingen extension-host, ingen marketplace, ingen workspace-trust-dialog-helvete. Tastevaner der de er billige (Monaco).

### 2. Preview — iframe som viser fremgangen

Ikke en tom ramme. Når bygget *har* noe å se (HTML, lokal dev-server på loopback, statisk export), fyrer preview automatisk. `iframe_write` + `/v1/desk/preview` er v0. «UFO» her betyr: treffsikre reloads, loopback-URL, klikk-for-fokus, ikke tilfeldig CDN, ikke 0.0.0.0.

Preview er **resultat**. Cli er **arbeidet**.

### 3. Cli — der samtalen skjer

Dette er Grok Build / Claude Code / Gemini CLI-flaten: du skriver hva som skal skje, orchestratoren planlegger, kaller tools, viser kort (read / edit / grep / bash), fortsetter til oppgaven er ferdig, **stopper**.

Ikke en svart xterm med LLM-tekst. Transkript med struktur. PTY er ved siden av for sudo og ting du vil taste selv.

Ny agent **`build`**: eier repo-loopen. `crew` kan sende én oppgave hit. `forge` eier canvas/preview. `term` eier PTY-linjen.

Foreslåtte tools (repo-rot, aldri hele `$HOME` som default):

| Tool | |
|------|--|
| `repo_glob` `repo_grep` `repo_read` | se |
| `repo_write` `repo_edit` | patch; vis diff i cli |
| `repo_bash` | cwd=rot, timeout, ingen `sudo -S` |
| `repo_git` | status/diff/log; commit bare med bekreftelse |

Haken «agent får kjøre» = write/bash. Les er fritt. Oneshot per oppgave, maks ~24 runder. Rutine = cron.

Ingen LangChain. Ingen Semantic Kernel. Samme `run_turn` + WS.

---

## Hiroshima — grei nå, skal vokse

I dag: burst-scan, fire siler, AIDE-gate, oneshot `kalived-ctl` fra skuffen, signal som SOC-dom. Det *virker* som personlig snapshot-SOC. Det er ikke always-on EDR, og det skal ikke late som det.

Vekst (senere, eget løp, ikke blandet inn i cli-v1):

- bedre støy vs. funn (python-ESTAB mot xAI er self-noise)
- defs/IOC som faktisk mates, ikke bare filer
- persistens og «er dette *mitt*» uten å whitelist-e ALERT
- antimalware som **lokal** evidens, ikke sky-agent
- samme loud UX: CLEAN/WARN/ALERT, norsk, ingen hemmeligheter i git

Hiroshima skal bli vanskelig å komme utenom når du er redd for maskinen. Den skal ikke bli vanskelig å *bruke*. Scan-kjernen (`kalived-scan.sh`, siler, ctl, AIDE) rører vi ikke «fordi UI».

---

## Hva vi bevisst ikke gjør i neste steg

- Nytt FastAPI-prosjekt
- Strangle `:8787`
- Theia / Electron
- Auto-commit til `kalive`
- Agent som eier `sudo` uten xterm
- Docker rundt UI
- Åpne preview mot internett
- Bygge alle tre flatene og antimalware i samme PR

---

## Faser (anbefalt rekkefølge)

1. **Cli-v1** — fane + `build` + glob/grep/read mot `~/kalived`. Transkript. Ingen bash ennå.
2. **Kode-tre** — filtre i canvas-kode, Monaco åpner disk-fil, save synces.
3. **Edit** — `repo_edit` / `repo_write` + diff i cli. Haken på.
4. **Preview-kobling** — når HTML eller `:5173`-lignende loopback finnes, iframe følger.
5. **Bash** — `repo_bash` bak haken, timeout, allowlist-cwd.
6. **Hiroshima-støy** — egne PRs, egne siler. Ikke i samme sleng som cli.

Etter (1) sitter du i noe som ligner denne sesjonen, inne i kalived. Da er det lett å kjenne om retningen er feil *før* vi bygger tre + bash.

---

## Åpne spørsmål (si ifra)

1. Workspace-rot: bare `~/kalived`, eller velger du mappe?
2. Skal cli *erstatte* venstre chat i Arbeid, eller ligge som tredje canvas-knapp ved siden av monaco/iframe?
3. Preview av *denne* cockpiten mens vi bygger den (meta) — ja/nei?
4. `build` som eget navn, eller skal `forge` ta repo-tools?

Anbefaling herfra: **(2) cli erstatter venstre chat når du er i Arbeid** (orchestratoren *er* samtalen). Hiroshima beholder sin egen chat/verdict. Workspace default `~/kalived`. `build` som eget id. Preview meta nei i v1.
