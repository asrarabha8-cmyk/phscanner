"""EMA 200 on the 1-minute chart: "only buy when price is near or touching it".

Rules were fixed before the run.
Symbols: SPY, QQQ, AAPL, MSFT, NVDA, AMZN, META, GOOGL, TSLA. Five years of
regular-session 1-minute bars; the EMA runs continuously across days.
Touch signals from 09:45 to 15:00 New York:
- Call: the two previous closes above the EMA, this bar's low touches it, and it
  closes above.
- Put: the mirror below the EMA.
Entry at the next bar's open, one trade per symbol at a time.
Exits measured separately: after 15, 30 and 60 minutes, and a stop version
(exit at the next open after a close back across the EMA, otherwise after 60 minutes).
Exits never cross the session close. Results in basis points of the stock, less
1 bp for SPY and QQQ and 2 bp for single stocks.
Control: entries in the same direction (side of the EMA) while price is more than
0.3% away from it, sampled every 30 bars, same hours.
Pass (pooled, 30-minute exit): development low 95% > 0, both halves positive,
holdout positive, and touch average above the far-control average in development
and holdout. Holdout: the last 12 months.
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

SYMBOLS = ("SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA")
HORIZONS = (15, 30, 60)
FAR = 0.003
Z95 = 1.96


def trades(b, sym):
    cost = 1.0 if sym in ("SPY", "QQQ") else 2.0
    c, o, h, l = (b[k].to_numpy() for k in ("close", "open", "high", "low"))
    e = b["close"].ewm(span=200, adjust=False).mean().to_numpy()
    mins, day = b["mins"].to_numpy(), b["day"].to_numpy()
    n = len(c)
    # last index of each day
    last = np.zeros(n, dtype=int)
    idx = np.arange(n)
    ends = np.r_[np.nonzero(day[1:] != day[:-1])[0], n - 1]
    starts = np.r_[0, ends[:-1] + 1]
    for s, t in zip(starts, ends):
        last[s:t + 1] = t
    win = (mins >= 585) & (mins <= 900)
    warm = idx >= 400
    same2 = np.r_[False, False, (day[2:] == day[1:-1]) & (day[1:-1] == day[:-2])]
    up = same2 & (np.r_[0, 0, c[1:-1]] > np.r_[0, 0, e[1:-1]]) & (np.r_[0, 0, c[:-2]] > np.r_[0, 0, e[:-2]]) & (l <= e) & (c > e)
    dn = same2 & (np.r_[0, 0, c[1:-1]] < np.r_[0, 0, e[1:-1]]) & (np.r_[0, 0, c[:-2]] < np.r_[0, 0, e[:-2]]) & (h >= e) & (c < e)
    sig = np.where(up & win & warm, 1, np.where(dn & win & warm, -1, 0))

    def outcome(i, dr):
        en = i + 1
        if en > last[i]:
            return None
        px = o[en]
        row = {}
        for H in HORIZONS:
            x = min(en + H, last[i])
            row[f"h{H}"] = dr * (c[x] / px - 1) * 1e4 - cost
        x = None
        for j in range(en, min(en + 60, last[i]) + 1):
            if (dr == 1 and c[j] < e[j]) or (dr == -1 and c[j] > e[j]):
                x = o[j + 1] if j + 1 <= last[i] else c[j]
                break
        if x is None:
            x = c[min(en + 60, last[i])]
        row["stop"] = dr * (x / px - 1) * 1e4 - cost
        return row

    out, busy_until = [], -1
    for i in np.nonzero(sig)[0]:
        if i <= busy_until:
            continue
        r = outcome(i, sig[i])
        if r is None:
            continue
        out.append({"sym": sym, "day": day[i], "dir": int(sig[i]), "kind": "touch", **r})
        busy_until = min(i + 1 + 60, last[i])
    far = np.nonzero(win & warm & (np.abs(c / e - 1) > FAR))[0][::30]
    for i in far:
        r = outcome(i, 1 if c[i] > e[i] else -1)
        if r is not None:
            out.append({"sym": sym, "day": day[i], "dir": 1 if c[i] > e[i] else -1, "kind": "far", **r})
    return out


def stats(x):
    x = pd.Series(x).dropna()
    if len(x) < 2:
        return {"n": len(x)}
    se = x.std(ddof=1) / math.sqrt(len(x))
    return {"n": len(x), "avg": round(x.mean(), 2), "low95": round(x.mean() - Z95 * se, 2), "win": round(100 * (x > 0).mean(), 1)}


def cell(s):
    return f"{s['avg']} ({s['low95']}) {s['win']}%" if s.get("n", 0) >= 2 else "-"


def main():
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        raise SystemExit("POLYGON_API_KEY is missing")
    rows = []
    for sym in SYMBOLS:
        bt.SYMBOL, bt.YEARS = sym, 5
        b = bt.rth_only(bt.fetch_bars(1, key))
        rows += trades(b, sym)
        print(sym, len(rows), flush=True)
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "trades.csv.gz", index=False, compression="gzip")
    cut = date.today() - timedelta(days=365)
    touch, far = t[t["kind"] == "touch"].sort_values("day"), t[t["kind"] == "far"]
    dev, hold = touch[touch["day"] < cut].reset_index(drop=True), touch[touch["day"] >= cut]
    fdev, fhold = far[far["day"] < cut], far[far["day"] >= cut]
    half = len(dev) // 2
    cols = [f"h{H}" for H in HORIZONS] + ["stop"]
    lines = ["# EMA 200 on 1-minute bars", "", f"Run date: {date.today()}. Rules were fixed before the run. Holdout from {cut}.",
             "Cells: average bps per trade after cost, (low 95%), win rate.", "",
             "## Pooled", "", "| Group | Trades | 15 min | 30 min | 60 min | Stop at EMA |", "|---|---|---|---|---|---|"]
    groups = {"Touch, development": dev, "Touch, dev first half": dev.iloc[:half], "Touch, dev second half": dev.iloc[half:],
              "Touch, calls (dev)": dev[dev["dir"] == 1], "Touch, puts (dev)": dev[dev["dir"] == -1],
              "Touch, holdout": hold, "Far control, development": fdev, "Far control, holdout": fhold}
    res = {}
    for k, g in groups.items():
        res[k] = {cc: stats(g[cc]) for cc in cols}
        lines.append(f"| {k} | {len(g)} | " + " | ".join(cell(res[k][cc]) for cc in cols) + " |")
    lines += ["", "## By symbol (30 minutes)", "", "| Symbol | Touch dev | Touch holdout | Far dev | Far holdout |", "|---|---|---|---|---|"]
    for sym in SYMBOLS:
        f = lambda df: stats(df[df["sym"] == sym]["h30"])  # noqa: E731
        lines.append(f"| {sym} | {cell(f(dev))} | {cell(f(hold))} | {cell(f(fdev))} | {cell(f(fhold))} |")
    a = lambda k: res[k]["h30"].get("avg", -99)  # noqa: E731
    ok = bool(res["Touch, development"]["h30"].get("low95", -1) > 0 and a("Touch, dev first half") > 0
              and a("Touch, dev second half") > 0 and a("Touch, holdout") > 0
              and a("Touch, development") > a("Far control, development") and a("Touch, holdout") > a("Far control, holdout"))
    lines += ["", f"Verdict: {'PASS' if ok else 'FAIL'}.", ""]
    (OUT / "results.md").write_text("\n".join(lines))
    (OUT / "results.json").write_text(json.dumps({"groups": res, "passed": ok}, indent=2, default=str))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
