# F-003 — AppArmor-service disabled

| | |
|--|--|
| Status | **fixed** (enabled; 117 profiles after harden 2026-08-13_1028) |
| Severity | was medium |
| First seen | 2026-08-10 |
| Closed | 2026-08-11 02:04 CEST |

## Fix

```bash
sudo systemctl enable --now apparmor
```

Verified:

- `enabled` + `active (exited)` since 2026-08-11 02:04:31
- Journal: Reloading AppArmor profiles — success

## Optional follow-up

```bash
sudo aa-status | tee logs/status/$(date +%Y-%m-%d_%H%M)/aa_status.txt
```

Document profile count for baseline (was only `docker-default` before enable).
