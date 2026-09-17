# Harden-script verifisert — 2026-08-13_1028

Operator output + post-check.

## Resultat: SUCCESS

| Steg | Resultat |
|------|----------|
| SSH | **masked** / inactive |
| open-vm-tools / vbox guest | **disabled** |
| xcape system autostart | **→ .disabled** |
| Sysctl | kptr/dmesg/ptrace/rp_filter hardened; ip_forward=1 (Docker OK) |
| UFW | active, deny in / allow out / deny routed, logging low |
| AppArmor | **117 profiles loaded** (18 enforce, 23 complain, …) |
| Listeners | only 127.0.0.1 (svl 7878, containerd 43305) — **no external** |

## Findings closed by this run

- F-003 AppArmor — fixed (was already on; now confirmed many profiles)
- F-004 Sysctl — fixed
- F-006 Guest tools — fixed
- F-001 UFW — still fixed (reasserted)

## Still open

- F-002 fail2ban (optional; SSH off)
- F-005 docker group root-equivalent
- F-007 unattended upgrades / manual apt
- F-010 phone/tether operational risk
- iQOO recovery plan

## Next

1. cep1er checklist on phone
2. iQOO Find My / factory reset plan
3. Optional: docker policy when ready
