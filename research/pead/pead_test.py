"""Post-earnings drift ("الانجراف بعد الأرباح") on all US stocks.

Rules fixed before the run (daily bars, all US tickers including delisted, Polygon grouped data):
- Event gap up: open >= 5% above the previous close, volume >= 3 x the previous 50-day average,
  and the day closes at or above its open (the gap held).
- Event gap down: the mirror (open <= -5%, volume >= 3x, close at or below the open).
- Earnings label: if Polygon's Benzinga earnings calendar is available, a gap is an earnings gap
  when the company reported on the gap day or the day before. If it is not available, all
  strong gaps are tested and labelled "all gaps".
- Entry at the next day's open. Returns after 5, 20 and 60 trading days. Gap downs are scored
  short (the sign is flipped), as for buying puts.
- Baseline: every stock-day with close >= 10 and 30-day average volume > 500,000.
- Main test: daily excess of the 20-day return over the baseline (signal-day averages),
  development low 95% > 0, both halves positive, holdout positive. Also the race
  "+20% before -10%" (for gap downs: -20% before +10%).
Holdout: the last 12 months.
"""
import json
import math
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

OUT = Path(__file__).parent
sys.path.insert(0, str(OUT.parent / "momentum_filter"))
import filter_test as ft  # noqa: E402

Z95 = 1.96


def earnings(key):
    s = requests.Session()
    start = date.today() - timedelta(days=int(ft.YEARS * 365.25))
    url = f"{ft.BASE}/benzinga/v1/earnings"
    params = {"date.gte": str(start), "limit": 50000, "sort": "date.asc", "apiKey": key}
    rows = []
    for _ in range(200):
        r = s.get(url, params=params, timeout=60)
        if r.status_code != 200:
            print(f"earnings calendar status {r.status_code}: {r.text[:200]}")
            return None
        j = r.json()
        rows += j.get("results") or []
        nxt = j.get("next_url")
        if not nxt:
            break
        url, params = nxt, {"apiKey": key}
        time.sleep(0.2)
    if not rows:
        return None
    e = pd.DataFrame(rows)
    print(f"earnings rows {len(e)}; columns {list(e.columns)[:12]}")
    return pd.DataFrame({"sym": e["ticker"], "date": pd.to_datetime(e["date"])}).dropna().drop_duplicates()


def first_touch_short(df, rows, dn=0.20, up=0.10, horizon=60):
    out = []
    groups = {s: g for s, g in df.groupby("sym", sort=False)}
    for _, r in rows.iterrows():
        g = groups[r["sym"]]
        i = g.index.get_loc(r.name)
        seg = g.iloc[i + 1:i + 1 + horizon]
        e = r["next_open"]
        if len(seg) < horizon or not e or np.isnan(e):
            out.append(np.nan)
            continue
        res = np.nan
        for h, l in zip(seg["h"].to_numpy(), seg["l"].to_numpy()):
            hit_win, hit_loss = l <= e * (1 - dn), h >= e * (1 + up)
            if hit_loss:
                res = 0.0
                break
            if hit_win:
                res = 1.0
                break
        out.append(res)
    return out


def st(x):
    se = x.std(ddof=1) / math.sqrt(len(x)) if len(x) > 1 else float("nan")
    return {"days": len(x), "avg": round(float(x.mean()), 2), "low95": round(float(x.mean() - Z95 * se), 2),
            "pos": round(100 * float((x > 0).mean()), 1)}


def main():
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        raise SystemExit("POLYGON_API_KEY is missing")
    df = ft.features(ft.grouped(key))
    g = df.groupby("sym", sort=False)
    df["pc"] = g["c"].shift(1)
    df["av50p"] = g["v"].transform(lambda x: x.shift(1).rolling(50).mean())
    df = df[df["n"] >= 60]
    for hz in (5, 20, 60):
        df[f"r{hz}"] = (df[f"c{hz}"] / df["next_open"] - 1) * 100
    base = df[(df["c"] >= 10) & (df["avgv30"] > 5e5) & df["r60"].notna() & (df["next_open"] > 0)].copy()
    gap = base["o"] / base["pc"] - 1
    big = base["v"] >= 3 * base["av50p"]
    up = base[(gap >= 0.05) & big & (base["c"] >= base["o"])].copy()
    dn = base[(gap <= -0.05) & big & (base["c"] <= base["o"])].copy()
    e = earnings(key)
    label = "all gaps"
    if e is not None:
        ed = set(zip(e["sym"], e["date"])) | set(zip(e["sym"], e["date"] + pd.offsets.BDay(1)))
        up["earn"] = [(s, d) in ed for s, d in zip(up["sym"], up["date"])]
        dn["earn"] = [(s, d) in ed for s, d in zip(dn["sym"], dn["date"])]
        label = "earnings gaps"
    else:
        up["earn"] = True
        dn["earn"] = True
    up["win"] = ft.first_touch(df, up, up=0.20, dn=0.10)
    dn["win"] = first_touch_short(df, dn)
    for k in ("r5", "r20", "r60"):
        dn[k] = -dn[k]
    cut = pd.Timestamp(date.today() - timedelta(days=365))
    bm = base.groupby("date")["r20"].mean()
    lines = ["# Post-earnings drift", "", f"Run date: {date.today()}. Rules fixed before the run. Holdout from {cut.date()}.",
             f"Earnings calendar: {'available' if e is not None else 'NOT available - testing all strong gaps'}.",
             f"Baseline 20-day return: development {base[base['date'] < cut]['r20'].mean():.2f}%, holdout {base[base['date'] >= cut]['r20'].mean():.2f}%.", ""]
    summary = {}
    groups = [("Gap up, " + label, up[up["earn"]], 1), ("Gap down (short), " + label, dn[dn["earn"]], -1)]
    if e is not None:
        groups += [("Gap up, not earnings", up[~up["earn"]], 1), ("Gap down (short), not earnings", dn[~dn["earn"]], -1)]
    lines += ["| Group | Part | Events | Avg 5d | Avg 20d | Avg 60d | Median 20d | Race won |", "|---|---|---|---|---|---|---|---|"]
    exl = ["", "## 20-day excess over the baseline (signal-day averages; shorts use minus the baseline)", "",
           "| Group | Dev days | Dev avg | Low 95% | Half 1 | Half 2 | Holdout avg | Verdict |", "|---|---|---|---|---|---|---|---|"]
    for name, x, sign in groups:
        for part, y in (("development", x[x["date"] < cut]), ("holdout", x[x["date"] >= cut])):
            lines.append(f"| {name} | {part} | {len(y)} | {y['r5'].mean():.2f}% | {y['r20'].mean():.2f}% | {y['r60'].mean():.2f}% | "
                         f"{y['r20'].median():.2f}% | {100 * np.nanmean(y['win']):.1f}% |")
        ex = (x.groupby("date")["r20"].mean() - sign * bm).dropna()
        d, h = ex[ex.index < cut], ex[ex.index >= cut]
        hf = len(d) // 2
        sd = st(d)
        h1, h2, hh = d.iloc[:hf].mean(), d.iloc[hf:].mean(), h.mean()
        ok = bool(sd["low95"] > 0 and h1 > 0 and h2 > 0 and hh > 0)
        exl.append(f"| {name} | {sd['days']} | {sd['avg']}% | {sd['low95']}% | {h1:.2f}% | {h2:.2f}% | {hh:.2f}% | {'PASS' if ok else 'FAIL'} |")
        yrs = d.groupby(d.index.year).mean().round(2).to_dict()
        exl.append(f"|  | by year: {yrs} | | | | | | |")
        summary[name] = {"passed": ok, "dev": sd, "half1": h1, "half2": h2, "holdout": hh}
    lines += exl
    (OUT / "results.md").write_text("\n".join(lines))
    (OUT / "results.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
