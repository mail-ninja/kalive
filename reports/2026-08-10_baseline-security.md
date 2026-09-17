# Baseline security report — Kali host

| | |
|--|--|
| Dato | 2026-08-10 ~23:05 CEST |
| Scope | Lokal host-sikkerhet (porter, brannmur, MAC, tjenester, hardening) |
| Operator | void (uten full sudo i denne runden) |
| Snapshot | `logs/status/2026-08-10_2305/` |
| Inventory | `inventory/host.md` |

---

## 1. Executive summary

Maskinen er en **fysisk Lenovo** som kjører **Kali 2026.3**, på nett via **telefon-hotspot** (SSID MrT, `wlan0` → 192.168.155.0/24).

**Positivt**

- **Ingen uventede TCP-tjenester eksponert utad.** Alle kjente TCP-lytttere er bundet til `127.0.0.1`.
- **SSH-server kjører ikke** (inactive/disabled) — stor reduksjon i remote attack surface.
- **UFW er installert, enabled, service active**, med default INPUT **DROP** i config.
- Bluetooth, CUPS, Avahi inactive.
- Ingen containers kjører akkurat nå.
- Login-historikk ser ut som lokal desktop (`tty7`/lightdm); ingen SSH-fail-logg funnet.

**Hull / oppfølging**

- UFW-**regler** ikke dumpet (sudo-pass manglet) → F-001.
- **fail2ban** ikke installert → F-002.
- **AppArmor**-service disabled (modul lastet) → F-003. (Dette er «applocker»-analogen på Linux.)
- **Sysctl** ikke hardnet (ptrace, dmesg, rp_filter, …) → F-004.
- **docker**-gruppe = root-ekvivalent for `void` → F-005.
- VMware/VBox guest-utils enabled på bare metal → F-006.
- Ingen auto-patch / unattended-upgrades → F-007.

**Helhetsvurdering:** For en workstation bak telefon-NAT er baseline **rimelig rolig**. Største umiddelbare «unknown» er full brannmur-verifikasjon med sudo. Største strukturelle risikoer er Docker-privilegier og manglende sysctl/AppArmor-hardening — ikke åpne porter utad.

---

## 2. Nettverkstopologi (snapshot)

```
[Internett]
    │
[Telefon hotspot "MrT" WPA-PSK]
    │  gw 192.168.155.89
    │
wlan0 192.168.155.203/24  + IPv6 (RA)
    │
kali (host)
    ├── lo / 127.0.0.1  ← Cursor, svl, …
    ├── docker0 172.17.0.1 (down)
    └── br-agent-hub 172.19.0.1 (down)
```

IPv6 er **på** og har default route via link-local RA. Vurder senere om IPv6-policy i UFW er ønsket (config har `IPV6=yes`).

---

## 3. Porte og lyttere

### 3.1 TCP LISTEN (alle localhost)

| Port | Prosess | Vurdering |
|------|---------|-----------|
| 3080, 5174, 5433–5434, 6380–6381, 7475–7476, 7688–7689, 8002–8003, 8080, 8088, 8098, 9201, 9222, 27018 | `cursor` | Dev/editor — OK på loopback |
| 7878 | `svl` (semanticvoid-launcher host-pty) | Lokal PTY-bridge — OK på 127.0.0.1 |
| 34499 | (pid ikke resolved uten ekstra rettigheter) | Loopback only — monitor |

**Ingen** `0.0.0.0:` eller `*:port` TCP LISTEN funnet.

### 3.2 UDP / ikke-localhost

| Binding | Prosess | Vurdering |
|---------|---------|-----------|
| `*:45730`, `*:48563` UDP | x-www-browser | Typisk WebRTC — F-008 accepted/monitor |
| fe80::…%wlan0:546 UDP | (DHCPv6 client) | Forventet med IPv6 |

### 3.3 Etablert trafikk (utvalg)

Utgående HTTPS (443) fra browser, Cursor og `grok` til diverse CDN/cloud (Cloudflare, Google, GCP). Forventet for desktop/IDE. Ingen mistenkelige lyttere på LAN-IP.

Rådata: `logs/status/2026-08-10_2305/ss_tulpn.txt`, `scans/ports/2026-08-10_baseline.txt`.

---

## 4. Brannmur (UFW / netfilter)

| Sjekk | Resultat |
|-------|----------|
| Pakke ufw | installert 2026-08-07 |
| `/etc/ufw/ufw.conf` ENABLED | **yes** |
| `ufw.service` | enabled, active (exited) siden boot |
| Default INPUT | **DROP** |
| Default FORWARD | **DROP** |
| Default OUTPUT | **ACCEPT** |
| IPV6 | yes |
| `sudo ufw status` | **ikke kjørt** (passord kreves) |
| iptables/nft list | **ikke tilgjengelig** uten sudo |

**Konklusjon:** Config tyder på at UFW er på med fornuftige defaults, men **runtime-regler er ikke bekreftet**. Prioritet #1 neste steg: dump med sudo → `logs/ufw/`.

---

## 5. Access control / «AppLocker»

| Mekanisme | Status |
|-----------|--------|
| **AppArmor** (MAC) | Modul enabled; **service disabled/inactive**; profiler finnes |
| SELinux | Ikke i bruk (normalt for Kali) |
| fail2ban | **Ikke installert** |
| PAM / pwquality | libpam + libpwquality/cracklib til stede |
| Passordalder | `PASS_MAX_DAYS=99999` (utløper i praksis aldri) |
| Encrypt method | YESCRYPT |
| SSH authorized_keys | ingen for void |
| sudo | void i sudo-gruppen; ingen passwordless sudo (bekreftet: `sudo -n` feiler) |

---

## 6. Tjenester

### Kjørende (utvalg)

accounts-daemon, colord, **containerd**, cron, dbus, **docker**, getty@tty1, haveged, lightdm, ModemManager, NetworkManager, pcscd, polkit, rtkit, systemd-\*, udisks2, upower, wpa_supplicant, user@1000.

### Viktige disabled/inactive

- **ssh/sshd** — bra for attack surface
- **fail2ban** — mangler
- **apparmor.service** — disabled
- bluetooth, cups, avahi — inactive

### Merkeligheter

- `open-vm-tools` + `virtualbox-guest-utils` **enabled** på bare metal (F-006).
- `regenerate-ssh-host-keys.service` enabled (normalt on-first-boot mønster).

---

## 7. Docker

| | |
|--|--|
| Version | 28.5.2+dfsg4 |
| Containers | 0 |
| Images | 48 (mange dangling `<none>`, aegir-app ~10GB) |
| Networks | bridge, host, none, agent-hub_default |
| Bruker void | i `docker`-gruppen |

---

## 8. Kernel / sysctl (utdrag)

Se F-004. Spesielt svakt for en hardnet workstation: `ptrace_scope=0`, `dmesg_restrict=0`, `kptr_restrict=0`, `rp_filter=0`. `ip_forward=1` forventes med Docker.

---

## 9. Auth / konto

- Siste logins: lokal grafisk sesjon for `void` (flere dager tilbake til 5. aug).
- Ingen journal-treff for SSH-enhet; auth.log failed password ikke lesbar/treff tomt.
- postgres-bruker har `/bin/bash` men postgresql inactive — lav risk, kan strammes til nologin hvis ønskelig.

---

## 10. Findings index

| ID | Tittel | Severity | Status |
|----|--------|----------|--------|
| F-001 | UFW-regler ikke verifisert (sudo) | medium | **fixed** (2026-08-10_2321) |
| F-002 | fail2ban mangler | low→med | open |
| F-003 | AppArmor service disabled (kun docker-default) | medium | open |
| F-004 | Sysctl svake defaults | medium | open |
| F-005 | Docker-gruppe + image-rot | med / low | open |
| F-006 | Guest-utils på bare metal | low | open |
| F-007 | Ingen unattended-upgrades | low–med | open |
| F-008 | Browser UDP wildcard | info | accepted |

Detaljer: `findings/F-00x_*.md`.

---

## 11. Anbefalt rekkefølge (neste runde)

1. **Sudo-runde:** `ufw status verbose`, `nft list ruleset`, `aa-status` → dump til `logs/`.
2. Enable AppArmor-service hvis profiler ser sunne ut.
3. Sysctl-hardening (playbook; respekter Docker).
4. Disable guest-tools hvis ikke brukt.
5. Beslutning fail2ban (kan vente mens SSH er av).
6. Docker image prune / policy for docker-gruppe.
7. Manuell `apt update && apt full-upgrade` når du er klar; noter dato.

---

## 12. Begrensninger i denne runden

- Ingen root: kan ikke bekrefte live netfilter-kjeder eller full AppArmor-profilstatus.
- Ingen ekstern portscan fra annen host (kun local `ss`).
- Ingen malware/rootkit-scan (rkhunter/chkrootkit) — kan legges i senere runde.
- Nett er telefon-tether: god isolasjon mot hjemme-LAN, men public-side av mobil er utenfor scope.

---

## 13. Artefakter

```
reports/2026-08-10_baseline-security.md   ← denne filen
inventory/host.md
findings/F-001 … F-008
logs/status/2026-08-10_2305/*
scans/ports/2026-08-10_baseline.txt
baselines/ports_localhost_only.expected
checklists/sec-round.md
scripts/collect-baseline.sh
```
