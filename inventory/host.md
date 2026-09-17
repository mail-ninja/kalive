# Host inventory

| Felt | Verdi |
|------|--------|
| Hostname | `kali` |
| OS | Kali GNU/Linux Rolling 2026.3 |
| Kernel | `7.1.5+kali-amd64` (#1 SMP PREEMPT_DYNAMIC Kali 7.1.5-1kali1, 2026-07-29) |
| Arch | x86_64 |
| Virt | none (bare metal) |
| Vendor / model | LENOVO / 21MC0059MX |
| Primary user | `void` (uid 1000), shell zsh, groups incl. `sudo`, `docker`, `vboxsf`, `libvirt` |
| Disk | `/dev/nvme0n1p2` ext4 ~454G (**95 %** brukt 2026-09-17; var ~74 % 2026-08-10) |
| Sist fase 0 | 2026-09-17 (`logs/status/2026-09-17_1443/`, `reports/2026-09-17_phase0-fresh-snapshot.md`) |

## Nettverk (fase 0 2026-09-17)

| Interface | State | Adresse | Merknad |
|-----------|-------|---------|---------|
| lo | UP | 127.0.0.1/8, ::1 | |
| eth0 | UP | 192.168.10.73/24 + IPv6 | kablet, default gw 192.168.10.1 metric 100 |
| wlan0 | DOWN | — | |
| proton0 | UP | 10.2.0.2/32 | ProtonVPN WireGuard (NL-FREE#212) |
| ipv6leakintrf0 | UP | dummy IPv6 | Proton killswitch |
| docker0 | DOWN | 172.17.0.1/16 | bridge, linkdown |
| br-283c3d8ea7b7 | DOWN | 172.19.0.1/16 | Docker network `agent-hub_default` |

- Default route: `192.168.10.1` via eth0 (DHCP). VPN-app holder ESTAB mot `10.2.0.1:65432`.
- Tidligere (2026-08-10): wlan0 hotspot SSID MrT. (2026-08-13): USB-tether usb0.

## Identiteter / shell-brukere

| User | UID | Shell | Notat |
|------|-----|-------|-------|
| root | 0 | zsh | |
| void | 1000 | zsh | primær, sudo |
| postgres | 119 | bash | PostgreSQL systembruker; tjeneste inactive |
| sync | 4 | /bin/sync | standard |

## Sikkerhetskomponenter (status)

| Komponent | Installert | Service | Notat |
|-----------|------------|---------|-------|
| UFW | ja (0.36.2-10, installert 2026-08-07) | enabled + active | **Verified 2026-08-10_2321:** deny in/out allow/routed deny; user rules empty; live INPUT drop |
| fail2ban | **nei** | — | |
| AppArmor | ja (4.1.7-5) | **enabled + active** (siden 2026-08-11 02:04) | Profiler reloaded; dump full `aa-status` valgfritt |
| SELinux | nei | — | forventet på Debian/Kali |
| firewalld | nei | — | |
| SSH server | config finnes | **masked / inactive** | ingen remote shell-lytter |
| Docker | ja 28.5.2 | enabled + running | 0 containers, 48 images; void ∈ docker |
| Bluetooth | — | inactive | |
| CUPS / Avahi | — | inactive | |

Firewall baseline: `baselines/firewall_ufw_default_deny.expected`

## Relaterte «gjest»-tjenester (på bare metal)

- `open-vm-tools.service` — **disabled** (F-006, 2026-08-13_1028; bekreftet 2026-09-17)
- `virtualbox-guest-utils.service` — **disabled** (samme)

SUID `vmware-user-suid-wrapper` ligger igjen. `void` er fortsatt i gruppen `vboxsf`.
