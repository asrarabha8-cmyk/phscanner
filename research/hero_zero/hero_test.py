"""Hero Zero: SPY same-day options bought in the last 20 minutes of the session.

Rules were fixed before the run.
Signal: SPY 1-minute close at 15:39 New York versus the close at 15:09.
- Continuation: buy a call if SPY rose over those 30 minutes, a put if it fell.
- Reversal: the opposite option.
Strikes: at the money (nearest dollar to SPY at 15:39) or one dollar out of the money.
Entry: the option's 15:40 minute open; it must have traded between 15:38 and 15:42
and cost at least 0.05.
Exits:
- hold: last price at or before 15:59.
- double: the first minute close at or above twice the entry price, otherwise hold.
Costs: slippage 0.01 plus 1% of price per side, 0.65 commission per side, one contract.
A sensitivity check adds 0.02 more slippage per side.
A predefined subgroup keeps days when SPY moved at least 0.15% over the 30 minutes.
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
SIG_MIN, REF_MIN, ENTRY_MIN, LAST_MIN = 939, 909, 940, 959
STRONG = 0.0015
COMM = 0.65
SLEEP = 12.5
BUDGET_MIN = 330
CACHE = OUT / "cache"
Z95 = 1.96


def spy_days(key):
    bt.SYMBOL, bt.YEARS = "SPY", 2
    b = bt.rth_only(bt.fetch_bars(1, key))
    b = b[b["day"] >= START]
    rows = []
    for day, d in b.groupby("day", sort=True):
        s = d.set_index("mins")["close"]
        if SIG_MIN not in s.index or REF_MIN not in s.index:
            continue
        spot, ref = float(s[SIG_MIN]), float(s[REF_MIN])
        rows.append({"day": day, "spot": spot, "move": spot / ref - 1, "atm": int(round(spot))})
    return pd.DataFrame(rows)


def contracts(r, kind):
    a = r["atm"]
    if kind == "atm":
        return {("C", 1): a, ("P", -1): a}
    return {("C", 1): a + 1, ("P", -1): a - 1}


def tk(day, cp, strike):
    return f"O:SPY{day:%y%m%d}{cp}{strike * 1000:08d}"


def fetch_mode(kind, days, key):
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"{kind}.json"
    cache = json.loads(path.read_text()) if path.exists() else {}
    session, t0, done, codes = requests.Session(), time.time(), 0, {}
    jobs = [(tk(r["day"], cp, k), r["day"]) for r in days.to_dict("records") for (cp, _), k in contracts(r, kind).items()]
    for ticker, day in jobs:
        ck = f"{ticker}|{day}"
        if ck in cache:
            continue
        if time.time() - t0 > BUDGET_MIN * 60:
            break
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
            if 930 <= m <= 960:
                out.append([m, x["o"], x["h"], x["l"], x["c"]])
        cache[ck] = out
        done += 1
        if done % 50 == 0:
            path.write_text(json.dumps(cache))
        time.sleep(SLEEP)
    path.write_text(json.dumps(cache))
    left = sum(1 for t, d in jobs if f"{t}|{d}" not in cache)
    print(f"{kind}: fetched {done}, status {codes}, still missing {left}")


def option_trade(bars, exit_rule, extra=0.0):
    s = pd.DataFrame(bars, columns=["hm", "o", "h", "l", "c"]).drop_duplicates("hm").set_index("hm").sort_index()
    if s.empty or not s.index.to_series().between(ENTRY_MIN - 2, ENTRY_MIN + 2).any():
        return None
    after = s[s.index >= ENTRY_MIN]
    if after.empty:
        return None
    raw = float(after["o"].iloc[0]) if after.index[0] <= ENTRY_MIN + 2 else None
    if raw is None or raw < 0.05:
        return None
    out_raw, why = None, "hold"
    if exit_rule == "double":
        hit = after[(after.index <= LAST_MIN) & (after["c"] >= 2 * raw)]
        if len(hit):
            out_raw, why = float(hit["c"].iloc[0]), "double"
    if out_raw is None:
        upto = s[s.index <= LAST_MIN]
        out_raw = float(upto["c"].iloc[-1])
    prem = raw + 0.01 + 0.01 * raw + extra
    px = max(out_raw - (0.01 + 0.01 * out_raw + extra), 0.0)
    return {"raw": raw, "prem": round(prem, 3), "exit": round(px, 3), "ret": px / prem - 1,
            "pnl": (px - prem) * 100 - 2 * COMM, "why": why}


def metrics(t):
    if len(t) == 0:
        return {"n": 0}
    r = t["ret"]
    se = r.std(ddof=0) / math.sqrt(len(r))
    gain, loss = t["pnl"][t["pnl"] > 0].sum(), -t["pnl"][t["pnl"] <= 0].sum()
    return {"n": len(t), "win": round(100 * (t["pnl"] > 0).mean(), 1), "avg_ret": round(100 * r.mean(), 1),
            "low95": round(100 * (r.mean() - Z95 * se), 1), "pnl": round(t["pnl"].sum()),
            "pf": round(gain / loss, 2) if loss > 0 else None,
            "best": round(float(t["pnl"].max())), "avg_prem": round(float(t["prem"].mean()), 2)}


def row(name, m):
    if not m.get("n"):
        return f"| {name} | 0 | - | - | - | - | - | - | - |"
    return (f"| {name} | {m['n']} | {m['win']}% | {m['avg_ret']}% | {m['low95']}% | {m['pnl']}$ | {m['pf']} | "
            f"{m['best']}$ | {m['avg_prem']} |")


HEAD = ("| Group | Trades | Win | Avg return | Low 95% | Profit | PF | Best trade | Avg premium |\n"
        "|---|---|---|---|---|---|---|---|---|")


def analyze(days):
    lines = ["# Hero Zero: SPY 0DTE in the last 20 minutes", "",
             f"Run date: {date.today()}. Rules were fixed before the run.",
             f"Days with a signal: {len(days)} from {days['day'].min()} to {days['day'].max()}.", ""]
    summary, all_trades = {}, []
    for kind in ("atm", "otm"):
        path = CACHE / f"{kind}.json"
        cache = json.loads(path.read_text()) if path.exists() else {}
        for idea in ("continuation", "reversal"):
            for exit_rule in ("hold", "double"):
                rows, missing, skipped = [], 0, 0
                for r in days.to_dict("records"):
                    if r["move"] == 0:
                        continue
                    trend = 1 if r["move"] > 0 else -1
                    dr = trend if idea == "continuation" else -trend
                    cp = "C" if dr == 1 else "P"
                    strike = contracts(r, kind)[(cp, dr)]
                    ck = f"{tk(r['day'], cp, strike)}|{r['day']}"
                    if ck not in cache:
                        missing += 1
                        continue
                    tr = option_trade(cache[ck], exit_rule)
                    if tr is None:
                        skipped += 1
                        continue
                    worse = option_trade(cache[ck], exit_rule, extra=0.02)
                    rows.append({**r, **tr, "dir": dr, "kind": kind, "idea": idea, "exit_rule": exit_rule,
                                 "pnl_slip": worse["pnl"] if worse else np.nan})
                name = f"{idea} / {kind} / {exit_rule}"
                lines += [f"## {name}", "", f"Not fetched: {missing}. Skipped for no trading or price under 0.05: {skipped}.", ""]
                t = pd.DataFrame(rows)
                if t.empty:
                    continue
                all_trades.append(t)
                t = t.sort_values("day").reset_index(drop=True)
                dev, test = t[t["day"] < TEST_START].reset_index(drop=True), t[t["day"] >= TEST_START]
                half = len(dev) // 2
                groups = {"Development": dev, "Dev first half": dev.iloc[:half], "Dev second half": dev.iloc[half:],
                          "Dev calls": dev[dev["dir"] == 1], "Dev puts": dev[dev["dir"] == -1],
                          "Dev strong move": dev[dev["move"].abs() >= STRONG], "Test": test,
                          "Test strong move": test[test["move"].abs() >= STRONG]}
                res = {k: metrics(v) for k, v in groups.items()}
                slip = dev["pnl_slip"].dropna().sum()
                ok = bool(res["Development"].get("low95", -1) > 0 and res["Dev first half"].get("avg_ret", -1) > 0
                          and res["Dev second half"].get("avg_ret", -1) > 0 and res["Test"].get("avg_ret", -1) > 0)
                lines += [HEAD] + [row(k, v) for k, v in res.items()]
                lines += [f"Development profit with 0.02 more slippage per side: {round(slip)}$.",
                          f"Exit reasons: {t['why'].value_counts().to_dict()}.", f"Verdict: {'PASS' if ok else 'FAIL'}.", ""]
                summary[name] = {"groups": res, "passed": ok}
    lines += ["Eight variants were tested, so a single pass needs extra caution before trusting it.", ""]
    if all_trades:
        pd.concat(all_trades).to_csv(OUT / "trades.csv", index=False)
    (OUT / "results.json").write_text(json.dumps(summary, indent=2, default=str))
    (OUT / "results.md").write_text("\n".join(lines))
    print("\n".join(lines))


def main():
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        raise SystemExit("POLYGON_API_KEY is missing")
    days = spy_days(key)
    print(f"days {len(days)}")
    if os.environ.get("MODE", "analyze") == "fetch":
        fetch_mode(os.environ["KIND"], days, key)
    else:
        analyze(days)


if __name__ == "__main__":
    main()
