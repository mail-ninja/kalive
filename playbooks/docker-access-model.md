# Docker-tilgangsmodell (låst 2026-09-17, hygiene 2026-09-17)

**Avgjørelse:** `void` blir i `docker`-gruppen (praktisk for aegir). Det er lokal root-ekvivalent.

**Mitigering:**

- `docker-hygiene.sh --stop-idle`: stopper og **disable** `docker.socket` + `docker.service` når ingen containere kjører. Ikke auto-start ved boot.
- Når du trenger Docker: `sudo systemctl start docker`
- Aldri publish `0.0.0.0` — scannen ALERT-er.
- `--prune` fjerner bare dangling (`<none>`) images, ikke navngitte aegir-lag.

**Ikke:** rootless i denne runden, ikke fjerne gruppen, ikke NOPASSWD docker.
