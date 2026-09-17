# Hvorfor ping bare funker via tether — ikke middleware

| | |
|--|--|
| Dato | 2026-08-13 ~16:38 |
| Snapshot | `logs/status/*_net_middleware/` |

## Konklusjon

**Ingen VPN, tunnel, proxy-middleware eller mistenkelig redirect** på Kali.  
Gjestenettet **`gjest.ihelse.net` krever web-login (captive portal)** for PC-en. Telefonen er sannsynligvis allerede «innlogget» på portalen, derfor fungerer tether.

## Bevis

### Middleware-sjekk (clean)

| Sjekk | Resultat |
|-------|----------|
| openvpn/wireguard/tailscale/tor/ssh-tunnel prosesser | **ingen** |
| tun/tap/wg interfaces | **ingen** |
| NM VPN-profiler | **ingen** |
| HTTP(S)_PROXY env / apt proxy | **ingen** |
| iptables REDIRECT/TPROXY (utover Docker) | **ingen** |
| Policy routing (ip rule) | standard 0/32766/32767 |
| Ekstra lyttere | bare localhost svl/containerd |

### Routing (dobbelt tilkoblet)

```
default via 192.168.57.4  dev usb0   metric 100   ← vinner (tether)
default via 10.95.48.1    dev wlan0  metric 600   ← gjest WiFi
```

Derfor går `ping 8.8.8.8` **via telefon** så lenge tether er på.

### Sammenligning wlan0 vs usb0

| Test | usb0 (tether) | wlan0 (gjest) |
|------|---------------|---------------|
| ping 8.8.8.8 | OK | **100% loss** |
| ping guest gw | — | **loss** (ICMP blokkert/isolert) |
| curl https://example.com | 200 | **reset / fail** |
| curl http neverssl / detectportal | — | **200 men redirect til portal** |

Portal-redirect:

```
https://gjest.ihelse.net/guest/guest_splashpage.php?...&mac=8c3b4a58e67c&...
```

= **Cisco/Ise-lignende guest splash** — ikke malware.

## Hva du skal gjøre for WiFi uten tether

1. Koble **fra** USB-tether.  
2. Bekreft WiFi: `nmcli -t device status` → wlan0 connected `gjest.ihelse.net`.  
3. Åpne i nettleser (må være **http**, ikke bare https til google):  
   - `http://gjest.ihelse.net/guest/guest_splashpage.php`  
   - eller `http://neverssl.com`  
4. Fullfør **gjestelogin** (vilkår / e-post / kode).  
5. Test: `ping -c 2 8.8.8.8` **og** `curl -I https://example.com`  
   - Noen gjestenett blokkerer ICMP fortsatt — da er curl mer pålitelig.

MAC på PC: `8c:3b:4a:58:e6:7c` (synlig i portal-URL).

## Ikke slett «alle nettverk» som fix

Det hjelper ikke mot captive portal. Du må **godta portal per enhet/MAC**.
