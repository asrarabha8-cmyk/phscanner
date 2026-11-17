"""VWAP grid: which timeframe and which helper indicator work best with VWAP on SPY.

Everything below was fixed before the run.
Timeframes: 1, 3, 5, 15 minutes. Five years of SPY regular-session bars.
Signals (long; short is the mirror):
- cross: close above session VWAP after the previous close was at or below it.
- bounce: the two previous closes above VWAP, this bar's low touches VWAP and
  it closes above.
Helper filters at the signal bar (default settings, not tuned):
none, ema (EMA9 > EMA21), rsi (RSI14 > 50), macd (histogram > 0),
rvol (volume > 1.5 x 20-bar average), ha (Heikin Ashi bar green), adx (ADX14 > 20),
supertrend (10, 3 up), dayopen (close above the day's open),
orb (close above the first 15 minutes' high), qqq (QQQ up more than SPY since the open).
Trades: entries from 09:45 to 15:00 New York at the next bar's open, one at a time.
Exit at the next bar's open after a close back across VWAP, or after 60 minutes,
or at the last bar's close. Result per trade in SPY basis points less 1 bp cost.
Selection uses development data only; the last 12 months are the holdout.
A combination passes with at least 200 development trades, development low 95% > 0,
both development halves positive, holdout average positive, and a development
average above the 95th percentile of 30 random filters with the same pass rate.
"""
import json
import math
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).parent
sys.path.insert(0, str(OUT.parent / "noise_band"))
import backtest as bt  # noqa: E402

TFS = (1, 3, 5, 15)
FILTERS = ("none", "ema", "rsi", "macd", "rvol", "ha", "adx", "supertrend", "dayopen", "orb", "qqq")
COST = 1.0
HOLD_MIN = 60
N_RANDOM = 30
Z95 = 1.96


def load(sym, tf, key):
    bt.SYMBOL, bt.YEARS = sym, 5
    return bt.rth_only(bt.fetch_bars(tf, key))


def ema(x, n):
    return x.ewm(span=n, adjust=False).mean()


def indicators(b, q, tf):
    b = b.copy()
    c, h, l, o, v = b["close"], b["high"], b["low"], b["open"], b["volume"]
    tp = (h + l + c) / 3
    w = v.where(v > 0, 1.0)
    b["vw"] = (tp * w).groupby(b["day"]).cumsum() / w.groupby(b["day"]).cumsum()
    b["first"] = b.groupby("day").cumcount() == 0
    b["ema"] = np.sign(ema(c, 9) - ema(c, 21))
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    b["rsi"] = np.sign(100 - 100 / (1 + up / dn.replace(0, np.nan)) - 50).fillna(0)
    macd = ema(c, 12) - ema(c, 26)
    b["macd"] = np.sign(macd - ema(macd, 9))
    b["rvol"] = (v > 1.5 * v.rolling(20).mean()).astype(float)
    ha_c = (o + h + l + c) / 4
    ha_o = ha_c.copy()
    vals_o, vals_c = o.to_numpy(), ha_c.to_numpy()
    out = np.empty(len(b))
    out[0] = (vals_o[0] + c.iloc[0]) / 2
    for i in range(1, len(b)):
        out[i] = (out[i - 1] + vals_c[i - 1]) / 2
    ha_o[:] = out
    b["ha"] = np.sign(ha_c - ha_o)
    atr = bt.rma_atr(h, l, c, 14)
    pdm = (h.diff()).where((h.diff() > -l.diff()) & (h.diff() > 0), 0.0)
    mdm = (-l.diff()).where((-l.diff() > h.diff()) & (-l.diff() > 0), 0.0)
    pdi = 100 * pdm.ewm(alpha=1 / 14, adjust=False).mean() / atr
    mdi = 100 * mdm.ewm(alpha=1 / 14, adjust=False).mean() / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    b["adx"] = (dx.ewm(alpha=1 / 14, adjust=False).mean() > 20).astype(float)
    b["supertrend"] = supertrend(h.to_numpy(), l.to_numpy(), c.to_numpy(), bt.rma_atr(h, l, c, 10).to_numpy())
    b["dayopen"] = np.sign(c - b.groupby("day")["open"].transform("first"))
    orb = b["mins"] < 585
    hi = h.where(orb).groupby(b["day"]).transform("max")
    lo = l.where(orb).groupby(b["day"]).transform("min")
    b["orb"] = np.where(b["mins"] < 585, 0, np.where(c > hi, 1, np.where(c < lo, -1, 0)))
    q = q[["dt", "close"]].rename(columns={"close": "qc"})
    b = b.merge(q, on="dt", how="left")
    b["qc"] = b["qc"].ffill()
    rq = b["qc"] / b.groupby("day")["qc"].transform("first") - 1
    rs = b["close"] / b.groupby("day")["open"].transform("first") - 1
    b["qqq"] = np.sign(rq - rs).fillna(0)
    b["none"] = 1.0
    return b


def supertrend(h, l, c, atr, mult=3.0):
    n = len(c)
    d = np.ones(n)
    up_b, dn_b = np.zeros(n), np.zeros(n)
    for i in range(n):
        mid = (h[i] + l[i]) / 2
        a = atr[i] if not np.isnan(atr[i]) else 0.0
        ub, lb = mid + mult * a, mid - mult * a
        if i == 0:
            up_b[i], dn_b[i] = ub, lb
            continue
        up_b[i] = ub if ub < up_b[i - 1] or c[i - 1] > up_b[i - 1] else up_b[i - 1]
        dn_b[i] = lb if lb > dn_b[i - 1] or c[i - 1] < dn_b[i - 1] else dn_b[i - 1]
        if d[i - 1] == -1 and c[i] > up_b[i - 1]:
            d[i] = 1
        elif d[i - 1] == 1 and c[i] < dn_b[i - 1]:
            d[i] = -1
        else:
            d[i] = d[i - 1]
    return d


def raw_signals(b):
    c, vw, low, high = b["close"], b["vw"], b["low"], b["high"]
    same1 = b["day"] == b["day"].shift(1)
    same2 = b["day"] == b["day"].shift(2)
    above, below = c > vw, c < vw
    cross = np.where(same1 & above & (c.shift(1) <= vw.shift(1)), 1,
                     np.where(same1 & below & (c.shift(1) >= vw.shift(1)), -1, 0))
    was_up = same2 & (c.shift(1) > vw.shift(1)) & (c.shift(2) > vw.shift(2))
    was_dn = same2 & (c.shift(1) < vw.shift(1)) & (c.shift(2) < vw.shift(2))
    bounce = np.where(was_up & (low <= vw) & above, 1, np.where(was_dn & (high >= vw) & below, -1, 0))
    return {"cross": cross, "bounce": bounce}


def allowed(b, sig, filt):
    f = b[filt].to_numpy()
    if filt in ("rvol", "adx", "none"):
        return (sig != 0) & (f > 0)
    return (sig != 0) & (f == sig)


def simulate(arr, sig, ok):
    mins, day, op, cl, vw = arr["mins"], arr["day"], arr["open"], arr["close"], arr["vw"]
    n = len(cl)
    res_day, res_r = [], []
    i = 0
    while i < n - 1:
        if ok[i] and 585 <= mins[i] <= 900 and day[i + 1] == day[i]:
            dr = sig[i]
            e = i + 1
            px = op[e]
            j = e
            x_px = None
            while True:
                last = j + 1 >= n or day[j + 1] != day[j]
                against = (dr == 1 and cl[j] < vw[j]) or (dr == -1 and cl[j] > vw[j])
                timed = mins[j] - mins[e] >= HOLD_MIN
                if last:
                    x_px = cl[j]
                    break
                if against or timed:
                    x_px = op[j + 1]
                    j += 1
                    break
                j += 1
            res_day.append(day[e])
            res_r.append(dr * (x_px / px - 1) * 1e4 - COST)
            i = j
            continue
        i += 1
    return pd.DataFrame({"day": res_day, "r": res_r})


def summarize(t):
    if len(t) < 2:
        return {"n": len(t)}
    r = t["r"]
    se = r.std(ddof=1) / math.sqrt(len(r))
    return {"n": len(t), "avg": round(r.mean(), 2), "low95": round(r.mean() - Z95 * se, 2),
            "win": round(100 * (r > 0).mean(), 1), "total": round(r.sum())}


def main():
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        raise SystemExit("POLYGON_API_KEY is missing")
    cut = date.today() - timedelta(days=365)
    rng = np.random.default_rng(7)
    rows = []
    for tf in TFS:
        b = indicators(load("SPY", tf, key), load("QQQ", tf, key), tf)
        arr = {k: b[k].to_numpy() for k in ("mins", "day", "open", "close", "vw")}
        dev_mask = b["day"].to_numpy() < cut
        sigs = raw_signals(b)
        for sname, sig in sigs.items():
            rand_avgs = []
            for filt in FILTERS:
                ok = allowed(b, sig, filt)
                t = simulate(arr, sig, ok)
                dev, hold = t[t["day"] < cut].reset_index(drop=True), t[t["day"] >= cut]
                half = len(dev) // 2
                rows.append({"tf": tf, "signal": sname, "filter": filt, "pass_rate": float(ok[dev_mask].sum() / max((sig[dev_mask] != 0).sum(), 1)),
                             "dev": summarize(dev), "h1": summarize(dev.iloc[:half]), "h2": summarize(dev.iloc[half:]),
                             "hold": summarize(hold)})
                print(tf, sname, filt, rows[-1]["dev"], rows[-1]["hold"], flush=True)
            # random filters with the same pass rate as the median real filter, for this tf and signal
            rates = [r["pass_rate"] for r in rows if r["tf"] == tf and r["signal"] == sname and r["filter"] != "none"]
            p = float(np.median(rates))
            for _ in range(N_RANDOM):
                ok = (sig != 0) & (rng.random(len(sig)) < p)
                t = simulate(arr, sig, ok)
                d = t[t["day"] < cut]
                rand_avgs.append(d["r"].mean() if len(d) else np.nan)
            thr = float(np.nanpercentile(rand_avgs, 95))
            for r in rows:
                if r["tf"] == tf and r["signal"] == sname:
                    r["random95"] = round(thr, 2)

    def passed(r):
        d = r["dev"]
        return bool(d.get("n", 0) >= 200 and d.get("low95", -1) > 0 and r["h1"].get("avg", -1) > 0
                    and r["h2"].get("avg", -1) > 0 and r["hold"].get("avg", -1) > 0 and d["avg"] > r["random95"])

    for r in rows:
        r["passed"] = passed(r)
    ranked = sorted(rows, key=lambda r: r["dev"].get("low95", -99), reverse=True)
    lines = ["# VWAP grid on SPY", "", f"Run date: {date.today()}. Holdout from {cut}. Results in SPY basis points per trade after 1 bp cost.",
             f"Combinations tested: {len(rows)}. Passed: {sum(r['passed'] for r in rows)}.", "",
             "## Ranked by development low 95%", "",
             "| TF | Signal | Filter | Dev trades | Dev avg | Dev low95 | Dev win | Half 1 | Half 2 | Random 95th | Holdout trades | Holdout avg | Holdout win | Pass |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in ranked:
        d, h = r["dev"], r["hold"]
        lines.append(f"| {r['tf']}m | {r['signal']} | {r['filter']} | {d.get('n')} | {d.get('avg')} | {d.get('low95')} | {d.get('win')}% | "
                     f"{r['h1'].get('avg')} | {r['h2'].get('avg')} | {r['random95']} | {h.get('n')} | {h.get('avg')} | {h.get('win')}% | "
                     f"{'PASS' if r['passed'] else '-'} |")
    lines += ["", "## Average by timeframe (development, all filters)", ""]
    for tf in TFS:
        a = [r["dev"].get("avg") for r in rows if r["tf"] == tf and r["dev"].get("avg") is not None]
        lines.append(f"- {tf}m: {np.mean(a):.2f} bps")
    lines += ["", "## Average by filter (development, all timeframes and signals)", ""]
    for f in FILTERS:
        a = [r["dev"].get("avg") for r in rows if r["filter"] == f and r["dev"].get("avg") is not None]
        lines.append(f"- {f}: {np.mean(a):.2f} bps")
    (OUT / "results.md").write_text("\n".join(lines))
    (OUT / "results.json").write_text(json.dumps(rows, indent=2, default=str))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
