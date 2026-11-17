"""SPY 0DTE opening-range breakout re-tested on 1-minute bars.

System (unchanged from the live bot): opening range = 09:30-09:45 high/low; trade only
when its size (% of the open) is under 0.8 x the average of the previous 20 days;
at-the-money same-day option in the breakout direction; stop -35% of the paid price;
exit by 13:00 New York; one trade per day; one contract.

Versions, fixed before the run:
- A5: the original method. Signal = first 5-minute close outside the range (bar
  starting 09:45-11:55), entry at the next 5-minute bar open, stop checked on
  5-minute option bars, exit at the 13:00 bar close. Option bars are 1-minute bars
  grouped into 5 minutes, so A5 and A1 use the same prices.
- A1: same signal, entry, stop and exit simulated on 1-minute option bars.
- B1: signal = first 1-minute close outside the range (bar starting 09:45-11:59),
  entry at the next minute's open, everything on 1-minute bars.
Strike: nearest dollar to SPY's close on the signal bar.
Costs: 0.02 slippage per side plus 0.65 commission per side; a check with 0.05.
The stop fills at the stop price on the entry bar, and at the lower of the stop
and the bar open afterwards.
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
sys.path.insert(0, str(OUT.parent / "noise_band"))
import backtest as bt  # noqa: E402

START = date(2024, 12, 16)
RATIO, LOOKBACK, STOP = 0.8, 20, 0.35
COMM = 0.65
SLEEP = 12.5
BUDGET_MIN = 330
CACHE = OUT / "cache.json"
Z95 = 1.96


def spy_1m(key):
    bt.SYMBOL, bt.YEARS = "SPY", 2.2
    b = bt.rth_only(bt.fetch_bars(1, key))
    return b[b["day"] >= START - timedelta(days=45)].reset_index(drop=True)


def signals(b):
    rows, hist = [], []
    for day, d in b.groupby("day", sort=True):
        d = d.set_index("mins")
        first = d.loc[d.index < 585]
        if len(first) < 10:
            continue
        hi, lo, op = first["high"].max(), first["low"].min(), first["open"].iloc[0]
        rp = (hi - lo) / op
        avg = np.mean(hist[-LOOKBACK:]) if len(hist) >= LOOKBACK else None
        hist.append(rp)
        if avg is None or day < START or rp >= RATIO * avg or 780 not in d.index:
            continue
        rec = {"day": day, "ratio": round(rp / avg, 3)}
        # 5-minute signal
        for s in range(585, 720, 5):
            blk = d.loc[(d.index >= s) & (d.index < s + 5)]
            if blk.empty:
                continue
            c = blk["close"].iloc[-1]
            if c > hi or c < lo:
                rec["s5"] = {"dir": 1 if c > hi else -1, "entry": s + 5, "strike": int(round(c))}
                break
        # 1-minute signal
        for m in range(585, 720):
            if m not in d.index:
                continue
            c = d.at[m, "close"]
            if c > hi or c < lo:
                rec["s1"] = {"dir": 1 if c > hi else -1, "entry": m + 1, "strike": int(round(c))}
                break
        rows.append(rec)
    return rows


def tk(day, s):
    return f"O:SPY{day:%y%m%d}{'C' if s['dir'] == 1 else 'P'}{s['strike'] * 1000:08d}"


def needed(sigs):
    out = []
    for r in sigs:
        for k in ("s5", "s1"):
            if k in r:
                out.append(f"{tk(r['day'], r[k])}|{r['day']}")
    return sorted(set(out))


def fetch(sigs, key):
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    session, t0, done, codes = requests.Session(), time.time(), 0, {}
    for ck in needed(sigs):
        if ck in cache:
            continue
        if time.time() - t0 > BUDGET_MIN * 60:
            break
        ticker, day = ck.split("|")
        url = f"{bt.BASE}/v2/aggs/ticker/{ticker}/range/1/minute/{day}/{day}"
        for _ in range(5):
            resp = session.get(url, params={"adjusted": "false", "limit": 5000, "apiKey": key}, timeout=60)
            if resp.status_code != 429:
                break
            time.sleep(60)
        codes[resp.status_code] = codes.get(resp.status_code, 0) + 1
        rows = (resp.json().get("results") or []) if resp.status_code == 200 else []
        out = []
        for x in rows:
            t = pd.Timestamp(x["t"], unit="ms", tz="UTC").tz_convert("America/New_York")
            m = t.hour * 60 + t.minute
            if 570 <= m < 960:
                out.append([m, x["o"], x["h"], x["l"], x["c"]])
        cache[ck] = out
        done += 1
        if done % 40 == 0:
            CACHE.write_text(json.dumps(cache))
        time.sleep(SLEEP)
    CACHE.write_text(json.dumps(cache))
    print(f"fetched {done}, status {codes}, missing {sum(1 for c in needed(sigs) if c not in cache)}")


def bars_frame(raw, step):
    s = pd.DataFrame(raw, columns=["m", "o", "h", "l", "c"]).drop_duplicates("m").set_index("m").sort_index()
    if step == 1 or s.empty:
        return s
    g = (s.index // step) * step
    return s.groupby(g).agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"))


def simulate(raw, entry_min, step, slip):
    s = bars_frame(raw, step)
    exit_last = 780 if step == 5 else 779   # 5m: the 13:00 bar closes 13:05 (as the bot); 1m: closes at 13:00
    s = s[(s.index >= entry_min) & (s.index <= exit_last)]
    if s.empty or s.index[0] > entry_min + (5 if step == 5 else 3):
        return None
    raw_in = float(s["o"].iloc[0])
    if raw_in < 0.05:
        return None
    prem = raw_in + slip
    stop = prem * (1 - STOP)
    why, px = "time", float(s["c"].iloc[-1])
    for i, (m, b) in enumerate(s.iterrows()):
        if b["l"] <= stop:
            why, px = "stop", stop if i == 0 else min(stop, float(b["o"]))
            break
    px = max(px - slip, 0.0)
    return {"prem": round(prem, 2), "exit": round(px, 2), "ret": px / prem - 1, "pnl": (px - prem) * 100 - 2 * COMM, "why": why}


def st(t):
    if len(t) < 2:
        return {"n": len(t)}
    p = t["pnl"]
    se = p.std(ddof=1) / math.sqrt(len(p))
    gain, loss = p[p > 0].sum(), -p[p <= 0].sum()
    eq = p.cumsum()
    return {"n": len(t), "win": round(100 * (p > 0).mean(), 1), "avg": round(p.mean(), 1), "low95": round(p.mean() - Z95 * se, 1),
            "total": round(p.sum()), "pf": round(gain / loss, 2) if loss else None,
            "maxdd": round(float((eq.cummax().clip(lower=0) - eq).max()))}


def row(name, s):
    if s.get("n", 0) < 2:
        return f"| {name} | {s.get('n', 0)} | - | - | - | - | - | - |"
    return f"| {name} | {s['n']} | {s['win']}% | {s['avg']}$ | {s['low95']}$ | {s['total']}$ | {s['pf']} | {s['maxdd']}$ |"


HEAD = "| Group | Trades | Win | Avg/trade | Low 95% | Total | PF | Max drawdown |\n|---|---|---|---|---|---|---|---|"


def analyze(sigs):
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    versions = {"A5": ("s5", 5), "A1": ("s5", 1), "B1": ("s1", 1)}
    lines = ["# SPY 0DTE opening-range breakout on 1-minute bars", "", f"Run date: {date.today()}. Rules unchanged from the live bot.",
             f"Qualified days: {len(sigs)} from {sigs[0]['day']} to {sigs[-1]['day']}. One contract per trade, dollars.", ""]
    summary, trades = {}, []
    for v, (sk, step) in versions.items():
        for slip in (0.02, 0.05):
            rows, miss, skip = [], 0, 0
            for r in sigs:
                if sk not in r:
                    continue
                ck = f"{tk(r['day'], r[sk])}|{r['day']}"
                if ck not in cache:
                    miss += 1
                    continue
                res = simulate(cache[ck], r[sk]["entry"], step, slip)
                if res is None:
                    skip += 1
                    continue
                rows.append({"day": r["day"], "version": v, "slip": slip, "dir": r[sk]["dir"],
                             "strike": r[sk]["strike"], "entry_min": r[sk]["entry"], **res})
            t = pd.DataFrame(rows)
            if t.empty:
                continue
            trades.append(t)
            t = t.sort_values("day").reset_index(drop=True)
            h = len(t) // 2
            last6 = t[t["day"] >= date.today() - timedelta(days=182)]
            groups = {"All": t, "First half": t.iloc[:h], "Second half": t.iloc[h:], "Calls": t[t["dir"] == 1],
                      "Puts": t[t["dir"] == -1], "Last 6 months": last6}
            res = {k: st(g) for k, g in groups.items()}
            summary[f"{v}_{slip}"] = res
            if slip == 0.02:
                lines += [f"## {v} (slippage 0.02)", "", f"Missing contracts: {miss}. Skipped (no trade near entry): {skip}.", "", HEAD]
                lines += [row(k, g) for k, g in res.items()]
                lines += ["", f"Exit reasons: {t['why'].value_counts().to_dict()}. Average entry price: {t['prem'].mean():.2f}.", ""]
            else:
                lines += [f"{v} with 0.05 slippage per side: " + row("All", res["All"]), ""]
    if trades:
        allt = pd.concat(trades)
        allt.to_csv(OUT / "trades.csv", index=False)
        a5 = allt[(allt.version == "A5") & (allt.slip == 0.02)].set_index("day")
        a1 = allt[(allt.version == "A1") & (allt.slip == 0.02)].set_index("day")
        j = a5[["pnl", "why"]].join(a1[["pnl", "why"]], lsuffix="_5", rsuffix="_1", how="inner")
        lines += ["## Same trades, 5-minute vs 1-minute execution", "",
                  f"Days compared: {len(j)}. Average difference (1m minus 5m): {(j.pnl_1 - j.pnl_5).mean():.1f}$ per trade.",
                  f"Days where the exit type changed: {(j.why_5 != j.why_1).sum()}.", ""]
    (OUT / "results.md").write_text("\n".join(lines))
    (OUT / "results.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\n".join(lines))


def main():
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        raise SystemExit("POLYGON_API_KEY is missing")
    sigs = signals(spy_1m(key))
    print(f"qualified days {len(sigs)}, contracts {len(needed(sigs))}", flush=True)
    if os.environ.get("MODE", "analyze") == "fetch":
        fetch(sigs, key)
    else:
        analyze(sigs)


if __name__ == "__main__":
    main()
