# Port A — byggespesifikasjon (operativ)

Operativ plan: [REVIEW.md](REVIEW.md). Destinasjon: arkitekturkritikken i Downloads. Dette er **det som bygges nå**.

**Ikke i denne runden:** Jev, Whisper, nye providers, `repo_bash`, FindingV2, signert audit, NIM, ElevenLabs.

## Leveranse

Agentkonsoll + `build` + repo-tools mot `~/kalived` + workspace-tre/Monaco **på disk** + `repo_edit` bak haken + preview av HTML-fil/loopback. PTY er skuff, ikke agent.

Global knapp: **Stopp all agentaktivitet** — avbryt loop og tool calls, behold logger/diff. Ingen prosess-kill, ingen UFW.

Preview: statiske filer og allerede kjørende loopback. Build/dev-server kjører du i PTY. `repo_bash` = Port B.

## Etter A

Levert 2026-09-24 (konsoll, `build`, disk, tre, stopp, `up.sh`, minne-gate v0).
**Neste:** [NOW.md](NOW.md) — Port B `repo_bash`. Ikke mer Port A-detaljer.
