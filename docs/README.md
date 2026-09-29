# Docs

Kalived er to rom: **Arbeid** (kodemiljø) og **Hiroshima** (lokal SOC). Overordnet historie og daglig bruk: [../README.md](../README.md).

| Fil | Les når |
|-----|---------|
| [NEXT.md](NEXT.md) | **Neste steg** — forslag før vi koder mer. Rådfør her. |
| [REVIEW.md](REVIEW.md) | Svar på arkitekturkritikken (2026-09-24): inn/ut og kompromiss |
| [KART.md](KART.md) | **2026-09-26** minne + kode-UI: bygd, test, ønsket slutt, hull |
| [MEMORY.md](MEMORY.md) | **Skriving og recall** — fem lag, MiniLM, Jev-gate |
| [CHAT-TESTS.md](CHAT-TESTS.md) | Paste-tester for minne (M), kode-loop (K) og Hiroshima (H) |
| [HIROSHIMA.md](HIROSHIMA.md) | **Hiroshima-protokollen** — H0 spekk, H1 port i treet 2026-09-29 |
| [JEV.md](JEV.md) | TypeSafe Jev — research, adapter, Vercel Gateway |
| [NOW.md](NOW.md) | Hvor vi er — Port A/B levert |
| [PORT-A.md](PORT-A.md) | Port A (levert) |
| [PORT-B.md](PORT-B.md) | Port B — `repo_bash` (i treet) |
| [COCKPIT.md](COCKPIT.md) | Hva som faktisk kjører på `:5173` / `:8788` i dag |
| [SURFACE.md](SURFACE.md) | Scan-kontrakt, CLI-flagg, finding-IDs, `:8787`-ruter |
| [../cockpit/PLAN.md](../cockpit/PLAN.md) | Teknisk cockpit-plan (Svelte, minne-lag, WS) |
| [../inventory/host.md](../inventory/host.md) | Denne maskinen |
| [../checklists/](../checklists/) | fase-0 og sec-runde |
| [../findings/](../findings/) | åpne/lukkede saker |
| [../remediation/CHANGELOG.md](../remediation/CHANGELOG.md) | hva playbooks faktisk gjorde |

Scan-sannhet er alltid `logs/status/<stamp>/verdict.json` og `echo $?` etter `kalived-ctl scan`. GUI finner ikke opp detektorer.
