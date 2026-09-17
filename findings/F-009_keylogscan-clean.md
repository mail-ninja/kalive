# F-009 — Keylogger / input-viewer scan

| | |
|--|--|
| Status | **closed (clean, with residual note)** |
| Severity | info |
| Updated | 2026-08-11 deep scan |

## Resultat

### Lett scan (02:07)
Ingen pakker/prosessnavn/cron/LD_PRELOAD-treff.

### Dyp scan (02:13) — `reports/2026-08-11_keylog_deep.md`

- 0 userland holders av `/dev/input/*` (93 lesbare PIDs)
- 0 libevdev/pynput/logkeys i process maps
- xlsclients: kun forventet desktop + cursor/firefox/qterminal
- libXtst: kun at-spi registry + **xcape** (key remap, legitim)
- Ingen deleted executables, kernel tainted=0
- Xorg.log: libinput only for keyboard/touchpad

### Eneste input-relaterte «active tool»

`xcape` (Super→Escape) — ikke keylogger.

### Residual

Uten `sudo lsof /dev/input/event0` kan root-level raw keylogger ikke utelukkes 100 %.
