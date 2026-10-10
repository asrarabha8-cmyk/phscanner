import os, requests, time
key=os.environ["POLYGON_API_KEY"].strip()
ok=lim=0; t0=time.time()
for i in range(25):
    k=650+i
    r=requests.get(f"https://api.polygon.io/v2/aggs/ticker/O:SPY260918C00{k}000/range/5/minute/2026-09-18/2026-09-18?limit=100&apiKey={key}",timeout=30)
    if r.status_code==429: lim+=1
    else: ok+=1
open("data/probe.txt","w").write(f"25 rapid requests in {time.time()-t0:.1f}s: ok={ok} 429={lim}\n")
