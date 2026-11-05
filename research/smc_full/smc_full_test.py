"""Full-market check of the daily SMC scanner, including delisted common stocks.

Ports detect() from smc_daily_scanner.py and the exit rules of smc_daily_track.py.
Part one scores the stored lookback signals. Part two runs five years of data,
with the last 12 months held out. Rules were fixed before the run.
"""
import json
import os
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

OUT = Path(__file__).parent
sys.path.insert(0, str(OUT.parent / "noise_band"))
sys.path.insert(0, str(OUT.parent / "flow_tests"))
import backtest as bt  # noqa: E402
import flow_test as ft  # noqa: E402

PIVOT_L = 3
MIN_RR = 1.5
FIB = 1.618
RELVOL_MIN = 2.0
CHANGE_MIN = 5.0
MIN_PRICE = 5.0
MIN_DOLLAR_VOL = 20_000_000
MAX_DAYS = 40
COST = 0.001
WINDOW = 252
MAX_SIGNAL_CHANGE = 100.0
DRAWS = 20
SEED = 42
HOLDOUT_START = date(2025, 11, 5)
BASE = set((OUT / "base_list.txt").read_text().split())


def pivots(h, l, n=PIVOT_L):
    ph, pl = [], []
    for k in range(n, len(h) - n):
        if h[k] >= h[k - n:k + n + 1].max():
            ph.append(k)
        if l[k] <= l[k - n:k + n + 1].min():
            pl.append(k)
    return np.array(ph), np.array(pl)


def detect(h, l, c, v):
    """Same logic as detect() in smc_daily_scanner.py, on the last bar of the arrays."""
    if len(c) < 80:
        return None
    i = len(c) - 1
    vavg = v[i - 20:i].mean()
    relvol = v[i] / vavg if vavg > 0 else 0
    chg = (c[i] / c[i - 1] - 1) * 100
    if not (relvol > RELVOL_MIN and chg > CHANGE_MIN and h[i] >= h[i - 19:i + 1].max()
            and c[i] >= MIN_PRICE and c[i] * vavg >= MIN_DOLLAR_VOL and chg <= MAX_SIGNAL_CHANGE):
        return None
    ph, pl = pivots(h, l)
    conf_h = ph[ph < i - PIVOT_L]
    if len(conf_h) == 0:
        return None
    a = conf_h[-1]
    level = h[a]
    if not (c[i] > level and c[i - 1] <= level):
        return None
    conf_l = pl[pl <= i - PIVOT_L]
    after_a = conf_l[conf_l > a]
    if len(after_a):
        b = after_a[-1]
    elif len(conf_l):
        b = conf_l[-1]
    else:
        return None
    stop = l[b]
    leg = level - l[max(0, a - 40):a + 1].min()
    if stop >= c[i] or leg <= 0:
        return None
    target = stop + leg * FIB
    rr = (target - c[i]) / (c[i] - stop)
    if rr < MIN_RR:
        return None
    return float(stop), float(target), float(rr)


def hold(o, h, l, c, entry_i, stop, target):
    """Tracker exit: stop, target, 40 days, or the last bar when a stock stops trading."""
    entry = o[entry_i]
    last = len(o) - 1
    n = 0
    for j in range(entry_i, last + 1):
        if l[j] <= stop:
            px = o[j] if (n > 0 and o[j] < stop) else stop
            return px, "stop", j
        if h[j] >= target:
            px = o[j] if (n > 0 and o[j] > target) else target
            return px, "target", j
        if n + 1 >= MAX_DAYS:
            return c[j], "time", j
        n += 1
    return c[last], "last_bar", last


def score(entry, px, risk):
    return (px * (1 - COST) - entry * (1 + COST)) / risk


def load_panels(days, key):
    session = requests.Session()
    names = ft.common_stocks(session, key)
    frames = []
    for d in days:
        url = f"{bt.BASE}/v2/aggs/grouped/locale/us/market/stocks/{d}"
        data = ft.api_get(session, url, {"adjusted": "true", "apiKey": key})
        rows = [x for x in data.get("results") or [] if x.get("T") in names]
        if rows:
            df = pd.DataFrame(rows)[["T", "o", "h", "l", "c", "v"]]
            df["date"] = d
            frames.append(df)
    return pd.concat(frames, ignore_index=True), names


def ticker_arrays(g):
    g = g.sort_values("date")
    return (g["date"].to_numpy(), *(g[x].to_numpy(float) for x in ("o", "h", "l", "c", "v")))


def run_ticker(sym, arrays, rng):
    dates, o, h, l, c, v = arrays
    rows, skipped, next_free = [], 0, 0
    vavg = pd.Series(v).shift(1).rolling(20).mean().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        chg = np.r_[np.nan, c[1:] / c[:-1] - 1] * 100
        hit = (v / vavg > RELVOL_MIN) & (chg > CHANGE_MIN)
    for i in np.where(hit)[0]:
        if i < 80 or i + 1 >= len(c) or i < next_free:
            continue
        lo = max(0, i - WINDOW + 1)
        sig = detect(h[lo:i + 1], l[lo:i + 1], c[lo:i + 1], v[lo:i + 1])
        if not sig:
            continue
        stop, target, rr = sig
        e = i + 1
        if o[e] <= stop or o[e] >= target:
            skipped += 1
            continue
        px, why, x = hold(o, h, l, c, e, stop, target)
        risk = o[e] - stop
        r = score(o[e], px, risk)
        s_pct, t_pct = stop / o[e], target / o[e]
        pool = np.arange(80, len(c) - 1)
        pool = pool[np.abs(pool - e) > MAX_DAYS]
        ctrl = []
        if len(pool):
            for k in rng.choice(pool, size=min(DRAWS, len(pool)), replace=False):
                s2, t2 = o[k] * s_pct, o[k] * t_pct
                px2, _, _ = hold(o, h, l, c, k, s2, t2)
                ctrl.append(score(o[k], px2, o[k] - s2))
        rows.append({"symbol": sym, "signal_date": dates[i], "entry_date": dates[e], "entry": o[e], "stop": stop,
                     "target": target, "exit_date": dates[x], "exit_px": px, "reason": why, "r": r, "days": x - e + 1,
                     "random_r": float(np.mean(ctrl)) if ctrl else np.nan, "in_base": sym in BASE})
        next_free = x + 1
    return rows, skipped


def lookback_results(data):
    src = pd.read_csv(OUT / "lookback.csv")
    rows = []
    for x in src.itertuples(index=False):
        if x.ticker not in data:
            continue
        dates, o, h, l, c, _ = data[x.ticker]
        after = np.where(dates > x.date)[0]
        if len(after) == 0:
            rows.append({"symbol": x.ticker, "signal": x.date, "status": "no_bars"})
            continue
        e = after[0]
        if o[e] <= x.stop or o[e] >= x.target:
            rows.append({"symbol": x.ticker, "signal": x.date, "status": "cancelled"})
            continue
        px, why, j = hold(o, h, l, c, e, x.stop, x.target)
        status = "open" if why == "last_bar" else "closed"
        rows.append({"symbol": x.ticker, "signal": x.date, "status": status, "reason": why, "days": j - e + 1,
                     "r": round(score(o[e], px, o[e] - x.stop), 2)})
    return pd.DataFrame(rows)


def dev_verdict(t):
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
    bt.SYMBOL = "SPY"
    daily = ft.daily_from_bars(bt.rth_only(bt.fetch_bars(5, key)))
    days = [d.isoformat() for d in daily.index]
    panel, names = load_panels(days, key)
    data = {sym: ticker_arrays(g) for sym, g in panel.groupby("T")}
    lines = ["# SMC daily full-market check", "", f"Run date: {date.today()}. Rules were fixed before the run.",
             f"Common stocks in reference list: {len(names)}. Tickers with bars: {len(data)}.", ""]

    lb = lookback_results(data)
    closed = lb[lb["status"] == "closed"]
    lines += ["## Part one: stored lookback signals", "", "```\n" + lb.to_csv(index=False) + "```", ""]
    if len(closed):
        lines += [f"Closed: {len(closed)}. Average R: {closed['r'].mean():.2f}. Wins: {(closed['r'] > 0).mean() * 100:.0f}%.", ""]

    rng = np.random.default_rng(SEED)
    rows, cancelled = [], 0
    for sym in sorted(data):
        r, skipped = run_ticker(sym, data[sym], rng)
        rows += r
        cancelled += skipped
    t = pd.DataFrame(rows).sort_values("entry_date").reset_index(drop=True)
    t["year"] = pd.to_datetime(t["entry_date"]).dt.year
    t["day"] = pd.to_datetime(t["entry_date"]).dt.date
    dev = t[t["day"] < HOLDOUT_START].reset_index(drop=True)
    hold_t = t[t["day"] >= HOLDOUT_START].reset_index(drop=True)
    half = len(dev) // 2
    groups = {"Development": dev, "Dev first half": dev.iloc[:half], "Dev second half": dev.iloc[half:],
              "Dev scanner list": dev[dev["in_base"]], "Dev other stocks": dev[~dev["in_base"]], "Holdout": hold_t,
              "Holdout scanner list": hold_t[hold_t["in_base"]]}
    for y, g in dev.groupby("year"):
        groups[f"Dev {y}"] = g
    res = {k: bt.stats(g["r"].reset_index(drop=True)) for k, g in groups.items()}
    res["Dev random"] = bt.stats(dev["random_r"].dropna().reset_index(drop=True))
    res["Dev excess"] = bt.stats((dev["r"] - dev["random_r"]).dropna().reset_index(drop=True))
    res["Holdout random"] = bt.stats(hold_t["random_r"].dropna().reset_index(drop=True))
    res["Holdout excess"] = bt.stats((hold_t["r"] - hold_t["random_r"]).dropna().reset_index(drop=True))
    check = dev_verdict(dev)
    hold_ok = bool(res["Holdout"].get("avg_r", -1) > 0 and res["Holdout excess"].get("avg_r", -1) > 0)
    top = t.groupby("symbol")["r"].sum().sort_values(ascending=False).head(10).round(1).to_dict()
    lines += ["## Part two: full market", "", f"Cancelled at the open: {cancelled}.",
              f"Exit reasons: {t['reason'].value_counts().to_dict()}. Median days: {t['days'].median():.0f}.", "", bt.HEADER]
    lines += [bt.row_md(k, x) for k, x in res.items()]
    lines += ["", f"Development verdict: {'PASS' if check['passed'] else 'FAIL'} {check}",
              f"Holdout verdict: {'PASS' if hold_ok else 'FAIL'}.",
              f"Final: {'PASS' if check['passed'] and hold_ok else 'FAIL'}.", "", f"Top symbols by total R: {top}", ""]
    lb.to_csv(OUT / "lookback_results.csv", index=False)
    t.drop(columns=["day"]).to_csv(OUT / "trades.csv", index=False)
    (OUT / "results.json").write_text(json.dumps({"groups": res, "dev": check, "holdout": hold_ok}, indent=2, default=str))
    (OUT / "results.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
