# Docs

Kalived er to rom: **Arbeid** (kodemiljø) og **Hiroshima** (lokal host-SOC). Start her: [../README.md](../README.md). Deretter NOW → HIROSHIMA, så SURFACE/COCKPIT ved behov.

| Fil | Les når |
|-----|---------|
| [NOW.md](NOW.md) | Hvor koden og verten står |
| [NEXT.md](NEXT.md) | Neste bygg — Arbeid-editor først |
| [HIROSHIMA.md](HIROSHIMA.md) | SOC-protokoll H0–H6 |
| [SURFACE.md](SURFACE.md) | Scan-kontrakt, CLI, finding-IDs, `:8787` |
| [COCKPIT.md](COCKPIT.md) | `:5173` / `:8788` |
| [MEMORY.md](MEMORY.md) | Fem lag, MiniLM, Jev-gate |
| [JEV.md](JEV.md) | TypeSafe Jev — port, ikke chat |
| [CHAT-TESTS.md](CHAT-TESTS.md) | Paste-tester minne (M), kode (K), Hiroshima (H) |
| [../cockpit/PLAN.md](../cockpit/PLAN.md) | Teknisk cockpit-plan |
| [../checklists/](../checklists/) | fase-0 og sec-runde |
| [../remediation/CHANGELOG.md](../remediation/CHANGELOG.md) | hva playbooks faktisk gjorde |

Scan-sannhet er `logs/status/<stamp>/verdict.json` og `echo $?` etter `kalived-ctl scan`. GUI finner ikke opp detektorer. Baseline er merkelapp, ikke rent-host-bevis.

Port A/B-spec, kartleggingsnotat og arkitekturkritikk-svar er pensjonert — innholdet sitter i NOW, NEXT, COCKPIT og koden.
