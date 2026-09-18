# shellcheck shell=bash

check_pcap() {
  [[ "${CFG_PCAP_LOCALHOST:-1}" == "1" ]] || return 0
  local note="$OUT/hunt_pcap.txt"
  local sum="$OUT/hunt_pcap_summary.json"

  if [[ -f "$note" ]] && grep -q 'pcap_localhost=0' "$note"; then
    return 0
  fi
  if [[ -f "$note" ]] && grep -q 'tshark missing' "$note"; then
    add_finding INFO PCAP-MISS "tshark ikke installert — lo-burst hoppet over" \
      "sudo apt-get install -y tshark" "hunt_pcap.txt"
    return 0
  fi
  if [[ ! -f "$sum" ]]; then
    if kalived_is_live; then
      add_finding INFO PCAP-MISS "hunt_pcap_summary.json mangler" "" "hunt_pcap.txt"
    fi
    return 0
  fi
  local py
  py="$(command -v python3 || command -v python || true)"
  [[ -n "$py" ]] || return 0
  local sev id title detail source
  while IFS=$'\t' read -r sev id title detail source || [[ -n "${sev:-}" ]]; do
    [[ -z "${sev:-}" ]] && continue
    add_finding "$sev" "$id" "$title" "${detail//\\n/$'\n'}" "$source"
  done < <("$py" - "$OUT" << 'PY'
import json, os, re, sys

out = sys.argv[1]
sum_path = os.path.join(out, "hunt_pcap_summary.json")
try:
    s = json.load(open(sum_path, encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    raise SystemExit(0)

def emit(sev, fid, title, detail, source):
    def clean(x):
        return str(x or "").replace("\t", " ").replace("\n", "\\n")
    print("\t".join([sev, fid, clean(title), clean(detail), clean(source)]))

EPHEMERAL = 32768
known = {8787, 45959, 7878}
try:
    known.add(int(os.environ.get("CFG_LISTEN_PORT") or 8787))
except ValueError:
    pass

nmap_ports = set()
gnmap = os.path.join(out, "hunt_nmap.gnmap")
if os.path.isfile(gnmap):
    for line in open(gnmap, encoding="utf-8", errors="replace"):
        for m in re.finditer(r"(\d+)/open/tcp", line):
            nmap_ports.add(int(m.group(1)))
ss_ports = set()
ss = os.path.join(out, "ss_tulpn.txt")
if os.path.isfile(ss):
    for line in open(ss, encoding="utf-8", errors="replace"):
        if "LISTEN" not in line:
            continue
        m = re.search(r"(127\.0\.0\.1|0\.0\.0\.0|\*|\[::1\]|\[::\]):(\d+)", line)
        if m:
            ss_ports.add(int(m.group(2)))
listen_known = set(known) | ss_ports | nmap_ports

def listen_from_raw(path):
    """SYN-ACK src port = server (listener). dst = client ephemeral."""
    ports = set()
    if not os.path.isfile(path):
        return ports
    for line in open(path, encoding="utf-8", errors="replace"):
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 8:
            continue
        try:
            sport, dport = int(parts[2] or 0), int(parts[4] or 0)
        except ValueError:
            continue
        syn = parts[5] in ("1", "True", "true")
        ack = parts[6] in ("1", "True", "true")
        rst = parts[7] in ("1", "True", "true")
        if not (syn and ack and not rst):
            continue
        if dport in listen_known and sport not in listen_known:
            continue
        if sport >= EPHEMERAL and dport >= EPHEMERAL and sport not in listen_known:
            continue
        ports.add(sport)
    return ports

pcap_ports = listen_from_raw(os.path.join(out, "hunt_pcap_raw.txt"))
if not pcap_ports:
    for p in s.get("synack_ports") or []:
        try:
            pcap_ports.add(int(p))
        except (TypeError, ValueError):
            pass

def classify(p):
    if p in ss_ports or p in known:
        return "confirm"
    if p in nmap_ports:
        return "hidden_listen"
    if p >= EPHEMERAL:
        return "ephemeral"
    return "extra"

ident = []
classes = {"hidden_listen": 0, "extra": 0, "confirm": 0, "ephemeral": 0}
kept = set()
for p in sorted(pcap_ports):
    cls = classify(p)
    classes[cls] = classes.get(cls, 0) + 1
    if cls == "ephemeral":
        continue
    kept.add(p)
    ident.append({"port": p, "in_ss": p in ss_ports, "in_nmap": p in nmap_ports, "class": cls})
pcap_ports = kept

ident_path = os.path.join(out, "hunt_pcap_ident.jsonl")
with open(ident_path, "w", encoding="utf-8") as f:
    for row in ident:
        f.write(json.dumps(row) + "\n")

vs_n = "match"
if pcap_ports - nmap_ports and nmap_ports:
    vs_n = "pcap_extra"
elif nmap_ports - pcap_ports and pcap_ports:
    vs_n = "nmap_not_in_pcap"
elif not pcap_ports:
    vs_n = "empty"
vs_s = "match"
if pcap_ports - ss_ports and pcap_ports:
    vs_s = "pcap_not_in_ss"
elif ss_ports - pcap_ports and pcap_ports:
    vs_s = "ss_extra_or_timing"

s["vs_nmap"] = vs_n
s["vs_ss"] = vs_s
s["classes"] = classes
json.dump(s, open(sum_path, "w", encoding="utf-8"), indent=2)

hidden = [r for r in ident if r["class"] == "hidden_listen"]
extra = [r for r in ident if r["class"] == "extra"]
raw = int(s.get("raw_rows") or 0)
if hidden:
    ports = ",".join(str(r["port"]) for r in hidden[:12])
    emit("INFO", "PCAP-CONFIRM",
         "tshark bekrefter nmap-åpne porter ss ikke viser: %s" % ports,
         "vs_nmap=%s vs_ss=%s — se NET-NMAP" % (vs_n, vs_s),
         "hunt_pcap_ident.jsonl")
if extra:
    ports = ",".join(str(r["port"]) for r in extra[:12])
    emit("WARN", "PCAP-EXTRA",
         "tshark SYN-ACK på lo som verken nmap eller ss har: %s" % ports,
         "kortlivd eller skjult lytter utenfor nmap-vindu",
         "hunt_pcap_ident.jsonl")
if raw:
    drop = s.get("drop") or {}
    emit("INFO", "PCAP-NOISE",
         "lo-burst: raw=%d synack_ports=%d vs_nmap=%s vs_ss=%s" % (
             raw, len(pcap_ports), vs_n, vs_s),
         "drop scan_self=%s other=%s" % (drop.get("scan_self"), drop.get("other")),
         "hunt_pcap_summary.json")
PY
)
}
