"""QQQ leadership rule: "if QQQ is up more than SPY, don't buy puts; if QQQ is
down more than SPY, don't buy calls."

Rules were fixed before the run.
Data: SPY and QQQ 5-minute regular-session bars, five years.
Checkpoints: bar closes at 10:05, 11:05, 12:05, 13:05, 14:05, 15:05 New York.
At each checkpoint, returns since the day's open: rS for SPY, rQ for QQQ.
- Rule (loose): favored direction = sign(rQ - rS).
- Rule (strict, as written): both up and QQQ up more -> calls favored;
  both down and QQQ down more -> puts favored; otherwise no view.
- Baseline: SPY's own move since open, sign(rS).
Outcome: SPY return over the next 30 minutes and to 15:55, signed by the
favored direction, in basis points. Each day's checkpoints are averaged so
days are independent samples.
The key check is the "disagree" subset, where QQQ's lead points against SPY's
own move: that is the only place the rule adds information beyond SPY itself.
Pass: development low 95% > 0 at 30 minutes, both halves positive, holdout
positive, and the disagree subset positive in development and holdout.
Holdout: the last 12 months.
Part B applies the rule as a filter to the SPY 0DTE opening-range trades.
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

CHECKS = (605, 665, 725, 785, 845, 905)
FWD_BARS = 6
LAST_BAR = 950
Z95 = 1.96


def bars(sym, key):
    bt.SYMBOL, bt.YEARS = sym, 5
    b = bt.rth_only(bt.fetch_bars(5, key))
    return b[["dt", "day", "mins", "open", "close"]]


def panel(key):
    s, q = bars("SPY", key), bars("QQQ", key)
    m = s.merge(q, on=["dt", "day", "mins"], suffixes=("_s", "_q"))
    first = m.groupby("day")[["open_s", "open_q"]].transform("first")
    m["rS"] = m["close_s"] / first["open_s"] - 1
    m["rQ"] = m["close_q"] / first["open_q"] - 1
    return m


def observations(m):
    rows = []
    for day, d in m.groupby("day", sort=True):
        d = d.set_index("mins")
        if LAST_BAR not in d.index:
            continue
        end = d.at[LAST_BAR, "close_s"]
        for c in CHECKS:
            # the bar starting at c-5 closes at c
            k = c - 5
            f = k + 5 * FWD_BARS
            if k not in d.index or f not in d.index:
                continue
            rS, rQ, px = d.at[k, "rS"], d.at[k, "rQ"], d.at[k, "close_s"]
            loose = np.sign(rQ - rS)
            if rS > 0 and rQ > rS:
                strict = 1
            elif rS < 0 and rQ < rS:
                strict = -1
            else:
                strict = 0
            rows.append({"day": day, "check": c, "rS": rS, "rQ": rQ, "lead": rQ - rS,
                         "loose": loose, "strict": strict, "base": np.sign(rS),
                         "f30": 1e4 * (d.at[f, "close_s"] / px - 1), "feod": 1e4 * (end / px - 1)})
    return pd.DataFrame(rows)


def day_stats(o, sign_col, fwd, mask=None):
    o = o if mask is None else o[mask]
    o = o[o[sign_col] != 0]
    if o.empty:
        return {"days": 0}
    per_day = (o[sign_col] * o[fwd]).groupby(o["day"]).mean()
    n = len(per_day)
    mu, sd = per_day.mean(), per_day.std(ddof=1) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n > 1 else float("nan")
    hit = float(((o[sign_col] * o[fwd]) > 0).mean())
    return {"days": n, "obs": len(o), "avg_bps": round(mu, 2), "low95": round(mu - Z95 * se, 2),
            "high95": round(mu + Z95 * se, 2), "hit": round(100 * hit, 1)}


def row(name, s):
    if not s.get("days"):
        return f"| {name} | 0 | - | - | - | - |"
    return f"| {name} | {s['days']} | {s['obs']} | {s['avg_bps']} | {s['low95']} | {s['hit']}% |"


HEAD = "| Group | Days | Checks | Avg bps | Low 95% | Right direction |\n|---|---|---|---|---|---|"


def part_a(o, cut):
    dev, hold = o[o["day"] < cut], o[o["day"] >= cut]
    days = sorted(dev["day"].unique())
    mid = days[len(days) // 2]
    lines, res = [], {}
    for fwd, label in (("f30", "next 30 minutes"), ("feod", "to 15:55")):
        lines += [f"### SPY {label}", "", HEAD]
        groups = {
            "Loose rule, development": (dev, "loose", None),
            "Loose rule, dev first half": (dev, "loose", dev["day"] < mid),
            "Loose rule, dev second half": (dev, "loose", dev["day"] >= mid),
            "Loose rule, holdout": (hold, "loose", None),
            "Strict rule, development": (dev, "strict", None),
            "Strict rule, holdout": (hold, "strict", None),
            "SPY own move, development": (dev, "base", None),
            "SPY own move, holdout": (hold, "base", None),
            "Disagree subset, development": (dev, "loose", dev["loose"] != dev["base"]),
            "Disagree subset, holdout": (hold, "loose", hold["loose"] != hold["base"]),
            "Lead >= 0.10%, development": (dev, "loose", dev["lead"].abs() >= 0.001),
            "Lead >= 0.10%, holdout": (hold, "loose", hold["lead"].abs() >= 0.001),
        }
        for name, (df, col, mask) in groups.items():
            s = day_stats(df, col, fwd, mask)
            res[f"{fwd}:{name}"] = s
            lines.append(row(name, s))
        years = []
        for y in sorted({d.year for d in dev["day"]}):
            s = day_stats(dev, "loose", fwd, dev["day"].map(lambda d: d.year) == y)
            years.append(row(f"Loose rule, {y}", s))
        lines += years + [""]
    lines += ["### Control for SPY's own move", "",
              "Regression of SPY's next 30 minutes on QQQ's lead and on SPY's own move since open,",
              "with errors grouped by day. A real QQQ effect needs a positive lead coefficient.", "",
              "| Sample | Lead coef (bps per 1% lead) | t | SPY move coef | t |", "|---|---|---|---|---|"]
    for name, df in (("Development", dev), ("Holdout", hold)):
        b, t = ols_cluster(df)
        res[f"reg:{name}"] = {"lead": round(b[1], 2), "lead_t": round(t[1], 2), "rs": round(b[2], 2), "rs_t": round(t[2], 2)}
        lines.append(f"| {name} | {b[1]:.2f} | {t[1]:.2f} | {b[2]:.2f} | {t[2]:.2f} |")
    lines.append("")
    g = lambda k: res[k].get("avg_bps", -1) or -1  # noqa: E731
    ok = bool(res["f30:Loose rule, development"].get("low95", -1) > 0
              and g("f30:Loose rule, dev first half") > 0 and g("f30:Loose rule, dev second half") > 0
              and g("f30:Loose rule, holdout") > 0
              and res["reg:Development"]["lead_t"] > 1.96 and res["reg:Holdout"]["lead"] > 0)
    lines += [f"Verdict for the rule as a direction signal: {'PASS' if ok else 'FAIL'}.", ""]
    return lines, res, ok


def ols_cluster(df):
    x = np.column_stack([np.ones(len(df)), 100 * df["lead"].to_numpy(), 100 * df["rS"].to_numpy()])
    y = df["f30"].to_numpy()
    xtx_inv = np.linalg.inv(x.T @ x)
    b = xtx_inv @ x.T @ y
    e = y - x @ b
    meat = np.zeros((3, 3))
    for _, idx in df.reset_index(drop=True).groupby("day").indices.items():
        s = x[idx].T @ e[idx]
        meat += np.outer(s, s)
    se = np.sqrt(np.diag(xtx_inv @ meat @ xtx_inv))
    return b, b / se


def part_b(m):
    t = pd.read_csv(OUT / "orb_trades.csv", parse_dates=["date"])
    t["day"] = t["date"].dt.date
    idx = m.set_index(["day", "mins"])
    lead = []
    for r in t.itertuples():
        k = (r.day, int(r.t) - 5)
        lead.append(idx.at[k, "rQ"] - idx.at[k, "rS"] if k in idx.index else np.nan)
    t["lead"] = lead
    t = t.dropna(subset=["lead"])
    t["agree"] = np.sign(t["lead"]) == t["dir"]
    lines = ["## Part B: filter on the SPY 0DTE opening-range trades", "",
             "| Group | Trades | Win | Avg profit | Total profit |", "|---|---|---|---|---|"]
    res = {}
    for name, g in (("All trades", t), ("Rule agrees", t[t["agree"]]), ("Rule says skip", t[~t["agree"]])):
        res[name] = {"n": len(g), "win": round(100 * (g["pnl"] > 0).mean(), 1) if len(g) else None,
                     "avg": round(g["pnl"].mean(), 1) if len(g) else None, "total": round(g["pnl"].sum())}
        lines.append(f"| {name} | {res[name]['n']} | {res[name]['win']}% | {res[name]['avg']}$ | {res[name]['total']}$ |")
    a, b = t[t["agree"]]["pnl"], t[~t["agree"]]["pnl"]
    if len(a) > 1 and len(b) > 1:
        diff = a.mean() - b.mean()
        se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
        lines.append(f"\nDifference in average profit (agree minus skip): {diff:.1f}$, 95% range "
                     f"{diff - Z95 * se:.1f}$ to {diff + Z95 * se:.1f}$.")
        res["diff"] = {"avg": round(diff, 1), "low95": round(diff - Z95 * se, 1), "high95": round(diff + Z95 * se, 1)}
    return lines + [""], res


def main():
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        raise SystemExit("POLYGON_API_KEY is missing")
    m = panel(key)
    o = observations(m)
    cut = date.today() - timedelta(days=365)
    lines = ["# QQQ leadership rule", "", f"Run date: {date.today()}. Rules were fixed before the run.",
             f"Data: {o['day'].min()} to {o['day'].max()}, {o['day'].nunique()} days. Holdout from {cut}.",
             "Returns are SPY basis points signed by the favored direction (1 bp = 0.01%).", "",
             "## Part A: does QQQ's lead predict SPY's next move?", ""]
    la, ra, ok = part_a(o, cut)
    lb, rb = part_b(m)
    lines += la + lb
    (OUT / "results.md").write_text("\n".join(lines))
    (OUT / "results.json").write_text(json.dumps({"part_a": ra, "pass": ok, "part_b": rb}, indent=2, default=str))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
