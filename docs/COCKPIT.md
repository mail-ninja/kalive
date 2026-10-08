# Cockpit

Svelte 5 + Vite (`:5173`) mot FastAPI (`:8788`). Loopback only. Plan: [../cockpit/PLAN.md](../cockpit/PLAN.md).

```bash
bash cockpit/scripts/up.sh
# UI  http://127.0.0.1:5173
# API http://127.0.0.1:8788/v1/health
```

`dev.sh` er tynnere variant uten minne-compose.

## Flater

```
http://127.0.0.1:5173
  ├── Arbeid     chat | tre + Monaco | iframe-preview | cockpit-PTY
  ├── Settings   Maskin → config.toml · Nøkler → env (hint, aldri full nøkkel)
  └── Hiroshima  skuff: verdict + protocol + ring + watch + Confirm + PTY
```

Hiroshima iframes ikke `:8787`. Den eldre API-en kan kjøre (`sudo kalived-ctl api`). Vi strangle-r den ikke.

## Agenter

Minne følger `agent_id`. Provider er munnstykke.

| id | desk | Rolle |
|----|------|--------|
| `build` | code | repo-loop på disk (`repo_glob/grep/read/edit/bash`) |
| `crew` | code | dirigent, `ask_agent` → build/forge/review/term |
| `forge` | code | skriver canvas; spill/app → `iframe_write` |
| `review` | code | leser canvas |
| `term` | code | eier xterm (`term_send` bak «agent får kjøre») |
| `signal` | soc | SOC-dom |
| `dummy` / ops | any | `prompts/advisor.md` |
| `mercury` | any | Inception som munnstykke |
| `swarm` | code | alias for crew |

Chip-raden i Arbeid viser `build`. Andre agenter under kjøredetaljer.

Tool-loop: OpenAI-kompatible function calls mot SpaceXAI (`grok-4.6`) eller Settings. Mutasjon krever haken. Passord aldri i chat.

Spill i iframe: HTML på disk via `GET /v1/workspace/raw?path=…` (f.eks. `docs/_probe.html`), eller `iframe_write`. Live stdout under `repo_bash`.

## HTTP på :8788 (utvalg)

| | |
|--|--|
| `GET /v1/health` | oppe |
| `GET /v1/agents` | register |
| `WS /v1/ws` | multiplex chat/tools/editor/log/hiroshima |
| `WS /v1/term` | lokal forkpty (denne uid) |
| `GET /v1/hiroshima/verdict` | siste ekte scan (`verdict.json` + `protocol.json`, ring, watch) |
| `GET /v1/hiroshima/watch` | siste egress-vindu |
| `POST /v1/hiroshima/scan` | oneshot `sudo -n kalived-ctl scan` |
| `POST /v1/hiroshima/run` | Confirm-playbook |
| `GET/PUT /v1/hiroshima/env` | SSID → `home`/`travel`/`tether` |
| `GET/POST /v1/desk/preview` `/play` | iframe-innhold |
| `/v1/memory/{agent}/…` | Kuzu / Qdrant / SQLite / MinIO / Redis |
| `GET/PUT /v1/secrets` | env, write-only |
| `GET/PUT /v1/config` | `config.toml` |

Scan-jobber overlever WS-kutt. Rutine = `kalived-scan.timer`, ikke agent-loop.

## Minne-lag

Se [MEMORY.md](MEMORY.md). MiniLM henter → Jev (ellers Mercury, ellers rules) velger `keep`/`act` → Grok → samme `decide()` merker slutt-engramet.

| Lag | Hvor | Hvis nede |
|-----|------|-----------|
| Kuzu + SQLite | `~/.config/kalived/memory/<id>/` | alltid (embedded) |
| Qdrant :6333, Redis :6379, MinIO :9100 | `cockpit/memory/compose.yml` | cockpit kjører; vektor/buss/blob 503 |

Docker rundt **bare** de tre tjenerne. Ikke rundt UI.

## :8787 vs :8788

| | 8787 | 8788 |
|--|------|------|
| Hva | eldre kalived-api (stdlib) | cockpit |
| Root | ja, når `kalived-ctl api` | nei. Scan via ctl |
| GUI | `api/static` | Svelte |
| Status | urørt | det vi bygger i |

PTY i cockpit er lokal (uid til uvicorn). Root-shell er 8787-xterm hvis den API-en startes med sudo.
