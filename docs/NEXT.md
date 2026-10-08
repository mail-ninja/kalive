# Neste bygg

Retningen: det feteste *lokale* kodemiljøet vi klarer, med Hiroshima som sikkerhetsrom som allerede ser. Ikke en omvei rundt SOC-kjernen. Ikke et nytt rammeverk.

H0–H5 er i treet og på verten. H6 Suricata er valgfri destinasjon. **Neste kode er Arbeid-editoren.**

---

## Arbeid — tre flater

I dag: chat til venstre, Monaco/iframe + PTY til høyre. Loopen virker (les → patch → `repo_bash` → preview). Det er for flatt mot UFO-målet.

```
┌──────────────────────────┬─────────────────────┐
│  3. cli                  │  1. kode            │
│  samtale + plan + tools  │  tre + Monaco       │
│  (orchestrator)          │  på disk            │
│                          ├─────────────────────┤
│                          │  2. preview         │
│                          │  iframe av bygget   │
└──────────────────────────┴─────────────────────┘
         PTY nederst eller bak «term» — passord der
```

### 1. Kode

Ikke Theia. Ikke full VS Code. Tydelig tre av workspace (default `~/kalived`, byttbar) og Monaco på fila du står i. Åpne / lagre / diff. `build` leser og patcher *filer på disk*.

### 2. Preview

Når bygget har noe å se (HTML, loopback-dev-server, statisk export), fyrer preview. Workspace-HTML er inne. Loopback-app med treffsikre reloads er neste sjikt. Ikke 0.0.0.0, ikke tilfeldig CDN.

### 3. Cli

Grok Build-flaten: du skriver hva som skal skje, orchestratoren planlegger, kaller tools, viser kort, fortsetter til oppgaven er ferdig, **stopper**. PTY er ved siden av for sudo.

Tools som `build` har i dag (cwd = workspace-rot, aldri hele `$HOME` som default):

| Tool | |
|------|--|
| `repo_glob` `repo_grep` `repo_read` | se |
| `repo_edit` | patch på disk; vis diff |
| `repo_bash` | én kommando, timeout, ingen `sudo` |
| `ping` | health |

Haken «agent får kjøre» = edit/bash. Les er fritt. Oneshot per oppgave. Ingen LangChain. Samme `run_turn` + WS.

Ikke i treet ennå: `repo_write` som eget tool, `repo_git` (status/diff/commit bak bekreftelse). Commit i dag går via `repo_bash` når haken er på; `git push` er nektet i koden.

Landet i Arbeid: cli-v1, tre+Monaco, edit, HTML-preview, bash. Gjenstår: tettere tre-følelse, preview som følger en lokal app, cli som føles som ett sted å sitte.

---

## Hiroshima — vedlikehold, ikke neste feature

Burst-scan, fire siler, scoped AIDE, oneshot `kalived-ctl` fra skuffen, `signal` som SOC-dom, H1–H5. Personlig snapshot-SOC + opt-in 5-min egress. Det later ikke som always-on EDR.

Jev porter digest; Mercury på candidate; `signal` forklarer; ctl utfører. Telefon-hotspot = `tether` / `env_shift`. Falco alene = candidate; Falco+FIM/nett = ALERT. Scan-kjernen røres ikke «fordi UI».

Valgfritt senere: Kuzu-tidslinje over stamps og Confirm; H6 Suricata på aktiv uplink.

---

## Hva vi bevisst ikke gjør i neste steg

- Nytt FastAPI-prosjekt
- Strangle `:8787`
- Theia / Electron
- Auto-commit til remote
- Agent som eier `sudo` uten xterm
- Docker rundt UI
- Åpne preview mot internett
- H6 og editor i samme runde
