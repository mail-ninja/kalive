# fail2ban — ikke i denne rebuild (F-002)

SSH er **masked**. fail2ban uten lytter er hygiene-teater.

Når SSH (eller annen auth-lytter) slås på:

1. `apt install fail2ban`
2. Jail `sshd` + evt. sudo
3. Ikke bruk fail2ban som IDS-erstatning for `kalived-scan.sh`

Ikke installer nå. `dpkg -l fail2ban` skal forbli tom.
