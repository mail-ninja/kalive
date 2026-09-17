# WiFi + ADB status — 2026-08-13

## ADB install

- `apt install adb` failed: Kali mirror **503 Service Unavailable**
- Installed Google **platform-tools** adb to `kalived/tools/adb` (v 37.0.1)
- Phone detected: **Unisoc/ZTE** serial `LZ0A36SEDDB003558`, USB mode `rndis_adb`
- State: **unauthorized** until user taps Allow on phone

## Laptop WiFi (gjest.ihelse.net)

Observed simultaneously:
- `wlan0` connected to **gjest.ihelse.net** (open), IP `10.95.51.166/21`, gw `10.95.48.1`
- `usb0` tether still up, IP `192.168.57.162`, gw `192.168.57.4`
- **Default route prefers USB tether** (metric 100 vs WiFi 600)

So laptop *can* associate to guest WiFi; earlier “rare errors” likely:
1. **Captive portal / guest policy** (hospital ihelse) — phones often pass portal more easily
2. **DHCP flap** (900s lease, reconnect loops in NM logs)
3. **Dual path confusion** — traffic still going via phone tether
4. Open WiFi with no encryption (SECURITY `--`) — some clients show warnings as “errors”

Internet currently works (via tether default route). Public IP seen via ifconfig.me: check live.

## What user must do for ADB scan

1. Unlock cep1er
2. USB debugging ON
3. Popup: **Allow USB debugging** from this computer → Allow
4. Say "kjør scan" or we re-run `scripts/adb-phone-scan.sh`
5. After: turn USB debugging OFF + revoke authorizations
