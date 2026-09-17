# Fortsatt sikring — etter telefon-kompromittering (iQOO)

| | |
|--|--|
| Dato | 2026-08-13 |
| Kontekst | Bruker rapporterer at iQOO-telefon ble «hacka live» for noen dager siden |
| Nåværende nett (snapshot) | **USB-tether** `usb0` → 192.168.57.162/24, gw 192.168.57.4 |

---

## 1. Viktigste trussel nå

Hvis telefonen er kompromittert og PC-en får internett via **USB-tether / hotspot fra den telefonen**, er telefonen:

- din **router** (kan se DNS, omdirigere, MITM hvis den kontrollerer gateway)
- en **lokal angriper på samme L2/L3-segment** (`192.168.57.0/24`)

Dette er **ikke** det samme som «PC er allerede hacket», men det er en **reell inn-vei** for nettverksangrep, phishing, skadelige oppdaterings-speil, osv.

### Anbefalt (prioritet)

1. **Ikke stol på den iQOO-telefonen til tether** før den er factory reset + ren app-install, eller bytt til en **ren** nettvei (annen telefon, kabel-router, offentlig WiFi med VPN du stoler på).
2. **Bytt passord** fra en ren enhet/nett: e-post, bank, Google/Apple, GitHub, SSH-nøkler, password manager master.
3. Anta at **SMS/2FA via den telefonen** kan være kompromittert — bytt til app-2FA/hardware der mulig.
4. På PC: fortsett harden under (script).

---

## 2. Status PC før dagens harden

| Sjekk | Status 2026-08-13 |
|-------|-------------------|
| TCP listen utad | **Ingen** (bra) |
| SSH | inactive / disabled (bra) |
| UFW | active |
| AppArmor | active |
| xcape | **kjørte igjen** → drept + user-autostart `Hidden=true` |
| Guest tools | enabled men inactive → må disable med sudo |
| Sysctl | fortsatt svak → sudo-script |
| Docker | daemon on, void i docker-gruppe (lokal root-ekv.) |

---

## 3. Allerede gjort i dag (uten sudo)

- Drept **xcape**, **gvfsd-network**, **gvfsd-dnssd**, **obexd**
- `~/.config/autostart/xcape-super-key-bind.desktop` med **Hidden=true** (overstyrer system-autostart for din user)

## 4. Må kjøres med sudo (én kommando)

```bash
sudo bash /home/void/kalived/playbooks/harden-host-sudo.sh
```

Scriptet:

1. SSH disable/mask  
2. open-vm-tools + virtualbox-guest-utils **disable**  
3. System-xcape autostart → `.disabled`  
4. **Sysctl hardening** (`/etc/sysctl.d/99-kalived-hardening.conf`)  
5. UFW default deny + enable  
6. AppArmor ensure on + dump  
7. Snapshot + changelog  

---

## 5. Funnet vi IKKE har: aktiv innbrudd på PC

Tidligere runder fant **ikke**:

- remote login-IP-er  
- åpen SSH  
- keylogger-prosess  
- malware patterns  

Vi sikrer **forebyggende** og reduserer surface — spesielt viktig etter telefon-hendelsen.

---

## 6. Neste etter script

| Prioritet | Handling |
|-----------|----------|
| P0 | Ren nettvei (ikke kompromittert telefon) |
| P1 | Kjør `harden-host-sudo.sh` |
| P2 | Bytt kritiske passord / 2FA |
| P3 | Vurder: `docker` gruppe (praktisk root) — rootless docker eller fjern gruppe |
| P4 | `apt update && apt full-upgrade` på rent nett |
| P5 | fail2ban bare hvis SSH skal på engang |
