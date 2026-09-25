# Port B — `repo_bash` (implementasjonsplan)

Ikke startet. **Ikke kode før operator sier GO.**

REVIEW.md pakket Port B med Groq, Jev og Hiroshima. [NOW.md](NOW.md) klemte det til **én evne**. Denne fila er den klemte planen.

## Hva det er

`build` kan kjøre **én kommando om gangen** i `~/kalived` (cwd = workspace-rot), med timeout, uten `sudo`, og bare når haken **agent får kjøre** er på.

Da kan loopen bli: plan → les → edit → **test/linter/`up.sh`-sjekk** → svar. Uten bash er vi en editor med prat. Med bash er vi et kodesystem på din maskin.

## Hva det ikke er (denne runden)

| Ut | Hvorfor |
|---|---|
| `sudo`, `sudo -S`, pipe-passord | Passord i PTY |
| Interaktiv tty (vim, less, passwd) | Timeout + capture stdout |
| Full sandbox-VM / nett-egress-kutt som hypervisor | Senere (Port C). Først cwd+timeout+deny-liste |
| Groq, Whisper, nye providers | Adapter etter at bash er kjedelig |
| Jev | Ingen routing-baseline ennå |
| FindingV2 / scan-kjerne | Egne PR-er |
| `git push` fra agent | Du eier remote. `git commit` er lov hvis du ba om det. |
| Vilkårlig `$HOME` | Bare workspace |
| Flere agenter | `build` får tool-et. `crew` kan `ask_agent` build |

## Sikkerhetsmodell (v0 gateway)

Samme hake som `repo_edit`. I tillegg **kode** som nekter, uansett hake:

1. cwd låst til `workspace.root()` — ingen `cd ..` ut.
2. Ingen shell-metachar som vi ikke vil ha: kjør **liste argv** (`["python3","-m","pytest",…]`) eller én linje som parses trygt. Anbefaling: **`argv: string[]`** primært, `line` kun hvis den ikke inneholder `sudo`, `| sudo`, `$(`, backticks mot root.
3. Blokker: `sudo`, `pkexec`, `chmod 777`, `rm -rf /`, skriving under `~/.config/kalived`, `curl|sh`, `dd if=`.
4. Timeout default **120 s**, maks **600 s**. Ved timeout: SIGTERM prosessgruppe, så SIGKILL. Returner `timeout` + logg-hale. Langlivet dev-server hører fortsatt hjemme i PTY/`up.sh`.
5. stdout/stderr cap ~**32 KiB** hver (hale hvis lengre).
6. `start_new_session=True` så vi kan drepe gruppa. Ikke `0.0.0.0`-bind i *våre* scripts; vi nekter ikke `npm` som allerede lytter loopback.
7. Stopp-knappen avbryter ventingen (cancel) og dreper pgid hvis jobb kjører.

Ikke «egress av» som nft-regler i B. Det er C.

## Tool

```
repo_bash
  mutating: true
  argv: string[]     # foretrukket
  line: string       # alternativ, én linje
  timeout_s: number  # 5–120, default 30
```

Retur:

```
{ argv, cwd, exit_code, timeout, stdout_tail, stderr_tail }
```

Lagres som engram `kind=tool` (som i dag). Ikke secrets i logg: rødakt linjer som matcher `sk-` / `API_KEY`.

`BUILD_TOOLS` += `repo_bash`. Playbook: bash er lov bak haken; `git commit`/`push` nei.

## UI

- Tool-kort viser kommando + exit + hale (som diff i dag).
- Ikke en ny fane. Ikke PTY-erstatning — PTY forblir der du taster sudo.
- Ved timeout: kortet sier timeout, agenten skal stoppe eller spørre — ikke restarte i evighet (eksisterende 8-runders tak).

## Implementasjon (rekkefølge)

1. `workspace.bash(argv, timeout)` i `workspace.py` — deny-liste, cwd, Popen, cap, killpg.
2. Tool `repo_bash` i `tools.py`, mutating, på `BUILD_TOOLS`.
3. Playbook `build.md`: når bruke bash (test, pytest, `python -m`, `npm test`); når ikke (sudo, commit).
4. WS/llm: ingen ny loop — `call_tool` er nok. Cancel: hvis `stop` under `subprocess.wait`, killpg (kjør wait i executor så event-loopen lever).
5. En røyk-test: `argv=["python3","-c","print(1)"]` → exit 0; `sudo` → error uten å kjøre; `sleep 5` med timeout 1 → timeout.

Ikke `up.sh` via bash i samme PR (den kan starte docker/sudo). Agenten kan *foreslå* at du kjører `up.sh` i PTY.

## Akseptanse

- Haken av: `repo_bash` returnerer mutating-feil, ingenting kjører.
- `python3 -c 'print("port-b")'` i workspace → stdout i kortet, exit 0.
- `sudo true` → nektet i kode.
- Path `cd /tmp && …` som argv som forlater rot → nektet (eller cwd ignoreres, alltid root).
- Timeout dreper, uvicorn lever, Stopp dreper ventingen.
- Ingen endring i `kalived-scan.sh` / `:8787`.

## Etter B (ikke denne PR)

Ekte embedder. Groq-adapter. Hiroshima-støy. Isolert runner.

## Åpne spørsmål (anbefaling i parentes)

1. **`argv` only, eller også `line`?** (Begge: `argv` først, `line` splittes med shlex, samme deny.)
2. **Får `crew` bash?** (Nei. Bare `build`. Crew dispatcher.)
3. **`npm run dev` via bash?** (Nei i B — langlivet. Timeout 30 s. Dev-server = PTY / `up.sh`.)
