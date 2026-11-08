"""VWAP + Heikin Ashi backtest on SPY and QQQ. Rules were fixed before the run.

Entry (long only, as in the source image): close above session VWAP and the
Heikin Ashi candle turns green with no lower wick. Exit at the first close
below VWAP with a red Heikin Ashi candle and no upper wick, at the stop
(lowest low of the last 10 bars, at least 0.05% away), or at the session end.
"""
import json
import os
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).parent
sys.path.insert(0, str(OUT.parent / "noise_band"))
import backtest as bt  # noqa: E402

SYMBOLS = ("SPY", "QQQ")
TIMEFRAMES = (3, 5, 15)
COSTS = (1.0, 2.0, 5.0)
MAIN = 2.0
SWING = 10
MIN_STOP = 0.0005
DRAWS = 20
SEED = 42
HOLDOUT = date(2025, 11, 5)


def prep(df):
    df = df.reset_index(drop=True)
    o, h, l, c = (df[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    hc = (o + h + l + c) / 4
    ho = np.empty_like(hc)
    ho[0] = (o[0] + c[0]) / 2
    for i in range(1, len(hc)):
        ho[i] = (ho[i - 1] + hc[i - 1]) / 2
    hh = np.maximum.reduce([h, ho, hc])
    hl = np.minimum.reduce([l, ho, hc])
    v = df["volume"].where(df["volume"] > 0, 1.0)
    tp = (df["high"] + df["low"] + df["close"]) / 3
    vw = ((tp * v).groupby(df["day"]).cumsum() / v.groupby(df["day"]).cumsum()).to_numpy()
    green = hc > ho
    clean_green = green & (hl >= np.minimum(ho, hc) - 1e-9)
    clean_red = (hc < ho) & (hh <= np.maximum(ho, hc) + 1e-9)
    days = df["day"].to_numpy()
    first = np.r_[True, days[1:] != days[:-1]]
    prev_green = np.r_[False, green[:-1]]
    df["entry"] = (c > vw) & clean_green & ~prev_green & ~first
    df["exit"] = (c < vw) & clean_red
    df["swing"] = df["low"].rolling(SWING, min_periods=1).min()
    df["last"] = pd.Series(np.arange(len(df))).groupby(days).transform("max").to_numpy()
    return df


def walk(i, entry, stop, lo, cl, ex, end, costs):
    risk = entry - stop
    for j in range(i + 1, end + 1):
        if lo[j] <= stop:
            return [(-risk - entry * k / 1e4) / risk for k in costs], j
        if ex[j] or j == end:
            return [(cl[j] - entry - entry * k / 1e4) / risk for k in costs], j
    return [(cl[end] - entry - entry * k / 1e4) / risk for k in costs], end


def run_symbol(df, sym, seed):
    df = prep(df)
    lo, cl, sw = (df[x].to_numpy(float) for x in ("low", "close", "swing"))
    en, ex, last = df["entry"].to_numpy(), df["exit"].to_numpy(), df["last"].to_numpy()
    mins, days, times = df["mins"].to_numpy(), df["day"].to_numpy(), df["dt"].to_numpy()
    same = {m: np.where(mins == m)[0] for m in np.unique(mins)}
    rng = np.random.default_rng(seed)
    rows, i = [], 0
    while i < len(df):
        if not en[i] or last[i] == i:
            i += 1
            continue
        entry = cl[i]
        stop = min(sw[i], entry * (1 - MIN_STOP))
        rs, j = walk(i, entry, stop, lo, cl, ex, last[i], COSTS)
        pct = stop / entry
        pool = same[mins[i]]
        pool = pool[(days[pool] != days[i]) & (last[pool] != pool)]
        ctrl = [walk(k, cl[k], cl[k] * pct, lo, cl, ex, last[k], (MAIN,))[0][0]
                for k in rng.choice(pool, size=min(DRAWS, len(pool)), replace=False)] if len(pool) else []
        row = {"symbol": sym, "entry_time": times[i], "day": days[i], "bars": j - i,
               "random_r": float(np.mean(ctrl)) if ctrl else np.nan}
        row.update({f"r_{k}": r for k, r in zip(COSTS, rs)})
        row["r"] = row[f"r_{MAIN}"]
        rows.append(row)
        i = j + 1
    return rows


def verdict(t):
    s = bt.stats(t["r"].reset_index(drop=True))
    ex = bt.stats((t["r"] - t["random_r"]).dropna().reset_index(drop=True))
    half = len(t) // 2
    total = float(t["r"].sum())
    years = t.groupby("year")["r"].sum()
    c = {"low95_above_zero": s["low95"] > 0,
         "first_half_positive": float(t["r"].iloc[:half].mean()) > 0,
         "second_half_positive": float(t["r"].iloc[half:].mean()) > 0,
         "no_single_year_dominates": total > 0 and float(years.max()) < 0.5 * total,
         "beats_random": ex["low95"] > 0}
    c["passed"] = all(c.values())
    return c


def main():
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        raise SystemExit("POLYGON_API_KEY is missing")
    lines = ["# VWAP + Heikin Ashi backtest", "", f"Run date: {date.today()}. Rules were fixed before the run.", ""]
    results = {}
    for tf in TIMEFRAMES:
        rows = []
        for n, sym in enumerate(SYMBOLS):
            bt.SYMBOL = sym
            rows += run_symbol(bt.rth_only(bt.fetch_bars(tf, key)), sym, SEED + n)
        t = pd.DataFrame(rows)
        t["entry_time"] = pd.to_datetime(t["entry_time"], utc=True)
        t = t.sort_values("entry_time").reset_index(drop=True)
        t["year"] = t["entry_time"].dt.year
        dev = t[t["day"] < HOLDOUT].reset_index(drop=True)
        hold = t[t["day"] >= HOLDOUT].reset_index(drop=True)
        half = len(dev) // 2
        groups = {"Development": dev, "Dev first half": dev.iloc[:half], "Dev second half": dev.iloc[half:]}
        for sym in SYMBOLS:
            groups[f"Dev {sym}"] = dev[dev["symbol"] == sym]
        for y, g in dev.groupby("year"):
            groups[f"Dev {y}"] = g
        groups["Holdout"] = hold
        res = {k: bt.stats(g["r"].reset_index(drop=True)) for k, g in groups.items()}
        res["Dev random"] = bt.stats(dev["random_r"].dropna().reset_index(drop=True))
        res["Dev excess"] = bt.stats((dev["r"] - dev["random_r"]).dropna().reset_index(drop=True))
        res["Holdout excess"] = bt.stats((hold["r"] - hold["random_r"]).dropna().reset_index(drop=True))
        check = verdict(dev)
        hold_ok = bool(res["Holdout"].get("avg_r", -1) > 0 and res["Holdout excess"].get("avg_r", -1) > 0)
        lines += [f"## {tf} minutes", "", f"Median bars held: {t['bars'].median():.0f}.", "", bt.HEADER]
        lines += [bt.row_md(k, v) for k, v in res.items()]
        lines += ["", f"Development: {'PASS' if check['passed'] else 'FAIL'} {check}",
                  f"Holdout: {'PASS' if hold_ok else 'FAIL'}. Final: {'PASS' if check['passed'] and hold_ok else 'FAIL'}.",
                  "", "### Cost sensitivity, development", "", bt.HEADER]
        lines += [bt.row_md(f"Cost {k} bps", bt.stats(dev[f"r_{k}"].reset_index(drop=True))) for k in COSTS] + [""]
        t.to_csv(OUT / f"trades_{tf}m.csv", index=False)
        results[f"{tf}m"] = {"groups": res, "dev": check, "holdout": hold_ok}
    (OUT / "results.json").write_text(json.dumps(results, indent=2, default=str))
    (OUT / "results.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
