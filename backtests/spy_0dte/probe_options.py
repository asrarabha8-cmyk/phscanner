import os, requests, json
key=os.environ["POLYGON_API_KEY"].strip()
tests={
 "agg_5m": "https://api.polygon.io/v2/aggs/ticker/O:SPY260918C00660000/range/5/minute/2026-09-18/2026-09-18?limit=5&apiKey=",
 "agg_1d_old": "https://api.polygon.io/v2/aggs/ticker/O:SPY250117C00590000/range/1/day/2025-01-10/2025-01-17?apiKey=",
 "contracts": "https://api.polygon.io/v3/reference/options/contracts?underlying_ticker=SPY&expiration_date=2026-09-18&limit=3&expired=true&apiKey=",
}
with open("data/probe.txt","w") as f:
    for k,u in tests.items():
        r=requests.get(u+key,timeout=30); j=r.json()
        s=json.dumps({kk:(vv[:2] if isinstance(vv,list) else vv) for kk,vv in j.items() if kk!="request_id"})[:400]
        f.write(f"{k} {r.status_code} {s}\n")
