# Plan: få tilgang til iQOO **eller** factory reset

| | |
|--|--|
| Situasjon | Telefon hacket live; **PIN endret** av andre; enhet av nå |
| Mål | Enten **regne tilbake kontroll**, eller **tørke og starte på null** |
| Data | Anta at data/kontoer **kan være kompromittert** uansett |

iQOO = Vivo-familie. Stegene under er generelle Android/Vivo; eksakte menyer varierer med modell/Android-versjon.

---

## Fase 0 — Sikkerhetsantakelser (før du gjør noe)

1. **PIN/biometri på enheten er fiendtlig kontrollert** til det motsatte er bevist.
2. **Kontoer brukt på telefonen** (Google, bank, e-post, sosiale) kan være kompromittert — bytt fra **annen ren enhet/nett** så snart du kan.
3. **SMS-2FA** til det nummeret er upålitelig til SIM er sikret (kontakt operatør ved behov).
4. Mål A (få inn uten wipe) vs mål B (wipe) — velg bevisst.  
   Etter live-hack er **B (reset) ofte riktig** selv om A lykkes.

---

## Fase 1 — Få tilgang **uten** fysisk PIN (konto / Find Device)

Prøv i denne rekkefølgen på **PC eller annen telefon** (ikke den hacket enheten):

### 1.1 Google Find My Device

- https://www.google.com/android/find  
- Logg inn med **Google-kontoen som var på iQOO**
- Hvis enheten vises:
  - [ ] **Lås** (ny melding/PIN du velger) — kan overstyre skjermlås i mange tilfeller
  - [ ] **Nullstill** (factory reset eksternt) hvis du vil tørke med en gang
  - [ ] **Spill av lyd** bare for å bekrefte at det er riktig enhet

### 1.2 Vivo / iQOO-konto («Find phone» / iManager)

- Logg inn på Vivo/iQOO cloud / Find Phone i nettleser (søk «Vivo Find Phone» / iQOO account for din region)
- Samme idé: lås / wipe eksternt hvis enheten er knyttet til kontoen

### 1.3 Operatør / SIM

- [ ] Er SIM fortsatt i iQOO eller har du tatt den ut?
- [ ] Kontakt operatør: sperre SIM ved mistanke om SIM-swap / misbruk
- [ ] Vurder nytt SIM / eSIM når du er klar

**Hvis 1.1/1.2 fungerer:** du har en vei til **lås eller wipe**.  
Etter live-hack: **anbefalt wipe**, deretter nye passord overalt.

**Hvis ingen konto var pålogget / «Find» finner ikke enheten:** gå til Fase 2.

---

## Fase 2 — Fysisk recovery / factory reset (uten kjent PIN)

> Dette **sletter** appdata, bilder, nedlastinger på intern lagring (ikke nødvendigvis SD hvis den er uavhengig — sjekk modell).

### 2.1 Boot til Recovery (typisk Vivo/iQOO)

Enheter varierer. Vanlige mønstre (prøv forsiktig, ikke hold for aggressivt):

1. Telefon **av**
2. Hold **Volum opp + Power** (noen modeller: Volum ned + Power)
3. Når logo: slipp Power, behold volum, eller følg skjerm
4. Naviger med volum, bekreft med power
5. Velg **Wipe data / Factory reset** (eller «Clear eMMC», «Wipe userdata»)
6. Bekreft, deretter **Reboot**

Hvis **«Enter password / lockscreen for wipe»** kreves i recovery (nyere Android):  
→ recovery-wipe kan være **låst** uten PIN. Da trenger du Fase 1 (Find My wipe) eller **autorisert service** med kvittering/eierskap.

### 2.2 Fastboot / edl (avansert)

- Kun hvis du har unlock-bar bootloader og vet hva du gjør
- På de fleste consumer-iQOO er bootloader **låst** → ikke en enkel vei
- **Ikke** last ned tilfeldige «unlock tools» fra nettet (ofte malware)

### 2.3 Offisiell service / butikk

- [ ] Kvittering / eierskapsbevis
- [ ] Be om **factory reset / firmware reflash**
- [ ] Ta ut SIM/SD før innlevering hvis mulig

---

## Fase 3 — Etter at du er «inne» eller etter wipe

### 3.1 Hvis du fikk PIN/tilgang **uten** wipe (ikke ideelt etter hack)

- [ ] **Umiddelbart** factory reset manuelt (Innstillinger → System → Reset)  
  Eller Find My → Nullstill  
- [ ] Ikke stol på apper som lå igjen

### 3.2 Etter factory reset (anbefalt tilstand)

1. Sett opp som **ny telefon** (ikke gjenopprett hele backup fra før hacket tidspunkt)
2. **Nytt** skjermlås-PIN (ikke det gamle)
3. Logg inn Google **etter** du har byttet Google-passord fra ren PC
4. Installer bare apper fra Play; 2FA med **app/hardware**, ikke bare SMS
5. Vivo/iQOO Find Phone på nytt med **sikret** konto
6. Ikke sett inn gammel «full backup»-image som kan inneholde malware

### 3.3 Kontoer (gjør fra **Kali/ren nett**, ikke fra usikker telefon)

Prioritet:

| Prioritet | Handling |
|-----------|----------|
| 1 | Google-passord + utlogging av alle enheter |
| 2 | E-post som er recovery for andre kontoer |
| 3 | Bank / Vipps / Betalingsapper |
| 4 | Apple/Microsoft/Facebook/Instagram/Discord osv. brukt på telefonen |
| 5 | Auth-apper: nye TOTP der det trengs |
| 6 | WiFi-passord hjemme hvis de var lagret på telefonen |

---

## Fase 4 — Beslutningstre (kort)

```
Kan Google/Vivo Find Device se iQOO?
├─ JA → Lås med ny PIN ELLER Nullstill eksternt
│         └─ Etter live-hack: velg Nullstill → Fase 3.2
└─ NEI → Prøv Recovery factory reset
          ├─ LYKKES → Fase 3.2
          └─ KREVER PIN / feiler → Offisiell service + konto-sikring uansett
```

---

## Fase 5 — Hva vi **ikke** skal gjøre

- Ikke «unlock»-APK / teamviewer-lignende remote fra ukjente  
- Ikke gi PIN til noen som ringer og utgir seg for support  
- Ikke gjenbruk samme PIN/passord som før hacket  
- Ikke tether Kali fra iQOO før den er resatt og ren  

---

## Logging i kalived

Når du har valgt vei, noter her:

| Dato | Handling | Resultat |
|------|----------|----------|
| | | |

Fil: oppdater `remediation/CHANGELOG.md` eller denne tabellen.
