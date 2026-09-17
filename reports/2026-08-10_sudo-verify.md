# Sudo-verifikasjon — brannmur + AppArmor

| | |
|--|--|
| Dato | 2026-08-10 ~23:21–23:25 CEST |
| Snapshot | `logs/status/2026-08-10_2321/` |
| Forrige rapport | `reports/2026-08-10_baseline-security.md` |

## Resultat i kortform

| Sjekk | Resultat | Finding |
|-------|----------|---------|
| UFW status | **active**, deny in / allow out / deny routed, logging low | **F-001 fixed** |
| User rules | **ingen** (tom `ufw-user-input`) | OK |
| Live INPUT policy | **drop** (ip + ip6) | OK |
| Live FORWARD | **drop** + Docker-kjeder idle | OK |
| aa-status | kun **docker-default** enforce | **F-003 open** (oppjustert) |

## UFW — detalj

```
Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), deny (routed)
New profiles: skip
```

Ingen To/Action/From-linjer → ingen manuelle allow-porter. Inbound som ikke treffer
built-in before-regler (lo, established, utvalgt ICMP, DHCP-client, mDNS/SSDP multiast)
faller til **DROP** og kan logges som `[UFW BLOCK]`.

Tellerne viste bl.a. NetBIOS UDP 137/138-støy som ble sendt til policy drop — sunt.

**ICMP echo-request er tillatt** (host svarer på ping hvis L3 når frem).
Akseptabelt for workstation; kan strammes senere om ønskelig.

## nft — Docker

Docker filter/nat-kjeder er på plass. Masquerade for 172.17/16 og 172.19/16.
Forward-tellere 0 → ingen aktiv container-nettverkstrafikk. Godt i tråd med `docker ps` tom.

## AppArmor — viktig avvik

Forventning ved «AppArmor installert»: mange profiler. Realitet:

- 1 profil lastet: `docker-default`
- 0 prosesser under profil
- `apparmor.service` disabled → profiler i `/etc/apparmor.d/` lastes ikke ved boot

**Linux «applocker» er i praksis av** utenom Docker default.

## Oppdatert findings-status

| ID | Status |
|----|--------|
| F-001 | **fixed** |
| F-002 | open (fail2ban) |
| F-003 | open, severity ↑ medium |
| F-004–F-007 | open |
| F-008 | accepted |

## Anbefalt neste (prioritert)

1. **Enable AppArmor** (`systemctl enable --now apparmor`) + ny `aa-status` → lukk/reduser F-003  
2. Sysctl-hardening (F-004)  
3. Disable guest-utils (F-006) — lav risiko, rask win  
4. fail2ban kan vente mens SSH er av (F-002)  
5. Docker image/policy (F-005) når det passer  

## Artefakter denne runden

```
logs/status/2026-08-10_2321/          # collect-baseline (uten sudo-del)
logs/ufw/2026-08-10_2321_status.txt
logs/status/2026-08-10_2321/aa_status.txt
scans/firewall/2026-08-10_2321_nft_summary.md
baselines/firewall_ufw_default_deny.expected
```

Full `nft list ruleset` ble sett i terminal; lagret som strukturert summary (ikke re-dump uten sudo-cache).
For full rådump neste gang:

```bash
sudo nft list ruleset | tee scans/firewall/$(date +%Y-%m-%d_%H%M)_nft.txt
```
