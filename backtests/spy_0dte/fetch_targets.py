"""يسحب عقودًا محددة فقط (data/targets_orb15.csv) — أسرع من السحب الشامل."""
import os, time, subprocess, requests, pandas as pd
KEY=os.environ["POLYGON_API_KEY"].strip(); OUT="data/options_t"; os.makedirs(OUT,exist_ok=True)
T=pd.read_csv("data/targets_orb15.csv"); last=0.0; n=0
def save(msg):
    subprocess.run(f'git add {OUT} && git commit -q -m "{msg}" && git pull -q --rebase && git push -q',shell=True)
for r in T.itertuples():
    f=f"{OUT}/{r.date}_{r.cp}{r.strike}.csv"
    if os.path.exists(f): continue
    ymd=pd.Timestamp(r.date).strftime("%y%m%d"); tk=f"O:SPY{ymd}{r.cp}{r.strike*1000:08d}"
    for _ in range(6):
        w=12.2-(time.time()-last)
        if w>0: time.sleep(w)
        last=time.time()
        q=requests.get(f"https://api.polygon.io/v2/aggs/ticker/{tk}/range/5/minute/{r.date}/{r.date}?adjusted=true&sort=asc&limit=500&apiKey={KEY}",timeout=40)
        if q.status_code!=429: break
        time.sleep(20)
    res=q.json().get("results") or []
    x=pd.DataFrame(res,columns=["t","o","h","l","c","v"]) if res else pd.DataFrame(columns=["t","o","h","l","c","v"])
    if res: x=x[["t","o","h","l","c","v"]]
    x.insert(0,"strike",r.strike); x.insert(0,"cp",r.cp); x.to_csv(f,index=False); n+=1
    if n%60==0: save("Targeted options progress [skip ci]")
save("Targeted options complete [skip ci]"); print("done",n)
