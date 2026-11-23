""""Black candle school" (مدرسة الشمعة السوداء) turned into fixed rules and tested.

The infographic gives no exact rules, so these readings were fixed before the run:
- Black candle: a down candle (close < open) whose body is at least 0.5 x ATR(14) and whose
  low is the lowest low of the last 20 candles. It marks the "strong support".
- Breakout: the first close above the black candle's high within 10 candles -> buy at the
  next open. A close below the black candle's low first cancels the setup.
- Exit ("break of the black or red candle = exit"): the stop starts at the black candle's low.
  After entry, every down candle is a "red candle"; when price closes above a red candle's
  high (the "red breakout = continuation"), the stop moves up to that red candle's low.
  Exit at the next open after a close below the stop, or after 60 candles.
- Long only, as in the infographic. 0.10% cost per round trip.
Universe: 164 liquid US stocks and ETFs from the weekly EMA scanner. Daily and weekly candles,
six years. The last 12 months are the holdout.
Control: entries on random candles with the same stop rules (stop starts at the most recent
down candle's low).
Pass: development low 95% > 0, both halves positive, holdout positive, above the control.
"""
import json
import math
import os
import random
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

OUT = Path(__file__).parent
BASE = "https://api.polygon.io"
YEARS = 6
LOOK, WAIT, MAX_HOLD, BODY_ATR = 20, 10, 60, 0.5
COST = 0.10
Z95 = 1.96


def daily(sym, key, s):
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=int(YEARS * 365.25))
    url = f"{BASE}/v2/aggs/ticker/{sym}/range/1/day/{start}/{end}"
    for _ in range(6):
        r = s.get(url, params={"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": key}, timeout=60)
        if r.status_code == 429:
            time.sleep(15)
            continue
        break
    rows = r.json().get("results") or [] if r.status_code == 200 else []
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df["t"], unit="ms")
    return df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close"})[["open", "high", "low", "close"]]


def weekly(df):
    return df.resample("W-FRI").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def atr(df, n=14):
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def exit_from(o, h, l, c, e, stop):
    """Run the stop rules from entry bar e. Returns (exit index, exit price)."""
    n = len(c)
    red_hi = red_lo = None
    j = e
    while j < n:
        if c[j] < stop:
            return (j + 1, o[j + 1]) if j + 1 < n else (j, c[j])
        if red_hi is not None and c[j] > red_hi:
            stop = max(stop, red_lo)
            red_hi = red_lo = None
        if c[j] < o[j]:
            red_hi, red_lo = h[j], l[j]
        if j - e + 1 >= MAX_HOLD:
            return (j + 1, o[j + 1]) if j + 1 < n else (j, c[j])
        j += 1
    return n - 1, c[n - 1]


def trades(df, sym, rng=None, rate=None):
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    a = atr(df).to_numpy()
    lowmin = df["low"].rolling(LOOK).min().to_numpy()
    idx = df.index
    n, out, i = len(c), [], LOOK
    while i < n - 2:
        if rng is not None:
            if rng.random() < rate:
                k = i
                while k > 0 and not c[k] < o[k]:
                    k -= 1
                e = i + 1
                x, px = exit_from(o, h, l, c, e, l[k])
                out.append({"sym": sym, "date": idx[e], "ret": 100 * (px / o[e] - 1) - COST, "bars": x - e})
                i = x + 1
                continue
            i += 1
            continue
        black = c[i] < o[i] and (o[i] - c[i]) >= BODY_ATR * a[i] and l[i] <= lowmin[i]
        if not black:
            i += 1
            continue
        bh, bl = h[i], l[i]
        hit = None
        for k in range(i + 1, min(i + 1 + WAIT, n - 1)):
            if c[k] < bl:
                break
            if c[k] > bh:
                hit = k
                break
        if hit is None:
            i += 1
            continue
        e = hit + 1
        x, px = exit_from(o, h, l, c, e, bl)
        out.append({"sym": sym, "date": idx[e], "ret": 100 * (px / o[e] - 1) - COST, "bars": x - e})
        i = x + 1
    return out


def st(r):
    r = np.asarray(r, float)
    if len(r) < 2:
        return {"n": len(r)}
    se = r.std(ddof=1) / math.sqrt(len(r))
    g, lo = r[r > 0].sum(), -r[r <= 0].sum()
    return {"n": len(r), "win": round(100 * (r > 0).mean(), 1), "avg": round(r.mean(), 2),
            "low95": round(r.mean() - Z95 * se, 2), "pf": round(g / lo, 2) if lo else None}


def row(name, s):
    if s.get("n", 0) < 2:
        return f"| {name} | {s.get('n', 0)} | - | - | - | - |"
    return f"| {name} | {s['n']} | {s['win']}% | {s['avg']}% | {s['low95']}% | {s['pf']} |"


def main():
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        raise SystemExit("POLYGON_API_KEY is missing")
    syms = [x for x in (OUT / "universe.txt").read_text().split() if "-" not in x]
    s = requests.Session()
    data = {}
    for sym in syms:
        d = daily(sym, key, s)
        if d is not None and len(d) > 300:
            data[sym] = d
    cut = pd.Timestamp(date.today() - timedelta(days=365))
    rng = random.Random(5)
    lines = ["# Black candle school", "", f"Run date: {date.today()}. Rules fixed before the run. Holdout from {cut.date()}.",
             f"Symbols with data: {len(data)}. Returns per trade in % after 0.10% cost.", ""]
    summary = {}
    for tf in ("daily", "weekly"):
        allt, ctrl = [], []
        for sym, d in data.items():
            df = d if tf == "daily" else weekly(d)
            t = trades(df, sym)
            allt += t
            rate = len(t) / max(1, len(df))
            ctrl += trades(df, sym, rng=rng, rate=rate)
        t = pd.DataFrame(allt).sort_values("date").reset_index(drop=True)
        cdf = pd.DataFrame(ctrl)
        dev, hold = t[t["date"] < cut].reset_index(drop=True), t[t["date"] >= cut]
        h = len(dev) // 2
        g = {"Development": st(dev["ret"]), "Dev first half": st(dev["ret"].iloc[:h]), "Dev second half": st(dev["ret"].iloc[h:]),
             "Holdout": st(hold["ret"]), "Random entries, same exits (dev)": st(cdf[cdf["date"] < cut]["ret"]) if len(cdf) else {"n": 0}}
        for y, gy in dev.groupby(dev["date"].dt.year):
            g[f"Dev {y}"] = st(gy["ret"])
        ok = bool(g["Development"].get("low95", -1) > 0 and g["Dev first half"].get("avg", -1) > 0
                  and g["Dev second half"].get("avg", -1) > 0 and g["Holdout"].get("avg", -1) > 0
                  and g["Development"]["avg"] > g["Random entries, same exits (dev)"].get("avg", 1e9))
        lines += [f"## {tf.capitalize()} candles", "", f"Median candles held: {int(t['bars'].median())}.", "",
                  "| Group | Trades | Win | Avg | Low 95% | PF |", "|---|---|---|---|---|---|"]
        lines += [row(k, v) for k, v in g.items()]
        lines += ["", f"Verdict: {'PASS' if ok else 'FAIL'}.", ""]
        summary[tf] = {"groups": g, "passed": ok}
        t.to_csv(OUT / f"trades_{tf}.csv", index=False)
    (OUT / "results.md").write_text("\n".join(lines))
    (OUT / "results.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
