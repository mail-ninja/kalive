# kalived — operatorflate (kontrakt for CLI og senere GUI)

Skrevet 2026-09-17 etter fase 8 CLEAN (`logs/status/2026-09-17_180808`).
Dette er **det som finnes**. Planlagte GUI/API-endepunkter er merket *planlagt*.

GUI skal være en **klient** av denne kontrakten, ikke et nytt deteksjonslag.

---

## 1. Hva systemet er

Host-SOC for én Kali-workstation (`void@kali`). Mål: avgjøre om maskinen **allerede er kompromittert**, med tydelig CLEAN / WARN / ALERT.

Live scan **krever root**. Testdata og `--fixture` krever ikke root.

Kjent-godt snapshot: `baselines/machine/prev_snapshot.txt` → `logs/status/2026-09-17_180808`.

---

## 2. Verdict-kontrakt (GUI-sannhet)

| Felt | Verdi |
|------|--------|
| Fil | `logs/status/<stamp>/verdict.json` |
| Schema | `1` |
| `verdict` | `CLEAN` \| `WARN` \| `ALERT` \| `ERROR` |
| `exit_code` | 0 / 1 / 2 / 3 |
| `sudo` | 0 \| 1 |
| `findings[]` | `{severity, id, title, detail, source}` |
| Banner | bokmål, rød/gul/grønn; `notify-send` på ALERT/ERROR (ikke `--fixture`) |
| Aggregering | ERROR > ALERT > WARN > CLEAN (INFO hever ikke) |

`reports/<stamp>_scan.md` = kopi av `VERDICT.md`.

---

## 3. CLI — inngangspunkter som finnes

### 3.1 `sudo ./scripts/kalived-scan.sh`

| Flagg | Effekt |
|-------|--------|
| *(ingen)* | live collect + hunt + rootkit + sjekker |
| `--sudo` | tving sudo-re-exec (default live) |
| `--from-dir DIR` | evaluer kopi av historisk snapshot; skriver ikke i DIR |
| `--fixture DIR` | som from-dir + testmodus (ingen live ss/ps) |
| `--skip-hunt` | hopp over hunt-persistence/keylog/rootkit; sjekker filer som finnes |
| `--quiet` | banner på stderr, JSON på stdout; `NO_COLOR=1` |
| `--help` | brukstekst |
| `--accept-alert-suppress` | **stub** — ignoreres |

Ukjent flagg → exit 3.

**Miljø:**

| Var | Rolle |
|-----|--------|
| `KALIVED_DATA` | logs/reports (default = kode-root) |
| `KALIVED_OUT` | tvungen snapshot-mappe |
| `KALIVED_STAMP` | tvungen stamp |
| `KALIVED_SUDO` | 1 når root |
| `KALIVED_OWNER` | chown etter root-scan (timer: `void`) |
| `KALIVED_FIXTURE` / `KALIVED_FROM_DIR` | settes av flagg |
| `NO_COLOR` | slå av ANSI |
| `KALIVED_AIDE_INIT_POLICY` | `clean_only` / `allow_known_warn` (default) / `always_prompt` — playbook |
| `SCAN_VERSION` | 5 (nå) |

Timer kjører: `/usr/local/lib/kalived/scripts/kalived-scan.sh --quiet` med `KALIVED_DATA=/home/void/kalived`.

### 3.2 Andre scripts

| Script | Sudo | Hva |
|--------|------|-----|
| `collect-baseline.sh` | ja for ufw/nft/aa | rå dump; kalles av scan |
| `hunt-persistence.sh` | ja | cron/systemd/preload/suid/docker/input |
| `hunt-rootkit.sh` | ja | rkhunter/chkrootkit/debsums/lsmod/taint |
| `keylogscan.sh` | ja for lsof | heuristikk |
| `update-threat-defs.sh` | ja | rkhunter `--update` + `defs/feeds.d/` |
| `tests/run.sh` | nei | fixture-tester |
| `adb-phone-scan.sh` | nei | **utenfor** host-scan (telefon) |

---

## 4. Finding-ID-er (GUI-rader)

### ALERT (løses, ikke whitelist uten evidens)

| ID | Trigger |
|----|---------|
| `NET-LISTEN-EXT` | TCP LISTEN utenfor loopback |
| `NET-SSH-UNIT` | ssh active/enabled |
| `NET-UFW` | UFW ikke active |
| `NET-UFW-ALLOW` | ALLOW IN vs tom baseline |
| `NET-NFT-NAT` | REDIRECT/DNAT/TPROXY utenom Docker-MASQ |
| `NET-PROMISC` | PROMISC på ikke-lo |
| `NET-DNS` | privat NS ≠ gw (unntak Proton 10.2.0.1) |
| `NET-ESTAB` | ncat/bash/ukjent python ESTAB ut |
| `PROC-TMPNET` | cwd /tmp+/dev/shm + ESTAB |
| `PROC-DELETED` / `PROC-MEMFD` | deleted/memfd exe |
| `PROC-INPUT` | ukjent holder av `/dev/input/event*` |
| `PROC-NAME` | ngrok/anydesk/… (supplement) |
| `PERS-UID0` | extra UID 0 |
| `PERS-PRELOAD` | ld.so.preload eller ukjent LD_PRELOAD |
| `PERS-AUTHKEYS` | nøkkelmateriale i authorized_keys |
| `PERS-CRON` / `PERS-RC` / `PERS-UDEV` / `PERS-AUTOSTART` | curl\|sh /tmp |
| `PERS-SUID` | SUID i home/tmp/opt (unntak chrome-sandbox) |
| `PERS-DOCKER` | privileged / 0.0.0.0 / docker.sock |
| `PERS-SYSTEMD` | ExecStart payload / ukjent home-unit |
| `FIM-AIDE` | AIDE endring i passwd/sudoers/ssh/preload/sudo |
| `FIM-DEBSUMS` | mismatch sudo/libc/ssh/systemd |
| `ROOT-RKH` | rkhunter/chkrootkit etter Kali-allow |
| `ROOT-LSMOD` | LKM-navn hide/adore/… |
| `ROOT-PROC-SS` | LISTEN i /proc/net/tcp, ikke i ss |
| `SCAN` | orchestrator/python/modulkrasj (ofte ERROR) |

### WARN (hygiene / kjent avvik)

`PERS-SUID` ny i `/usr`, `PERS-DOCKER` socket idle, `PERS-SYSTEMD` spice-vdagent, `FIM-AIDE` systemd/cron mtime, `ROOT-RKH` rkhunter-støy, `ROOT-TAINT`, `ROOT-LSMOD` nye hw-moduler, `ROOT-BPF`, `F-007` dpkg > 30 d, `LOG-AUDIT`/`LOG-JOURNAL`, `NET-DNS` usb0 tether.

### INFO (hever ikke verdict)

Brave sandbox, Proton DNS, SNAP-MISS, timer ikke enabled, auditd-playbook ikke kjørt.

---

## 5. Playbooks (muterende) — GUI Confirm-knapper

Alle unntatt merket: **gate = siste `kalived_scan=1` verdict ≠ ALERT/ERROR**.

| Playbook | Gate | Effekt | Rollback |
|----------|------|--------|----------|
| `journald-persistent.sh` | ja | journald 500M/14d | slett drop-in, restart journald |
| `auditd-mini.sh` | ja | auditd + `99-kalived.rules` | slett rules, `augenrules --load` |
| `ufw-logging-medium.sh` | ja | `ufw logging medium` | `ufw logging low` |
| `aide-init.sh` | ja (+ policy) | init/re-baseline AIDE DB | slett `/var/lib/aide/kalived.db.gz` |
| `install-kalived-helper.sh` | **nei** | kopi root:root `/usr/local/lib/kalived` | slett prefix |
| `install-scan-timer.sh` | ja | weekly system-timer | `systemctl disable --now kalived-scan.timer` |
| `docker-hygiene.sh [--prune] [--no-stop]` | ja | stop-idle + dangling prune | `systemctl start docker` |
| `rkhunter-setup.sh` | ja | apt rkhunter/chkrootkit/debsums, propupd | apt remove |
| `disable-vendor-rk-cron.sh` | **nei** | slå av Debian-cron/timer | chmod +x / enable timer |
| `harden-host-sudo.sh` | nei (eldre) | SSH mask, UFW deny, sysctl, AA | se CHANGELOG |
| `update-threat-defs.sh` | nei (script) | rkhunter `--update` | n/a |
| `run-auditd-then-aide.sh` | via barn | fase 4–5 | |
| `run-timer-and-docker.sh` | via barn | fase 6–7 | |
| `run-fase8-rootkit.sh` | via barn | fase 8 | |

**Ikke installer:** fail2ban (`playbooks/install-fail2ban.md` kun tekst). SSH masked.

**Telefon** (utenfor host-GUI v1): `cep1er-phone-checklist.md`, `iqoo-*`.

Etter bevisst filendring: `aide-init.sh` deretter scan. Etter script-endring: `install-kalived-helper.sh`.

---

## 6. Runtime-config (`config.toml`) — **finnes**

Fil: `~/.config/kalived/config.toml` (ikke i git).  
Eksempel: `config/kalived.toml.example`.  
Install: `sudo bash playbooks/install-config.sh`.  
Parser: `scripts/lib/kalived-config.sh`. Ugyldig enum / `listen_bind` ≠ loopback → scan **ERROR exit 3**.  
Override: `KALIVED_CONFIG=/sti/til.toml`.

| Nøkkel | Default | Merknad |
|--------|---------|---------|
| `aide_init_policy` | `allow_known_warn` | `clean_only` / `always_prompt` |
| `scan_sudo_mode` | `prompt` | `helper` / `never`; live krever fortsatt root |
| `docker_stop_idle` | true | playbook default; `--no-stop` overstyrer |
| `timer_enabled` | true | GUI-felt; systemd er sannhet |
| `ai_enabled` | false | SpaceXAI advisor |
| `ai_model` | `grok-4.6` | |
| `ai_after_scan` | true | etter interaktiv scan (ikke timer) |
| `listen_bind` | `127.0.0.1` | kun loopback; **ikke** `0.0.0.0` |
| `listen_port` | 8787 | 1–65535 |
| `apparmor_enforce_selected` | false | F-019 |
| `nmap_localhost` | true | TCP-scan kun 127.0.0.1, parallelt med rkhunter |
| `nmap_port_spec` | `"-"` | nmap `-p` (siffer/`,`/`-`). Ikke CIDR/host |
| `helper_stale_check` | true | WARN helper ≠ git-tre |
| `aide_watch_helper` | true | AIDE på `/usr/local/lib/kalived` + ctl |

---

## 7. HTTP-endepunkter — **finnes** (loopback)

Start: `sudo kalived-ctl api` (etter `playbooks/install-nopasswd-ctl.sh`).  
Token: `~/.config/kalived/api.token` eid av **void** (ikke root). Bearer eller `X-Kalived-Token`.  
OpenAPI: `api/openapi.yaml`. Bind fra config; **ikke** `0.0.0.0`.

| Metode | Sti | Mapper til |
|--------|-----|------------|
| GET | `/v1/health` | prosess oppe |
| GET | `/v1/verdict/latest` | siste `verdict.json` |
| GET | `/v1/snapshots` | `logs/status/*` |
| GET | `/v1/snapshots/{stamp}` | snapshot + VERDICT.md |
| POST | `/v1/scan` | `kalived-scan.sh` (sudo/polkit) |
| GET | `/v1/findings` | aggregert ID-katalog |
| GET | `/v1/config` | `config.toml` |
| PUT | `/v1/config` | skriv tillatte nøkler |
| POST | `/v1/playbooks/{name}` | Confirm + gate |
| POST | `/v1/defs/update` | `update-threat-defs.sh` |
| GET | `/v1/defs/feeds` | `defs/feeds.d/` |
| POST | `/v1/ai/advise` | SpaceXAI, redacted verdict.json. Body: `{stamp?, ask?}`. Ikke root. |

Auth: token i `~/.config/kalived/api.token` modus 0600. AI får aldri sudo.

---

## 8. Defs / oppdateringer

| Sti | Rolle |
|-----|--------|
| `defs/VERSION` | 1 |
| `defs/kali-allow/rkhunter-allow.txt` | FP-strenger |
| `defs/kali-allow/chkrootkit-allow.txt` | FP-strenger |
| `defs/feeds.d/rkhunter.feed` | enabled — `rkhunter --update` |
| `defs/feeds.d/*.example` | URLhaus, CISA KEV, The Register (news, aldri auto-ALERT) |
| `defs/ioc/` | tom stub |
| `baselines/machine/*` | suid, lsmod, input holders, preload allow, systemd allow |
| `baselines/aide.sha256` | AIDE-DB checksum |

`sudo ./scripts/update-threat-defs.sh` — aldri `eval` av nedlastet innhold.

---

## 9. Tester (GUI skal ikke erstatte)

```bash
./scripts/tests/run.sh
```

Fixtures: `alert_listen_ncat`, `alert_uid0`, `alert_ufw_8000`, `alert_preload`, `alert_deleted`, `alert_ncat_estab`, `alert_suid_tmp`, `alert_docker_publish`, `alert_rkhunter`, `chkrootkit_debian_fp`, `clean_full_root`.

---

## 10. Host-tilstand (etter 180808)

| Komponent | Tilstand |
|-----------|----------|
| UFW | deny in, tomme user-regler, logging medium |
| SSH | masked |
| auditd | active, kalived_* |
| journald | persistent |
| AIDE | 225 entries, NO differences |
| timer | enabled, ukentlig |
| docker.socket | inactive (start: `systemctl start docker`) |
| docker-gruppe | void beholdt |
| rkhunter/chkrootkit | installert; vendor-cron av |
| fail2ban | ikke installert |

**Åpne hygiene:** F-005 gruppe=root-ekvivalent (mitigert stop-idle), F-019 AppArmor unconfined, F-002 fail2ban utsatt, F-007 manuell apt, disk 95 %, vmware SUID-wrapper.

---

## 11. GUI-byggerekkefølge (når vi bygger)

1. Denne filen + `config.toml` (PR 11) — knapper uten HTTP.
2. FastAPI 127.0.0.1 (PR 12) — tabellen i §7.
3. Tynn HTML (PR 13) — verdict, scan, playbook-confirm, defs-update.
4. AI advise (PR 14) — redacted JSON inn, Confirm-gate, ingen sudo.
