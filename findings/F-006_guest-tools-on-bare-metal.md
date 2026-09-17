# F-006 — VMware/VirtualBox guest utils enabled på bare metal

| | |
|--|--|
| Status | **fixed** (disabled 2026-08-13_1028) |
| Severity | low |
| First seen | 2026-08-10 |

## Observasjon

`systemd-detect-virt` = **none**, maskin = LENOVO, men enabled:

- `open-vm-tools.service`
- `virtualbox-guest-utils.service`

Også SUID: `/usr/bin/vmware-user-suid-wrapper`.

## Risiko

Unødvendig attack surface / bakgrunnsstøy. Lav umiddelbar risk hvis tjenestene ikke
aktivt kjører med nettverkseksponering.

## Anbefalt handling

```bash
systemctl is-active open-vm-tools virtualbox-guest-utils
sudo systemctl disable --now open-vm-tools.service virtualbox-guest-utils.service
# evt. apt purge senere hvis sikker
```

## Done-kriterium

Disabled (eller begrunnelse for å beholde hvis dual-boot/VM-bruk).
