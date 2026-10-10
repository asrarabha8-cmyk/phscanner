"""يسحب أسعار عقود SPY 0DTE الحقيقية (5 دقائق) من Polygon: Call و Put عند سترايكات ATM
لأوقات 10:00 و 12:00 و 14:30، لكل يوم. يحفظ ملف لكل يوم ويكمل من حيث توقف.
يحفظ التقدم في الفرع كل 40 يوم، ويتوقف قبل حد الست ساعات ثم يعيد تشغيل نفسه."""
import os, time, subprocess, requests, pandas as pd

KEY = os.environ["POLYGON_API_KEY"].strip()
BUDGET_MIN = float(os.environ.get("BUDGET_MIN", "320"))
OUT = "data/options"
os.makedirs(OUT, exist_ok=True)
t_start = time.time()

spy = pd.read_csv("data/spy_5m.csv")
spy["datetime"] = pd.to_datetime(spy.datetime, utc=True).dt.tz_convert("America/New_York")
spy["d"] = spy.datetime.dt.date
spy["hm"] = spy.datetime.dt.hour * 60 + spy.datetime.dt.minute

def git_save(msg, cont=False):
    subprocess.run("git add data/options", shell=True)
    if cont:
        open(f"{OUT}/.continue", "w").write(str(time.time()))
        subprocess.run(f"git add {OUT}/.continue", shell=True)
    r = subprocess.run(f'git commit -q -m "{msg}"', shell=True)
    if r.returncode == 0:
        subprocess.run("git pull -q --rebase && git push -q", shell=True)

last_call = 0.0
def get(url):
    global last_call
    for _ in range(6):
        wait = 12.2 - (time.time() - last_call)
        if wait > 0:
            time.sleep(wait)
        last_call = time.time()
        r = requests.get(url + "&apiKey=" + KEY, timeout=40)
        if r.status_code == 429:
            time.sleep(20); continue
        return r.json()
    return {}

done_new = 0
for d, g in spy.groupby("d"):
    f = f"{OUT}/{d}.csv"
    if os.path.exists(f):
        continue
    if (time.time() - t_start) / 60 > BUDGET_MIN:
        git_save(f"Options data progress [continue]", cont=True)
        print("time budget reached; continuing in next run"); raise SystemExit(0)
    strikes = set()
    for hm in (600, 720, 870):
        row = g[g.hm <= hm - 5].tail(1)
        if len(row):
            strikes.add(int(round(row.close.iloc[0])))
    ymd = pd.Timestamp(d).strftime("%y%m%d")
    frames = []
    for k in sorted(strikes):
        for cp in ("C", "P"):
            tk = f"O:SPY{ymd}{cp}{k*1000:08d}"
            j = get(f"https://api.polygon.io/v2/aggs/ticker/{tk}/range/5/minute/{d}/{d}?adjusted=true&sort=asc&limit=500")
            if j.get("results"):
                x = pd.DataFrame(j["results"])[["t", "o", "h", "l", "c", "v"]]
                x.insert(0, "strike", k); x.insert(0, "cp", cp)
                frames.append(x)
    (pd.concat(frames) if frames else pd.DataFrame(columns=["cp","strike","t","o","h","l","c","v"])).to_csv(f, index=False)
    done_new += 1
    print(d, sorted(strikes), sum(len(x) for x in frames), "bars", flush=True)
    if done_new % 40 == 0:
        git_save(f"Options data progress [skip ci]")
git_save("Options data complete [skip ci]")
print("ALL DONE")
