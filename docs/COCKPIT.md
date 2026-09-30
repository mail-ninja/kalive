# Cockpit — det som finnes

Svelte 5 + Vite (`:5173`) mot FastAPI (`:8788`). Loopback only. Plan-detaljer: [../cockpit/PLAN.md](../cockpit/PLAN.md).

Start: `bash cockpit/scripts/dev.sh`.

## Flater

```
http://127.0.0.1:5173
  ├── Arbeid     chat | canvas (monaco | iframe) | cockpit-PTY
  ├── Settings   Maskin → config.toml · Nøkler → env (hint, aldri full nøkkel)
  └── Hiroshima  skuff: verdict + protocol + ring + watch + Confirm + PTY
```

Hiroshima **iframes ikke** `:8787`. Den gamle API-en kan fortsatt kjøre (`sudo kalived-ctl api`) for den opprinnelige SOC-GUIen. Vi strangle-r den ikke.

## Agenter

Minne følger `agent_id`. Provider er munnstykke.

| id | desk | Rolle |
|----|------|--------|
| `build` | code | repo-loop på disk (`repo_glob/grep/read/edit/bash`) |
| `crew` | code | dirigent, `ask_agent` → build/forge/review/term |
| `forge` | code | skriver canvas; spill/app → `iframe_write` |
| `review` | code | leser canvas |
| `term` | code | eier xterm (`term_send` bak «agent får kjøre») |
| `signal` | soc | SOC-dom, sil 4 |
| `dummy` / ops | any | terminal-sec, `prompts/advisor.md` |
| `mercury` | any | Inception som munnstykke |
| `swarm` | code | alias for crew |

Tool-loop: OpenAI-kompatible function calls mot SpaceXAI (`grok-4.6`) eller det du har i Settings. Maks runder, oneshot. Mutasjon krever haken. Passord aldri i chat.

Spill i iframe: HTML **på disk** via `GET /v1/workspace/raw?path=…` (f.eks. `docs/_probe.html`), eller `iframe_write` / `POST /v1/desk/play`. Live stdout under `repo_bash` i agentkonsollen.

## HTTP på :8788 (utvalg)

| | |
|--|--|
| `GET /v1/health` | oppe |
| `GET /v1/agents` | register |
| `WS /v1/ws` | multiplex chat/tools/editor/log/hiroshima |
| `WS /v1/term` | lokal forkpty (denne uid) |
| `GET /v1/hiroshima/verdict` | siste ekte scan (`verdict.json` + `protocol.json`, ring, watch) |
| `GET /v1/hiroshima/watch` | siste egress-vindu (felter, 0600) |
| `POST /v1/hiroshima/scan` | oneshot `sudo -n kalived-ctl scan`, watchdog 15 min |
| `POST /v1/hiroshima/run` | Confirm-playbook (`watch`, `isolate-dst`, `aide-init`, …) |
| `GET/PUT /v1/hiroshima/env` | SSID → `home`/`travel`/`tether` |
| `GET/POST /v1/desk/preview` `/play` | iframe-innhold |
| ` /v1/memory/{agent}/…` | Kuzu / Qdrant / SQLite / MinIO / Redis |
| `GET/PUT /v1/secrets` | env, write-only |
| `GET/PUT /v1/config` | `config.toml` (watch_timer, skip_rootkit, loopback-lås) |

Scan-jobber overlever WS-kutt. Når prosessen er død: `done` + stopp. Rutine = `kalived-scan.timer`, ikke agent-loop.

## Minne-lag

Se [MEMORY.md](MEMORY.md). Kort: MiniLM henter kandidater → **Jev** (ellers Mercury-2.5, ellers rules) velger `keep`/`act` → Grok → **samme decide()** merker slutt-engramet. Verifisert uthenting `src=jev+rules` 2026-09-28. Tool-engrams er korte. Disk vinner.

Alle agenter bruker alle lag. Namespace `kalived:{agent_id}:`.

| Lag | Hvor | Hvis nede |
|-----|------|-----------|
| Kuzu + SQLite | `~/.config/kalived/memory/<id>/` | alltid (embedded) |
| Qdrant :6333, Redis :6379, MinIO :9100 | `cockpit/memory/compose.yml` | cockpit kjører; vektor/buss/blob 503 |

Docker rundt **bare** de tre tjenerne. Ikke rundt UI.

## :8787 vs :8788

| | 8787 | 8788 |
|--|------|------|
| Hva | gammel kalived-api (stdlib) | cockpit |
| Root | ja, når `kalived-ctl api` | nei (void). Scan via ctl |
| GUI | `api/static` | Svelte |
| Status | urørt | det vi bygger i |

PTY i cockpit er **lokal** (uid til uvicorn). Root-shell er fortsatt 8787-xterm hvis du starter den API-en med sudo.
