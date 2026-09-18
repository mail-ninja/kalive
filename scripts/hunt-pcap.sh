#!/usr/bin/env bash
# Short TCP burst on lo, overlapping nmap. Fields only — no pcapng, no payload.
# Four sieves: raw rows → drop scan-self/noise → enrich ports → class for join.
set -euo pipefail
OUT="${KALIVED_OUT:?}"
mkdir -p "$OUT"
if [[ "${KALIVED_FIXTURE:-0}" == "1" || "${KALIVED_FROM_DIR:-0}" == "1" ]]; then
  exit 0
fi
if [[ "${CFG_PCAP_LOCALHOST:-1}" != "1" ]]; then
  echo "pcap_localhost=0" > "$OUT/hunt_pcap.txt"
  exit 0
fi
if ! command -v tshark >/dev/null 2>&1; then
  echo "tshark missing" > "$OUT/hunt_pcap.txt"
  echo "[*] tshark mangler — hopp over lo-burst (sudo apt-get install -y tshark)" >&2
  exit 0
fi
dur="${CFG_PCAP_DURATION_S:-8}"
maxp="${CFG_PCAP_MAX_PACKETS:-4000}"
[[ "$dur" =~ ^[0-9]+$ ]] || dur=8
[[ "$maxp" =~ ^[0-9]+$ ]] || maxp=4000
(( dur >= 1 && dur <= 30 )) || dur=8
(( maxp >= 1 && maxp <= 20000 )) || maxp=4000

echo "[*] tshark lo SYN-ACK ${dur}s max=${maxp} (overlap nmap)" >&2
raw="$OUT/hunt_pcap_raw.txt"
# SYN+ACK only — nmap -sT floods lo with SYN/RST and would fill -c before :8787.
# tcp[tcpflags] & 0x12 == 0x12 is IPv4 SYN+ACK (portable BPF, not tcp-syn names).
timeout "$((dur + 3))" tshark -i lo -n -q \
  -a "duration:${dur}" -c "$maxp" \
  -f "tcp[tcpflags] & 0x12 == 0x12" \
  -T fields -E header=n -E separator=$'\t' \
  -e frame.time_epoch -e ip.src -e tcp.srcport -e ip.dst -e tcp.dstport \
  -e tcp.flags.syn -e tcp.flags.ack -e tcp.flags.reset \
  > "$raw" 2>"$OUT/hunt_pcap_tshark.err" || true
echo "iface=lo duration_s=$dur max_packets=$maxp" > "$OUT/hunt_pcap.txt"

python3 - "$OUT" "$dur" << 'PY' || true
import json, os, sys

out, dur = sys.argv[1], sys.argv[2]
raw_path = os.path.join(out, "hunt_pcap_raw.txt")
noise_path = None
root = os.environ.get("ROOT") or os.environ.get("KALIVED_ROOT") or ""
for cand in (
    os.path.join(root, "defs/ioc/tshark-noise-ports.txt") if root else "",
    os.path.join(os.path.dirname(out), "..", "..", "defs/ioc/tshark-noise-ports.txt"),
):
    if cand and os.path.isfile(cand):
        noise_path = cand
        break

noise_ports = {53, 80, 443, 5353, 546, 547}
if noise_path:
    for line in open(noise_path, encoding="utf-8", errors="replace"):
        s = line.strip()
        if s.isdigit():
            noise_ports.add(int(s))

rows = []
if os.path.isfile(raw_path):
    for line in open(raw_path, encoding="utf-8", errors="replace"):
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 8:
            continue
        try:
            src_p, dst_p = int(parts[2] or 0), int(parts[4] or 0)
        except ValueError:
            continue
        rows.append({
            "src": parts[1], "sport": src_p,
            "dst": parts[3], "dport": dst_p,
            "syn": parts[5] in ("1", "True", "true"),
            "ack": parts[6] in ("1", "True", "true"),
            "rst": parts[7] in ("1", "True", "true"),
        })

# nmap -sT uses a *new* sport per dest, so (src,sport) never hits 20 ports.
# Detect scan_self as many unique dports from lo SYNs (not per-flow).
lo = {"127.0.0.1", "::1"}
syn_dports = {r["dport"] for r in rows if r["src"] in lo and r["syn"] and not r["ack"]}
scan_self = len(syn_dports) >= 20

drops = []
kept_synack = []
drop_counts = {"scan_self": 0, "noise_port": 0, "other": 0}
for r in rows:
    if scan_self and r["src"] in lo and r["syn"] and not r["ack"]:
        drop_counts["scan_self"] += 1
        continue
    if scan_self and r["rst"] and r["ack"]:
        drop_counts["scan_self"] += 1
        continue
    if r["dport"] in noise_ports and r["dst"] not in ("127.0.0.1", "::1"):
        drop_counts["noise_port"] += 1
        continue
    if r["syn"] and r["ack"] and not r["rst"]:
        kept_synack.append(r)
    else:
        drop_counts["other"] += 1

with open(os.path.join(out, "hunt_pcap_drop.txt"), "w", encoding="utf-8") as f:
    f.write("# sieve2: scan_self=%d noise_port=%d other=%d\n" % (
        drop_counts["scan_self"], drop_counts["noise_port"], drop_counts["other"]))
    f.write("scan_self=%s syn_dports=%d\n" % (scan_self, len(syn_dports)))

# SYN-ACK source port is the listener; dest is the client's ephemeral.
# Using dport here produced PCAP-EXTRA on 33xxx/34xxx (nmap's sports).
synack_ports = sorted({
    r["sport"] for r in kept_synack
    if r["src"] in lo and r["syn"] and r["ack"] and not r["rst"]
})[:40]

# Join vs nmap/ss happens in check-pcap after both hunts finish.
summary = {
    "status": "ran",
    "iface": "lo",
    "duration_s": int(dur) if str(dur).isdigit() else dur,
    "raw_rows": len(rows),
    "kept_synack": len(kept_synack),
    "hidden_raw": len(rows),
    "hidden_kept": len(synack_ports),
    "drop": drop_counts,
    "synack_ports": synack_ports,
}
json.dump(summary, open(os.path.join(out, "hunt_pcap_summary.json"), "w", encoding="utf-8"), indent=2)
with open(os.path.join(out, "hunt_pcap_kept.txt"), "w", encoding="utf-8") as f:
    f.write("synack_ports=%s\n" % ",".join(map(str, synack_ports)))
    f.write("kept=%d\n" % len(synack_ports))
PY

echo "[+] tshark lo burst done" >&2
