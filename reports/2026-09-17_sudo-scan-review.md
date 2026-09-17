# Sudo-scan 2026-09-17_145806 — gjennomgang

| | |
|--|--|
| Kommando | `sudo ./scripts/kalived-scan.sh` |
| Snapshot | `logs/status/2026-09-17_145806/` (eid root:root) |
| Maskin-verdict | **CLEAN** (exit 0, tom `findings.jsonl`) |
| Etter manuell gjennomgang | **Ikke hermetisk CLEAN** — F-020 |

---

## Er jeg enig i CLEAN?

**Enig i det PR 2 faktisk sjekket:**

| Sjekk | Resultat | Belegg |
|-------|----------|--------|
| TCP LISTEN utenfor localhost | ingen | kun `127.0.0.1:45959` **containerd** |
| SSH | inactive | `sec_units.txt` |
| Extra UID 0 | kun root | `passwd.txt` |
| ld.so.preload | absent | keylog |
| event0 | systemd-logind + Xorg | forventet |
| Root crontab | none | |
| Keylog-pakker | none | self-hit på script-navn |

**Ikke enig i CLEAN som «maskinen er ferdig sjekket».** Scannen **samlet** UFW/nft men **vurderte dem ikke**. August-baseline krevde tomme user-regler.

## F-020 (det banneret hoppet over)

```
8000                       ALLOW IN    Anywhere
8000 (v6)                  ALLOW IN    Anywhere (v6)
```

nft: `tcp/udp dport 8000 accept`, **0 pakker**. Ingen LISTEN på :8000 nå.

Åpent hull, ikke aktiv bakdør. Skal være ALERT. G3 mot `baselines/firewall_ufw_default_deny.expected` er **ikke** grønn.

## G-tabell etter sudo

| Gate | 145806 |
|------|--------|
| G1 | PASS |
| G2 | PASS |
| G3 | **avvik** — deny-default OK, user-allow 8000 (F-020) |
| G4–G7 | PASS |
| G8 | PASS event0; `event*` ikke scannet |
| G9–G10 | PASS (ProtonVPN python mot 10.2.0.1 er VPN, ikke shell) |

## Støy i terminalen (fikset i koden etter denne runden)

- `aa-status` (147 profiler) dumpet to ganger til TTY
- keylogscan som root leste kernel-tråder (`/proc/2/environ` …)
- `groups.txt` ble `root` i stedet for void
- snapshot + `reports/2026-09-17_145806_scan.md` eid av root

## Før vi går videre

Ikke freeze AIDE/baselines på denne CLEAN. Neste sudo-scan skal ALERT-e på 8000. Enten `sudo ufw delete allow 8000` hvis utilsiktet, eller dokumenter det som accepted.
