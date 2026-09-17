# cep1er ADB-scan — ZTE Z2472

| | |
|--|--|
| Dato | 2026-08-13 ~15:48 CEST |
| Serial | LZ0A36SEDDB003558 |
| Modell | **ZTE Z2472** (Unisoc), product EEA_P606F20_1 |
| OS | Android **15**, MyOS15.0.5_Z2472_Power |
| Snapshot | `logs/status/2026-08-13_1548_adb_phone/` |

---

## Executive verdict

**Ingen klassiske bakdører funnet** via ADB (ingen spy/RAT-pakkenavn, **ingen enabled accessibility-tjenester**, **ingen enabled device admins**, ingen mistenkelig notification-access, ingen aktiv VPN-app).

Telefonen ser ut som en **vanlig ZTE/Cepter-brukertelefon** med kjente apper + litt bloat (Gameloft).

**Residual / hygiene:**
1. **USB-debugging er fortsatt PÅ** (`adb_enabled=1`) — skru **AV** nå etter scan  
2. **Tredjeparts tastatur** `com.preff.kb.zx` er standard IME (kan lese alt du skriver — typisk OEM, men verdt å vite)  
3. Flere **ringe-/SMS-relaterte** apper installert (se under) — standard SMS er Google Messages; dialer er Fossify  

---

## Tredjepartsapper (20)

| Package | Vurdering |
|---------|-----------|
| org.thoughtcrime.securesms | **Signal** — OK |
| org.telegram.messenger | Telegram — OK |
| org.mozilla.firefox | Firefox — OK |
| com.github.android | GitHub — OK |
| com.google.android.apps.authenticator2 | Google Authenticator — OK |
| com.google.android.apps.googlevoice | Google Voice — OK |
| com.google.android.apps.enterprise.cpanel | Google admin/enterprise — OK hvis du bruker det |
| com.google.android.contactkeys / safetycore | Google-system — OK |
| ai.perplexity.app.android | Perplexity — OK |
| com.facebook.katana / orca | Facebook / Messenger — OK (personvern, ikke bakdør) |
| org.fossify.phone | Fossify Phone — **standard dialer** — OK (FOSS) |
| com.sms.messenger | Ekstra SMS-app — **ikke** standard (standard = Google Messages) |
| com.moontechnolabs.moondialer | Moon Dialer — ekstra dialer; fjern hvis ubrukt |
| com.mmcallsapp.duovoice.android | DuoVoice/calls — ekstra call-app; fjern hvis ubrukt |
| com.usb_tethering | Tether-hjelp (OEM/bruk) — forventet |
| com.zte.cn.compass | ZTE kompass — OEM |
| com.gameloft.* (2 stk) | Spill-bloat — OK å fjerne |

Ingen treff på spy/keylog/anydesk/teamviewer/RAT i pakkenavn.

---

## Sensitive system-tilstander

| Sjekk | Resultat |
|-------|----------|
| Enabled accessibility services | **Tom** (null / Bound services {}) |
| Enabled device admins | **Ingen** |
| Notification listeners | Bare ZTE power save + launcher |
| Standard SMS | `com.google.android.apps.messaging` |
| Standard dialer | `org.fossify.phone` |
| Standard tastatur | `com.preff.kb.zx` (OEM/ZX LatinIME) |
| Aktiv VPN-app | Ikke funnet |
| USB config under scan | `rndis,adb` |

Accessibility **klienter** (apps som snakker med a11y API, ikke «enabled services»): Google AS, ZTE zdm, Authenticator, Photos, usb_tethering, launcher, Bard, Search, GitHub, keyboard, enterprise cpanel, zboard — typisk OEM/Google-støy, **ikke** enabled malware services.

---

## Anbefalte handlinger (cep1er)

### Nå (obligatorisk)
1. **USB-debugging AV**  
2. Utviklermuligheter → **Tilbakekall USB-autorisasjoner**  
3. (Valgfritt) skru av hele utviklermenyen  

### Hygiene (anbefalt)
- Avinstaller hvis ubrukt: Moon Dialer, DuoVoice, Gameloft, ekstra `com.sms.messenger`  
- Behold Fossify/Signal/Telegram hvis du bruker dem  
- Vurder Google/Gboard som tastatur hvis du ikke stoler på OEM-IME  

### På åpent gjestenett
- Unngå bank/passordbytte  
- Skru av tether når PC ikke trenger nett  

---

## Begrensninger

Scan er **read-only ADB uten root**. Kan ikke utelukke kernel-rootkit eller skjulte system-modifikasjoner 100 %, men bruker-nivå bakdører ville vanligvis vist seg som accessibility/admin/ukjent pakke.
