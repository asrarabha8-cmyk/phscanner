"""Three flow-based hypotheses tested with rules fixed before the run.

1. Last half hour: trade with a large day move from 15:30 to the close.
2. Turn of month: hold SPY from the second-last day to the third day of next month.
3. Loser reversal: buy the worst liquid stocks after a quiet open and hold for three days.

Results are in basis points after cost. Pass needs low 95% above zero, both
halves positive, and no single year making up half or more of the total.
"""
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

OUT = Path(__file__).parent
sys.path.insert(0, str(OUT.parent / "noise_band"))
from backtest import BASE, YEARS, fetch_bars, rma_atr, rth_only, stats  # noqa: E402

MOVE_K = 0.5
ETF_COSTS_BPS = (0.5, 1.0, 2.0)
MAIN_ETF_COST = 1.0
STOCK_COSTS_BPS = (5.0, 10.0, 20.0)
MAIN_STOCK_COST = 10.0
TOM_HOLD_DAYS = 4
TOP_LIQUID = 500
N_LOSERS = 10
MAX_GAP = 0.03
MAX_ABS_RET = 0.40
MIN_PRICE = 5.0
LOSER_HOLD = 3

HEADER = ("| Group | Trades | Win | Avg bps | Low 95% | Total bps | PF | Max DD bps |\n"
          "|---|---|---|---|---|---|---|---|")


def row(name, s):
    if not s.get("trades"):
        return f"| {name} | 0 | - | - | - | - | - | - |"
    return (f"| {name} | {s['trades']} | {s['win_pct']}% | {s['avg_r']:.2f} | {s['low95']:.2f} | "
            f"{s['total_r']:.0f} | {s['profit_factor']} | {s['max_dd_r']:.0f} |")


def verdict(t, col="bps"):
    r = t[col].reset_index(drop=True)
    half = len(r) // 2
    total = float(r.sum())
    years = t.groupby("year")[col].sum()
    s = stats(r)
    checks = {
        "low95_above_zero": s["low95"] > 0,
        "first_half_positive": float(r.iloc[:half].mean()) > 0,
        "second_half_positive": float(r.iloc[half:].mean()) > 0,
        "no_single_year_dominates": total > 0 and float(years.max()) < 0.5 * total,
    }
    checks["passed"] = all(checks.values())
    return checks


def daily_from_bars(bars):
    return bars.groupby("day").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                   close=("close", "last"))


def last_half_hour(bars, cost_bps):
    daily = daily_from_bars(bars)
    atr = rma_atr(daily["high"], daily["low"], daily["close"]).shift(1)
    prev = daily["close"].shift(1)
    rows = []
    for day, g in bars.groupby("day", sort=True):
        sig = g[g["mins"] == 925]
        last = g[g["mins"] == 955]
        if sig.empty or last.empty or np.isnan(prev.get(day, np.nan)) or np.isnan(atr.get(day, np.nan)):
            continue
        entry = float(sig["close"].iloc[0])
        move = entry / prev[day] - 1
        if abs(move) < MOVE_K * atr[day] / prev[day]:
            continue
        side = 1 if move > 0 else -1
        bps = side * (float(last["close"].iloc[0]) / entry - 1) * 1e4 - cost_bps
        rows.append({"day": day, "side": "long" if side == 1 else "short", "bps": bps})
    return pd.DataFrame(rows)


def turn_of_month(daily, cost_bps):
    closes = daily["close"]
    rets = closes.pct_change().dropna()
    base = float(rets.mean()) * TOM_HOLD_DAYS * 1e4
    days = pd.to_datetime(pd.Series(daily.index))
    is_last = days.dt.to_period("M") != days.shift(-1).dt.to_period("M")
    rows = []
    for i in np.where(is_last.iloc[:-1])[0]:
        if i < 1 or i + 3 >= len(closes):
            continue
        ret = (closes.iloc[i + 3] / closes.iloc[i - 1] - 1) * 1e4 - cost_bps
        rows.append({"day": daily.index[i - 1], "raw_bps": ret, "bps": ret - base})
    return pd.DataFrame(rows)


def api_get(session, url, params=None):
    for _ in range(6):
        r = session.get(url, params=params, timeout=60)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            time.sleep(15)
            continue
        raise SystemExit(f"Data request failed with status {r.status_code}")
    raise SystemExit("Data request kept hitting the rate limit")


def common_stocks(session, key):
    names = set()
    for active in ("true", "false"):
        params = {"market": "stocks", "type": "CS", "active": active, "limit": 1000, "apiKey": key}
        url = f"{BASE}/v3/reference/tickers"
        while url:
            data = api_get(session, url, params)
            names.update(x["ticker"] for x in data.get("results", []))
            url = data.get("next_url")
            params = {"apiKey": key}
    return names


def stock_panels(days, key):
    session = requests.Session()
    names = common_stocks(session, key)
    frames = []
    for d in days:
        url = f"{BASE}/v2/aggs/grouped/locale/us/market/stocks/{d}"
        data = api_get(session, url, {"adjusted": "true", "apiKey": key})
        rows = [x for x in data.get("results") or [] if x.get("T") in names]
        if rows:
            df = pd.DataFrame(rows)[["T", "o", "c", "v"]]
            df["date"] = d
            frames.append(df)
    all_rows = pd.concat(frames, ignore_index=True)
    return (all_rows.pivot_table(index="date", columns="T", values=x, aggfunc="last") for x in ("o", "c", "v"))


def loser_reversal(o, c, v, spy_o, spy_c, cost_bps):
    r = c / c.shift(1) - 1
    gap = o / c.shift(1) - 1
    dollar = (c * v).rolling(20, min_periods=15).mean()
    liquid = dollar.rank(axis=1, ascending=False) <= TOP_LIQUID
    spy_r = spy_c.pct_change()
    rows = []
    for t in range(20, len(c) - LOSER_HOLD, LOSER_HOLD):
        d = c.index[t]
        ok = liquid.iloc[t] & (c.iloc[t] >= MIN_PRICE) & (gap.iloc[t].abs() <= MAX_GAP) & (r.iloc[t].abs() <= MAX_ABS_RET)
        excess = (r.iloc[t] - spy_r.loc[d])[ok].dropna().nsmallest(N_LOSERS)
        if len(excess) < N_LOSERS:
            continue
        names = excess.index
        rets = (c.iloc[t + LOSER_HOLD][names] / o.iloc[t + 1][names] - 1).dropna()
        if rets.empty:
            continue
        d1, d3 = c.index[t + 1], c.index[t + LOSER_HOLD]
        spy_ret = spy_c.loc[d3] / spy_o.loc[d1] - 1
        rows.append({"day": d, "raw_bps": float(rets.mean()) * 1e4 - cost_bps,
                     "bps": (float(rets.mean()) - spy_ret) * 1e4 - cost_bps})
    return pd.DataFrame(rows)


def report(name, t, costs_table, extra=None):
    t = t.copy()
    t["year"] = pd.to_datetime(t["day"]).dt.year
    half = len(t) // 2
    groups = {"All": t, "First half": t.iloc[:half], "Second half": t.iloc[half:]}
    groups.update(extra(t) if extra else {})
    for y, g in t.groupby("year"):
        groups[str(y)] = g
    res = {k: stats(g["bps"]) for k, g in groups.items()}
    check = verdict(t)
    lines = [f"## {name}", "", HEADER] + [row(k, v) for k, v in res.items()]
    lines += ["", f"Verdict: {'PASS' if check['passed'] else 'FAIL'} {check}", "",
              "### Cost sensitivity", "", HEADER] + [row(k, v) for k, v in costs_table.items()] + [""]
    return lines, {"groups": res, "verdict": check}


def main():
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        raise SystemExit("POLYGON_API_KEY is missing")
    bars = rth_only(fetch_bars(5, key))
    daily = daily_from_bars(bars)
    lines = ["# Flow hypothesis tests", "", f"Run date: {date.today()}. Rules were fixed before the run.",
             f"SPY data: {bars['day'].min()} to {bars['day'].max()}, {len(daily)} days.",
             "SPY prices are split adjusted, without dividends.", ""]
    results = {}

    t1 = last_half_hour(bars, MAIN_ETF_COST)
    costs = {f"Cost {c} bps": stats(last_half_hour(bars, c)["bps"]) for c in ETF_COSTS_BPS}
    extra = lambda t: {"Long": t[t["side"] == "long"], "Short": t[t["side"] == "short"]}
    out, results["last_half_hour"] = report("Last half hour", t1, costs, extra)
    lines += out
    t1.to_csv(OUT / "trades_last_half_hour.csv", index=False)

    t2 = turn_of_month(daily, MAIN_ETF_COST)
    costs = {f"Cost {c} bps": stats(turn_of_month(daily, c)["bps"]) for c in ETF_COSTS_BPS}
    out, results["turn_of_month"] = report("Turn of month, excess over normal days", t2, costs)
    lines += out + [f"Raw average per trade: {t2['raw_bps'].mean():.1f} bps.", ""]
    t2.to_csv(OUT / "trades_turn_of_month.csv", index=False)

    days = [d.isoformat() for d in daily.index]
    o, c, v = stock_panels(days, key)
    spy_o = daily["open"].copy()
    spy_c = daily["close"].copy()
    spy_o.index = spy_c.index = [d.isoformat() for d in daily.index]
    t3 = loser_reversal(o, c, v, spy_o, spy_c, MAIN_STOCK_COST)
    costs = {f"Cost {x} bps": stats(loser_reversal(o, c, v, spy_o, spy_c, x)["bps"]) for x in STOCK_COSTS_BPS}
    out, results["loser_reversal"] = report("Loser reversal, excess over SPY", t3, costs)
    lines += out + [f"Raw average per trade: {t3['raw_bps'].mean():.1f} bps.", ""]
    t3.to_csv(OUT / "trades_loser_reversal.csv", index=False)

    (OUT / "results.json").write_text(json.dumps(results, indent=2, default=str))
    (OUT / "results.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
