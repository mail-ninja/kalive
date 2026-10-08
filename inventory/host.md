# Host inventory

Live facts about a specific workstation (hostname, serial, LAN-IP, SSID, brukernavn) hører **ikke** i git. De ligger i scan-snapshots under `logs/status/<stamp>/` (ikke i repoet) og i `~/.config/kalived/`.

Denne fila beskriver *hva* vi noterer, ikke *denne* maskinen.

| Felt | Hvor det leses |
|------|----------------|
| OS / kernel / arch | `uname`, `/etc/os-release` |
| Virt vs bare metal | systemd-detect-virt |
| Disk | `df` — ikke commit fyllingsprosent |
| Nett | `ip route`, `nmcli` — ikke commit SSID eller LAN-IP |
| Bruker | `$USER` / `KALIVED_OWNER` — ikke commit uid-tabell |
| UFW / AppArmor / SSH / Docker | siste `verdict.json` |

Forventet kalived-layout på en Kali-vert:

- Loopback-lyttere: cockpit `:5173` / `:8788`, eldre API `:8787`, minne-docker `:6333` `:6379` `:9100`
- ProtonVPN (`proton0`, DNS `10.2.0.1`) er kjent unntak, ikke ALERT
- SSH-server masked
- Helper `/usr/local/lib/kalived`, ctl `/usr/sbin/kalived-ctl`

Firewall-baseline: `baselines/firewall_ufw_default_deny.expected`.
