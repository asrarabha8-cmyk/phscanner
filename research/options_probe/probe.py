"""Find how far back SPY 0DTE contract bars reach on this API plan. Prints no secrets."""
import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

import requests

KEY = os.environ["POLYGON_API_KEY"].strip()
BASE = "https://api.polygon.io"
OUT = Path(__file__).parent


def get(url, params=None):
    p = dict(params or {}, apiKey=KEY)
    for _ in range(4):
        r = requests.get(url, params=p, timeout=60)
        if r.status_code == 429:
            time.sleep(65)
            continue
        return r.status_code, r.json() if "json" in r.headers.get("content-type", "") else {}
    return 429, {}


def bday(d):
    while d.weekday() >= 4:   # Monday to Thursday avoids most holidays and matches daily expiries
        d -= timedelta(days=1)
    return d


today = date.today()
rows = []
for months in (0, 1, 3, 6, 12, 18, 23, 25, 30, 36, 48, 60):
    d = bday(today - timedelta(days=max(months * 30, 1)))
    code, data = get(f"{BASE}/v2/aggs/ticker/SPY/range/1/day/{d}/{d}", {"adjusted": "false"})
    res = (data.get("results") or [{}])[0]
    spot = res.get("o")
    row = {"months_back": months, "date": str(d), "spot": spot}
    if spot:
        k = round(spot)
        t = f"O:SPY{d.strftime('%y%m%d')}C{k * 1000:08d}"
        for label, tf in (("min1", 1), ("min5", 5)):
            time.sleep(13)
            c, x = get(f"{BASE}/v2/aggs/ticker/{t}/range/{tf}/minute/{d}/{d}", {"adjusted": "false", "limit": 5000})
            row[label] = {"status": c, "bars": len(x.get("results") or []), "first": (x.get("results") or [{}])[0]}
        time.sleep(13)
        c, x = get(f"{BASE}/v3/quotes/{t}", {"timestamp": str(d), "limit": 1})
        row["quotes_status"] = c
        time.sleep(13)
        c, x = get(f"{BASE}/v3/trades/{t}", {"timestamp": str(d), "limit": 1})
        row["trades_status"] = c
    rows.append(row)
    print(json.dumps(row), flush=True)
    time.sleep(13)
(OUT / "probe_results.json").write_text(json.dumps(rows, indent=1))
