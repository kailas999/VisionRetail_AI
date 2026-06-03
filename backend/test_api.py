"""Quick API smoke test — run from backend/ directory."""
import json
import urllib.request

BASE = "http://localhost:8000"
STORE = "STORE_BLR_002"

def fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

# Health
h = fetch(f"{BASE}/health")
print("HEALTH:", h.get("status"), "| db:", h.get("database"))

# Metrics
m = fetch(f"{BASE}/stores/{STORE}/metrics")
if "error" in m:
    print("METRICS ERROR:", m["error"])
else:
    uv = m["unique_visitors"]
    conv = m["conversions"]
    rate = round(m["conversion_rate"] * 100, 1)
    dwell = m["avg_dwell_seconds"]
    hourly = len(m["hourly_breakdown"])
    print(f"METRICS: visitors={uv} conversions={conv} rate={rate}% dwell={dwell}s hourly_rows={hourly}")

# Funnel
f = fetch(f"{BASE}/stores/{STORE}/funnel")
if "error" in f:
    print("FUNNEL ERROR:", f["error"])
else:
    stages = [(s["stage"], s["count"]) for s in f.get("stages", [])]
    print("FUNNEL stages:", stages)

# Anomalies
a = fetch(f"{BASE}/stores/{STORE}/anomalies")
if "error" in a:
    print("ANOMALIES ERROR:", a["error"])
else:
    print(f"ANOMALIES: {a['active_count']} active")
    for anom in a.get("anomalies", []):
        print(f"  [{anom['severity']}] {anom['anomaly_type']}")

# Heatmap
hm = fetch(f"{BASE}/stores/{STORE}/heatmap")
if "error" in hm:
    print("HEATMAP ERROR:", hm["error"])
else:
    zones = hm.get("zones", [])
    print(f"HEATMAP zones: {len(zones)}")
    for z in zones[:4]:
        print(f"  {z['zone_name']}: dwell={z['avg_dwell_seconds']}s visitors={z['visitor_count']} intensity={z['intensity']}")
