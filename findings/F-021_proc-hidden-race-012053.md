# F-021 — PROC-HIDDEN burst 2026-09-18_012053 (race, ikke implantat)

| | |
|--|--|
| Status | **accepted** (støy; sil 2 fantes ikke ennå) |
| Severity | info (kandidater, ikke bevist skjuling) |
| First seen | 2026-09-18_012053 |
| Closed | 2026-09-18 — PID-ene borte; sil 2–4 i hunt-procs |

## Observasjon

Scan `2026-09-18_012053` ALERT `PROC-HIDDEN` på PID 2452082–2452085.

- Fortløpende, rett etter `hunt-nmap` / `nmap -sT -p -` / `hunt-procs` i samme burst
- `vs_ss: match`, ingen skjulte lyttere
- Ingen ident (exe/cwd) ble samlet
- Timer senere: `/proc/PID` = No such file for alle fire

Første `/proc`−`ps`-diff er sil 1 (bulk). `ps` uten `-T` viser TGID; `/proc` lister også TID. nmap-tråder og døde barn lander der.

## Risiko

Ingen evidens for prosesskjuling. Å ALERT-e på raw-diff gjør støy og signal samme farge.

## Done-kriterium

`check-procs` ALERT-er ikke på `hidden_raw` alene. Tom `hidden_kept` → INFO `PROC-HIDDEN-NOISE`. Ekte hide (deleted/memfd + usynlig for `ps -eT`) → `PROC-HIDDEN`.

Ikke reboot og ikke `aide-init` «for å rydde» denne ALERT-en.
