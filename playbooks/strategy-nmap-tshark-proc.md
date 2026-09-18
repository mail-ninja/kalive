# Strategi: nmap + tshark + prosess (burst)

Kalived er **ikke** et SIEM og **ikke** en LAN-pentest. Vinneren for trojan-jakt på *denne* hosten er tre sensorer i **samme vindu**, fire siler, felles defs.

## Hva som tapte

| Teknikk | Hvorfor den taper |
|---------|-------------------|
| `nmap -A -p- 192.168.0.0/24` | LAN-sweep, støy, policy-brudd |
| `tshark -i any -a duration:3600` | always-on, persondata, Proton-støy |
| Bare rkhunter / unhide | én sil; FP og miss i samme farge |
| NSE `malware,vuln` mot localhost | tregt, ser ut som angrep, lite C2-signal |

## Vinneren (det scannen gjør)

1. **Start tshark på `lo`** (8 s, max 4000 TCP-rader, felt — ikke pcapng).
2. **Samtidig** `nmap -sT -p - 127.0.0.1`, deretter `-sV` *bare* på åpne porter.
3. **Samtidig** hunt-procs (ps / `/proc` / pstree / lsof) med sil 1–4.
4. **Etter wait:** join tshark SYN-ACK × nmap-open × ss LISTEN × lsof pid.

```
sil 1 bulk     nmap-open, tshark-rader, /proc−ps
sil 2 støy     nmap scan_self, gone/tråd, Proton, mdns/443
sil 3 berik    -sV, hunt_proc_ident, pcap ident (port in_ss/in_nmap)
sil 4 verdict  hidden_listen / extra / fakekth / commexe / IOC
```

## Tshark-taktikk som er verdt det

- Filter **SYN+ACK only** på **lo** (`tcp[tcpflags] & 0x12 == 0x12`). Raw `tcp` fylles av nmap-RST før :8787 vises.
- `-T fields` (src/dst/port/flags). Aldri payload til advisor.
- Drop flyt der én sport treffer ≥ 20 dports = vår egen nmap.
- SYN-ACK **source port** = lytter; dest = klient-ephemeral. Join aldri på dport.
- Port ≥ 32768 som verken ss eller nmap kjenner = ephemeral, ikke EXTRA.
- EXTRA bare hvis serverport ikke lyttes, ikke er nmap-open, og ikke er kjent lo (8787/45959/7878).
- Egress-pcap på usb0/wlan0 er **fase 2** (`pcap_egress` finnes ikke ennå). Ikke slå på «any» som default.

## nmap-taktikk som er verdt det

- Bare `127.0.0.1`. `-n -Pn --open`.
- Full `-p -` for dual-source mot ss (skjulte lyttere).
- `-sV` bare på åpne porter vi **ikke** allerede kjenner. Hopp over 8787/45959/7878 (HTTP-API; `-sV` gir TLS-ClientHello → 400).
- ALERT bare hvis -sV sier meterpreter/backdoor/trojan, eller port åpen i nmap ikke i ss.

## Prosess-taktikk som er verdt det

- Første `/proc`−`ps`-diff er kandidater.
- IOC-navn fra `defs/ioc/process-names.txt` = ALERT (git).
- Remote `defs/cache/*.remote.txt` = WARN (ikke merget).
- Join mot socket: lsof LISTEN + ESTAB cwd `/tmp` (allerede PROC-TMPNET).

## Defs

```bash
sudo kalived-ctl defs    # rkhunter + local-pack parallelt; HTTP hvis enabled=1
```

Ikke lim defs foran hver scan. `defs_auto_update=false`. URLhaus er opt-in.

## Config

`pcap_localhost`, `pcap_duration_s` (1–30), `pcap_max_packets`, `nmap_svc_probe`.
