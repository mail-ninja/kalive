# Masterplan — sikre Kali + cep1er + iQOO

| | |
|--|--|
| Dato | 2026-08-13 |
| Nett nå | Åpent gjestenett → **cep1er** WiFi → USB-tether → **Kali** |
| iQOO | Av, PIN endret av andre — egen plan |

---

## Spor 1 — Kali (hermetisk / harden)

### Status allerede

- Ingen TCP-lytttere utad  
- SSH av  
- UFW + AppArmor på  
- Ingen klassiske bakdører i scan  
- xcape sperret på user-nivå  

### Gjør nå (sudo)

```bash
sudo bash /home/void/kalived/playbooks/harden-host-sudo.sh
```

Det fikser: SSH mask, guest-utils av, xcape system-autostart, sysctl, UFW deny, AppArmor dump.

### Etter script

- [ ] Lim output / be agent verifisere  
- [ ] (Valgfritt senere) Docker-gruppe-policy  
- [ ] `apt update && apt full-upgrade` på mer pålitelig nett  

Playbook: `playbooks/harden-host-sudo.sh`

---

## Spor 2 — cep1er (front mot gjestenett)

Gå gjennom: **`playbooks/cep1er-phone-checklist.md`**

Fokus: USB-debug AV, accessibility, rare apper, VPN, Bluetooth.

Fra Kali mot tether-gw: bare DNS :53 åpen (normalt); ADB 5555 lukket (bra).

---

## Spor 3 — iQOO (tilgang eller reset)

Full plan: **`playbooks/iqoo-access-or-reset-plan.md`**

Kort rekkefølge:

1. **Google Find My Device** (+ Vivo Find) → lås eller **nullstill**  
2. Hvis ikke: **Recovery factory reset**  
3. Hvis PIN kreves i recovery: **service** + eierskap  
4. Etter wipe: ny oppsett, **ikke** gammel full-backup; bytt alle konto-passord fra ren PC  
5. Anta SMS-2FA usikker til SIM er under din kontroll  

**Anbefaling etter live-hack:** sikte på **factory reset**, ikke bare «få igjen gammel PIN».

---

## Rekkefølge i praksis (i dag)

| # | Hva | Hvor |
|---|-----|------|
| 1 | Kjør Kali harden-script (sudo) | Terminal på PC |
| 2 | cep1er-sjekkliste A+B | På telefonen |
| 3 | Start iQOO Fase 1 (Find My) | Nettleser på PC — **uten** å skru på iQOO før du er klar |
| 4 | Når hjemme/renere nett: passordbytte kritiske kontoer | PC |
| 5 | iQOO wipe når du har valgt vei | Fysisk / Find My |

---

## Suksesskriterier

| Enhet | «Ferdig nok» |
|-------|----------------|
| Kali | Script grønt; fortsatt 0 eksterne lyttere; SSH av |
| cep1er | Sjekkliste ferdig; ingen rare admin/accessibility |
| iQOO | Enten slettet + ren setup, eller i service-kø; kontoer rotert |
