# Nå

HEAD `d9a8cfa`. Live `2026-10-26_123925` exit **2 ALERT**. SCAN_VERSION 12. Falco jsonl 0 (`duration_s=8` rc=124). HELPER-STALE borte. `protocol.json` på stamp (skuff, `src=rules`).

**ALERT FIM-AIDE identity:** `/etc/ssh/ssh_host_mldsa44_ed25519_key` · `…key.pub` · `/etc/ssh` · `/etc/ssh/ssh_config` · `/etc/ssh/ssh_config.d` · `…/20-systemd-ssh-proxy.conf` · `/etc/ssh/sshd_config` · `/etc/ssh/sshd_config.d` · `…/20-systemd-userdb.conf` · `/usr/bin/passwd` · `/usr/bin/su` · `/usr/bin/sudo`

**WARN path-for-path**

- FIM snap_proton: `snap-proton-vpn-{14,15}.mount` (multi-user, snapd.mounts) · `/etc/udev/rules.d/70-snap.proton-vpn.rules`
- FIM snap_other: `snap-snapd-28254.mount` (multi-user, snap, snapd.mounts)
- FIM other: `/etc/systemd/system/falco.service` · `falco-modern-bpf.service` · `falcoctl-artifact-follow.service` · `/etc/cron.daily/brave-browser` · `/etc/systemd/system/display-manager.service` · `/usr/bin/sudoedit` · `/usr/bin/sudoreplay`
- ROOT-LSMOD: `ccm`
- ROOT-RKH rkhunter file-property (61, apt): `/usr/sbin/{adduser,cron,fsck,groupadd,groupdel,groupmod,grpck,ifdown,ifup,init,ip,nologin,pwck,sshd,sulogin,sysctl,useradd,userdel,usermod,vipw}` · `/usr/bin/{bash,chattr,curl,dmesg,dpkg,dpkg-query,find,ip,ipcs,kill,ldd,less,locate,logger,login,lsattr,more,mount,newgrp,passwd,perl,pgrep,pkill,ps,size,ssh,strings,su,sudo,telnet,top,vmstat,w,watch,whereis,plocate,x86_64-linux-gnu-size,x86_64-linux-gnu-strings,inetutils-telnet,which.debianutils}` · `/usr/lib/systemd/systemd`
- ROOT-RKH chkrootkit: `/tmp/kalived-live-scan.sh` (wrapper, slettet)

**Vert**

| | |
|--|--|
| scan-timer | `kalived-scan.timer` enabled+active, weekly, neste 2026-11-02 00:08 CET |
| watch-timer | `kalived-watch.timer` enabled+active, 5 min |
| Falco | `falco` · `falco-modern-bpf` · `falcoctl-artifact-follow` masked/inactive; `falco-kmod` disabled |
| cockpit | `127.0.0.1:5173` Vite · `127.0.0.1:8788` uvicorn |
| helper | HELPER-STALE-settet 52 filer = git (mismatch tom). ctl `4afa3ea91e2c` = `/usr/sbin/kalived-ctl` |

**Hull**

1. **interp** — `kalived_interp` er python/sh/bash/dash; node og php er ute, ESTAB-shellish har php uten node.
2. **runtime-sil** — ingen HOST-RUNTIME for node/openssl/ca-certificates; F-007 er 30 dager uten dpkg.
3. **apt-identity vs ALERT-gate** — identity-AIDE etter apt er ALERT; `kalived-ctl aide-init --force` stopper på ALERT.
4. **UFW-tittel** — `NET-UFW-NOISE` tittel «støy, ikke angrep» er hardkodet når HIT/SCAN er tom.
5. **protocol.json uten skuff** — ctl/timer-scan skriver ikke protocol; Jev/rules først når skuffen henter verdict.
6. **8 s Falco** — burst etter watch; vindu mellom samples er usett.

**Cockpit kan** scan (`kalived-ctl`), Confirm (isolate/kill/aide-init/rkhunter/helper), watch (5 min), agent-loop (`repo_*` + preview bak hake).

README: Arbeid-loopen sitter. Hiroshima ser burst og rydder bak Confirm.
