"""يسحب SPY 5m (سنتين، Polygon) + VIX اليومي (Yahoo) ويحفظهم CSV للاختبار المحلي."""
import os, time, requests, pandas as pd, yfinance as yf

key = os.environ["POLYGON_API_KEY"].strip()
end = pd.Timestamp.now(tz="America/New_York").normalize()
cur = end - pd.Timedelta(days=int(os.environ.get("DAYS", "730")))
frames = []
while cur < end:
    nxt = min(cur + pd.Timedelta(days=30), end)
    url = (f"https://api.polygon.io/v2/aggs/ticker/SPY/range/5/minute/{cur.date()}/{nxt.date()}"
           f"?adjusted=true&sort=asc&limit=50000&apiKey={key}")
    for _ in range(4):
        r = requests.get(url, timeout=30)
        if r.status_code != 429:
            break
        time.sleep(20)
    j = r.json()
    print(cur.date(), j.get("status"), j.get("resultsCount"), j.get("message", "")[:80])
    if j.get("results"):
        frames.append(pd.DataFrame(j["results"]))
    cur = nxt + pd.Timedelta(days=1)
    time.sleep(13)
d = pd.concat(frames).drop_duplicates("t")
d["datetime"] = pd.to_datetime(d.t, unit="ms", utc=True).dt.tz_convert("America/New_York")
d = d.rename(columns=dict(o="open", h="high", l="low", c="close", v="volume"))
d = d.set_index("datetime").between_time("09:30", "15:55")
d[["open", "high", "low", "close", "volume"]].round(4).to_csv("data/spy_5m.csv")
v = yf.download("^VIX", period="3y", interval="1d", progress=False)
if isinstance(v.columns, pd.MultiIndex):
    v.columns = v.columns.get_level_values(0)
v[["Open", "Close"]].round(2).to_csv("data/vix_daily.csv")
print("saved", len(d), "bars", d.index[0], d.index[-1])
# rev2
