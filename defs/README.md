# Threat definitions (kalived)

Oppdaterbare lister scannen bruker. **Nyheter ≠ signaturer.**

| Kilde | Type | Brukes nå | Kommentar |
|-------|------|-----------|-----------|
| rkhunter mirrors (`rkhunter --update`) | rootkit-filer / hashes | **ja** | offisiell DB |
| `defs/kali-allow/` | whitelist for Kali-støy | **ja** | lokale unntak, ikke «maskering» av unknown |
| `defs/ioc/` | hashes / domen / YARA | nei (stub) | fremtid |
| The Register / nyhetssider | kontekst | nei | RSS kan bli `type=news` senere, **ikke** ALERT-grunnlag |
| URLhaus, CISA KEV, OpenPhish | IOC-feeds | nei (eksempel i `feeds.d/`) | bedre enn nyheter for «siste skrik» |

Oppdater:

```bash
sudo ./scripts/update-threat-defs.sh
```

Aldri `eval` av nedlastet innhold. Feeds skrives til `defs/cache/` og parses som data.
