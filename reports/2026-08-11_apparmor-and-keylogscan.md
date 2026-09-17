# AppArmor status + keylogger scan

| | |
|--|--|
| Dato | 2026-08-11 ~02:04–02:08 CEST |
| Snapshot | `logs/status/2026-08-11_0207_keylogscan/` |

---

## 1. AppArmor — ferdig?

**Ja — service-delen er ferdig.**

| Sjekk | Resultat |
|-------|----------|
| `systemctl is-enabled apparmor` | **enabled** |
| `systemctl is-active apparmor` | **active (exited)** |
| Startet | 2026-08-11 02:04:31 CEST (`apparmor.systemd reload`) |
| Kernel module | loaded (`enabled=Y`) |
| Full `aa-status` (profilantall) | krever sudo — ikke re-dumpet denne runden |

Journal:

```
Starting apparmor.service...
Restarting AppArmor / Reloading AppArmor profiles
Finished apparmor.service
```

**F-003** → **fixed** (enable --now utført; profiler lastet ved boot heretter).

Valgfritt cleanup (én gang med sudo for dokumentasjon):

```bash
sudo aa-status | tee logs/status/$(date +%Y-%m-%d_%H%M)/aa_status.txt
```

Forvent mange profiler i enforce (ikke bare `docker-default` som før).

---

## 2. Keylogscan — metode

Sjekket uten root der mulig:

1. `/dev/input/*` + `/proc/bus/input/devices`
2. Prosesser med keylog-relaterte navn
3. Kernel-moduler (hid/evdev)
4. Cron, user systemd, autostart (xdg + `~/.config/autostart`)
5. Pakker (`logkeys`, keylogger-navn)
6. `LD_PRELOAD` på brukerprosesser + `/etc/ld.so.preload`
7. Filer `*keylog*` under home/tmp
8. Åpenbare reverse-shell-navn / ikke-localhost TCP
9. Python/cmdline med pynput/evdev/logkeys

**Begrensning:** `lsof`/`fuser` på `/dev/input` som `void` ser lite (enheter `root:input`, void ikke i `input`-gruppen). Xorg (root) holder normalt event-devices — det er forventet, ikke malware.

---

## 3. Keylogscan — funn

| Sjekk | Resultat | Vurdering |
|-------|----------|-----------|
| Pakke logkeys/keylogger | ikke installert | OK |
| Prosessnavn keylog/logkeys/pynput | ingen (kun vår egen scan) | OK |
| Cron (user) | ingen | OK |
| Autostart suspicious grep | none | OK |
| `/etc/ld.so.preload` | finnes ikke / utilgjengelig | OK |
| LD_PRELOAD | kun Firefox `libmozsandbox.so` | forventet |
| Kernel-moduler | standard hid/evdev/i2c_hid | OK |
| uinput | finnes, root-only | normalt |
| Ikke-localhost TCP LISTEN | ingen | OK |
| `xev` installert | ja (`/usr/bin/xev`) | debug-verktøy, ikke aktiv keylogger |
| Session | X11 (`DISPLAY=:0`) | mer «grabbar» enn Wayland i teorien — OK for XFCE |

### Autostart (normalt støy, ikke keylog)

- XFCE stack, nm-applet, gnome-keyring, pipewire, …
- `vmware-user.desktop`, `kali-vboxclient.desktop` → se **F-006** (guest tools)
- `onboard-autostart.desktop` — on-screen keyboard (tilgjengelighet), ikke keylogger
- User: kun `fix-old-genmon-config.desktop`

### Input hardware (forventet laptop)

- AT keyboard, Elan TrackPoint, Synaptics touchpad, power/lid, …

### Ingen treff på

- logkeys, keylogger packages  
- pynput/pyxhook/evdev sniffer-prosesser  
- keylog-filer i home/tmp (utenom denne scan-mappa)

**Konklusjon keylogscan:** Ingen indikasjon på aktiv keylogger. Runden er **clean** innenfor det vi kan se uten root-lsof.

---

## 4. Dypere (valgfritt, med sudo)

```bash
# Hvem holder keyboard event-device?
sudo lsof /dev/input/event0 /dev/input/event* 2>/dev/null | head -50

# Kjørende under AppArmor nå
sudo aa-status

# Hurtigsøk etter logkeys binary residual
sudo find /usr /opt /home -iname '*logkeys*' 2>/dev/null | head
```

Forventet lsof: mest **Xorg** (+ evt. libinput-hjelpere). Ukjente userland-PIDs med raw event0 → da escalere.

---

## 5. Artefakter

```
logs/status/2026-08-11_0207_keylogscan/
reports/2026-08-11_apparmor-and-keylogscan.md
findings/F-003 (fixed)
findings/F-009_keylogscan-clean.md
```
