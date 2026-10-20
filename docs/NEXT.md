# Neste bygg

Retningen: det feteste *lokale* kodemiljøet vi klarer, med Hiroshima som sikkerhetsrom som allerede ser. Ikke en omvei rundt SOC-kjernen. Ikke et nytt rammeverk.

H0–H5 er i treet og på verten. H6 Suricata er valgfri destinasjon. Tre kolonner, `repo_write`, grep→linje, loopback-preview, `repo_git` og cli som stopper etter verifikasjon er inne. **Neste er å bruke loopen på større systemer og stramme der den gnisser.**

---

## Arbeid — tre flater

Målet er Cursor-følelsen med én tiendedel av kromet: du snakker, du ser koden, du ser resultatet. Samme vindu. Loopen er allerede der (les → patch → `repo_bash` → preview).

```
┌──────────────┬─────────────────────┬─────────────────┐
│  cli         │  kode               │  preview        │
│  samtale     │  tre + Monaco       │  iframe av      │
│  plan tools  │  på disk            │  bygget         │
└──────────────┴─────────────────────┴─────────────────┘
         PTY bak knappen — passord der
```

Landet i denne runden: tre kolonner samtidig, `repo_edit` åpner fila i Monaco og laster preview på nytt når det er HTML, treet merker dirty og folder-åpner stien, tool-kort med path er klikkbare, PTY tar bare plass når den er åpen. Minne-dots sitter bak «kjøredetaljer».

### 1. Kode

Ikke Theia. Ikke full VS Code. Tydelig tre av workspace (default `~/kalived`, byttbar) og Monaco på fila du står i. Åpne / lagre / diff. `build` leser og patcher *filer på disk*.

### 2. Preview

Når bygget har noe å se (HTML, loopback-dev-server, statisk export), fyrer preview. Workspace-HTML og `preview_serve` på `127.0.0.1` er inne. Iframe venter til porten svarer. Ikke 0.0.0.0, ikke tilfeldig CDN.

### 3. Cli

Grok Build-flaten: du skriver hva som skal skje, orchestratoren planlegger, kaller tools, viser kort, fortsetter til oppgaven er ferdig, **stopper**. PTY er ved siden av for sudo.

Tools som `build` har i dag (cwd = workspace-rot, aldri hele `$HOME` som default):

| Tool | |
|------|--|
| `repo_glob` `repo_grep` `repo_read` | se (`read` har `start_line`) |
| `repo_write` | ny fil / hele fila |
| `repo_edit` | patch på disk; vis diff |
| `repo_bash` | én kommando, timeout, ingen `sudo` |
| `repo_git` | `status` `diff` `log` `commit` (commit bak haken). Aldri push |
| `preview_serve` | én tjener på `127.0.0.1` |
| `preview_set` | pek iframe på loopback-URL eller HTML |
| `ping` | health |

Haken «agent får kjøre» = write/edit/bash. Les er fritt. Oneshot per oppgave. Ingen LangChain. Samme `run_turn` + WS.

`git commit` via `repo_bash` er nektet — bruk `repo_git`. `git push` er nektet.

Landet i Arbeid: tre kolonner, `repo_write`, grep-treff åpner linja, ny fil fra treet, loopback-preview, `repo_git`, cli som stopper etter verifikasjon.

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
