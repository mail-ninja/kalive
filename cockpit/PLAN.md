# kalived cockpit — plan (galskap inn fra dag 1)

Svelte er **ikke** pannekaker. Det er en UI-compiler (små bundles, mindre magi enn React).  
Security-API på `:8787` ligger. Dette er **agent-laget**. Dagens GUI flyttes ikke — den **embeds** som skuffen **Hiroshima**.

## Målbilde

```
browser  :5173  (Vite → Svelte)
    │  HTTP + WS
    ▼
cockpit FastAPI  :8788   ← agenter, tools, stream, editor-RPC
    │
    ├── iframe Hiroshima → kalived-api :8787  (urørt SOC)
    └── senere: security som FastAPI-modul, iframe vekk
```

Loopback only. Token (egen eller gjenbruk `api.token`). Ingen `0.0.0.0`.

## Secrets (Settings-fanen)

API-nøkler skrives i UI, **lagres ikke i nettleseren**.

- Fil: `~/.config/kalived/env` (samme som advisor), `chmod 600`
- `PUT /v1/secrets` tar verdier; `GET /v1/secrets` returnerer bare `{set, hint}` — aldri full nøkkel
- Tomt felt = uendret. Tøm med eksplisitt slett senere
- Ikke `localStorage`, ikke `config.toml`, ikke git
- Kjente nøkler: `XAI_API_KEY`, `INCEPTION_API_KEY`, `GITHUB_TOKEN`/`GH_TOKEN`, `X_BEARER_TOKEN` + `X_API_KEY`/`SECRET`/`ACCESS_TOKEN`

## Stack (låst nå, ikke «senere»)

| Lag | Valg | Hvorfor |
|-----|------|---------|
| UI | **Svelte 5 + Vite + TypeScript** | fetere enn React her; mindre seremoni |
| CSS | **Tailwind v4** + egne kalived-farger (mint/kobber/kirsebær) | ikke generic purple dashboard |
| Primitives | **bits-ui** + **lucide-svelte** | skuffer, dialog, tabs uten React |
| Editor | **Monaco** | se under |
| Terminal | xterm.js (allerede vendoret i 8787) — **slot** i cockpit; Hiroshima har PTY i dag |
| API | **FastAPI + uvicorn** + Pydantic v2 | OpenAPI gratis, WS native |
| Stream | **WebSocket multiplex fra commit 1** | ikke «vi tar WS senere» |
| Extra stream | SSE `/v1/chat/stream` som fallback | når proxy/WS streiker |
| Schemas | Pydantic (server) + **Zod** (klient) | samme tool-args begge veier |
| Agent | egen loop senere; **tool-registry tom men wired** | capability = funksjon + schema |

Ikke Next.js. Ikke Electron. Ikke Theia som skall (se editor).

## Python-runtime (låst)

Kali har en **Debian-`fastapi` som er et tomt namespace** (`/usr/lib/python3/dist-packages/fastapi` uten `FastAPI`-klassen). Derfor «ødelagt» — ikke at FastAPI-prosjektet er dødt. System-Python er ikke cockpit-Python.

| Valg | Til *denne* appen |
|------|-------------------|
| **`uv`** (anbefalt) | fetere venv: lockfil, lynrask install, én kommando. Lager likevel et `.venv`. |
| raw `venv` + pip | det vi har i `cockpit/backend/.venv` nå. Virker. Mer friksjon. |
| **Docker rundt cockpiten** | nei. Loopback-UI + senere host-tools (scan, PTY) hater et ekstra OS. |
| Docker *inni* et tool | ja, senere: «kjør denne untrusted tingen i en boks». Det er sandbox, ikke runtime. |
| Nix/Poetry/PDM | overkill til ett lokal-prosjekt. |

**Nå:** `uv` når det er installert (`curl -LsSf https://astral.sh/uv/install.sh | sh`), ellers venv som i `cockpit/scripts/dev.sh`.  
**Ikke:** `apt install python3-fastapi` som sannhet.

## Editor: Monaco, ikke Theia (nå)

**Theia** er et *IDE-produkt* (VS Code-kompatible extensions, workbench, Electron/browser). Du bygger en IDE og limer kalived inn. Tungt, treigt å theme, to livssykluser.

**Monaco** er *editor-komponenten* inne i VS Code. LSP, diff, multi-tab, samme tastevaner. Passer i en Svelte-rute ved siden av chat.

**CodeMirror 6** er lettere og mer Svelte-native, dårligere «ekte VS Code»-følelse.

**Nå:** Monaco i et pane, interface `EditorHost` (open/save/diff/setLanguage).  
**Senere, hvis du vil ha full IDE:** Theia som *egen modus* bak samme `EditorHost`. Ikke bytt skall til Theia i uke 1.

## WS-protokoll (inn fra dag 1)

Én socket `ws://127.0.0.1:8788/v1/ws?token=`. Multiplex:

```json
{ "v": 1, "ch": "chat"|"tools"|"editor"|"log"|"hiroshima", "id": "uuid", "type": "string", "payload": {} }
```

Kanaler:

| `ch` | `type` (eksempler) |
|------|-------------------|
| chat | `user`, `token`, `done`, `error` |
| tools | `list`, `call`, `result`, `log` |
| editor | `open`, `edit`, `save`, `diag` |
| log | `line` |
| hiroshima | `open`, `focus` (skuff) |

Hvis vi venter med dette, blir chat REST og tools «egne» sockets. Ikke.

## Mapper

```
cockpit/
  PLAN.md                 ← denne
  backend/app/main.py     FastAPI
  backend/app/ws.py       multiplex
  backend/app/tools.py    registry (tom + ping)
  web/                    Svelte 5 Vite
```

## Faser (korte)

1. **Heimsted** — dette: health, WS echo+chat-stub, Hiroshima-skuff (iframe :8787), Monaco «untitled».
2. **Capabilities** — første ekte tools (les fil i repo, kjør `kalived-advise --pb signal`, list snapshots). Confirm-gate på mutasjon.
3. **Agent-loop** — modell + tool-calls over samme WS.
4. **Merge** — security-ruter inn i FastAPI; Hiroshima slutter å ifram-e.

## Hva vi bevisst ikke rører

`scripts/kalived-scan.sh`, siler, `kalived-ctl`, AIDE-gaten, 8787-PTY. Finpuss SOC-GUI i Hiroshima, ikke i Svelte, før fase 4.
