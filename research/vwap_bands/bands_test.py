"""SPY VWAP bands traded with real SPY option contracts at three expiries.

Rules were fixed before the run. Signals use SPY 5-minute bars, from 10:00 to
15:00 New York, at most one trade per idea per day:
- Reversion: close back inside the 2-sigma band, buy the option toward VWAP.
  Exit when SPY touches VWAP, closes beyond the signal bar, or at 15:45.
- Breakout: close outside the 2-sigma band, buy the option in that direction.
  Exit when SPY closes back inside the 1-sigma band, closes beyond the signal
  bar, or at 15:45.
Options: strike nearest SPY at entry, expiring the same day, 1 trading day
later, or 5 trading days later. Entry at the next bar's open and exit at the
bar after the exit signal, each with slippage of 0.02 plus 1% of the price,
and 0.65 commission per side. One contract per trade.
Development runs to 2026-04-30; the test period starts 2026-05-01.
"""
import json
import math
import os
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

OUT = Path(__file__).parent
sys.path.insert(0, str(OUT.parent / "noise_band"))
import backtest as bt  # noqa: E402

START = date(2024, 12, 16)
TEST_START = date(2026, 5, 1)
K_OUT, K_IN = 2.0, 1.0
FIRST_MIN, LAST_ENTRY, EXIT_MIN = 600, 900, 945
DTES = (0, 1, 5)
COMM = 0.65
SLEEP = 12.5
BUDGET_MIN = 330
CACHE = OUT / "cache"
Z95 = 1.96


def spy_bars(key):
    bt.SYMBOL, bt.YEARS = "SPY", 2
    b = bt.rth_only(bt.fetch_bars(5, key))
    return b[b["day"] >= START].reset_index(drop=True)


def signals(b):
    tp = (b["high"] + b["low"] + b["close"]) / 3
    v = b["volume"].where(b["volume"] > 0, 1.0)
    cv = v.groupby(b["day"]).cumsum()
    vw = (tp * v).groupby(b["day"]).cumsum() / cv
    sd = np.sqrt(((tp ** 2) * v).groupby(b["day"]).cumsum() / cv - vw ** 2).fillna(0).clip(lower=0)
    b = b.assign(vw=vw, up2=vw + K_OUT * sd, dn2=vw - K_OUT * sd, up1=vw + K_IN * sd, dn1=vw - K_IN * sd)
    rows = []
    for day, d in b.groupby("day", sort=True):
        d = d.reset_index(drop=True)
        taken = set()
        for i in range(1, len(d) - 1):
            if not FIRST_MIN <= d.mins[i] <= LAST_ENTRY:
                continue
            c, p = d.close[i], d.close[i - 1]
            cand = []
            if p < d.dn2[i - 1] and c > d.dn2[i]:
                cand.append(("revert", 1))
            if p > d.up2[i - 1] and c < d.up2[i]:
                cand.append(("revert", -1))
            if p <= d.up2[i - 1] and c > d.up2[i]:
                cand.append(("breakout", 1))
            if p >= d.dn2[i - 1] and c < d.dn2[i]:
                cand.append(("breakout", -1))
            for idea, dr in cand:
                if idea in taken:
                    continue
                taken.add(idea)
                level = d.low[i] if dr == 1 else d.high[i]
                x, why = len(d) - 1, "close"
                for j in range(i + 1, len(d)):
                    cj = d.close[j]
                    if (dr == 1 and cj < level) or (dr == -1 and cj > level):
                        x, why = j, "stop"
                        break
                    if idea == "revert" and ((dr == 1 and d.high[j] >= d.vw[j]) or (dr == -1 and d.low[j] <= d.vw[j])):
                        x, why = j, "target"
                        break
                    if idea == "breakout" and ((dr == 1 and cj < d.up1[j]) or (dr == -1 and cj > d.dn1[j])):
                        x, why = j, "fade"
                        break
                    if d.mins[j] >= EXIT_MIN:
                        x, why = j, "time"
                        break
                e = i + 1
                on_open = x + 1 < len(d)
                rows.append({"day": day, "idea": idea, "dir": dr, "spot": float(d.open[e]),
                             "entry_hm": int(d.mins[e]), "exit_hm": int(d.mins[x + 1] if on_open else d.mins[x]),
                             "exit_on": "open" if on_open else "close", "why": why})
    return pd.DataFrame(rows)


def ticker(r, dte, tdays):
    idx = tdays.index(r["day"])
    if idx + dte < len(tdays):
        exp = tdays[idx + dte]
    else:
        exp = (pd.Timestamp(r["day"]) + pd.offsets.BDay(dte)).date()
    cp = "C" if r["dir"] == 1 else "P"
    return f"O:SPY{exp:%y%m%d}{cp}{int(round(r['spot'])) * 1000:08d}"


def fetch_mode(dte, sigs, tdays, key):
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"dte{dte}.json"
    cache = json.loads(path.read_text()) if path.exists() else {}
    session, t0, done, codes = requests.Session(), time.time(), 0, {}
    for r in sigs.to_dict("records"):
        ck = f"{ticker(r, dte, tdays)}|{r['day']}"
        if ck in cache:
            continue
        if time.time() - t0 > BUDGET_MIN * 60:
            break
        tk, day = ck.split("|")
        url = f"{bt.BASE}/v2/aggs/ticker/{tk}/range/5/minute/{day}/{day}"
        for _ in range(5):
            resp = session.get(url, params={"adjusted": "false", "limit": 5000, "apiKey": key}, timeout=60)
            if resp.status_code != 429:
                break
            time.sleep(60)
        codes[resp.status_code] = codes.get(resp.status_code, 0) + 1
        rows = resp.json().get("results") or [] if resp.status_code == 200 else []
        out = []
        for x in rows:
            t = pd.Timestamp(x["t"], unit="ms", tz="UTC").tz_convert("America/New_York")
            out.append([t.hour * 60 + t.minute, x["o"], x["h"], x["l"], x["c"]])
        cache[ck] = out
        done += 1
        if done % 50 == 0:
            path.write_text(json.dumps(cache))
        time.sleep(SLEEP)
    path.write_text(json.dumps(cache))
    left = sum(1 for r in sigs.to_dict("records") if f"{ticker(r, dte, tdays)}|{r['day']}" not in cache)
    print(f"dte {dte}: fetched {done}, status {codes}, still missing {left}")


def option_trade(bars, r, extra=0.0):
    grid = list(range(570, 960, 5))
    s = pd.DataFrame(bars, columns=["hm", "o", "h", "l", "c"]).drop_duplicates("hm").set_index("hm").reindex(grid)
    traded = s["c"].notna()
    c = s["c"].ffill()
    o = s["o"].fillna(c.shift()).fillna(c)
    e, x = r["entry_hm"], r["exit_hm"]
    near = traded.loc[e - 10:e + 5]
    if pd.isna(o.get(e)) or not near.any():
        return None
    raw = float(o[e])
    if raw < 0.10:
        return None
    slip = 0.02 + 0.01 * raw + extra
    prem = raw + slip
    out_raw = float(o[x]) if r["exit_on"] == "open" else float(c[x])
    if math.isnan(out_raw):
        return None
    px = max(out_raw - (0.02 + 0.01 * out_raw + extra), 0.0)
    return {"prem": round(prem, 2), "exit": round(px, 2), "ret": px / prem - 1, "pnl": (px - prem) * 100 - 2 * COMM}


def metrics(t):
    if len(t) == 0:
        return {"n": 0}
    r = t["ret"]
    se = r.std(ddof=0) / math.sqrt(len(r))
    gain, loss = t["pnl"][t["pnl"] > 0].sum(), -t["pnl"][t["pnl"] <= 0].sum()
    return {"n": len(t), "win": round(100 * (t["pnl"] > 0).mean(), 1), "avg_ret": round(100 * r.mean(), 1),
            "low95": round(100 * (r.mean() - Z95 * se), 1), "pnl": round(t["pnl"].sum()),
            "pf": round(gain / loss, 2) if loss > 0 else None}


def row(name, m):
    if not m.get("n"):
        return f"| {name} | 0 | - | - | - | - | - |"
    return f"| {name} | {m['n']} | {m['win']}% | {m['avg_ret']}% | {m['low95']}% | {m['pnl']}$ | {m['pf']} |"


HEAD = "| Group | Trades | Win | Avg return | Low 95% | Profit | PF |\n|---|---|---|---|---|---|---|"


def analyze(sigs, tdays):
    lines = ["# SPY VWAP bands on real option contracts", "", f"Run date: {date.today()}. Rules were fixed before the run.",
             f"Signals: {len(sigs)} from {sigs['day'].min()} to {sigs['day'].max()}.", ""]
    summary, all_trades = {}, []
    for dte in DTES:
        path = CACHE / f"dte{dte}.json"
        cache = json.loads(path.read_text()) if path.exists() else {}
        rows, missing, skipped = [], 0, 0
        for r in sigs.to_dict("records"):
            ck = f"{ticker(r, dte, tdays)}|{r['day']}"
            if ck not in cache:
                missing += 1
                continue
            tr = option_trade(cache[ck], r)
            if tr is None:
                skipped += 1
                continue
            worse = option_trade(cache[ck], r, extra=0.03)
            rows.append({**r, **tr, "dte": dte, "pnl_slip": worse["pnl"] if worse else np.nan})
        t = pd.DataFrame(rows)
        lines += [f"## Expiry {dte} trading days", "", f"Not fetched yet: {missing}. Skipped for no trading or price under 0.10: {skipped}.", ""]
        if t.empty:
            continue
        all_trades.append(t)
        for idea in ("revert", "breakout"):
            g = t[t["idea"] == idea].sort_values("day").reset_index(drop=True)
            dev, test = g[g["day"] < TEST_START].reset_index(drop=True), g[g["day"] >= TEST_START]
            half = len(dev) // 2
            groups = {"Development": dev, "Dev first half": dev.iloc[:half], "Dev second half": dev.iloc[half:],
                      "Dev calls": dev[dev["dir"] == 1], "Dev puts": dev[dev["dir"] == -1], "Test": test}
            res = {k: metrics(v) for k, v in groups.items()}
            slip = dev.assign(pnl=dev["pnl_slip"]).dropna(subset=["pnl"])
            ok = bool(res["Development"].get("low95", -1) > 0 and res["Dev first half"].get("avg_ret", -1) > 0
                      and res["Dev second half"].get("avg_ret", -1) > 0 and res["Test"].get("avg_ret", -1) > 0)
            lines += [f"### {idea}", "", HEAD] + [row(k, v) for k, v in res.items()]
            lines += [f"Development profit with 0.03 more slippage per side: {round(slip['pnl'].sum())}$.",
                      f"Exit reasons: {g['why'].value_counts().to_dict()}.", f"Verdict: {'PASS' if ok else 'FAIL'}.", ""]
            summary[f"{idea}_{dte}"] = {"groups": res, "passed": ok}
    if all_trades:
        pd.concat(all_trades).to_csv(OUT / "trades.csv", index=False)
    (OUT / "results.json").write_text(json.dumps(summary, indent=2, default=str))
    (OUT / "results.md").write_text("\n".join(lines))
    print("\n".join(lines))


def main():
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        raise SystemExit("POLYGON_API_KEY is missing")
    bars = spy_bars(key)
    tdays = sorted(bars["day"].unique())
    sigs = signals(bars)
    print(f"signals {len(sigs)}: {sigs.groupby('idea').size().to_dict()}")
    mode = os.environ.get("MODE", "analyze")
    if mode == "fetch":
        fetch_mode(int(os.environ["DTE"]), sigs, tdays, key)
    else:
        analyze(sigs, tdays)


if __name__ == "__main__":
    main()
