"""Moving-average crossovers on SPY and QQQ intraday.

Rules were fixed before the run.
Pairs (EMA): 9/21, 8/48, 20/50, 50/200. Timeframes: 1, 5, 15 minutes.
Averages run continuously across days on regular-session bars.
Entry: the bar after a fast/slow cross, from 09:45 to 15:00 New York, at its open,
in the cross direction. Exit: the open after the opposite cross, otherwise the
session's last close. Results in basis points less 1 bp per trade.
Pass: at least 150 development trades, development low 95% > 0, both halves
positive, holdout positive. Holdout: the last 12 months.
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

SYMBOLS = ("SPY", "QQQ")
TFS = (1, 5, 15)
PAIRS = ((9, 21), (8, 48), (20, 50), (50, 200))
COST = 1.0
Z95 = 1.96


def run(b, fast, slow):
    c, o = b["close"], b["open"].to_numpy()
    d = np.sign(c.ewm(span=fast, adjust=False).mean() - c.ewm(span=slow, adjust=False).mean()).to_numpy()
    mins, day, cl = b["mins"].to_numpy(), b["day"].to_numpy(), c.to_numpy()
    n, out, i = len(cl), [], slow * 2
    while i < n - 1:
        if d[i] != 0 and d[i] != d[i - 1] and 585 <= mins[i] <= 900 and day[i + 1] == day[i]:
            dr, e = d[i], i + 1
            px, j = o[e], e
            while True:
                if j + 1 >= n or day[j + 1] != day[j]:
                    x = cl[j]
                    break
                if d[j] == -dr:
                    x = o[j + 1]
                    j += 1
                    break
                j += 1
            out.append((day[e], dr * (x / px - 1) * 1e4 - COST, int(dr)))
            i = j
            continue
        i += 1
    return pd.DataFrame(out, columns=["day", "r", "dir"])


def st(t):
    if len(t) < 2:
        return {"n": len(t)}
    r = t["r"]
    se = r.std(ddof=1) / math.sqrt(len(r))
    return {"n": len(t), "avg": round(r.mean(), 2), "low95": round(r.mean() - Z95 * se, 2), "win": round(100 * (r > 0).mean(), 1)}


def main():
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        raise SystemExit("POLYGON_API_KEY is missing")
    cut = date.today() - timedelta(days=365)
    rows = []
    for sym in SYMBOLS:
        for tf in TFS:
            bt.SYMBOL, bt.YEARS = sym, 5
            b = bt.rth_only(bt.fetch_bars(tf, key))
            for f, s in PAIRS:
                t = run(b, f, s)
                dev, hold = t[t["day"] < cut].reset_index(drop=True), t[t["day"] >= cut]
                h = len(dev) // 2
                r = {"sym": sym, "tf": tf, "pair": f"{f}/{s}", "dev": st(dev), "h1": st(dev.iloc[:h]),
                     "h2": st(dev.iloc[h:]), "hold": st(hold)}
                r["pass"] = bool(r["dev"].get("n", 0) >= 150 and r["dev"].get("low95", -1) > 0 and r["h1"].get("avg", -1) > 0
                                 and r["h2"].get("avg", -1) > 0 and r["hold"].get("avg", -1) > 0)
                rows.append(r)
                print(sym, tf, f, s, r["dev"], r["hold"], flush=True)
    rows.sort(key=lambda r: r["dev"].get("low95", -99), reverse=True)
    lines = ["# EMA crossovers on SPY and QQQ", "", f"Run date: {date.today()}. Holdout from {cut}. Bps per trade after 1 bp cost.",
             f"Combinations: {len(rows)}. Passed: {sum(r['pass'] for r in rows)}.", "",
             "| Symbol | TF | Pair | Dev trades | Dev avg | Dev low95 | Dev win | Half 1 | Half 2 | Holdout trades | Holdout avg | Holdout win | Pass |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        d, ho = r["dev"], r["hold"]
        lines.append(f"| {r['sym']} | {r['tf']}m | {r['pair']} | {d.get('n')} | {d.get('avg')} | {d.get('low95')} | {d.get('win')}% | "
                     f"{r['h1'].get('avg')} | {r['h2'].get('avg')} | {ho.get('n')} | {ho.get('avg')} | {ho.get('win')}% | {'PASS' if r['pass'] else '-'} |")
    (OUT / "results.md").write_text("\n".join(lines))
    (OUT / "results.json").write_text(json.dumps(rows, indent=2, default=str))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
