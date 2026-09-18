# Threat definitions (kalived)

Oppdaterbare lister scannen bruker. **Nyheter ≠ signaturer.**

Tillitsmodell:

| Lag | Sti | Verdict |
|-----|-----|---------|
| Git IOC | `defs/ioc/*.txt` | ALERT (kjent navn/port) |
| Kali-allow | `defs/kali-allow/` | sil 2 — kast vendor-støy |
| Remote cache | `defs/cache/*.remote.txt` | WARN inntil det merges i git |
| News / CISA KEV | `feeds.d/*.example` | kontekst, **aldri** ALERT |

| Kilde | Type | Brukes nå |
|-------|------|-----------|
| rkhunter `--update` | rootkit-filer / hashes | ja (`enabled=1`) |
| `local-ioc` | kopi av git-lister til cache | ja |
| URLhaus | url-ioc → hostnames i cache | nei (`enabled=0`) |
| CISA KEV / The Register | json-cve / news | nei — aldri ALERT |

Oppdater (parallelt rkhunter + enabled HTTP):

```bash
sudo kalived-ctl defs
```

Aldri `eval` av nedlastet innhold. Feeds skrives til `defs/cache/` og parses som data.
`MANIFEST.json` i cache er evidens for hva som ble hentet.
