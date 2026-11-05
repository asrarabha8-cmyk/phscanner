"""Options Sniper on daily-selected volatile stocks, with rules fixed before the run.

Selection uses data through the prior close only. Intraday bars are fetched for
each selected stock and day. The last 12 months are held out from the main verdict.
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

OUT = Path(__file__).parent
sys.path.insert(0, str(OUT.parent / "noise_band"))
sys.path.insert(0, str(OUT.parent / "options_sniper"))
sys.path.insert(0, str(OUT.parent / "flow_tests"))
import backtest as bt  # noqa: E402
import flow_test as ft  # noqa: E402
import sniper_test as sn  # noqa: E402

TF = 15
TOP_LIQUID = 1000
MIN_PRICE = 10.0
N_PICKS = 10
MAIN_COST = 5.0
COSTS = (2.0, 5.0, 10.0)
DRAWS = 20
THREADS = 8
HOLDOUT_START = date(2025, 11, 5)


def pick_stocks(o, c, v):
    r = c / c.shift(1) - 1
    vol = r.abs().rolling(14, min_periods=10).mean()
    relvol = v / v.shift(1).rolling(20, min_periods=15).mean()
    dollar = (c * v).rolling(20, min_periods=15).mean()
    liquid = dollar.rank(axis=1, ascending=False) <= TOP_LIQUID
    picks = []
    for t in range(20, len(c) - 1):
        ok = liquid.iloc[t] & (c.iloc[t] >= MIN_PRICE) & (r.iloc[t].abs() <= 0.5)
        names = ok[ok].index
        if len(names) < N_PICKS:
            continue
        score = relvol.iloc[t][names].rank(pct=True) + vol.iloc[t][names].rank(pct=True)
        for sym in score.dropna().nlargest(N_PICKS).index:
            picks.append((date.fromisoformat(str(c.index[t + 1])[:10]), sym))
    return picks


def fetch_day(session, sym, day, key):
    start = day - timedelta(days=7)
    url = f"{bt.BASE}/v2/aggs/ticker/{sym}/range/{TF}/minute/{start}/{day}"
    params = {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": key}
    data = ft.api_get(session, url, params)
    rows = data.get("results") or []
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["dt"] = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_convert("America/New_York")
    df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    return bt.rth_only(df[["dt", "open", "high", "low", "close", "volume"]])


def trade_day(bars, day, sym, seed):
    df = sn.indicators(bars).reset_index(drop=True)
    idx = np.where(df["day"].to_numpy() == day)[0]
    if len(idx) < 3:
        return []
    lo, hi, cl = (df[x].to_numpy() for x in ("low", "high", "close"))
    sig, times = df["signal"].to_numpy(), df["dt"].to_numpy()
    last = idx[-1]
    day_end = np.full(len(df), last)
    rng = np.random.default_rng(seed)
    pool = idx[:-1]
    rows = []
    i = idx[0]
    while i < last:
        if not sig[i] or cl[i] <= lo[i]:
            i += 1
            continue
        entry, risk = cl[i], max(cl[i] - lo[i], 0.01)
        pct = risk / entry
        out = {}
        for c in COSTS:
            out[f"r_{c}"], exit_i, win = sn.walk(i, entry, risk, entry * c / 1e4, lo, hi, cl, day_end)
            if c == MAIN_COST:
                main_exit, main_win = exit_i, win
        ctrl = [sn.walk(k, cl[k], cl[k] * pct, cl[k] * MAIN_COST / 1e4, lo, hi, cl, day_end)[0]
                for k in rng.choice(pool, size=min(DRAWS, len(pool)), replace=False)]
        rows.append({"symbol": sym, "day": day, "entry_time": times[i], "win": main_win,
                     "r": out[f"r_{MAIN_COST}"], "random_r": float(np.mean(ctrl)), "risk_pct": pct, **out})
        i = main_exit + 1
    return rows


def run_picks(picks, key):
    session = requests.Session()

    def one(item):
        n, (day, sym) = item
        try:
            bars = fetch_day(session, sym, day, key)
            return ("ok", trade_day(bars, day, sym, n)) if bars is not None and len(bars) else ("empty", [])
        except (requests.RequestException, SystemExit):
            return ("failed", [])

    with ThreadPoolExecutor(THREADS) as pool:
        results = list(pool.map(one, enumerate(picks)))
    status = pd.Series([s for s, _ in results]).value_counts().to_dict()
    rows = [row for _, r in results for row in r]
    return pd.DataFrame(rows), status


def dev_verdict(t):
    s = bt.stats(t["r"].reset_index(drop=True))
    ex = bt.stats((t["r"] - t["random_r"]).reset_index(drop=True))
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
    bt.SYMBOL = "SPY"
    daily = ft.daily_from_bars(bt.rth_only(bt.fetch_bars(5, key)))
    days = [d.isoformat() for d in daily.index]
    o, c, v = ft.stock_panels(days, key)
    picks = pick_stocks(o, c, v)
    t, status = run_picks(picks, key)
    t["entry_time"] = pd.to_datetime(t["entry_time"], utc=True)
    t = t.sort_values("entry_time").reset_index(drop=True)
    t["year"] = t["entry_time"].dt.year
    dev = t[t["day"] < HOLDOUT_START].reset_index(drop=True)
    hold = t[t["day"] >= HOLDOUT_START].reset_index(drop=True)
    half = len(dev) // 2
    groups = {"Development": dev, "Dev first half": dev.iloc[:half], "Dev second half": dev.iloc[half:],
              "Holdout": hold}
    for y, g in dev.groupby("year"):
        groups[f"Dev {y}"] = g
    res = {k: bt.stats(g["r"].reset_index(drop=True)) for k, g in groups.items()}
    res["Dev random"] = bt.stats(dev["random_r"].reset_index(drop=True))
    res["Dev excess"] = bt.stats((dev["r"] - dev["random_r"]).reset_index(drop=True))
    res["Holdout random"] = bt.stats(hold["random_r"].reset_index(drop=True))
    res["Holdout excess"] = bt.stats((hold["r"] - hold["random_r"]).reset_index(drop=True))
    check = dev_verdict(dev)
    hold_ok = bool(res["Holdout"].get("avg_r", -1) > 0 and res["Holdout excess"].get("avg_r", -1) > 0)
    top = t.groupby("symbol")["r"].sum().sort_values(ascending=False).head(10).round(1).to_dict()
    lines = ["# Options Sniper on selected stocks", "", f"Run date: {date.today()}. Rules were fixed before the run.",
             f"Picks: {len(picks)}. Fetch status: {status}.", "", bt.HEADER]
    lines += [bt.row_md(k, x) for k, x in res.items()]
    lines += ["", f"Development verdict: {'PASS' if check['passed'] else 'FAIL'} {check}",
              f"Holdout verdict: {'PASS' if hold_ok else 'FAIL'}.",
              f"Final: {'PASS' if check['passed'] and hold_ok else 'FAIL'}.", "",
              f"Top symbols by total R: {top}", "", "### Cost sensitivity, development", "", bt.HEADER]
    for cost in COSTS:
        lines.append(bt.row_md(f"Cost {cost} bps", bt.stats(dev[f"r_{cost}"].reset_index(drop=True))))
    lines.append("")
    t.to_csv(OUT / "trades.csv", index=False)
    (OUT / "results.json").write_text(json.dumps({"groups": res, "dev": check, "holdout": hold_ok}, indent=2, default=str))
    (OUT / "results.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
