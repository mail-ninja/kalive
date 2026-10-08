# Scan-kontrakt (CLI / findings / :8787)

Kontrakt for **scan, findings, config og den eldre API-en**. Produkt og cockpit: [README.md](../README.md), [COCKPIT.md](COCKPIT.md). Protokoll: [HIROSHIMA.md](HIROSHIMA.md).

Cockpit (`:5173` / `:8788`) er klient av `verdict.json`, `protocol.json` og `kalived-ctl`. Den er ikke et nytt deteksjonslag.

---

## 1. Hva systemet er

Host-SOC for én workstation. Avgjøre om maskinen **allerede er kompromittert**: CLEAN / WARN / ALERT / ERROR. Burst-scan + opt-in rolling egress-watch.

Live scan **krever root**. Testdata og `--fixture` krever ikke.

`baselines/machine/` og `outbound_proc.allow` er merkelapper, ikke rent-host-bevis.

---

## 2. Verdict-kontrakt

| Felt | Verdi |
|------|--------|
| Fil | `logs/status/<stamp>/verdict.json` |
| Schema | `1` |
| `verdict` | `CLEAN` \| `WARN` \| `ALERT` \| `ERROR` |
| `exit_code` | 0 / 1 / 2 / 3 |
| `sudo` | 0 \| 1 |
| `findings[]` | `{severity, id, title, detail, source}` |
| `baseline_ref` | machine-baselines + `prev_snapshot.txt` |
| Aggregering | ERROR > ALERT > WARN > CLEAN (INFO hever ikke) |

`reports/<stamp>_scan.md` = kopi av `VERDICT.md`. `protocol.json` forklarer; overskriver ikke.

---

## 3. CLI

### 3.1 `sudo kalived-ctl scan` → `kalived-scan.sh --quiet`

| Flagg | Effekt |
|-------|--------|
| *(ingen)* | live collect + hunt + rootkit + sjekker |
| `--from-dir DIR` | evaluer kopi av historisk snapshot |
| `--fixture DIR` | som from-dir + testmodus |
| `--skip-hunt` | hopp over hunt; sjekker filer som finnes |
| `--quiet` | banner på stderr, JSON på stdout. **Default for ctl** |

**Miljø:**

| Var | Rolle |
|-----|--------|
| `KALIVED_DATA` | logs/reports (default = kode-root) |
| `KALIVED_OUT` | tvungen snapshot-mappe |
| `KALIVED_STAMP` | tvungen stamp |
| `KALIVED_OWNER` | chown etter root-scan og watch (`SUDO_USER`) |
| `KALIVED_OWNER_HOME` | config/window-sti når systemd mangler `HOME` |
| `KALIVED_AIDE_INIT_POLICY` | `clean_only` / `allow_known_warn` (default) / `always_prompt` |
| `SCAN_VERSION` | 12 |

Timer: `/usr/local/lib/kalived/scripts/kalived-scan.sh --quiet` med `KALIVED_DATA` = operatorens workspace.

### 3.2 Andre scripts

| Script | Sudo | Hva |
|--------|------|-----|
| `collect-baseline.sh` | ja for ufw/nft/aa | rå dump |
| `hunt-persistence.sh` | ja | cron/systemd/preload/suid/docker/input |
| `hunt-rootkit.sh` | ja | rkhunter/chkrootkit/debsums/lsmod/taint |
| `keylogscan.sh` | ja for lsof | heuristikk; tåler ubundet `HOME` |
| `kalived-falco.sh` | ja | host-burst ~8 s |
| `kalived-watch.sh` | ja | H4-sample |
| `update-threat-defs.sh` | ja | rkhunter `--update` + `defs/feeds.d/` |
| `tests/run.sh` | nei | fixture-tester |

---

## 4. Finding-ID-er

### ALERT (løses, ikke whitelist uten evidens)

| ID | Trigger |
|----|---------|
| `NET-LISTEN-EXT` | TCP LISTEN utenfor loopback |
| `NET-NMAP` | nmap åpen TCP på 127.0.0.1 som ss ikke viser |
| `NET-NMAP-SVC` | nmap `-sV` meterpreter/backdoor/trojan |
| `NET-SSH-UNIT` | ssh active/enabled |
| `NET-UFW` | UFW ikke active |
| `NET-UFW-ALLOW` | ALLOW IN vs tom baseline |
| `NET-UFW-HIT` | UFW BLOCK/ALLOW mot lyttende port med `IN≠lo` |
| `NET-NFT-NAT` | REDIRECT/DNAT/TPROXY utenom Docker-MASQ |
| `NET-PROMISC` | PROMISC på ikke-lo |
| `NET-DNS` | privat NS ≠ gw (unntak kjent VPN-DNS) |
| `NET-ESTAB` | ncat/bash/ukjent python ESTAB ut |
| `PROC-TMPNET` | cwd /tmp+/dev/shm + ESTAB |
| `PROC-DELETED` / `PROC-MEMFD` | deleted/memfd exe |
| `PROC-INPUT` | ukjent holder av `/dev/input/event*` |
| `PROC-HIDDEN` | sil 4: PID lever, usynlig for `ps`, exe deleted/memfd |
| `PROC-FAKEKTH` | sil 4: `[kworker…]` men PPID≠2 eller userspace-exe |
| `PROC-COMMEXE` | sil 4: comm≠exe på tmp/shm/home |
| `PERS-UID0` | extra UID 0 |
| `PERS-PRELOAD` | ld.so.preload eller ukjent LD_PRELOAD |
| `PERS-AUTHKEYS` | nøkkelmateriale i authorized_keys |
| `PERS-SUID` | SUID i home/tmp/opt (unntak chrome-sandbox) |
| `PERS-DOCKER` | privileged / 0.0.0.0 / docker.sock |
| `FIM-AIDE` | identity=ALERT; self_sudoers/snap_*/other=WARN; self_helper=INFO |
| `HOST-FALCO` | Falco + FIM eller nett = ALERT. Falco alene = WARN/candidate |
| `FIM-DEBSUMS` | mismatch sudo/libc/ssh/systemd |
| `ROOT-RKH` | rkhunter/chkrootkit etter kali-allow |
| `SCAN` | orchestrator-krasj (ofte ERROR) |

### WARN (hygiene)

AIDE etter egen install (sudoers, VPN-snap, Falco-units), `ROOT-LSMOD` nye hw-moduler, `ROOT-RKH` kjent støy, `PROC-HIDDEN-WEAK`, `PCAP-EXTRA`, `HOST-FALCO` candidate. Falco + FIM/nett hever til ALERT (høyeste severity per id).

### INFO (hever ikke)

Brave sandbox, VPN-DNS, `PROC-HIDDEN-NOISE`, `PCAP-NOISE`, `NET-UFW-NOISE`, `HOST-FALCO` absent/rejected/engine failed.

---

## 5. Playbooks (Confirm)

Gate = siste `kalived_scan=1` verdict ≠ ALERT/ERROR, med mindre merket.

| Playbook | Gate | Effekt |
|----------|------|--------|
| `auditd-mini.sh` | ja | auditd + `99-kalived.rules` |
| `aide-init.sh` | ja | default **scoped** (sudoers+helper+watch). `--all` = full DB (gjemmer VPN-snap). Confirm kaller ikke `--all`. `--force` tillater WARN; hopper ikke over ALERT |
| `install-kalived-helper.sh` | nei | kopi `root:root` `/usr/local/lib/kalived` |
| `install-scan-timer.sh` | ja | ukentlig timer |
| `install-watch-timer.sh` | ja | 5 min egress |
| `rkhunter-setup.sh` | ja | apt rkhunter/chkrootkit/debsums |
| `install-falco-host.sh` | ja | printer tredjeparts-apt; kjører den ikke. Masker units |
| `isolate-dst.sh` / `isolate-undo.sh` | ja | UFW deny-out mot unknown dest fra scan-snapshot |
| `kill-pid.sh` | ja | exe-match, ikke ours |

Etter script-endring: helper-install. Etter bevisst filendring: scoped aide-init, deretter scan. `--force-alert` bare når evidens allerede er lagret.

---

## 6. Runtime-config (`config.toml`)

Fil: `~/.config/kalived/config.toml` (ikke i git). Eksempel: `config/kalived.toml.example`. Ugyldig enum / `listen_bind` ≠ loopback → scan ERROR exit 3.

| Nøkkel | Default | Merknad |
|--------|---------|---------|
| `aide_init_policy` | `allow_known_warn` | |
| `watch_timer` | false | H4 5 min. Opt-in |
| `ai_enabled` | false | |
| `ai_model` | `grok-4.6` | |
| `listen_bind` | `127.0.0.1` | **ikke** `0.0.0.0` |
| `nmap_localhost` | true | bare 127.0.0.1 |
| `pcap_localhost` | true | tshark lo-burst |
| `pcap_duration_s` | 8 | 1–30 |
| `helper_stale_check` | true | WARN helper ≠ git |

---

## 7. Eldre HTTP `:8787`

`sudo kalived-ctl api`. Token: `~/.config/kalived/api.token` 0600. OpenAPI: `api/openapi.yaml`. Bind fra config; ikke `0.0.0.0`.

Primær GUI er cockpit `:5173`. `:8787` er urørt stdlib-UI.

---

## 8. Defs

| Sti | Rolle |
|-----|--------|
| `defs/VERSION` | 2 |
| `defs/falco-host.yaml` | host-regler (ikke stock) |
| `defs/falco.yaml` | `engine.kind=modern_ebpf`, plugins av |
| `defs/kali-allow/` | rkhunter/chkrootkit FP |
| `defs/feeds.d/` | rkhunter `--update`; examples er aldri auto-ALERT |
| `defs/ioc/` | process-names, tshark-noise-ports |
| `baselines/machine/*` | suid, lsmod, preload, systemd |

`sudo kalived-ctl defs` — aldri `eval` av nedlastet innhold.

---

## 9. Tester

```bash
./scripts/tests/run.sh
```

Fixtures under `scripts/testdata/cases/` (ALERT, WARN, CLEAN, Falco empty/absent/rejected). GUI erstatter ikke denne suiten.

Host-tilstand leses fra siste `verdict.json`, ikke fra denne fila.
