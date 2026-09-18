# Remediation / endringslogg

Format: dato — hva — hvorfor — referanse (finding/rapport).

## 2026-08-10

- Opprettet `kalived/` struktur for intern host-sikkerhet.
- Baseline-kartlegging uten sudo (porter, tjenester, UFW config, sysctl, docker).
- Rapport: `reports/2026-08-10_baseline-security.md`.
- Findings F-001–F-008 åpnet (F-008 accepted/monitor).
- **Ingen systemendringer** (kun dokumentasjon + snapshots).

### 2026-08-10 ~23:21 (sudo-verifikasjon)

- `collect-baseline.sh` → `logs/status/2026-08-10_2321/`
- `sudo ufw status verbose` + `nft list ruleset` + `aa-status` kjørt av operator.
- **F-001 closed:** UFW active, default deny in, empty user rules, live policy drop.
- **F-003 updated:** kun `docker-default` profil lastet; severity medium.
- Artefakter: `logs/ufw/2026-08-10_2321_status.txt`, `scans/firewall/2026-08-10_2321_nft_summary.md`, `reports/2026-08-10_sudo-verify.md`.
- Fortsatt **ingen** hardening-endringer på systemet (kun lesing + docs).

### 2026-08-11 ~02:04 — AppArmor enable

- Operator: `sudo systemctl enable --now apparmor`
- Verified enabled+active; profiles reloaded (journal OK)
- **F-003 fixed**

### 2026-08-11 ~02:07 — Keylogscan

- Scan uten root: prosesser, input devices, cron, autostart, LD_PRELOAD, pakker
- Resultat: **clean** → F-009 closed
- Rapport: `reports/2026-08-11_apparmor-and-keylogscan.md`
- Snapshot: `logs/status/2026-08-11_0207_keylogscan/`

### 2026-08-11 ~02:18 — Kill gray-area processes

- Full scan: **no malware** (logkeys/miners/shells/deleted-exec)
- Killed (surface reduction / input-related gray area):
  - `xcape` (2540) — Super-key remap, not keylogger; will return at next login via `/etc/xdg/autostart/` unless disabled with sudo
  - `gvfsd-network` (15119), `gvfsd-dnssd` (15143) — LAN discovery
  - `obexd` (2796) — Bluetooth file-transfer agent
- Left running on purpose: XFCE, Xorg, Firefox, Cursor, grok, svl, docker daemon
- Log: `logs/status/2026-08-11_0218_kill_suspects/`

### 2026-08-11 ~02:13 — Keylog DEEP

- /proc fd-scan alle lesbare PIDs for event*/uinput
- X11: xlsclients, RECORD/XTEST, libXi/libXtst/libevdev maps
- AT-SPI bus names, xcape/genmon, deleted exes, Xorg.log libinput, root cmdlines
- Rapport: `reports/2026-08-11_keylog_deep.md`
- Snapshot: `logs/status/2026-08-11_0213_keylog_deep/`
- Funnet: **xcape** (legitim remap). Ingen keylogger-indikator.
- Residual: trenger `sudo lsof /dev/input/event0` for root raw-device 100 %

### 2026-08-13 ~10:15 — continue harden (user-level + playbook)

- Context: user reported iQOO phone compromised live days ago; PC often tethered via phone (now usb0).
- Killed again: xcape, gvfsd-network, gvfsd-dnssd, obexd.
- User autostart override: ~/.config/autostart/xcape-super-key-bind.desktop (Hidden=true).
- Added: playbooks/harden-host-sudo.sh (SSH mask, guest-utils off, sysctl, UFW, AppArmor, xcape system disable).
- Report: reports/2026-08-13_continue-hardening.md
- **Awaiting sudo run of harden-host-sudo.sh**

### 2026-08-13 ~10:19 — hermetic check (Kali + cep1er path)

- Clarified: tether via **cep1er** (not iQOO); open guest WiFi; iQOO off/PIN locked later.
- Kali: **no non-localhost listeners**, SSH off, no reverse-shell patterns, no deleted exes, 0 authorized_keys.
- UFW enabled (default DROP in config), AppArmor active.
- Phone gateway 192.168.57.4: only **:53 DNS** open of probed set; ADB 5555 closed.
- Report: reports/2026-08-13_hermetic-kali-and-cep1er.md
- Snapshot: logs/status/2026-08-13_1019_hermetic/
- Still pending: sudo harden-host-sudo.sh (guest-utils, sysctl, mask ssh, etc.)

### 2026-08-13 — master plan (Kali + cep1er + iQOO)

- Topology confirmed: open guest WiFi → cep1er → USB tether → Kali (not iQOO).
- Plans written:
  - playbooks/cep1er-phone-checklist.md
  - playbooks/iqoo-access-or-reset-plan.md
  - reports/2026-08-13_master-plan.md
- Kali harden still needs: sudo bash playbooks/harden-host-sudo.sh

### 2026-08-13_1028 — harden-host-sudo.sh
- SSH disabled/masked
- open-vm-tools + virtualbox-guest-utils disabled
- xcape system autostart disabled
- sysctl /etc/sysctl.d/99-kalived-hardening.conf applied
- UFW deny-in reasserted
- AppArmor ensure enabled
- Log: logs/status/2026-08-13_1028_harden/

### 2026-08-13_1028 — harden verified (operator ran script)

- SSH masked, guest-utils disabled, xcape system desktop .disabled
- sysctl 99-kalived-hardening.conf live
- UFW deny-in reasserted; AppArmor 117 profiles
- F-003, F-004, F-006 closed; report: reports/2026-08-13_harden-verified.md

### 2026-08-13_1034 — full root PC audit

- UFW active deny-in; nft INPUT drop; empty user rules
- 0 external listeners; SSH masked; no authorized_keys
- lsof /dev/input: only logind+Xorg(+upower) — clean
- no reverse shells, deleted exes, ld.so.preload
- AppArmor 117 profiles; sysctl hardened
- Phone gw 192.168.57.4: only :53 open (ADB 5555 closed)
- Report: reports/2026-08-13_full-root-pc.md
- Snapshot: logs/status/2026-08-13_1034_full_root/

### 2026-08-13 — cep1er checklist progress

- A1 USB-debugging: user reported complete (was ON → addressed as A1)

### 2026-08-13_1548 — cep1er ADB scan

- tools/adb (Google platform-tools); device ZTE Z2472 authorized
- 20 third-party apps; no spy/RAT keywords; a11y enabled empty; device admin empty
- Report: reports/2026-08-13_cep1er-adb-scan.md
- Snapshot: logs/status/2026-08-13_1548_adb_phone/
- USER ACTION: turn USB debugging OFF + revoke authorizations

### 2026-08-13_1632 — harden-host-sudo.sh
- SSH disabled/masked
- open-vm-tools + virtualbox-guest-utils disabled
- xcape system autostart disabled
- sysctl /etc/sysctl.d/99-kalived-hardening.conf applied
- UFW deny-in reasserted
- AppArmor ensure enabled
- Log: logs/status/2026-08-13_1632_harden/

### 2026-08-13_1638 — WiFi vs tether diagnosis

- No VPN/tunnel/proxy middleware on host
- Dual default routes: usb0 metric 100 wins over wlan0 metric 600
- wlan0 has captive portal: https://gjest.ihelse.net/guest/guest_splashpage.php
- ping/https fail via wlan0 until portal auth; tether works because phone already authorized
- Report: reports/2026-08-13_wifi-vs-tether-diagnosis.md

### 2026-08-13 — iQOO primary incident plan

- User: cep1er factory-reset yesterday; out of picture
- iQOO: live hack observed; unknown boot PIN; ~200 odd strings in security settings; voices heard after SIM removed (implies WiFi/remote mic, not just cellular)
- All authenticator/2FA on iQOO → account lockout elsewhere
- Plan: playbooks/iqoo-2fa-lockout-and-wipe.md (recover accounts without phone → wipe iQOO → new 2FA)

## 2026-09-17 — fase 0 + rebuild start

- Design: `reports/2026-09-17_rebuild-design.md` (rev 4). PR 1 runbook + F-011–F-019.
- Fase 0 snapshot (non-sudo, denne sesjonen uten TTY-sudo): `logs/status/2026-09-17_1443/`. Rapport: `reports/2026-09-17_phase0-fresh-snapshot.md`. **Ingen systemendring.**
- `collect-baseline.sh`: `systemctl is-active/is-enabled` tåler exit ≠ 0 (`set -e`).
- Operator: live scan/baseline **alltid sudo**. G3/G8 lukkes ved neste `sudo`-kjøring.
- Inventory oppdatert (kernel 7.1.5, eth0+ProtonVPN, guest-utils disabled, disk 95 %).
- PR 2: `scripts/kalived-scan.sh` (live krever root), verdict CLEAN/WARN/ALERT/ERROR, NET-LISTEN-EXT + PERS-UID0 + SSH-unit. Tester: `./scripts/tests/run.sh`.

### 2026-09-17_145806 — første sudo-scan

- Maskin sa CLEAN. Manuell gjennomgang: **UFW 8000 ALLOW IN Anywhere** (ikke i august-baseline). F-020.
- Rapport: `reports/2026-09-17_sudo-scan-review.md`
- Etterpå: `check-firewall.sh` (NET-UFW-ALLOW), stille aa-status/nft, groups via SUDO_USER, chown snapshot til SUDO_USER, keylogscan hopper over kernel-tråder.

### 2026-09-17_151255 — sudo-scan etter ufw delete 8000

- Operator: `sudo ufw delete allow 8000` (v4+v6).
- Scan CLEAN; ufw-user-input tom; nft uten dport 8000. **F-020 fixed.**
- Freeze: `baselines/machine/SOURCE.txt` + `prev_snapshot.txt` → 151255.
- Residual støy: keylogscan self-grep på scriptnavn (fikset i script etterpå). Snapshot-`ls` i collect er før chown (ser root; etter scan er eier void).

### 2026-09-17 — persistensjakt + utgående heuristikk

- `scripts/hunt-persistence.sh` + check-persistence/process/outbound/network-hygiene.
- ALERT: ld.so.preload, extra SUID i /tmp/home, deleted exe, ncat/bash ESTAB, udev RUN=/tmp, authorized_keys med materiale.
- Proton VPN LD_PRELOAD og python→10.2.0.1 allowlistes via cmdline, ikke via «python er OK».
- Fixture-tester: alert_preload, alert_deleted, alert_ncat_estab, alert_suid_tmp. `./scripts/tests/run.sh` ALL OK.
- F-012/F-013: implemented, trenger live `sudo ./scripts/kalived-scan.sh`.

### 2026-09-17_160215 — sudo-scan etter FP-fiks

- CLEAN. INFO: Brave `chrome-sandbox` SUID, ProtonVPN DNS 10.2.0.1. svl user-unit allowlistet (ingen ALERT).
- Testdata-notify på skrivebord er av. Freeze prev_snapshot → 160215.

### 2026-09-17 — auditd + AIDE playbooks (ikke kjørt på host ennå)

- Gate: `playbooks/lib/kalived-gate.sh` nekter ved ALERT/ERROR (siste live CLEAN=160215).
- `journald-persistent.sh`, `auditd-mini.sh` + `auditd-mini.rules` (USB/execve kommentert), `ufw-logging-medium.sh`, `aide-init.sh` + `aide-99-kalived.conf`.
- Scan samler audit_rules/journald drop-in/ausearch/aide --check. F-014/F-015/F-017: kode klar, host-install venter sudo.
- Kjør: `sudo bash playbooks/run-auditd-then-aide.sh` deretter `sudo ./scripts/kalived-scan.sh`.

### 2026-09-17_162224 — etter run-auditd-then-aide

- journald persistent: OK. auditd active + kalived_* regler lastet (USB kommentert). UFW logging medium: OK.
- AIDE --init **feilet**: AIDE 0.19 kjenner ikke gruppenavn `mtime` (skal være `m`). Config rettet.
- WARN `PERS-SUID /usr/sbin/exim4`: **ekte ny SUID** fra `aide-common` som trakk inn exim4/bsd-mailx. Ikke innbrudd, men ekstra MTA-flate. Ikke whitelistet automatisk.
- Nye systembrukere (ikke UID 0): `_aide`, `Debian-exim` (nologin).

### 2026-09-17_163400 — AIDE init OK + CLEAN

- AIDE 0.19.3 DB 218 entries, `AIDE found NO differences`. Checksum i baselines/aide.sha256.
- Scan CLEAN. exim4 SUID borte fra suid.txt (MTA fjernet). Debian-exim-bruker kan ligge igjen som nologin-rest.

### 2026-09-17 — timer + docker-hygiene (kode, venter sudo)

- Helper `/usr/local/lib/kalived` root:root (ingen NOPASSWD mot home). System-timer weekly, SuccessExitStatus=1 2, logger til KALIVED_DATA=/home/void/kalived.
- Docker: behold gruppe; `--stop-idle` disable socket+service når 0 containere; `--prune` kun dangling. Modell: playbooks/docker-access-model.md
- Kjør: `sudo bash playbooks/run-timer-and-docker.sh` deretter `sudo ./scripts/kalived-scan.sh`

### 2026-09-17_1618 — journald-persistent.sh
- journald persistent 500M/14d (/etc/systemd/journald.conf.d/99-kalived.conf). Gate: ikke ALERT.

### 2026-09-17_1618 — auditd-mini.sh
- auditd + /etc/audit/rules.d/99-kalived.rules (USB/execve kommentert). Gate: ikke ALERT.

### 2026-09-17_1618 — ufw-logging-medium.sh
- ufw logging medium (ikke deny-out). Gate: ikke ALERT. Rollback: ufw logging low

### 2026-09-17_1632 — aide-init.sh
- AIDE kalived.db.gz init (identity/persistens). Gate: WARN. Checksum i baselines/aide.sha256

### 2026-09-17_165742 — timer+docker live

- Helper root:root, timer enabled (neste man 21.09 00:10). docker.socket/service inactive. void ∈ docker.
- Scan WARN AIDE = **våre** filer: +kalived-scan.{service,timer}, −docker wants. Re-init for ny kjent-god.

### 2026-09-17_170517 — CLEAN etter AIDE re-baseline

- AIDE NO differences (219 entries). timer enabled, docker.socket inactive, auditd active.
- Freeze prev_snapshot → 170517.

### 2026-09-17 — fase 8 rootkit defs (kode)

- rkhunter/chkrootkit/debsums playbook + hunt-rootkit + Kali-allowlists under defs/.
- `scripts/update-threat-defs.sh` + `defs/feeds.d/` (rkhunter enabled; URLhaus/CISA/The Register som eksempel, news aldri auto-ALERT).
- fail2ban: kun markdown-stub. Fixture alert_rkhunter → ALERT.
- Kjør: `sudo bash playbooks/run-fase8-rootkit.sh` deretter scan (rkhunter tar tid) og `install-kalived-helper.sh`.

### 2026-09-17_173947 — chkrootkit ALERT = FP

- chkrootkit: Debian-skjulte filer (llvm/ruby/firmware) + ifpromisc på NetworkManager/wpa_supplicant. Parser ALERT-et på overskrift `WARNING:`.
- rkhunter: XFCE shm, obsolete ssh Protocol, haveged sem, /etc/.updated.
- AIDE: vendor cron/timer for chkrootkit/rkhunter/debsums/exim. exim4 SUID tilbake.
- Parser+allowlist+disable-vendor-rk-cron. Helper uten ALERT-gate. SuckIT-fixture fortsatt ALERT.

### 2026-09-17_180808 — fase 8 CLEAN

- AIDE NO differences (225). rkhunter desktop-støy allowlistet (shm/Protocol/haveged/.updated). chkrootkit Debian/NM FP filtrert. exim4 SUID borte.
- Freeze prev_snapshot → 180808. F-018 closed.

### 2026-09-17 — config.toml (PR 11)

- `config/kalived.toml.example`, parser `scripts/lib/kalived-config.sh`, `playbooks/install-config.sh`.
- Scan/playbooks leser samme fil. Ugyldig enum og listen_bind≠loopback → ERROR 3.
- `docs/SURFACE.md` §6 oppdatert. Tester: bogus policy + 0.0.0.0.

### 2026-09-17 — local API + config-knapper

- Nye config: verbose, notify_on_alert, skip_hunt, skip_rootkit, defs_auto_update.
- `scripts/kalived-api.sh` + `api/server.py` (stdlib, 127.0.0.1, Bearer). POST scan/playbooks/defs krever root.
- OpenAPI: api/openapi.yaml. API-test i tests/run.sh.

### 2026-09-17_201000 — CLEAN etter sudoers i AIDE

- `sudo kalived-ctl scan` OK. Hunt+rootkit kjørte. AIDE NO differences (226, inkl. sudoers.d/kalived).
- INFO: Brave sandbox, Proton DNS. docker.socket inactive, timer enabled.
- Freeze prev_snapshot → 201000.

### 2026-09-17_1656 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-17_1656 — install-scan-timer.sh
- kalived-scan.timer weekly enabled. SuccessExitStatus=1 2. Opt-in av operator.

### 2026-09-17_1656 — docker-hygiene.sh
- F-005: behold docker-gruppe. stop-idle=1 prune=1. Marker /etc/kalived/docker-stop-idle. Start: systemctl start docker

### 2026-09-17_1704 — aide-init.sh
- AIDE kalived.db.gz init (identity/persistens). Gate: WARN. Checksum i baselines/aide.sha256

### 2026-09-17_1709 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-17_1732 — rkhunter-setup.sh
- rkhunter+chkrootkit+debsums. --propupd. lsmod.expected freeze. Defs: defs/ + update-threat-defs.sh

### 2026-09-17_1807 — aide-init.sh
- AIDE kalived.db.gz init (identity/persistens). Gate: WARN. Checksum i baselines/aide.sha256

### 2026-09-17_1927 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-17_1930 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-17_1937 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-17_1939 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-17_1955 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-17_2008 — aide-init.sh
- AIDE kalived.db.gz init (identity/persistens). Gate: ALERT. Checksum i baselines/aide.sha256

### 2026-09-17_2219 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-17_2229 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-17_2247 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-17_2247 — aide-init.sh
- AIDE kalived.db.gz init (identity/persistens). Gate: CLEAN. Checksum i baselines/aide.sha256

### 2026-09-17_2303 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-17_2303 — aide-init.sh
- AIDE kalived.db.gz init (identity/persistens). Gate: WARN. Checksum i baselines/aide.sha256

### 2026-09-17_2358 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-18_0007 — aide-init.sh
- AIDE kalived.db.gz init (identity/persistens). Gate: WARN. Checksum i baselines/aide.sha256

### 2026-09-18_0120 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-18_0120 — aide-init.sh
- AIDE kalived.db.gz init (identity/persistens). Gate: CLEAN. Checksum i baselines/aide.sha256

### 2026-09-18_0155 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-18_0155 — aide-init.sh
- AIDE kalived.db.gz init (identity/persistens). Gate: WARN. Checksum i baselines/aide.sha256

### 2026-09-18_0240 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-18_0240 — aide-init.sh
- AIDE kalived.db.gz init (identity/persistens). Gate: CLEAN force=1 force_alert=0. Checksum i baselines/aide.sha256

### 2026-09-18_0417 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-18_0417 — aide-init.sh
- AIDE kalived.db.gz init (identity/persistens). Gate: CLEAN force=1 force_alert=0. Checksum i baselines/aide.sha256

### 2026-09-18_0435 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-18_0435 — aide-init.sh
- AIDE kalived.db.gz init (identity/persistens). Gate: CLEAN force=1 force_alert=0. Checksum i baselines/aide.sha256

### 2026-09-18_0502 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-18_0512 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-18_0512 — aide-init.sh
- AIDE kalived.db.gz init (identity/persistens). Gate: CLEAN force=1 force_alert=0. Checksum i baselines/aide.sha256

### 2026-09-18_0545 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-18_0551 — auditd-mini.sh
- auditd + /etc/audit/rules.d/99-kalived.rules (USB/execve kommentert). Gate: ikke ALERT.

### 2026-09-18_0601 — rkhunter-setup.sh
- rkhunter+chkrootkit+debsums. --propupd. lsmod.expected freeze. Defs: defs/ + update-threat-defs.sh

### 2026-09-18_0710 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-18_0716 — journald-persistent.sh
- journald persistent 500M/14d (/etc/systemd/journald.conf.d/99-kalived.conf). Gate: ikke ALERT.

### 2026-09-18_0716 — aide-init.sh
- AIDE kalived.db.gz init (identity/persistens). Gate: WARN force=1 force_alert=0. Checksum i baselines/aide.sha256

### 2026-09-18_0717 — auditd-mini.sh
- auditd + /etc/audit/rules.d/99-kalived.rules (USB/execve kommentert). Gate: ikke ALERT.

### 2026-09-18_0718 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-18_0718 — install-scan-timer.sh
- kalived-scan.timer weekly enabled. SuccessExitStatus=1 2. Opt-in av operator.

### 2026-09-18_0719 — journald-persistent.sh
- journald persistent 500M/14d (/etc/systemd/journald.conf.d/99-kalived.conf). Gate: ikke ALERT.

### 2026-09-18_0719 — journald-persistent.sh
- journald persistent 500M/14d (/etc/systemd/journald.conf.d/99-kalived.conf). Gate: ikke ALERT.

### 2026-09-18_0721 — ufw-logging-medium.sh
- ufw logging medium (ikke deny-out). Gate: ikke ALERT. Rollback: ufw logging low

### 2026-09-18_0722 — rkhunter-setup.sh
- rkhunter+chkrootkit+debsums. --propupd. lsmod.expected freeze. Defs: defs/ + update-threat-defs.sh

### 2026-09-18_0723 — rkhunter-setup.sh
- rkhunter+chkrootkit+debsums. --propupd. lsmod.expected freeze. Defs: defs/ + update-threat-defs.sh

### 2026-09-18_0726 — rkhunter-setup.sh
- rkhunter+chkrootkit+debsums. --propupd. lsmod.expected freeze. Defs: defs/ + update-threat-defs.sh

### 2026-09-18_0816 — install-kalived-helper.sh
- scan-kopi til /usr/local/lib/kalived root:root (timer ExecStart). Ingen NOPASSWD mot home.

### 2026-09-18_0932 — aide-init.sh
- AIDE kalived.db.gz init (identity/persistens). Gate: CLEAN force=1 force_alert=0. Checksum i baselines/aide.sha256

### 2026-09-18_0932 — auditd-mini.sh
- auditd + /etc/audit/rules.d/99-kalived.rules (USB/execve kommentert). Gate: ikke ALERT.
