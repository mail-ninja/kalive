# Kanban

Lite brett med tre kolonner (todo / doing / done). State i `localStorage` (`kanban-v1`).

## Funksjoner

1. Dra-og-slipp mellom kolonner
2. Tastatursnarvei: `n` = nytt kort, `1`/`2`/`3` = flytt valgt til todo/doing/done
3. Søkefelt som filtrerer kort
4. Prioritet på kort (lav / mid / høy)
5. Forfallsdato
6. Tags
7. Eksport/import JSON via knapper
8. Lys/mørk-toggle
9. Test uten DOM: `node docs/_lab/kanban/test.mjs`
10. Tom-tilstand-tekst i hver kolonne
11. Bekreft før slett
12. Stats-linje med antall per kolonne

Kjernelogikk (load/save, uten DOM) ligger i `store.mjs`.

## Preview

Start en lokal tjener på `docs/_lab/kanban` og pek iframe mot `index.html` (f.eks. `http://127.0.0.1:PORT/index.html`).
