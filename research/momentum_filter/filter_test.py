"""Test of the TradingView screen "momentum + VWAP" on all US stocks.

Rules fixed before the run, applied at each day's close (daily bars, all US tickers
including ones later delisted, from Polygon grouped daily data):
- close >= 10
- relative volume: today's volume / average of the previous 10 days > 1.5
- RSI(14) between 50 and 75
- close above EMA 50 and above EMA 200
- 1-month performance (21 trading days) > 5%
- 30-day average volume > 500,000
- close above the day's VWAP
Entry at the next day's open. Outcomes: return after 5, 20 and 60 trading days, and whether
the stock reached +10%, +20%, +50% (on the high) within 60 days, and whether +10% came
before -10%.
Baseline: every stock-day with close >= 10 and 30-day average volume > 500,000.
Signals cluster on the same days, so the main test averages the daily excess over the
baseline (signal mean minus baseline mean on each day) and uses those daily values.
Pass: development low 95% of the daily 20-day excess > 0, both halves positive, holdout positive.
Holdout: the last 12 months (outcomes need 60 days, so recent signals are trimmed).
"""
import json
import math
import os
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

OUT = Path(__file__).parent
BASE = "https://api.polygon.io"
YEARS = 5.5
Z95 = 1.96


def grouped(key):
    s = requests.Session()
    end = date.today() - timedelta(days=1)
    d = end - timedelta(days=int(YEARS * 365.25))
    frames = []
    while d <= end:
        if d.weekday() < 5:
            url = f"{BASE}/v2/aggs/grouped/locale/us/market/stocks/{d}"
            for _ in range(6):
                r = s.get(url, params={"adjusted": "true", "apiKey": key}, timeout=60)
                if r.status_code == 429:
                    time.sleep(12)
                    continue
                break
            rows = (r.json().get("results") or []) if r.status_code == 200 else []
            if rows:
                f = pd.DataFrame(rows)[["T", "o", "h", "l", "c", "v", "vw"]]
                f["date"] = pd.Timestamp(d)
                frames.append(f)
        d += timedelta(days=1)
    df = pd.concat(frames, ignore_index=True)
    df = df[df["T"].str.fullmatch(r"[A-Z]{1,5}")]
    keep = df[(df["c"] >= 10) & (df["v"] >= 3e5)]["T"].unique()
    df = df[df["T"].isin(keep)]
    return df.rename(columns={"T": "sym"}).sort_values(["sym", "date"]).reset_index(drop=True)


def rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def features(df):
    g = df.groupby("sym", sort=False)
    c, v = df["c"], df["v"]
    df["ema50"] = g["c"].transform(lambda x: x.ewm(span=50, adjust=False).mean())
    df["ema200"] = g["c"].transform(lambda x: x.ewm(span=200, adjust=False).mean())
    df["rsi"] = g["c"].transform(rsi)
    df["n"] = g.cumcount()
    df["rvol"] = v / g["v"].transform(lambda x: x.shift(1).rolling(10).mean())
    df["avgv30"] = g["v"].transform(lambda x: x.rolling(30).mean())
    df["perf1m"] = g["c"].transform(lambda x: x / x.shift(21) - 1) * 100
    df["next_open"] = g["o"].shift(-1)
    for h in (5, 20, 60):
        df[f"c{h}"] = g["c"].shift(-h)
    hi = g["h"]
    lo = g["l"]
    # max high and min low over the next 60 days (from the entry day onward)
    df["max60"] = hi.transform(lambda x: x[::-1].rolling(60, min_periods=60).max()[::-1].shift(-1))
    # first-touch of +10% vs -10% is computed for signal rows only (below)
    return df


def first_touch(df, rows, up=0.10, dn=0.10, horizon=60):
    out = []
    groups = {s: g for s, g in df.groupby("sym", sort=False)}
    for _, r in rows.iterrows():
        g = groups[r["sym"]]
        i = g.index.get_loc(r.name)
        seg = g.iloc[i + 1:i + 1 + horizon]
        e = r["next_open"]
        if len(seg) < horizon or not e or np.isnan(e):
            out.append(np.nan)
            continue
        res = np.nan
        for h, l in zip(seg["h"].to_numpy(), seg["l"].to_numpy()):
            hit_up, hit_dn = h >= e * (1 + up), l <= e * (1 - dn)
            if hit_up and hit_dn:
                res = 0.0  # same day, unknown order: count as a loss
                break
            if hit_up:
                res = 1.0
                break
            if hit_dn:
                res = 0.0
                break
        out.append(res)
    return out


def main():
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        raise SystemExit("POLYGON_API_KEY is missing")
    df = features(grouped(key))
    df = df[df["n"] >= 200]
    for h in (5, 20, 60):
        df[f"r{h}"] = (df[f"c{h}"] / df["next_open"] - 1) * 100
    df["g60"] = (df["max60"] / df["next_open"] - 1) * 100
    base = df[(df["c"] >= 10) & (df["avgv30"] > 5e5) & df["r60"].notna() & (df["next_open"] > 0)]
    sig = base[(base["rvol"] > 1.5) & base["rsi"].between(50, 75) & (base["c"] > base["ema50"]) & (base["c"] > base["ema200"])
               & (base["perf1m"] > 5) & (base["c"] > base["vw"])].copy()
    sig["touch10"] = first_touch(df, sig)
    cut = pd.Timestamp(date.today() - timedelta(days=365))

    def describe(x):
        return {"n": len(x), "r5": x["r5"].mean(), "r20": x["r20"].mean(), "r60": x["r60"].mean(),
                "med20": x["r20"].median(), "up10": (x["g60"] >= 10).mean() * 100, "up20": (x["g60"] >= 20).mean() * 100,
                "up50": (x["g60"] >= 50).mean() * 100}

    lines = ["# Momentum + VWAP screen test", "", f"Run date: {date.today()}. Rules fixed before the run. Holdout from {cut.date()}.",
             f"Signals: {len(sig)} on {sig['date'].nunique()} days. Baseline stock-days: {len(base)}.", "",
             "| Group | Count | Avg 5d | Avg 20d | Avg 60d | Median 20d | Reached +10% in 60d | +20% | +50% |",
             "|---|---|---|---|---|---|---|---|---|"]
    res = {}
    for name, x in (("Signals, development", sig[sig["date"] < cut]), ("Signals, holdout", sig[sig["date"] >= cut]),
                    ("Baseline, development", base[base["date"] < cut]), ("Baseline, holdout", base[base["date"] >= cut])):
        d = describe(x)
        res[name] = d
        lines.append(f"| {name} | {d['n']} | {d['r5']:.2f}% | {d['r20']:.2f}% | {d['r60']:.2f}% | {d['med20']:.2f}% | "
                     f"{d['up10']:.0f}% | {d['up20']:.0f}% | {d['up50']:.0f}% |")
    t = sig["touch10"].dropna()
    lines += ["", f"+10% reached before -10% (signals with a full 60 days): {100 * t.mean():.0f}% of {len(t)}.", ""]

    bm = base.groupby("date")["r20"].mean()
    ex = (sig.groupby("date")["r20"].mean() - bm).dropna()
    dev, hold = ex[ex.index < cut], ex[ex.index >= cut]
    half = len(dev) // 2

    def st(x):
        se = x.std(ddof=1) / math.sqrt(len(x)) if len(x) > 1 else float("nan")
        return {"days": len(x), "avg": round(x.mean(), 2), "low95": round(x.mean() - Z95 * se, 2), "pos": round(100 * (x > 0).mean(), 1)}

    g = {"Development": st(dev), "Dev first half": st(dev.iloc[:half]), "Dev second half": st(dev.iloc[half:]), "Holdout": st(hold)}
    for y, gy in dev.groupby(dev.index.year):
        g[f"Dev {y}"] = st(gy)
    lines += ["## 20-day excess over the baseline, averaged by signal day", "",
              "| Group | Days | Avg excess | Low 95% | Days positive |", "|---|---|---|---|---|"]
    lines += [f"| {k} | {v['days']} | {v['avg']}% | {v['low95']}% | {v['pos']}% |" for k, v in g.items()]
    ok = bool(g["Development"]["low95"] > 0 and g["Dev first half"]["avg"] > 0 and g["Dev second half"]["avg"] > 0 and g["Holdout"]["avg"] > 0)
    lines += ["", f"Verdict: {'PASS' if ok else 'FAIL'}.", ""]
    top = sig.groupby("sym")["r20"].agg(["count", "mean"]).sort_values("count", ascending=False).head(10)
    lines += ["Most frequent symbols: " + ", ".join(f"{s} ({int(r['count'])})" for s, r in top.iterrows()), ""]
    (OUT / "results.md").write_text("\n".join(lines))
    (OUT / "results.json").write_text(json.dumps({"groups": res, "excess": g, "passed": ok}, indent=2, default=str))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
