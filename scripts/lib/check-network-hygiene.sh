# shellcheck shell=bash

check_network_hygiene() {
  local nft="$OUT/nft_ruleset.txt"
  if [[ ! -f "$nft" || ! -s "$nft" ]]; then
    if kalived_is_live; then
      add_finding WARN SUDO-MISS-NFT "nft_ruleset.txt mangler" "" "nft_ruleset.txt"
    else
      add_finding INFO SNAP-MISS "nft_ruleset.txt ikke i snapshotet" "" "nft_ruleset.txt"
    fi
  else
    if grep -E 'redirect|dnat to|tproxy' "$nft" | grep -viE 'comment|"dnat"' >/dev/null 2>&1; then
      # nft keywords REDIRECT / dnat
      if grep -Ei '^\s*(redirect|dnat |tproxy )' "$nft" >/dev/null 2>&1; then
        local hits
        hits="$(grep -Ein 'redirect|dnat |tproxy' "$nft" | grep -vi masquerade || true)"
        if [[ -n "$hits" ]]; then
          add_finding ALERT NET-NFT-NAT "nft REDIRECT/DNAT/TPROXY utenfor forventet Docker-MASQUERADE" "$hits" "nft_ruleset.txt"
        fi
      fi
    fi
  fi

  local link="$OUT/ip_link_detail.txt"
  if [[ -f "$link" ]]; then
    if grep -E 'PROMISC' "$link" | grep -vE 'lo:|LOOPBACK' >/dev/null 2>&1; then
      add_finding ALERT NET-PROMISC "Nettverksgrensesnitt i PROMISC" "$(grep PROMISC "$link")" "ip_link_detail.txt"
    fi
  elif kalived_is_live; then
    add_finding INFO SNAP-MISS "ip_link_detail.txt ikke samlet" "" "ip_link_detail.txt"
  fi

  local res="$OUT/resolv.txt"
  if [[ -f "$res" ]]; then
    local ns
    ns="$(awk '/^nameserver/ {print $2}' "$res" | head -5 | tr '\n' ' ')"
    local gw
    gw="$(awk '/^default/ {print $3; exit}' "$OUT/ip_route.txt" 2>/dev/null || true)"
    # ALERT if nameserver is RFC1918 and not gw and not stub
    local py
    py="$(command -v python3 || command -v python || true)"
    if [[ -n "$py" && -n "$ns" ]]; then
      "$py" - "$ns" "$gw" << 'PY'
import ipaddress, sys
nss, gw = sys.argv[1].split(), sys.argv[2]
ok_stub = {"127.0.0.53", "127.0.0.1", "::1"}
try:
    gw_ip = ipaddress.ip_address(gw) if gw else None
except Exception:
    gw_ip = None
bad = []
for n in nss:
    if n in ok_stub:
        continue
    try:
        ip = ipaddress.ip_address(n)
    except Exception:
        continue
    if ip.is_private and gw_ip and ip != gw_ip:
        bad.append(n)
    elif ip.is_private and gw_ip is None:
        pass
open("/tmp/kalived-dns-bad", "w").write("\n".join(bad))
PY
      if [[ -s /tmp/kalived-dns-bad ]]; then
        local dnsbad
        dnsbad="$(cat /tmp/kalived-dns-bad)"
        if [[ "$dnsbad" == *10.2.0.1* ]] && grep -qE 'proton0|ProtonVPN' "$OUT/nm_active.txt" "$OUT/ip_addr.txt" 2>/dev/null; then
          add_finding INFO NET-DNS "Nameserver 10.2.0.1 er ProtonVPN-gw (ikke hijack)" "$ns gw=$gw" "resolv.txt"
        else
          add_finding ALERT NET-DNS "Nameserver er privat IP som ikke er default-gw: $dnsbad" "$ns gw=$gw" "resolv.txt"
        fi
      fi
      rm -f /tmp/kalived-dns-bad
    fi
  fi
  if [[ -f "$OUT/ip_route.txt" ]] && grep -qE 'dev usb0' "$OUT/ip_route.txt"; then
    if grep -qE '^default .* usb0' "$OUT/ip_route.txt"; then
      add_finding WARN NET-DNS "Default route via usb0 (tether, F-010)" "$(grep '^default' "$OUT/ip_route.txt")" "ip_route.txt"
    fi
  fi
}
