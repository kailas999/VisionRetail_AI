"""Fetch error details from 500 responses."""
import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000"
STORE = "STORE_BLR_002"

def fetch_detail(url):
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return json.loads(body)
        except Exception:
            return {"raw": body}
    except Exception as e:
        return {"error": str(e)}

print("=== METRICS ===")
r = fetch_detail(f"{BASE}/stores/{STORE}/metrics")
print(json.dumps(r, indent=2, default=str)[:800])

print("\n=== FUNNEL ===")
r = fetch_detail(f"{BASE}/stores/{STORE}/funnel")
print(json.dumps(r, indent=2, default=str)[:800])

print("\n=== HEATMAP ===")
r = fetch_detail(f"{BASE}/stores/{STORE}/heatmap")
print(json.dumps(r, indent=2, default=str)[:800])
