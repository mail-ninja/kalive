# F-008 — Browser UDP på 0.0.0.0 (ephemeral)

| | |
|--|--|
| Status | accepted (monitor) |
| Severity | info |
| First seen | 2026-08-10 |

## Observasjon

```
udp UNCONN *:45730  x-www-browser
udp UNCONN *:48563  x-www-browser   # kan variere
```

Typisk WebRTC/media. Ikke TCP-listen. Ephemeral porter endres.

## Handling

Monitor i fremtidige port-scans. Ingen fix med mindre uønsket P2P.
UFW default INPUT DROP begrenser inbound hvis policy er aktiv (se F-001).
