# Neste bygg — forslag

Skrevet for å **rådføre** før mer kode. Retningen: det feteste *lokale* kodemiljøet vi klarer, med Hiroshima som sikkerhetsrom som vokser. Ikke en omvei rundt SOC-kjernen. Ikke et nytt rammeverk.

**Landet 2026-09-30** (ikke les resten som «ikke startet»): Port A/B, MiniLM+`decide()`, HTML-preview, Hiroshima H0–H4 på verten (scan, ring, Gal=`tether`, Confirm, watch-timer). Hvor vi er: [NOW.md](NOW.md). Produkt: [../README.md](../README.md).

**Neste kode:** H5 Falco (host-regler, container av). Arbeid-flatene under er delvis inne (venstre konsoll + tre + Monaco + iframe); det som gjenstår der er tettere VS Code-følelse, ikke en ny app.

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

## Hiroshima — H4 i treet, H5 neste

I dag: burst-scan, fire siler, AIDE-gate, oneshot `kalived-ctl` fra skuffen, signal som SOC-dom, H1–H4 (ring, Gal-overlay, Confirm, rolling watch på verten). Personlig snapshot-SOC + opt-in 5-min egress. Det later ikke som always-on EDR.

Protokoll: [HIROSHIMA.md](HIROSHIMA.md) (H0–H4, 2026-09-30). Jev porter digest; Mercury på candidate; `signal` forklarer; ctl utfører. Gal (telefon-hotspot) = `tether`. Overlay + Confirm isolate/aide + watch i skuffen. Falco er H5. Scan-kjernen rører vi ikke «fordi UI». Baseline-allow er merkelapp, ikke rent-host-bevis.

Neste kode: **H5** — Falco host-regler (container-regler av) inn i samme kandidat-ring.

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

## Faser (Arbeid — 1–5 landet)

1. **Cli-v1** — landet. `build` + glob/grep/read, transkript.
2. **Kode-tre** — landet. Monaco på disk.
3. **Edit** — landet. `repo_edit` / `repo_write` bak haken.
4. **Preview-kobling** — landet for workspace-HTML. Loopback-app senere.
5. **Bash** — landet. `repo_bash` bak haken, timeout, cwd=rot.
6. **Hiroshima** — H0–H4 landet; **H5 Falco** er neste SOC-kode.

Gjenstår i Arbeid: tettere tre-følelse, ikke ny app. Workspace default `~/kalived`. `build` som eget id.

---

Etter 2026-09-24-kritikken: [REVIEW.md](REVIEW.md). Agentkonsoll = venstre; `build` eier repo-loopen; policy-gate er kode. Jev er i minne-gaten. Whisper er ikke neste.
