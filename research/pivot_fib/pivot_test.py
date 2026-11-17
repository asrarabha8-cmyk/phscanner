"""Fibonacci pivot points on SPY, as shown in the video.

Rules were fixed before the run.
Levels from the previous regular session: P = (H + L + C) / 3, range = H - L,
R1/R2/R3 = P + 0.382/0.618/1.0 x range, S1/S2/S3 = P - the same.
Strategy A (open side): the first 5-minute bar (09:30-09:35) closes above P -> long,
below -> short. Entry at the next bar's open.
Strategy B (rejection): from 09:35 to 14:00, the first bar whose high touches P from
below and closes below it -> short; low touches P from above and closes above -> long.
Entry at the next bar's open. One trade per day.
Entries already past the target, or on the wrong side of P, are skipped.
Exits for both: target R1 (long) or S1 (short) touched inside a bar (filled at the level),
stop when a bar closes back across P (exit at the next open), otherwise the last close.
Results in SPY basis points less 1 bp.
Pass: development low 95% > 0, both halves positive, holdout positive.
Holdout: the last 12 months.
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

FIB = (0.382, 0.618, 1.0)
COST = 1.0
Z95 = 1.96


def levels(b):
    d = b.groupby("day").agg(H=("high", "max"), L=("low", "min"), C=("close", "last")).shift(1).dropna()
    d["P"] = (d["H"] + d["L"] + d["C"]) / 3
    rng = d["H"] - d["L"]
    for i, f in enumerate(FIB, 1):
        d[f"R{i}"] = d["P"] + f * rng
        d[f"S{i}"] = d["P"] - f * rng
    return d


def run_trade(g, e, dr, lv, flip=False):
    if flip:
        dr = -dr
    tgt = lv["R1"] if dr == 1 else lv["S1"]
    P = lv["P"]
    px = g.open[e]
    if (dr == 1 and px >= tgt) or (dr == -1 and px <= tgt) or (dr == 1 and px <= P) or (dr == -1 and px >= P):
        return None, "skip"
    for j in range(e, len(g)):
        if (dr == 1 and g.high[j] >= tgt) or (dr == -1 and g.low[j] <= tgt):
            out = max(tgt, g.open[j]) if dr == 1 else min(tgt, g.open[j])
            return dr * (out / px - 1) * 1e4 - COST, "target"
        if (dr == 1 and g.close[j] < P) or (dr == -1 and g.close[j] > P):
            out = g.open[j + 1] if j + 1 < len(g) else g.close[j]
            return dr * (out / px - 1) * 1e4 - COST, "stop"
    return dr * (g.close.iloc[-1] / px - 1) * 1e4 - COST, "close"


def entries(b, lv):
    a, r = [], []
    for day, g in b.groupby("day", sort=True):
        if day not in lv.index or len(g) < 10:
            continue
        g = g.reset_index(drop=True)
        L = lv.loc[day]
        P = L["P"]
        dr = 1 if g.close[0] > P else -1 if g.close[0] < P else 0
        if dr:
            a.append((day, g, 1, dr, L))
        for i in range(1, len(g) - 1):
            if g.mins[i] > 840:
                break
            if g.high[i] >= P and g.close[i] < P and g.open[i] < P:
                r.append((day, g, i + 1, -1, L))
                break
            if g.low[i] <= P and g.close[i] > P and g.open[i] > P:
                r.append((day, g, i + 1, 1, L))
                break
    return {"A open side": a, "B rejection": r}


def evaluate(ents, cut, rng, flips=None):
    rows = []
    for k, (day, g, e, dr, L) in enumerate(ents):
        f = bool(flips[k]) if flips is not None else False
        r, why = run_trade(g, e, dr, L, flip=f)
        if r is None:
            continue
        rows.append({"day": day, "dir": dr * (-1 if f else 1), "r": r, "why": why})
    return pd.DataFrame(rows)


def stats(t):
    if len(t) < 2:
        return {"n": len(t)}
    r = t["r"]
    se = r.std(ddof=1) / math.sqrt(len(r))
    return {"n": len(t), "avg": round(r.mean(), 2), "low95": round(r.mean() - Z95 * se, 2),
            "win": round(100 * (r > 0).mean(), 1), "total": round(r.sum())}


def row(name, s):
    if s.get("n", 0) < 2:
        return f"| {name} | {s.get('n', 0)} | - | - | - | - |"
    return f"| {name} | {s['n']} | {s['avg']} | {s['low95']} | {s['win']}% | {s['total']} |"


HEAD = "| Group | Trades | Avg bps | Low 95% | Win | Total bps |\n|---|---|---|---|---|---|"


def reach_table(b, lv):
    hit = {k: [0, 0] for k in ("R1", "R2", "R3", "S1", "S2", "S3")}
    for day, g in b.groupby("day"):
        if day not in lv.index:
            continue
        L = lv.loc[day]
        above = g["close"].iloc[0] > L["P"]
        side = ("R1", "R2", "R3") if above else ("S1", "S2", "S3")
        for k in side:
            hit[k][1] += 1
            if (above and g["high"].max() >= L[k]) or (not above and g["low"].min() <= L[k]):
                hit[k][0] += 1
    return {k: round(100 * v[0] / v[1], 1) if v[1] else None for k, v in hit.items()}


def main():
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        raise SystemExit("POLYGON_API_KEY is missing")
    bt.SYMBOL, bt.YEARS = "SPY", 5
    b = bt.rth_only(bt.fetch_bars(5, key))
    lv = levels(b)
    cut = date.today() - timedelta(days=365)
    rng = np.random.default_rng(11)
    lines = ["# Fibonacci pivot points on SPY", "", f"Run date: {date.today()}. Rules were fixed before the run.",
             f"Data: {b['day'].min()} to {b['day'].max()}. Holdout from {cut}. Results in SPY bps after 1 bp cost.", ""]
    summary = {}
    for name, ents in entries(b, lv).items():
        t = evaluate(ents, cut, rng)
        dev, hold = t[t["day"] < cut].reset_index(drop=True), t[t["day"] >= cut]
        half = len(dev) // 2
        groups = {"Development": dev, "Dev first half": dev.iloc[:half], "Dev second half": dev.iloc[half:],
                  "Dev long": dev[dev["dir"] == 1], "Dev short": dev[dev["dir"] == -1], "Holdout": hold}
        res = {k: stats(v) for k, v in groups.items()}
        ok = bool(res["Development"].get("low95", -1) > 0 and res["Dev first half"].get("avg", -1) > 0
                  and res["Dev second half"].get("avg", -1) > 0 and res["Holdout"].get("avg", -1) > 0
                  )
        lines += [f"## {name}", "", HEAD] + [row(k, v) for k, v in res.items()]
        lines += ["",
                  f"Exit reasons: {t['why'].value_counts().to_dict()}.", f"Verdict: {'PASS' if ok else 'FAIL'}.", ""]
        summary[name] = {"groups": res, "passed": ok}
    reach = reach_table(b, lv)
    lines += ["## How often price reaches each level on the side of the first bar", "",
              "| Level | Days reached |", "|---|---|"] + [f"| {k} | {v}% |" for k, v in reach.items()] + [""]
    summary["reach"] = reach
    (OUT / "results.md").write_text("\n".join(lines))
    (OUT / "results.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
