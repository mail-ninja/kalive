# Hermetisk sjekk — Kali + cep1er-tether (åpent gjestenett)

| | |
|--|--|
| Dato | 2026-08-13 ~10:19 CEST |
| Nett | USB-tether `usb0` → 192.168.57.162/24, gw **192.168.57.4** (cep1er) |
| iQOO | av, PIN endret — utsatt |
| Snapshot | `logs/status/2026-08-13_1019_hermetic/` |

---

## 1. Kontekst (korrigert)

- **Ikke** tether via kompromittert iQOO (av).
- **Ja** tether via **cep1er** på **åpent gjestenett**.
- Mål: innganger/bakdører på **Kali** + så langt vi kan vurdere **cep1er** fra PC-siden.

Åpent gjestenett + USB-tether betyr: cep1er er «vegg» mot internett; Kali er bak telefon-NAT. Gjestenettet ser primært **telefonen**, ikke nødvendigvis PC-ens porter — men dårlig tether-konfig kan eksponere mer. Derfor sjekker vi at **Kali ikke lytter utad**.

---

## 2. Kali — hermetisk status (nå)

### Innganger utad (det som betyr mest)

| Sjekk | Resultat | Vurdering |
|-------|----------|-----------|
| TCP/UDP LISTEN på LAN/USB/0.0.0.0 | **Ingen** | **Lukket** |
| Kun localhost | `127.0.0.1:7878` (svl), `127.0.0.1:43305` | OK (ikke nåbar utenfra) |
| SSH server | inactive, disabled, **ingen port 22** | **Lukket** |
| `authorized_keys` (void) | **0 nøkler** | Ingen remote key-login |
| UFW | ENABLED=yes, service active | **På** (full regel-dump krever fortsatt sudo-script) |
| AppArmor | enabled + active | **På** |
| Containers | 0 | OK |
| Reverse shell / ngrok / anydesk / vnc / meterpreter | **0 treff** | OK |
| Deleted running binaries | **0** | OK |
| `/etc/ld.so.preload` | finnes ikke | OK |
| User crontab | tom | OK |
| Utgående nå | grok → HTTPS 443 (forventet) | OK |

### Fortsatt ikke «perfekt hermetikk» (hardening, ikke bevis på bakdør)

| Punkt | Status |
|-------|--------|
| Guest tools (open-vm-tools) | **enabled** (inactive) — unødvendig; `harden-host-sudo.sh` |
| Sysctl | fortsatt svake defaults uten script |
| Docker daemon | kjører; void i **docker**-gruppe = lokal root-ekv. |
| fail2ban | ikke installert (OK mens SSH er av) |
| spice-vdagent.user unit | enabled (typisk VM-spice; på bare metal unødvendig) |
| xcape | ikke kjørende; user autostart Hidden=true |

**Konklusjon Kali:** Fra nettverkssiden ser maskinen **lukket** ut — ingen åpne inngangsporter, ingen SSH, ingen klassiske bakdør-indikatorer i denne scannen.  
«Hermetisk» 100 % krever fortsatt **sudo-harden-script** + bevisst Docker-policy + rent nett.

---

## 3. cep1er-telefon — hva vi kan/kan ikke se

### Kan fra Kali

- Gateway-IP på tether: **192.168.57.4**
- Port-probe mot gateway (se `phone_gw_scan.txt` i snapshot)
- USB-tether betyr telefonen deler nett; PC er klient

**Probe 192.168.57.4 (cep1er som tether-gateway):**

| Port | Resultat | Tolkning |
|------|----------|----------|
| 53 | **OPEN** | Forventet — DNS på tether |
| 22, 23, 80, 443, 8080, 8443 | closed/filtered | Ingen web/SSH mot PC-segment |
| **5555** (ADB) | closed/filtered | **Bra** — ingen åpen Android Debug Bridge |
| 62078 (klassisk iOS lockdownd-ish) | closed/filtered | n/a |

Dette er **ikke** full telefonsikkerhet — bare at den ikke eksponerer vanlige remote-admin-porter mot USB-nettet.

### Kan ikke fra Kali (uten mer tilgang)

- App-liste, root/magisk, skadelige APK-er  
- Accessibility-tjenester, SMS-tyveri, overlay-angrep  
- Om gjestenettet har angrepet **telefonen**  

### Praktisk sjekkliste cep1er (gjør på telefonen)

1. **Ukjente admin-apper?** Innstillinger → Apper → sorter etter installert  
2. **Enhetsadmin / tilgjengelighet:** Innstillinger → Tilgjengelighet — bare det du kjenner  
3. **Ukjente VPN / «cleaner» / «security»-APK** utenfor Play  
4. **USB:** bare filoverføring/tether når du trenger det; ikke «filoverføring» til fremmede PC-er  
5. **Play Protect** på; oppdater system  
6. **Utvikler-modus / USB-debugging AV** med mindre du trenger det  
7. **Bluetooth av** når ikke i bruk  
8. På åpent gjestenett: unngå bank/passordbytte; bruk HTTPS; vurder VPN **du stoler på** (på telefon eller PC)  
9. Etter gjestenett: bytt WiFi-passord hjemme hvis du logget inn på noe sensitive  

---

## 4. Åpent gjestenett — råd

| | |
|--|--|
| Gjestenettet | Kan sniffe ukryptert, hoste fake captive portal, angripe telefonen |
| Kali bak tether | Ingen åpne lyttere funnet → vanskelig å «komme inn» på PC direkte fra WiFi |
| Svakeste ledd nå | **Telefonen på åpent WiFi** + tillit til tether-gateway |

Anbefalt mens du er her:

- Ikke logg inn på bank/e-post-passordbytte hvis du kan vente  
- Hold Kali som nå (SSH av, ingen deling)  
- Kjør `sudo bash ~/kalived/playbooks/harden-host-sudo.sh` når du kan taste sudo  

---

## 5. iQOO (utsatt)

- Av, PIN endret av angriper → fysisk/kontosikring senere  
- Factory reset når du får tilgang igjen  
- Anta alt på den enheten kompromittert (kontoer, 2FA SMS, osv.)

---

## 6. Anbefalt rekkefølge nå

1. **Godta:** Kali ser lukket ut på nett i denne scannen.  
2. **Kjør** `sudo bash /home/void/kalived/playbooks/harden-host-sudo.sh`  
3. **cep1er:** gå gjennom sjekklisten over (spesielt accessibility + USB-debug + rare apper)  
4. **iQOO:** senere, factory reset + konto-sikring  
5. Docker-gruppe: ta bevisst beslutning senere (praktisk vs. hermetikk)
