# Docs

Kalived er to rom: **Arbeid** (kodemiljø) og **Hiroshima** (lokal SOC). Overordnet historie og daglig bruk: [../README.md](../README.md).

| Fil | Les når |
|-----|---------|
| [NEXT.md](NEXT.md) | **Neste steg** — forslag før vi koder mer. Rådfør her. |
| [REVIEW.md](REVIEW.md) | Svar på arkitekturkritikken (2026-09-24): inn/ut og kompromiss |
| [NOW.md](NOW.md) | **Hvor vi er i kveld** — Port A levert, neste er `repo_bash` |
| [PORT-A.md](PORT-A.md) | Port A (levert) |
| [COCKPIT.md](COCKPIT.md) | Hva som faktisk kjører på `:5173` / `:8788` i dag |
| [SURFACE.md](SURFACE.md) | Scan-kontrakt, CLI-flagg, finding-IDs, `:8787`-ruter |
| [../cockpit/PLAN.md](../cockpit/PLAN.md) | Teknisk cockpit-plan (Svelte, minne-lag, WS) |
| [../inventory/host.md](../inventory/host.md) | Denne maskinen |
| [../checklists/](../checklists/) | fase-0 og sec-runde |
| [../findings/](../findings/) | åpne/lukkede saker |
| [../remediation/CHANGELOG.md](../remediation/CHANGELOG.md) | hva playbooks faktisk gjorde |

Scan-sannhet er alltid `logs/status/<stamp>/verdict.json` og `echo $?` etter `kalived-ctl scan`. GUI finner ikke opp detektorer.
