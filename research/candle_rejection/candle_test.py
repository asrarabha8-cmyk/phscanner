"""Rejection-candle backtest on SPY.

Ports the base signal and the hammer condition of RevLab_v3.pine with fixed
defaults. Positions close by the session end. Pass criteria were set before
this test ran: low 95% above zero, both halves positive, and no single year
making up half or more of total R.
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
from backtest import HEADER, fetch_bars, rma_atr, row_md, rth_only, stats  # noqa: E402

TIMEFRAMES = (3, 5)
COSTS = (0.02, 0.05, 0.10)
MAIN_COST = 0.05
EXT_LEN = 24
COOLDOWN = 6
WICK_MIN = 0.35
CANDLE_M = 1.3
HORIZON_MIN = 60
RR = 1.5
STOP_PAD = 0.25


def simulate(df, tf, cost):
    o, h, l, c = (df[x].to_numpy() for x in ("open", "high", "low", "close"))
    atr = rma_atr(df["high"], df["low"], df["close"]).to_numpy()
    ext_hi = df["high"].rolling(EXT_LEN).max().to_numpy()
    ext_lo = df["low"].rolling(EXT_LEN).min().to_numpy()
    days = df["day"].to_numpy()
    mins = df["mins"].to_numpy()
    times = df["dt"].to_numpy()
    horizon = max(1, round(HORIZON_MIN / tf))
    trades, open_trades = [], []
    last_sig = -100000

    for i in range(len(df)):
        end_of_day = i == len(df) - 1 or days[i + 1] != days[i]
        still_open = []
        for t in open_trades:
            hit_stop = l[i] <= t["stop"] if t["dir"] == 1 else h[i] >= t["stop"]
            hit_tgt = h[i] >= t["target"] if t["dir"] == 1 else l[i] <= t["target"]
            if hit_stop or hit_tgt or i >= t["expiry"] or end_of_day:
                pnl = -t["risk"] if hit_stop else RR * t["risk"] if hit_tgt else t["dir"] * (c[i] - t["entry"])
                trades.append({"entry_time": t["time"], "side": "bottom" if t["dir"] == 1 else "top",
                               "hammer": t["hammer"], "first_hour": t["hot"],
                               "win": bool(hit_tgt and not hit_stop), "r": (pnl - cost) / t["risk"]})
            else:
                still_open.append(t)
        open_trades = still_open

        if np.isnan(ext_hi[i]) or np.isnan(atr[i]):
            continue
        mid = (h[i] + l[i]) / 2
        top = h[i] >= ext_hi[i] and c[i] < mid
        bot = l[i] <= ext_lo[i] and c[i] > mid
        if top == bot or i - last_sig < COOLDOWN:
            continue
        last_sig = i
        if end_of_day:
            continue
        rng = max(h[i] - l[i], 0.01)
        wick = (h[i] - max(o[i], c[i])) / rng if top else (min(o[i], c[i]) - l[i]) / rng
        prev_atr = atr[i - 1] if i > 0 and not np.isnan(atr[i - 1]) else atr[i]
        hammer = bool(h[i] - l[i] >= CANDLE_M * prev_atr and wick >= WICK_MIN)
        direction = 1 if bot else -1
        stop = l[i] - STOP_PAD * atr[i] if bot else h[i] + STOP_PAD * atr[i]
        risk = max(abs(c[i] - stop), 0.01)
        open_trades.append({"dir": direction, "entry": c[i], "stop": stop, "risk": risk,
                            "target": c[i] + direction * RR * risk, "expiry": i + horizon,
                            "hammer": hammer, "hot": bool(mins[i] < 630), "time": times[i]})
    return pd.DataFrame(trades)


def verdict(t):
    s = stats(t["r"])
    half = len(t) // 2
    a, b = t["r"].iloc[:half], t["r"].iloc[half:]
    years = t.groupby("year")["r"].sum()
    total = float(t["r"].sum())
    checks = {
        "low95_above_zero": s["low95"] > 0,
        "first_half_positive": float(a.mean()) > 0,
        "second_half_positive": float(b.mean()) > 0,
        "no_single_year_dominates": total > 0 and float(years.max()) < 0.5 * total,
    }
    checks["passed"] = all(checks.values())
    return checks


def main():
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        raise SystemExit("POLYGON_API_KEY is missing")
    results = {}
    lines = ["# Rejection-candle backtest on SPY", "",
             f"Run date: {date.today()}. Rules and pass criteria were fixed before the run.", ""]
    for tf in TIMEFRAMES:
        bars = rth_only(fetch_bars(tf, key))
        lines += [f"## {tf} minutes", "",
                  f"Data: {bars['day'].min()} to {bars['day'].max()}, {bars['day'].nunique()} days.", ""]
        t = simulate(bars, tf, MAIN_COST)
        t["year"] = pd.to_datetime(t["entry_time"], utc=True).dt.tz_convert("America/New_York").dt.year
        ham = t[t["hammer"]].reset_index(drop=True)
        half = len(ham) // 2
        groups = {"All base signals": t, "Hammer": ham, "No hammer": t[~t["hammer"]],
                  "Hammer tops": ham[ham["side"] == "top"], "Hammer bottoms": ham[ham["side"] == "bottom"],
                  "Hammer first hour": ham[ham["first_hour"]], "Hammer rest of day": ham[~ham["first_hour"]],
                  "Hammer first half": ham.iloc[:half], "Hammer second half": ham.iloc[half:]}
        for y, g in ham.groupby("year"):
            groups[f"Hammer {y}"] = g
        res = {k: stats(g["r"]) for k, g in groups.items()}
        check = verdict(ham)
        lines += [HEADER] + [row_md(k, v) for k, v in res.items()]
        lines += ["", f"Verdict: {'PASS' if check['passed'] else 'FAIL'} {check}", "",
                  "### Hammer cost sensitivity", "", HEADER]
        for cost in COSTS:
            x = simulate(bars, tf, cost)
            lines.append(row_md(f"Cost ${cost:.2f}", stats(x[x["hammer"]]["r"])))
        lines.append("")
        ham.to_csv(OUT / f"trades_{tf}m.csv", index=False)
        results[f"{tf}m"] = {"groups": res, "verdict": check}
    (OUT / "results.json").write_text(json.dumps(results, indent=2, default=str))
    (OUT / "results.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
