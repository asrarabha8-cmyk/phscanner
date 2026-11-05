"""Options Sniper backtest with rules fixed before the run.

Ports OptionsSniper.pine on regular-session bars. The script has no time exit,
so positions close by the session end, with one position per symbol at a time.
Each real trade is compared with random long entries at the same time of day,
using the same percent stop, target and cost.
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

DEFAULT_SYMBOLS = "SPY,QQQ,AAPL,MSFT,NVDA,AMZN,META,TSLA,AMD,GOOGL"
SYMBOLS = tuple(os.environ.get("SNIPER_SYMBOLS", DEFAULT_SYMBOLS).split(","))
SUFFIX = "" if len(SYMBOLS) > 1 else f"_{SYMBOLS[0]}"
TIMEFRAMES = (3, 5, 15)
COST_BPS = (1.0, 2.0, 5.0)
MAIN_COST = 2.0
VOL_MULT = 1.5
LENGTH = 20
RR = 2.0
DRAWS = 20
SEED = 42


def indicators(df):
    df = df.copy()
    avg_vol = df["volume"].rolling(20).mean()
    resistance = df["high"].rolling(LENGTH).max().shift(1)
    pv = (df["close"] * df["volume"]).groupby(df["day"]).cumsum()
    vol = df["volume"].groupby(df["day"]).cumsum()
    vwap = pv / vol.replace(0, np.nan)
    ema9 = df["close"].ewm(span=9, adjust=False).mean()
    df["signal"] = ((df["close"] > resistance) & (df["volume"] > avg_vol * VOL_MULT)
                    & (df["close"] > vwap) & (df["close"] > ema9))
    return df


def walk(i, entry, risk, cost, lo, hi, cl, day_end):
    """Hold from the bar after i to stop, target or session end. A bar touching both counts as a stop."""
    stop, target = entry - risk, entry + RR * risk
    end = day_end[i]
    for j in range(i + 1, end + 1):
        if lo[j] <= stop:
            return (-risk - cost) / risk, j, False
        if hi[j] >= target:
            return (RR * risk - cost) / risk, j, True
    return (cl[end] - entry - cost) / risk, end, False


def run_symbol(df, sym, cost_bps, seed):
    df = indicators(df)
    lo, hi, cl = (df[x].to_numpy() for x in ("low", "high", "close"))
    sig = df["signal"].to_numpy()
    days = df["day"].to_numpy()
    mins = df["mins"].to_numpy()
    times = df["dt"].to_numpy()
    last_of_day = pd.Series(np.arange(len(df))).groupby(days).transform("max").to_numpy()
    same_time = {m: np.where(mins == m)[0] for m in np.unique(mins)}
    rng = np.random.default_rng(seed)
    rows = []
    i, n = 0, len(df)
    while i < n:
        if not sig[i] or last_of_day[i] == i or cl[i] <= lo[i]:
            i += 1
            continue
        entry, risk = cl[i], max(cl[i] - lo[i], 0.01)
        cost = entry * cost_bps / 1e4
        r, exit_i, win = walk(i, entry, risk, cost, lo, hi, cl, last_of_day)
        pct = risk / entry
        pool = same_time[mins[i]]
        pool = pool[(days[pool] != days[i]) & (last_of_day[pool] != pool)]
        ctrl = []
        if len(pool):
            for k in rng.choice(pool, size=min(DRAWS, len(pool)), replace=False):
                e2 = cl[k]
                ctrl.append(walk(k, e2, e2 * pct, e2 * cost_bps / 1e4, lo, hi, cl, last_of_day)[0])
        rows.append({"symbol": sym, "entry_time": times[i], "win": win, "r": r,
                     "random_r": float(np.mean(ctrl)) if ctrl else np.nan, "risk_pct": pct})
        i = exit_i + 1
    return pd.DataFrame(rows)


def verdict(t):
    s = bt.stats(t["r"].reset_index(drop=True))
    half = len(t) // 2
    total = float(t["r"].sum())
    excess = bt.stats((t["r"] - t["random_r"]).dropna().reset_index(drop=True))
    years = t.groupby("year")["r"].sum()
    checks = {
        "low95_above_zero": s["low95"] > 0,
        "first_half_positive": float(t["r"].iloc[:half].mean()) > 0,
        "second_half_positive": float(t["r"].iloc[half:].mean()) > 0,
        "no_single_year_dominates": total > 0 and float(years.max()) < 0.5 * total,
        "beats_random": excess["low95"] > 0,
    }
    checks["passed"] = all(checks.values())
    return checks


def run_all(data, cost):
    frames = [run_symbol(df, sym, cost, SEED + i) for i, (sym, df) in enumerate(data.items())]
    t = pd.concat([f for f in frames if len(f)], ignore_index=True)
    t["entry_time"] = pd.to_datetime(t["entry_time"], utc=True)
    t = t.sort_values("entry_time").reset_index(drop=True)
    t["year"] = t["entry_time"].dt.year
    return t


def main():
    if not os.environ.get("POLYGON_API_KEY", "").strip():
        raise SystemExit("POLYGON_API_KEY is missing")
    key = os.environ["POLYGON_API_KEY"].strip()
    lines = [f"# Options Sniper backtest{SUFFIX}", "", f"Run date: {date.today()}. Rules were fixed before the run.", ""]
    results = {}
    for tf in TIMEFRAMES:
        data = {}
        for sym in SYMBOLS:
            bt.SYMBOL = sym
            data[sym] = bt.rth_only(bt.fetch_bars(tf, key))
        t = run_all(data, MAIN_COST)
        half = len(t) // 2
        groups = {"All": t, "First half": t.iloc[:half], "Second half": t.iloc[half:]}
        for sym in SYMBOLS:
            groups[sym] = t[t["symbol"] == sym]
        for y, g in t.groupby("year"):
            groups[str(y)] = g
        res = {k: bt.stats(g["r"].reset_index(drop=True)) for k, g in groups.items()}
        res["Random control"] = bt.stats(t["random_r"].dropna().reset_index(drop=True))
        res["Excess over random"] = bt.stats((t["r"] - t["random_r"]).dropna().reset_index(drop=True))
        check = verdict(t)
        first = min(d["day"].min() for d in data.values())
        last = max(d["day"].max() for d in data.values())
        lines += [f"## {tf} minutes", "", f"Data: {first} to {last}.", "", bt.HEADER]
        lines += [bt.row_md(k, v) for k, v in res.items()]
        lines += ["", f"Verdict: {'PASS' if check['passed'] else 'FAIL'} {check}", "",
                  "### Cost sensitivity", "", bt.HEADER]
        for c in COST_BPS:
            lines.append(bt.row_md(f"Cost {c} bps", bt.stats(run_all(data, c)["r"].reset_index(drop=True))))
        lines.append("")
        t.to_csv(OUT / f"trades{SUFFIX}_{tf}m.csv", index=False)
        results[f"{tf}m"] = {"groups": res, "verdict": check}
    (OUT / f"results{SUFFIX}.json").write_text(json.dumps(results, indent=2, default=str))
    (OUT / f"results{SUFFIX}.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
