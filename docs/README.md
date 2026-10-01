# Docs

Kalived er to rom: **Arbeid** (kodemiljø) og **Hiroshima** (lokal host-SOC). Start her: [../README.md](../README.md) (mål, stack, ambisjon, hvor vi er). Rådgiver: README → NOW → HIROSHIMA, deretter SURFACE/COCKPIT ved behov.

| Fil | Les når |
|-----|---------|
| [NOW.md](NOW.md) | **Hvor vi er** — 2026-10-01, H5 Falco i git |
| [HIROSHIMA.md](HIROSHIMA.md) | SOC-protokoll H0–H6. H0–H5 i treet; H0–H4 på host |
| [NEXT.md](NEXT.md) | Neste bygg. Live Falco-pakke / H6. Arbeid-flater delvis landet |
| [SURFACE.md](SURFACE.md) | Scan-kontrakt, CLI-flagg, finding-IDs, `:8787` |
| [COCKPIT.md](COCKPIT.md) | `:5173` / `:8788` — flater, agenter, HTTP |
| [MEMORY.md](MEMORY.md) | Fem lag, MiniLM, Jev-gate |
| [JEV.md](JEV.md) | TypeSafe Jev — adapter, Vercel Gateway |
| [CHAT-TESTS.md](CHAT-TESTS.md) | Paste-tester minne (M), kode (K), Hiroshima (H) |
| [KART.md](KART.md) | 2026-09-26 minne + kode-UI (historisk måling) |
| [REVIEW.md](REVIEW.md) | Arkitekturkritikk 2026-09-24 |
| [PORT-A.md](PORT-A.md) · [PORT-B.md](PORT-B.md) | Levert |
| [../cockpit/PLAN.md](../cockpit/PLAN.md) | Teknisk cockpit-plan |
| [../inventory/host.md](../inventory/host.md) | Denne maskinen |
| [../checklists/](../checklists/) | fase-0 og sec-runde |
| [../findings/](../findings/) | saker |
| [../remediation/CHANGELOG.md](../remediation/CHANGELOG.md) | hva playbooks faktisk gjorde |

Scan-sannhet er `logs/status/<stamp>/verdict.json` og `echo $?` etter `kalived-ctl scan`. GUI finner ikke opp detektorer. Baseline på denne verten er mistenkt.
