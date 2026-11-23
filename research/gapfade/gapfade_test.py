"""Stage 1: is the "gap-up fade" real? Rules fixed before the run.

Event (unchanged from the drift test): open >= 5% above the previous close, volume >= 3 x the
previous 50-day average, close >= open; close >= 10 and 30-day average volume > 500,000.
Entry at the next day's open, scored SHORT (as for buying puts): short return = -(price change).

Checks:
1. Size, by 30-day average dollar volume (a proxy for option liquidity):
   small < $20M a day, mid $20M-$100M, large > $100M.
2. Robustness: median, and the mean after dropping the top and bottom 1% of returns.
3. Squeeze risk: within 20 days, how often the stock rises +15% from entry before falling -10%,
   and how often it falls -10% before rising +15%.
4. Timing: average short return after 1, 2, 3, 5, 10, 15 and 20 days.
5. Gap size groups: 5-10%, 10-20%, over 20%.
Pass for stage 1 (decides whether to test real puts): in the large group, the daily excess of the
20-day short return over the baseline (baseline = all eligible stock-days, also scored short)
has development low 95% > 0, both halves positive, and a positive holdout.
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
sys.path.insert(0, str(OUT.parent / "momentum_filter"))
import filter_test as ft  # noqa: E402

Z95 = 1.96
STEPS = (1, 2, 3, 5, 10, 15, 20)


def race(df, rows, up=0.15, dn=0.10, horizon=20):
    """1 = fell dn first (good for puts), 0 = rose up first (squeeze), nan = neither."""
    out = []
    groups = {s: g for s, g in df.groupby("sym", sort=False)}
    for _, r in rows.iterrows():
        g = groups[r["sym"]]
        i = g.index.get_loc(r.name)
        seg = g.iloc[i + 1:i + 1 + horizon]
        e = r["next_open"]
        res = np.nan
        for h, l in zip(seg["h"].to_numpy(), seg["l"].to_numpy()):
            if h >= e * (1 + up):
                res = 0.0
                break
            if l <= e * (1 - dn):
                res = 1.0
                break
        out.append(res)
    return out


def st(x):
    x = pd.Series(x).dropna()
    se = x.std(ddof=1) / math.sqrt(len(x)) if len(x) > 1 else float("nan")
    return {"n": len(x), "avg": round(float(x.mean()), 2), "low95": round(float(x.mean() - Z95 * se), 2)}


def main():
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        raise SystemExit("POLYGON_API_KEY is missing")
    df = ft.features(ft.grouped(key))
    g = df.groupby("sym", sort=False)
    df["pc"] = g["c"].shift(1)
    df["av50p"] = g["v"].transform(lambda x: x.shift(1).rolling(50).mean())
    for k in STEPS:
        if f"c{k}" not in df:
            df[f"c{k}"] = g["c"].shift(-k)
    df = df[df["n"] >= 60]
    base = df[(df["c"] >= 10) & (df["avgv30"] > 5e5) & df["c20"].notna() & (df["next_open"] > 0)].copy()
    for k in STEPS:
        base[f"s{k}"] = -(base[f"c{k}"] / base["next_open"] - 1) * 100
    base["dv"] = base["avgv30"] * base["c"]
    base["tier"] = np.where(base["dv"] > 1e8, "large", np.where(base["dv"] > 2e7, "mid", "small"))
    gap = base["o"] / base["pc"] - 1
    ev = base[(gap >= 0.05) & (base["v"] >= 3 * base["av50p"]) & (base["c"] >= base["o"])].copy()
    ev["gap"] = gap[ev.index] * 100
    ev["gapgrp"] = pd.cut(ev["gap"], [5, 10, 20, 1e9], labels=["5-10%", "10-20%", ">20%"], include_lowest=True)
    ev["fall_first"] = race(df, ev)
    cut = pd.Timestamp(date.today() - timedelta(days=365))
    bm = base.groupby("date")["s20"].mean()

    lines = ["# Gap-up fade, stage 1", "", f"Run date: {date.today()}. Rules fixed before the run. Holdout from {cut.date()}.",
             f"Events: {len(ev)}. Short returns (positive = the stock fell).", "",
             "| Group | Events | Avg 20d short | Median | Trimmed avg | Fell -10% first | Rose +15% first | Neither |",
             "|---|---|---|---|---|---|---|---|"]

    def desc(name, x):
        s = x["s20"]
        lo, hi = s.quantile(0.01), s.quantile(0.99)
        t = s[(s >= lo) & (s <= hi)]
        f = x["fall_first"]
        return (f"| {name} | {len(x)} | {s.mean():.2f}% | {s.median():.2f}% | {t.mean():.2f}% | {100 * (f == 1).mean():.0f}% | "
                f"{100 * (f == 0).mean():.0f}% | {100 * f.isna().mean():.0f}% |")

    for part, x in (("development", ev[ev["date"] < cut]), ("holdout", ev[ev["date"] >= cut])):
        lines.append(desc(f"All, {part}", x))
        for tier in ("small", "mid", "large"):
            lines.append(desc(f"{tier}, {part}", x[x["tier"] == tier]))
        for gg in ("5-10%", "10-20%", ">20%"):
            lines.append(desc(f"gap {gg}, {part}", x[x["gapgrp"] == gg]))
    lines += ["", "## Timing: average short return after N days (all events)", "",
              "| Part | " + " | ".join(f"{k}d" for k in STEPS) + " |", "|---|" + "---|" * len(STEPS)]
    for part, x in (("development", ev[ev["date"] < cut]), ("holdout", ev[ev["date"] >= cut])):
        lines.append(f"| {part} | " + " | ".join(f"{x[f's{k}'].mean():.2f}%" for k in STEPS) + " |")
    for tier in ("large", "mid"):
        x = ev[(ev["tier"] == tier)]
        lines.append(f"| {tier}, all years | " + " | ".join(f"{x[f's{k}'].mean():.2f}%" for k in STEPS) + " |")

    lines += ["", "## Daily excess of the 20-day short return over the baseline", "",
              "| Group | Dev days | Dev avg | Low 95% | Half 1 | Half 2 | Holdout | Verdict |", "|---|---|---|---|---|---|---|---|"]
    summary = {}
    for name, x in (("All", ev), ("small", ev[ev["tier"] == "small"]), ("mid", ev[ev["tier"] == "mid"]), ("large", ev[ev["tier"] == "large"])):
        ex = (x.groupby("date")["s20"].mean() - bm).dropna()
        d, h = ex[ex.index < cut], ex[ex.index >= cut]
        hf = len(d) // 2
        sd = st(d)
        h1, h2, hh = d.iloc[:hf].mean(), d.iloc[hf:].mean(), h.mean()
        ok = bool(sd["low95"] > 0 and h1 > 0 and h2 > 0 and hh > 0)
        lines.append(f"| {name} | {sd['n']} | {sd['avg']}% | {sd['low95']}% | {h1:.2f}% | {h2:.2f}% | {hh:.2f}% | {'PASS' if ok else 'FAIL'} |")
        yrs = d.groupby(d.index.year).mean().round(2).to_dict()
        lines.append(f"|  | by year: {yrs} | | | | | | |")
        summary[name] = {"passed": ok, "dev": sd, "half1": h1, "half2": h2, "holdout": hh}
    big = ev[ev["tier"] == "large"].sort_values("s20")
    lines += ["", "Large group, worst squeezes (20-day short return): " +
              ", ".join(f"{r.sym} {r.date.date()} {r.s20:.0f}%" for r in big.head(8).itertuples()), ""]
    ev[["sym", "date", "gap", "tier", "c", "next_open"] + [f"s{k}" for k in STEPS] + ["fall_first"]].to_csv(OUT / "events.csv", index=False)
    (OUT / "results.md").write_text("\n".join(lines))
    (OUT / "results.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
