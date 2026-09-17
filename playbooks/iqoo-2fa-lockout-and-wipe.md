# iQOO kompromittert + alle 2FA der — handlingsplan

| | |
|--|--|
| Situasjon | Live-hack observert; ~200 rare strenger i sikkerhetsinnstillinger; ukjent oppstartskode; stemmer hørt **etter SIM ute** |
| cep1er | Resatt recovery i går — sekundær |
| Blokkering | Authenticator / 2FA på iQOO → innlogginger låst andre steder |

**Tolkning av «stemmer etter SIM ute»:**  
Ikke nødvendigvis mobilnett. Ofte **WiFi + spionvare med mikrofon**, WiFi-calling, eller remote-access. Behandle telefonen som **fiendtlig enhet på nett** til den er wipe’t og du er sikker.

---

## Fase 0 — Nå (minutter)

1. **iQOO: av, bli av.** Ikke sett inn SIM. Ikke koble WiFi «for å fikse».  
2. **Ikke** prøv tilfeldige PIN-er i loop (lockout / sletting).  
3. Jobb fra **denne Kali-en** (allerede hardnet + gjestenett OK) eller annen ren PC.  
4. Mål rekkefølge: **(A) regn tilbake kontoer uten 2FA-telefon** → **(B) wipe iQOO** → **(C) ny 2FA-setup**.

---

## Fase A — Få tilbake kontoer UTEN iQOO-authenticator

Du trenger **ikke** den gamle telefonen for alt — men hver tjeneste har egen «mistet 2FA»-vei.

### A1 — Google (ofte nøkkelen til alt)

På PC: https://accounts.google.com  

1. Prøv innlogging → «Prøv en annen måte» / «Don't have your phone».  
2. **Backup-koder** (hvis du lagret dem engang) — sjekk passordmanager, e-post, USB, utskrift.  
3. **Annen enhet** som allerede er innlogget (gammel laptop, nettbrett, Chrome-profil).  
4. **Account recovery:** https://accounts.google.com/signin/recovery  
5. Hvis Google Authenticator bare var «app-koder» uten backup: recovery-form + tid (dager).  

**Hvis Google lykkes:**  
- Bytt passord med en gang  
- **Logg ut alle enheter**  
- Fjern gamle 2FA-metoder knyttet til iQOO  
- Sett **nye** backup-koder + ny authenticator på **cep1er (ren)** eller hardware key  
- Skru på **Google Find My Device** → Nullstill iQOO hvis den er på nett (vanligvis ikke hvis av)

### A2 — Andre vanlige 2FA (samme mønster)

For **hver** viktig tjeneste (bank, e-post, Microsoft, Apple, Meta, Discord, GitHub, arbeids-SSO):

| Steg | Handling |
|------|----------|
| 1 | «Lost phone / can't use authenticator / prøv en annen måte» |
| 2 | Backup-koder / SMS til **nummer du kontrollerer nå** |
| 3 | E-post til **recovery-adresse du fortsatt har** |
| 4 | Support med ID (bank er streng — ring dem) |
| 5 | Etter innlogging: **kill sessions**, bytt passord, **ny 2FA** ikke på iQOO |

### A3 — Prioritetsliste (gjør i denne rekkefølgen)

1. **Primær e-post** (den som resetter alt annet)  
2. **Google** (Play, Find My, mange app-logins)  
3. **Bank / Vipps / Betaling** — ring bank, si enhet kompromittert  
4. **Microsoft / Apple** hvis brukt  
5. **Jobb/IdP** (IT-support kan resette MFA)  
6. Resten (sosiale, GitHub, …)

### A4 — Authenticator-app backup?

Sjekk om du noen gang:

- Eksporterte **Google Authenticator** QR/transfer  
- Brukte **Authy** multi-device  
- **1Password / Bitwarden / KeePass** TOTP  
- Skrev ned **backup codes**

Hvis ja → gjenopprett på **ren** cep1er, ikke på iQOO.

### A5 — SMS-2FA til iQOO-nummeret

- SIM ute = du mottar ikke SMS der.  
- Sett SIM i **cep1er** (ren) **etter** wipe/reset av cep1er (du sa den er resatt) hvis nummeret er ditt.  
- Eller kontakt operatør: sperre SIM / nytt SIM samme nummer.  
- Anta angriper kan ha hatt SMS-tilgang mens de eide enheten → bytt kritiske passord uansett.

---

## Fase B — Wipe / nøytralisere iQOO

### B1 — Uten å slå den på (best)

1. Google Find My / Vivo Find Phone fra PC (når Google er tilbake).  
2. **Nullstill** / wipe eksternt hvis enheten noen gang kommer på nett.  
3. Ellers: fysisk **factory reset via recovery** (se `iqoo-access-or-reset-plan.md`).  
4. Hvis recovery krever oppstartskode: **offisiell service** med eierskap.

### B2 — Ikke gjør dette

- Ikke «unlock tool» fra nettet  
- Ikke gi den WiFi «for å se»  
- Ikke sett inn SIM før wipe  
- Ikke stol på den etter bare å ha «fått PIN» uten full wipe

### B3 — Etter wipe

- Oppsett som **ny telefon**  
- **Ingen** full backup fra før hacket tidspunkt  
- Nye PIN, ny 2FA-app, backup-koder på papir/passordmanager  

---

## Fase C — Ny sikkerhetsbaseline (når du er inne igjen)

1. **Passordmanager** med TOTP der det går  
2. **Backup-koder** skrevet ned offline  
3. Helst **2 enheter** eller hardware key (YubiKey) til kritiske kontoer  
4. Authenticator **ikke bare** på én telefon  
5. Finn My / remote wipe aktiv på alle telefoner  

---

## Hva de «200 rare strengene» + remote voice betyr for deg

- Høy sannsynlighet for **remote access / spyware**, ikke bare «glipp-PIN».  
- Mikrofon over **WiFi** forklarer stemmer uten SIM.  
- Behandle **alle sessions** på den telefonen som kompromittert:  
  passordbytte + session revoke overalt når du får inn.

---

## Sjekkliste (kryss av)

### I dag
- [ ] iQOO forblir AV, uten SIM/WiFi  
- [ ] List alle kontoer du husker (e-post, bank, Google, jobb, …)  
- [ ] Søk backup-koder / passordmanager / gamle enheter som er innlogget  
- [ ] Start Google account recovery  
- [ ] Ring bank hvis mobilbank/Vipps på iQOO  

### Når Google/e-post er inne
- [ ] Nytt passord + utlogg alle enheter  
- [ ] Ny 2FA på ren cep1er + backup-koder  
- [ ] Find My → wipe iQOO hvis mulig  
- [ ] Recovery-reset eller service for iQOO  

### Etter iQOO wipe
- [ ] Ren setup, ingen gammel backup  
- [ ] Flytt TOTP dit bevisst, med backup  

---

## Kobling til kalived

- PC: allerede hardnet — bruk den til recovery  
- cep1er: resatt — OK som **ny** 2FA-enhet når du stoler på den  
- iQOO: **ikke** 2FA-enhet før wipe + ren install  
