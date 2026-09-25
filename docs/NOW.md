# Nå — etter kvelds (2026-09-24)

Port A er **inne**. Ikke mer detaljpolering før neste hopp.

## Hva som nettopp skjedde

Du ba `build` forklare kalived. Første forsøk: den leste åtte docs og døde (reload/WS). Andre forsøk, med tak: to `repo_read` (README + COCKPIT) og et **ferdig svar** — to rom, loopback, tre trær, cockpit `:5173`/`:8788`. Minne-gaten skrev tool + chat. Det er loopen vi ville bevise.

## Port A er ferdig nok

Agentkonsoll, `build`, filer på disk, mappetre, Fil/Ctrl+S, stopp, `up.sh`, minne inn og ut (hash-vektor, sqlite-nøkkelord). Hiroshima er skuff, `:8787` valgfri. Det som gjenstår der er *tuning*, ikke mer produkt.

**Ikke nå:** flere agenter, Jev, Whisper, FindingV2, Theia, mer UI-knapper.

## Neste hopp (det som gjør det til et kodesystem)

**Port B, én ting:** `repo_bash` — cwd=`~/kalived`, timeout 120s (maks 600), ingen sudo/git push, haken på. **I treet.** `build` kan kjøre test og linter. Dev-server og passord = PTY.

Rett etter, samme uke, ikke samme PR:

1. Minne: ekte embedder når bash-loopen er kjedelig å rose (ikke før).
2. Preview av loopback som *allerede kjører* (Vite gjør det).
3. Hiroshima: egen PR, støy vi kjenner — ikke i bash-uken.

Port C (sandbox-VM, NIM, tale, mobil) er destinasjon. Ikke neste.

## Når du er tilbake

Spes: [PORT-B.md](PORT-B.md). Si **GO** når den er ok.

Planfiler: [PORT-A.md](PORT-A.md) (levert), [PORT-B.md](PORT-B.md) (neste), [REVIEW.md](REVIEW.md) (destinasjon).
