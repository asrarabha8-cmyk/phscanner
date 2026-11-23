"""Four "before the explosion" filters, fixed before the run, tested on all US stocks.

Each looks for a stock that is quiet or coiled while strong, before a big move:
- A Squeeze near highs: within 10% of the 52-week high, 20-day Bollinger width within 10% of its
  6-month low, ATR(10)/ATR(50) < 0.75, close > EMA50 > EMA200.
- B Dry-up then pocket pivot: 10-day average volume < 0.7 x 50-day average over the previous
  days, then today an up close in the top quarter of the day's range with volume above every
  down-day volume of the previous 10 days; within 15% of the 52-week high; close > EMA50.
- C Quiet accumulation: up-day volume / down-day volume over 50 days > 1.5, 20-day high-low range
  < 15% of price, close > EMA50.
- D Leader in a tight base: 6-month return in the top 10% of all stocks that day, 10-day
  high-low range < 8% of price, close > EMA50.
All need close >= 10 and 30-day average volume > 500,000 (the baseline group).
Entry at the next open. Main outcome: +20% reached before -10% within 60 trading days
(same-day touches count as a loss). Also the average 20- and 60-day returns and the daily
excess of the 60-day return over the baseline.
Pass: "+20% before -10%" rate above the baseline in development and holdout, development low 95% of
the daily 60-day excess > 0, both halves positive, and holdout excess positive.
Holdout: the last 12 months (trimmed by the 60-day outcome window).
"""
import json
import math
import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).parent
sys.path.insert(0, str(OUT.parent / "momentum_filter"))
import filter_test as ft  # noqa: E402

Z95 = 1.96


def add(df):
    g = df.groupby("sym", sort=False)
    c, h, l, v = df["c"], df["h"], df["l"], df["v"]
    pc = g["c"].shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    df["tr"] = tr
    df["atr10"] = df.groupby("sym", sort=False)["tr"].transform(lambda x: x.rolling(10).mean())
    df["atr50"] = df.groupby("sym", sort=False)["tr"].transform(lambda x: x.rolling(50).mean())
    sd = g["c"].transform(lambda x: x.rolling(20).std())
    ma = g["c"].transform(lambda x: x.rolling(20).mean())
    df["bbw"] = 4 * sd / ma
    df["bbw_min126"] = df.groupby("sym", sort=False)["bbw"].transform(lambda x: x.rolling(126).min())
    df["hi252"] = g["h"].transform(lambda x: x.rolling(252, min_periods=200).max())
    df["hi20"] = g["h"].transform(lambda x: x.rolling(20).max())
    df["lo20"] = g["l"].transform(lambda x: x.rolling(20).min())
    df["hi10"] = g["h"].transform(lambda x: x.rolling(10).max())
    df["lo10"] = g["l"].transform(lambda x: x.rolling(10).min())
    up = (c > pc)
    dn = (c < pc)
    df["upv"] = v.where(up, 0.0)
    df["dnv"] = v.where(dn, 0.0)
    g2 = df.groupby("sym", sort=False)
    df["ud50"] = g2["upv"].transform(lambda x: x.rolling(50).sum()) / g2["dnv"].transform(lambda x: x.rolling(50).sum()).replace(0, np.nan)
    df["maxdnv10"] = g2["dnv"].transform(lambda x: x.shift(1).rolling(10).max())
    df["av10p"] = g2["v"].transform(lambda x: x.shift(1).rolling(10).mean())
    df["av50p"] = g2["v"].transform(lambda x: x.shift(1).rolling(50).mean())
    df["ret126"] = g2["c"].transform(lambda x: x / x.shift(126) - 1)
    df["up_close"] = c > pc
    df["pos_in_range"] = (c - l) / (h - l).replace(0, np.nan)
    return df


def main():
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        raise SystemExit("POLYGON_API_KEY is missing")
    df = ft.features(ft.grouped(key))
    df = add(df)
    df = df[df["n"] >= 252].drop(columns=["tr", "upv", "dnv", "atr10", "atr50"] and [], errors="ignore")
    fl = df.select_dtypes("float64").columns
    df[fl] = df[fl].astype("float32")
    for hz in (20, 60):
        df[f"r{hz}"] = (df[f"c{hz}"] / df["next_open"] - 1) * 100
    base = df[(df["c"] >= 10) & (df["avgv30"] > 5e5) & df["r60"].notna() & (df["next_open"] > 0)].copy()
    base["rs_pct"] = base.groupby("date")["ret126"].rank(pct=True)
    trend = base["c"] > base["ema50"]
    near = lambda p: base["c"] >= (1 - p) * base["hi252"]  # noqa: E731
    filters = {
        "A squeeze near highs": near(0.10) & (base["bbw"] <= 1.1 * base["bbw_min126"]) & (base["atr10"] < 0.75 * base["atr50"])
                                & trend & (base["ema50"] > base["ema200"]),
        "B dry-up then pocket pivot": (base["av10p"] < 0.7 * base["av50p"]) & base["up_close"] & (base["pos_in_range"] >= 0.75)
                                      & (base["v"] > base["maxdnv10"]) & near(0.15) & trend,
        "C quiet accumulation": (base["ud50"] > 1.5) & ((base["hi20"] - base["lo20"]) / base["c"] < 0.15) & trend,
        "D leader in tight base": (base["rs_pct"] >= 0.90) & ((base["hi10"] - base["lo10"]) / base["c"] < 0.08) & trend,
    }
    cut = pd.Timestamp(date.today() - timedelta(days=365))
    rng = random.Random(3)
    bsample = base.loc[rng.sample(list(base.index), 40000)]
    bsample = bsample.assign(win=ft.first_touch(df, bsample, up=0.20, dn=0.10))
    lines = ["# Pre-breakout filters", "", f"Run date: {date.today()}. Rules fixed before the run. Holdout from {cut.date()}.",
             f"Baseline stock-days: {len(base)} (40,000 sampled for the +20%/-10% race).", "",
             "| Filter | Group | Signals | +20% before -10% | Avg 20d | Avg 60d | Median 60d |", "|---|---|---|---|---|---|---|"]

    def row(name, part, x, w):
        return (f"| {name} | {part} | {len(x)} | {100 * np.nanmean(w):.1f}% | {x['r20'].mean():.2f}% | {x['r60'].mean():.2f}% | "
                f"{x['r60'].median():.2f}% |")

    bdev, bhold = bsample[bsample["date"] < cut], bsample[bsample["date"] >= cut]
    lines.append(row("Baseline", "development", bdev, bdev["win"]))
    lines.append(row("Baseline", "holdout", bhold, bhold["win"]))
    bm = base.groupby("date")["r60"].mean()
    summary = {}
    excess_lines = ["", "## 60-day excess over the baseline, averaged by signal day", "",
                    "| Filter | Dev days | Dev avg | Dev low 95% | Half 1 | Half 2 | Holdout avg | Verdict |", "|---|---|---|---|---|---|---|---|"]
    for name, mask in filters.items():
        s = base[mask].copy()
        if len(s) > 60000:
            s = s.loc[rng.sample(list(s.index), 60000)]
        s["win"] = ft.first_touch(df, s, up=0.20, dn=0.10)
        sd, sh = s[s["date"] < cut], s[s["date"] >= cut]
        lines.append(row(name, "development", sd, sd["win"]))
        lines.append(row(name, "holdout", sh, sh["win"]))
        ex = (s.groupby("date")["r60"].mean() - bm).dropna()
        ed, eh = ex[ex.index < cut], ex[ex.index >= cut]
        hf = len(ed) // 2
        se = ed.std(ddof=1) / math.sqrt(len(ed)) if len(ed) > 1 else float("nan")
        low = ed.mean() - Z95 * se
        h1, h2 = ed.iloc[:hf].mean(), ed.iloc[hf:].mean()
        ok = bool(np.nanmean(sd["win"]) > np.nanmean(bdev["win"]) and np.nanmean(sh["win"]) > np.nanmean(bhold["win"])
                  and low > 0 and h1 > 0 and h2 > 0 and eh.mean() > 0)
        excess_lines.append(f"| {name} | {len(ed)} | {ed.mean():.2f}% | {low:.2f}% | {h1:.2f}% | {h2:.2f}% | {eh.mean():.2f}% | {'PASS' if ok else 'FAIL'} |")
        yrs = sd.groupby(sd["date"].dt.year)["win"].mean().mul(100).round(1).to_dict()
        excess_lines.append(f"|  | by year (+20% before -10%): {yrs} | | | | | | |")
        summary[name] = {"passed": ok, "dev_win": float(np.nanmean(sd["win"])), "hold_win": float(np.nanmean(sh["win"])),
                         "dev_excess": float(ed.mean()), "dev_low95": float(low), "hold_excess": float(eh.mean())}
    lines += excess_lines
    (OUT / "results.md").write_text("\n".join(lines))
    (OUT / "results.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
