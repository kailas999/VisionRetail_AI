import urllib.request
import json
import sys
url = "http://localhost:8000/stores/STORE_BLR_002/metrics"
try:
    with urllib.request.urlopen(url, timeout=8) as r:
        pass
except Exception as e:
    body = e.read().decode()
    d = json.loads(body)
    print(d.get("traceback", ""))
