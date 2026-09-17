# Fase 0 — ferskt snapshot (hard gate)

| | |
|--|--|
| Dato | 2026-09-17 ~14:43 CEST |
| Collect | `logs/status/2026-09-17_1443/` (komplett non-sudo etter `set -e`-fiks) |
| Delvis | `logs/status/2026-09-17_1442/` (avbrutt), `logs/status/2026-09-17_1444/` (sudo-prompt feilet) |
| Keylog | `logs/status/2026-09-17_1444_keylogscan/` |
| Manual | `logs/status/2026-09-17_144419_phase0_manual/` |
| Sudo i denne sesjonen | **nei** (`sudo -n` krever passord; ingen TTY-askpass) |

Sudo-scan kjørt: `logs/status/2026-09-17_145806/` — se `reports/2026-09-17_145806_scan.md`.
G3 live-regler dumpet: **8000 ALLOW IN Anywhere** (F-020). G8 event0: kun logind+Xorg.

---

## Executive verdict

**Ingen ALERT-klasse med dagens verktøy på det vi *kunne* se.** Ingen eksterne TCP-lyttere, SSH masked, ingen `ld.so.preload`, ingen extra UID 0, ingen void `authorized_keys`, ingen deleted execs i lesbart `/proc`, ingen remote logins.

| Gate | Resultat | Merknad |
|------|----------|---------|
| G1 TCP utenfor localhost | **PASS** | `ALERT_non_localhost_tcp.txt`: OK none. Kun `127.0.0.1:45959` (prosess uidentifisert uten root) |
| G2 SSH | **PASS** | `inactive` + **masked** |
| G3 UFW live-regler | **UVERIFISERT** | service enabled+active, `ENABLED=yes`, `LOGLEVEL=low`. Live nft/user-rules krever sudo |
| G4 ld.so.preload | **PASS** | absent |
| G5 authorized_keys | **PASS** (void) / **UVERIFISERT** (root) | void: fil mangler. root: sudo |
| G6 extra UID 0 | **PASS** | kun `root` |
| G7 deleted exe | **PASS** | `find /proc -maxdepth 2 -name exe`: none |
| G8 `/dev/input/event*` | **UVERIFISERT** | noder finnes (event0–15, root:input). `lsof` krever sudo |
| G9 remote logins | **PASS** | `last`: kun `:0` / tty7 / lightdm. journal `ssh`: tom |
| G10 reverse-shell | **PASS** (tolket) | python3 pid 3756 = **Proton VPN** (`/snap/proton-vpn/10/usr/bin/protonvpn-app`) mot `10.2.0.1:65432` (VPN-gw). grok/chromium :443/:5228 forventet |

**Rebuild:** read-only detektorer (PR 2–5) **kan** landes. Muterende playbooks (PR 6 auditd/journald/UFW-logging, PR 7 AIDE, PR 10 rkhunter) **venter** på sudo-bekreftet G3+G8.

Machine-baselines (`baselines/machine/`) fryses **ikke** fra dette snapshotet — freeze etter sudo-scan.

---

## Hva som endret seg siden 2026-08-13

| | Aug 13 | Sep 17 |
|--|--------|--------|
| Kernel | `7.0.12+kali-amd64` | `7.1.5+kali-amd64` (2026-07-29 pakke) |
| Nett | USB-tether `usb0` / wlan hotspot | **eth0** `192.168.10.73/24` gw `192.168.10.1`; **ProtonVPN** `proton0` `10.2.0.2/32` |
| Disk | ~74 % | **95 %** (`408G/454G`) — hygiene, ikke innbrudd |
| Guest-utils | disabled 2026-08-13_1028 | **bekreftet disabled** (inventory var stale) |
| Docker | 0 containers, daemon on | 0 containers, daemon **active**, 48 images |
| dpkg | sist notert 2026-08-07 | aktivitet **2026-09-17 12:39** (man-db, kali-menu) — F-007 ikke lenger «>30 dager stille» |

## WARN / hygiene (stopper ikke rebuild)

- Docker-socket oppe, 0 containere (F-005) — `void` ∈ docker + vboxsf + libvirt
- `vmware-user-suid-wrapper` SUID fortsatt
- UFW logging **low** (F-017)
- Chromium mDNS UDP `224.0.0.251:5353`; UDP wildcard `:56324` uten prosessnavn (F-008-klasse)
- Proton VPN `LD_PRELOAD=.../bindtextdomain.so` — forventet snap, ikke keylogger
- Uidentifisert loopback-lytter `127.0.0.1:45959` (ss uten prosess — typisk root-eid; lukkes med sudo `ss -tlnp`)
- Disk 95 %

## Keylogscan (non-sudo)

- Ingen logkeys-pakker; ingen keylog-prosessnavn (self-hit på scriptet)
- `ld.so.preload` absent; user crontab tom; autostart grep none
- LD_PRELOAD kun Proton VPN bindtextdomain

## Collect-fiks

`scripts/collect-baseline.sh` døde med exit 3 på `systemctl is-active ssh` (`set -e`). Hver `systemctl is-*` har nå `|| true`. Snapshot `1443` er det kanoniske non-sudo bildet.

## Neste

1. Operator: `sudo ./scripts/kalived-scan.sh` (når orkestrator finnes) **eller** `sudo KALIVED_SUDO=1 ./scripts/collect-baseline.sh` + `sudo lsof /dev/input/event*` for å lukke G3/G8.
2. PR 2: `kalived-scan.sh` — **live scan krever root**.
