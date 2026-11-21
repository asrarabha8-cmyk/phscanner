"""RSI on SPY options: four ways to line RSI up with the contract's price.

Rules were fixed before the run.
Contracts: each day, SPY call and put at the strike nearest the day's open, expiring the
next trading day. 5-minute regular-session bars. Entries from 10:40 to 15:00 New York,
exits by the 15:55 bar close. Entry and exit at the next bar's open.
RSI(14), buy level 35, sell level 65.
- V1 contract: the contract's own RSI drops to 35 or below -> buy that contract; sell when
  its RSI reaches 65.
- V2 stock: SPY's RSI drops to 35 or below -> buy the call, sell when SPY's RSI reaches 65.
  SPY's RSI reaches 65 or above -> buy the put, sell when SPY's RSI drops to 35.
- V3 both: as V2, but the contract's own RSI must also be 35 or below at the signal bar;
  exit when either RSI reaches its sell level.
- V4 decay-free: RSI on the contract price with the time decay added back. Decay is the
  Black-Scholes value lost from the first bar to each bar with SPY and implied volatility
  held at their first-bar values. Same levels as V1; profit uses real prices.
Costs: slippage 0.02 plus 1% per side, commission 0.65 per side, one contract.
Control: random entries at the same rate with the same exit rule.
Development to the cut date; the last 6 months are the test.
Pass: development low 95% > 0, both halves positive, test average positive, and above the
random control average.
"""
import json
import math
import os
import random
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
TEST_START = date.today() - timedelta(days=182)
BUY, SELL, N = 35.0, 65.0, 14
FIRST, LAST_ENTRY, LAST_BAR = 640, 900, 955
COMM = 0.65
SLEEP = 12.5
BUDGET_MIN = 330
CACHE = OUT / "cache.json"
Z95 = 1.96
GRID = list(range(570, 960, 5))


def rsi(c, n=N):
    c = np.asarray(c, float)
    d = np.diff(c, prepend=c[0])
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean()
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean()
    return (100 - 100 / (1 + up / dn.replace(0, np.nan))).fillna(50).to_numpy()


def spy(key):
    bt.SYMBOL, bt.YEARS = "SPY", 2.2
    b = bt.rth_only(bt.fetch_bars(5, key))
    b["rsi"] = rsi(b["close"].to_numpy())
    return b[b["day"] >= START].reset_index(drop=True)


def plan(b):
    days = sorted(b["day"].unique())
    rows = []
    for i, d in enumerate(days[:-1]):
        g = b[b["day"] == d]
        if len(g) < 70:
            continue
        k = int(round(g["open"].iloc[0]))
        exp = days[i + 1]
        rows.append({"day": d, "exp": exp, "strike": k,
                     "call": f"O:SPY{exp:%y%m%d}C{k * 1000:08d}", "put": f"O:SPY{exp:%y%m%d}P{k * 1000:08d}"})
    return rows


def fetch(rows, key):
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    s, t0, done, codes = requests.Session(), time.time(), 0, {}
    for r in rows:
        for side in ("call", "put"):
            ck = f"{r[side]}|{r['day']}"
            if ck in cache:
                continue
            if time.time() - t0 > BUDGET_MIN * 60:
                break
            url = f"{bt.BASE}/v2/aggs/ticker/{r[side]}/range/5/minute/{r['day']}/{r['day']}"
            for _ in range(5):
                resp = s.get(url, params={"adjusted": "false", "limit": 5000, "apiKey": key}, timeout=60)
                if resp.status_code != 429:
                    break
                time.sleep(60)
            codes[resp.status_code] = codes.get(resp.status_code, 0) + 1
            res = (resp.json().get("results") or []) if resp.status_code == 200 else []
            out = []
            for x in res:
                tt = pd.Timestamp(x["t"], unit="ms", tz="UTC").tz_convert("America/New_York")
                m = tt.hour * 60 + tt.minute
                if 570 <= m < 960:
                    out.append([m, x["o"], x["c"]])
            cache[ck] = out
            done += 1
            if done % 40 == 0:
                CACHE.write_text(json.dumps(cache))
            time.sleep(SLEEP)
    CACHE.write_text(json.dumps(cache))
    miss = sum(1 for r in rows for sd in ("call", "put") if f"{r[sd]}|{r['day']}" not in cache)
    print(f"fetched {done}, status {codes}, missing {miss}")


def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs(S, K, T, v, call):
    if T <= 0 or v <= 0:
        return max(0.0, S - K) if call else max(0.0, K - S)
    d1 = (math.log(S / K) + 0.5 * v * v * T) / (v * math.sqrt(T))
    d2 = d1 - v * math.sqrt(T)
    return S * ncdf(d1) - K * ncdf(d2) if call else K * ncdf(-d2) - S * ncdf(-d1)


def implied(price, S, K, T, call):
    lo, hi = 0.01, 3.0
    if price <= bs(S, K, T, lo, call):
        return lo
    for _ in range(60):
        mid = (lo + hi) / 2
        if bs(S, K, T, mid, call) < price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def series(raw):
    s = pd.DataFrame(raw, columns=["m", "o", "c"]).drop_duplicates("m").set_index("m").reindex(GRID)
    traded = s["c"].notna().to_numpy()
    c = s["c"].ffill().bfill()
    o = s["o"].fillna(c.shift()).fillna(c)
    return o.to_numpy(), c.to_numpy(), traded


def decay_free(c, spot, K, exp_minutes, call):
    """Contract price plus the time value lost since the first bar."""
    T0 = exp_minutes[0] / (365 * 1440)
    v = implied(c[0], spot[0], K, T0, call)
    out = np.empty(len(c))
    for i in range(len(c)):
        T = exp_minutes[i] / (365 * 1440)
        out[i] = c[i] + (bs(spot[i], K, T0, v, call) - bs(spot[i], K, T, v, call))
    return out


def trade_loop(o, c, traded, enter, leave, rng=None, rate=None, extra=0.0):
    """enter(i) -> bool, leave(j) -> bool. Returns list of (pnl, ret, i)."""
    out, i, n = [], 0, len(c)
    while i < n - 1:
        m = GRID[i]
        if m > LAST_ENTRY:
            break
        go = (rng.random() < rate) if rng is not None else enter(i)
        if m >= FIRST and go and traded[max(0, i - 1):i + 3].any() and o[i + 1] >= 0.10:
            buy = o[i + 1] + 0.02 + 0.01 * o[i + 1] + extra
            j = i + 1
            while GRID[j] < LAST_BAR and not leave(j):
                j += 1
            px = o[j + 1] if (GRID[j] < LAST_BAR and j + 1 < n) else c[j]
            sell = max(px - 0.02 - 0.01 * px - extra, 0.0)
            out.append(((sell - buy) * 100 - 2 * COMM, sell / buy - 1))
            i = j + 1
            continue
        i += 1
    return out


def analyze(b, rows):
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    rng = random.Random(7)
    res = {v: [] for v in ("V1 contract", "V2 stock", "V3 both", "V4 decay-free")}
    ctrl = {v: [] for v in res}
    slip = {v: [] for v in res}
    for r in rows:
        g = b[b["day"] == r["day"]].set_index("mins").reindex(GRID)
        if g["close"].isna().sum() > 5:
            continue
        spot = g["close"].ffill().bfill().to_numpy()
        srsi = g["rsi"].ffill().bfill().to_numpy()
        exp_min = np.array([(1440 - m) + 960 for m in GRID], float)  # minutes to next day's 16:00
        for side, call in (("call", True), ("put", False)):
            ck = f"{r[side]}|{r['day']}"
            if ck not in cache or len(cache[ck]) < 20:
                continue
            o, c, traded = series(cache[ck])
            if c[0] < 0.10:
                continue
            crsi = rsi(c)
            arsi = rsi(decay_free(c, spot, r["strike"], exp_min, call))
            lo = (lambda x: x <= BUY)
            hi = (lambda x: x >= SELL)
            rules = {
                "V1 contract": (lambda i: lo(crsi[i]) and not lo(crsi[i - 1]), lambda j: hi(crsi[j])),
                "V4 decay-free": (lambda i: lo(arsi[i]) and not lo(arsi[i - 1]), lambda j: hi(arsi[j])),
            }
            if call:
                rules["V2 stock"] = (lambda i: lo(srsi[i]) and not lo(srsi[i - 1]), lambda j: hi(srsi[j]))
                rules["V3 both"] = (lambda i: lo(srsi[i]) and lo(crsi[i]) and not (lo(srsi[i - 1]) and lo(crsi[i - 1])),
                                    lambda j: hi(srsi[j]) or hi(crsi[j]))
            else:
                rules["V2 stock"] = (lambda i: hi(srsi[i]) and not hi(srsi[i - 1]), lambda j: lo(srsi[j]))
                rules["V3 both"] = (lambda i: hi(srsi[i]) and lo(crsi[i]) and not (hi(srsi[i - 1]) and lo(crsi[i - 1])),
                                    lambda j: lo(srsi[j]) or hi(crsi[j]))
            for v, (en, lv) in rules.items():
                for p, ret in trade_loop(o, c, traded, en, lv):
                    res[v].append({"day": r["day"], "side": side, "pnl": p, "ret": ret})
                for p, ret in trade_loop(o, c, traded, en, lv, extra=0.03):
                    slip[v].append(p)
                elig = [i for i in range(1, len(c)) if FIRST <= GRID[i] <= LAST_ENTRY]
                rate = max(0.002, sum(1 for i in elig if en(i)) / max(1, len(elig)))
                for p, ret in trade_loop(o, c, traded, en, lv, rng=rng, rate=rate):
                    ctrl[v].append(p)

    def st(p):
        p = np.asarray(p, float)
        if len(p) < 2:
            return {"n": len(p)}
        se = p.std(ddof=1) / math.sqrt(len(p))
        return {"n": len(p), "win": round(100 * (p > 0).mean(), 1), "avg": round(p.mean(), 1),
                "low95": round(p.mean() - Z95 * se, 1), "total": round(p.sum())}

    def row(name, s):
        if s.get("n", 0) < 2:
            return f"| {name} | {s.get('n', 0)} | - | - | - | - |"
        return f"| {name} | {s['n']} | {s['win']}% | {s['avg']}$ | {s['low95']}$ | {s['total']}$ |"

    lines = ["# RSI on SPY next-day options", "", f"Run date: {date.today()}. Rules were fixed before the run. Test from {TEST_START}.",
             f"Days planned: {len(rows)}. Dollars per one contract after costs.", ""]
    summary = {}
    for v, t in res.items():
        t = pd.DataFrame(t)
        if t.empty:
            lines += [f"## {v}", "", "No trades.", ""]
            continue
        t = t.sort_values("day").reset_index(drop=True)
        dev, test = t[t["day"] < TEST_START].reset_index(drop=True), t[t["day"] >= TEST_START]
        h = len(dev) // 2
        g = {"Development": st(dev["pnl"]), "Dev first half": st(dev["pnl"].iloc[:h]), "Dev second half": st(dev["pnl"].iloc[h:]),
             "Calls (dev)": st(dev[dev["side"] == "call"]["pnl"]), "Puts (dev)": st(dev[dev["side"] == "put"]["pnl"]),
             "Test": st(test["pnl"]), "Random entries (all)": st(ctrl[v])}
        ok = bool(g["Development"].get("low95", -1) > 0 and g["Dev first half"].get("avg", -1) > 0
                  and g["Dev second half"].get("avg", -1) > 0 and g["Test"].get("avg", -1) > 0
                  and g["Development"]["avg"] > g["Random entries (all)"].get("avg", 1e9))
        lines += [f"## {v}", "", "| Group | Trades | Win | Avg | Low 95% | Total |", "|---|---|---|---|---|---|"]
        lines += [row(k, s) for k, s in g.items()]
        lines += ["", f"With 0.03 more slippage per side: average {np.mean(slip[v]):.1f}$.", f"Verdict: {'PASS' if ok else 'FAIL'}.", ""]
        summary[v] = {"groups": g, "passed": ok}
    (OUT / "results.md").write_text("\n".join(lines))
    (OUT / "results.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\n".join(lines))


def main():
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        raise SystemExit("POLYGON_API_KEY is missing")
    b = spy(key)
    rows = plan(b)
    print(f"days {len(rows)}, contracts {2 * len(rows)}", flush=True)
    if os.environ.get("MODE", "analyze") == "fetch":
        fetch(rows, key)
    else:
        analyze(b, rows)


if __name__ == "__main__":
    main()
