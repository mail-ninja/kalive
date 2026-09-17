# Dyp keylogger / input-viewer-analyse

| | |
|--|--|
| Dato | 2026-08-11 ~02:13 CEST |
| Snapshot | `logs/status/2026-08-11_0213_keylog_deep/` |
| Scope | Raw `/dev/input`, X11 RECORD/grab, AT-SPI, libs, persistence, kernel |

---

## Konklusjon (ærlig)

**Ingen funn som ligner aktiv keylogger eller input-viewer** (logkeys, screenkey, pynput/evdev-sniffer, skjulte deleted-binaries, mistenkelige autostart).

Det **én** prosess som **manipulerer tastaturhendelser med vilje**:

| PID | Prosess | Vurdering |
|-----|---------|-----------|
| 2540 | `xcape -e Super_L=Control_L\|Escape` → `/usr/bin/xcape` | **Legitim key-remapper** (Kali/XFCE autostart). Bruker `libXtst`. Lytter/omskriver Super — lagrer ikke keystrokes til fil. |

**Hard grense uten sudo:** 241 prosesser (mest root) har utilgjengelige `/proc/PID/fd`.  
`Xorg` (root, pid ~902) **skal** holde `/dev/input/event0` via libinput — det er designet, ikke malware.  
En **root-keylogger** som bare leser event0 ville kreve `sudo lsof` for å utelukkes 100 %.

---

## Angrepsflater sjekket

### 1. Raw `/dev/input/event*` (kernel keylog path)

| Sjekk | Resultat |
|-------|----------|
| Scan alle lesbare `/proc/*/fd/*` for `event*`, `mouse*`, `uinput` | **0 treff** (93 PIDs lesbare som void) |
| void i gruppen `input`? | **Nei** — userland kan ikke åpne event* uten ekstra rettigheter |
| Devices i `/proc/bus/input/devices` | Kun ThinkPad-HW (tastatur=event0, touchpad, trackpoint, thinkpad buttons, audio jacks) |

**Tolking:** Ingen *bruker*-prosess sitter på raw keyboard device.  
For root-hold: kjør selv:

```bash
sudo lsof /dev/input/event0 /dev/input/event8
# forvent: Xorg (evt. systemd-logind). Alt annet = escalate.
```

### 2. X11 keylog paths (viktigere enn event* på desktop)

På X11 kan en klient keylogge **uten** `/dev/input` via:

- XRecord extension (**tilgjengelig** på denne sesjonen)
- XI2 raw events / passive grabs
- Samme cookie som din sesjon (`~/.Xauthority`)

| Sjekk | Resultat |
|-------|----------|
| `xlsclients -l` | Kun forventet desktop: xfce*, Thunar, nm-applet, blueman, screensaver, polkit, **cursor**, **firefox**, **qterminal**, portal |
| Ukjente X-klientnavn | **ingen** |
| Extensions | RECORD, XInput, XTEST alle på (normalt) |
| Prosesser med **libXtst** | `at-spi2-registryd`, **xcape** |
| Prosesser med **libevdev / pynput / logkeys** | **ingen** |
| Kjørende: xev, showkey, xdotool, screenkey, logkeys, wshowkeys | **ingen** (binaries finnes: xev, showkey, xdotool — ikke startet) |

`xlsclients` er ikke 100 % perfekt (noen klienter uten vindu), men koblet med lib-scan + full process-list er det solid for userland.

### 3. AT-SPI / accessibility (annen klassisk vector)

- Bus kjører: `at-spi-bus-launcher`, `at-spi2-registryd` — **standard**
- **Ikke** kjørende: orca, accerciser, onboard (onboard autostart er OnlyShowIn Unity/MATE + GSettings-gate)
- Bus-navn: kun `org.a11y.atspi.Registry` + anonyme `:1.x` (apps som registrerer a11y — normalt)

### 4. Persistence / «input viewer»-verktøy

| | |
|--|--|
| logkeys / screenkey installert | **nei** |
| Cron user | tom |
| genmon | `/usr/share/kali-themes/xfce4-panel-genmon-vpnip.sh` (VPN IP) — ikke keylog |
| xcape autostart | ja, system `/etc/xdg/autostart/xcape-super-key-bind.desktop` |
| shell rc keylog hooks | ingen treff |
| `/etc/ld.so.preload` | fraværende |
| Deleted running executables | **ingen** |
| Kernel tainted | **0** |
| eBPF/kprobe (uten root debug) | ingen åpenbar bpffs-støy |

### 5. Xorg driver-path (hvem «eier» tastaturet i GUI)

Fra `/var/log/Xorg.0.log`:

- `event0` — AT keyboard → **libinput** → XINPUT keyboard
- `event6` touchpad, `event7` trackpoint, `event8` ThinkPad Extra Buttons → libinput  
- Ingen tredjeparts input-driver nevnt

### 6. Root-prosessliste (cmdline lesbar selv uten fd)

Synlige root-userland: journald, udevd, NetworkManager, ModemManager, cron, **lightdm**, **Xorg**, containerd, haveged, accounts-daemon, wpa_supplicant, fusermount portal, …  
**Ingen** `logkeys`, `evtest`, `keylog*`, merkelige paths under `/tmp`.

---

## Hva som *kan* se «mistenkelig» ut (men ikke er det)

1. **`xcape`** — fanger Super og sender Escape/Ctrl. Input-manipulasjon, ikke logger.  
2. **RECORD / XTEST extensions** — finnes alltid på Xorg; ikke bevis på misbruk.  
3. **Firefox/Cursor** har `libXi` — alle GUI-apper har det.  
4. **AT-SPI bus** — accessibility, ikke keylogger i seg selv.  
5. **Mange X11-socket-connections** — normal multi-window desktop.

---

## Restrisiko (må være tydelig)

| Scenario | Status |
|----------|--------|
| Userland keylogger (samme user) | **Svært usannsynlig** gitt scan |
| screenkey / key-mon type overlay | ikke installert/kjører ikke |
| Root raw-device keylogger | **Ikke 100 % utelukket** uten `sudo lsof` |
| Compromised Xorg/libinput | utenfor denne runden (krever integritetssjekk av pakker) |
| Browser extension keylog | ikke sjekket (annen threat model) |
| Kernel rootkit | tainted=0, men ikke full rkhunter |

---

## Påkrevd root-kommando (for å lukke siste hull)

```bash
cd ~/kalived
STAMP=$(date +%Y-%m-%d_%H%M)
mkdir -p "logs/status/${STAMP}_lsof_input"
sudo lsof /dev/input/event0 /dev/input/event6 /dev/input/event7 /dev/input/event8 \
  | tee "logs/status/${STAMP}_lsof_input/lsof.txt"
sudo fuser -v /dev/input/event0 2>&1 | tee -a "logs/status/${STAMP}_lsof_input/lsof.txt"
```

**Godkjent output:** kun `Xorg` (og evt. `systemd-logind`).  
**Eskaler:** ukjent PID, python, paths i `/tmp`/`/home`, eller binary under `(deleted)`.

---

## Artefakter

Full dump under `logs/status/2026-08-11_0213_keylog_deep/`  
(a–t: proc fd, X11 clients, libs, a11y, deleted, xorg log, root procs, …)
