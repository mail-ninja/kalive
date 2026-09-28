# Nå — etter kvelds (2026-09-24)

Port A er **inne**. Ikke mer detaljpolering før neste hopp.

## Hva som nettopp skjedde

Du ba `build` forklare kalived. Første forsøk: den leste åtte docs og døde (reload/WS). Andre forsøk, med tak: to `repo_read` (README + COCKPIT) og et **ferdig svar** — to rom, loopback, tre trær, cockpit `:5173`/`:8788`. Minne-gaten skrev tool + chat. Det er loopen vi ville bevise.

## Port A er ferdig nok

Agentkonsoll, `build`, filer på disk, mappetre, Fil/Ctrl+S, stopp, `up.sh`, minne inn og ut (hash-vektor, sqlite-nøkkelord). Hiroshima er skuff, `:8787` valgfri. Det som gjenstår der er *tuning*, ikke mer produkt.

**Ikke nå:** flere agenter, Jev, Whisper, FindingV2, Theia, mer UI-knapper.

## Neste hopp (det som gjør det til et kodesystem)

Kart 2026-09-26: minne+UI målt.

**Port B, én ting:** `repo_bash` — cwd=`~/kalived`, timeout 120s (maks 600), ingen sudo/git push, haken på. **I treet.** `build` kan kjøre test og linter. Dev-server og passord = PTY.

Rett etter, samme uke, ikke samme PR:

1. Minne: MiniLM + **samme `decide()` på uthenting og skriving**. Graf: `path:`-noder + `ABOUT`/`EDITED`/`USED` på samme `memory_id` som sqlite/Qdrant. Se [MEMORY.md](MEMORY.md).
2. Preview: statisk HTML i boks. **Auto-iframe** ved `repo_edit`/klikk/lagre av `.html` (`/v1/workspace/raw`). Loopback-app senere.
3. Hiroshima: egen runde (Jev/tshark/Mercury) når du forklarer protokollen.

Chat-tester: [CHAT-TESTS.md](CHAT-TESTS.md). **M1–M4 + K1–K3 2026-09-28** (K3: stack oppe, pipe i argv = exit 6). Neste: auto-preview HTML, Hiroshima-protokoll.

Port C (sandbox-VM, NIM, tale, mobil) er destinasjon. Ikke neste.

## Når du er tilbake

Spes: [PORT-B.md](PORT-B.md). Si **GO** når den er ok.

Planfiler: [PORT-A.md](PORT-A.md), [PORT-B.md](PORT-B.md), [KART.md](KART.md) (måling 26.sep), [REVIEW.md](REVIEW.md).
