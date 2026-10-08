# Nå

To rom: **Arbeid** (lokal kode-cockpit) og **Hiroshima** (personlig host-SOC). Loopback. Tre trær. Overordnet: [../README.md](../README.md).

Sist avstemt mot treet 2026-10.

## Landet

| | |
|--|--|
| Kode-loop | Agentkonsoll, mappetre, Monaco på disk, `repo_bash`, HTML auto-preview, MiniLM + `decide()` |
| Minne | Fem lag. Jev → Mercury → rules. Kuzu-kanter `ABOUT` / `EDITED` / `USED` / `CONNECTED` |
| Hiroshima H0–H5 | Spekk, digest-port, ring+graf, env-overlay, Confirm isolate/kill/aide, 5-min egress-watch, Falco host-burst (`modern_ebpf`, custom yaml, tom jsonl = ingen finding) |
| Settings | Maskin + Nøkler. `watch_timer` styrer systemd |
| Verten | helper, nopasswd-ctl, auditd-connect, watch-timer, Falco-pakke (units masked). Scoped AIDE-freeze av kalived-filer |

Falco-burst mints ny stamp uten `KALIVED_OUT`. `hunt_falco.*` eies av operator 0600. Dual-source leser høyeste severity per funn-id (siste INFO overskriver ikke WARN). keylogscan tåler ubundet `HOME`.

Ærlig hygiene-WARN på en typisk vert etter install: VPN-snap, Falco unit-filer utenfor scope, lsmod vs gammel freeze. Sudoers/helper forsvinner etter scoped `aide-init --force`.

Chat-tester: [CHAT-TESTS.md](CHAT-TESTS.md).

## Neste

1. **Arbeid-editoren** — tettere tre, preview som følger bygget, cli som planlegger og stopper. UFO-kvalitet, samme loop. Se [NEXT.md](NEXT.md).
2. Valgfri Kuzu-tidslinje for scan-stamps og Confirm-playbooks (disk forblir orakel).
3. H6 Suricata — valgfri, ikke neste.
4. Port C (sandbox-VM, tale, mobil) — destinasjon.

## Ikke nå

Flere agenter, Theia, Whisper, FindingV2, strangle `:8787`, CrowdSec/Zeek, always-on tshark, auto-ban, `aide --all` som default.

## Planfiler

[HIROSHIMA.md](HIROSHIMA.md) · [NEXT.md](NEXT.md) · [SURFACE.md](SURFACE.md) · [COCKPIT.md](COCKPIT.md)
