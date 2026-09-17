# Full root audit — Kali PC

| | |
|--|--|
| Dato | 2026-08-13 ~10:34 CEST |
| Snapshot | `logs/status/2026-08-13_1034_full_root/` |
| Scope | Root: UFW/nft, AppArmor, ports, input lsof, SSH, auth, persistence |

---

## Executive verdict

**PC er i praksis hermetisk lukket mot nettverks-innganger.**  
Ingen bakdør-indikatorer, ingen remote login, ingen eksterne lyttere. Hardening fra script er aktiv.

| Område | Verdict |
|--------|---------|
| Inngående porter | **LUKKET** (0 non-localhost listen) |
| SSH | **MASKED / off** |
| UFW | **ACTIVE** deny in / deny routed |
| AppArmor | **117 profiles** loaded |
| Keylog raw device | **Kun** systemd-logind + Xorg (+ upower for lid) — **forventet** |
| Root/void authorized_keys | **Tom / mangler** |
| Malware patterns | **Clean** |
| Residual risk | Docker-gruppe, daemon on; tether/gjestenett er telefonens jobb |

---

## Detaljer

### Nett / porter

- Listen: `127.0.0.1:7878` (svl), `127.0.0.1:43305` (containerd) only  
- **Ingen** 0.0.0.0 / LAN listen  

### Brannmur

- UFW: active, logging low, default deny in / allow out / deny routed  
- User rules: tomme (ingen allow-porter)  
- Live nft: INPUT/FORWARD **policy drop**  

### Input (keylog residual lukket)

```
event0/event8: systemd-logind + Xorg
event*: also upowerd (lid/power — normal)
```

**Ingen** ukjent userland keylogger på raw devices.

### SSH / auth

- ssh.service: **masked**, inactive  
- Journal ssh: empty  
- Failed password / Accepted remote: ingen treff (7d)  
- last: kun lokale `:0` sesjoner  
- root `authorized_keys`: finnes ikke  
- void `authorized_keys`: 0 linjer  

### Persistence

- root crontab: none  
- /etc/ld.so.preload: none  
- deleted executables: none  
- reverse shell / anydesk / ngrok patterns: none  

### Hardening (post-script)

- Guest tools: disabled  
- Sysctl: kptr/dmesg/ptrace/rp_filter hardnet; ip_forward=1 (Docker)  
- xcape system: .disabled  

### Docker

- 0 containers running  
- mange dangling images (disk, ikke inngang)  
- void ∈ docker group → **lokal** root-ekvivalent hvis kontoen kompromitteres  

### AppArmor note

Mange profiler i **unconfined** mode (apps som 1password, discord, …) — de er lastet men ikke enforce. Enforce har bl.a. docker-default, cursor_sandbox, haveged. Xorg i complain. Dette er normalt for desktop, ikke en åpen port.

---

## Phone gateway (forhåndsblikk — full tlf-runde etterpå)

Probe mot default gw (cep1er tether) lagret i snapshot `extra_and_phone_gw.txt`.

---

## Anbefalt (PC) senere

1. Bevisst Docker-policy (F-005)  
2. `docker image prune` når trygt  
3. apt full-upgrade på mer pålitelig nett  
4. Disable `run-vmblock-fuse.mount` hvis den fortsatt er enabled (rest fra VMware)

---

## Artefakter

- `logs/status/2026-08-13_1034_full_root/`  
- `logs/ufw/*_status.txt`  
- `scans/firewall/*_nft.txt`  
