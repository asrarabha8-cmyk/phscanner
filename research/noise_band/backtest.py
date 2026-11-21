"""Noise Band long-history backtest on SPY.

Mirrors the rules of NoiseBand_v1.pine with fixed default settings.
The settings are not tuned here: only cost is varied to check sensitivity.
"""
import json
import math
import os
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

OUT = Path(__file__).parent
BASE = "https://api.polygon.io"
SYMBOL = "SPY"
YEARS = 5
TIMEFRAMES = (3, 5)
COSTS = (0.02, 0.05, 0.10)      # dollars per share, round trip
MAIN_COST = 0.05                # about 0.5 SPX points

LOOK = 14
BAND_MULT = 1.0
START_MIN = 30
NO_NEW_MIN = 30
MAX_TRADES = 2
ADR_MAX = 1.0
STOP_PAD = 0.25
MIN_RISK = 0.5
Z95 = 1.96


def fetch_bars(tf, key):
    frames = []
    end = date.today() - timedelta(days=1)
    cur = end - timedelta(days=int(YEARS * 365.25) - 7)
    session = requests.Session()
    while cur <= end:
        stop = min(cur + timedelta(days=31), end)
        url = f"{BASE}/v2/aggs/ticker/{SYMBOL}/range/{tf}/minute/{cur}/{stop}"
        params = {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": key}
        for attempt in range(6):
            r = session.get(url, params=params, timeout=60)
            if r.status_code == 200:
                break
            if r.status_code == 429:
                time.sleep(15)
                continue
            raise SystemExit(f"Data request failed with status {r.status_code}")
        else:
            raise SystemExit("Data request kept hitting the rate limit")
        rows = r.json().get("results") or []
        if rows:
            frames.append(pd.DataFrame(rows))
        cur = stop + timedelta(days=1)
    if not frames:
        raise SystemExit("No data returned")
    df = pd.concat(frames, ignore_index=True).drop_duplicates("t")
    df["dt"] = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_convert("America/New_York")
    df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    return df[["dt", "open", "high", "low", "close", "volume"]].sort_values("dt").reset_index(drop=True)


def rth_only(df):
    mins = df["dt"].dt.hour * 60 + df["dt"].dt.minute
    out = df[(mins >= 570) & (mins < 960)].copy().reset_index(drop=True)
    out["mins"] = out["dt"].dt.hour * 60 + out["dt"].dt.minute
    out["day"] = out["dt"].dt.date
    return out


def rma_atr(high, low, close, n=14):
    prev = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def simulate(df, tf, cost):
    df = df.copy()
    df["atr"] = rma_atr(df["high"], df["low"], df["close"])
    daily = df.groupby("day").agg(high=("high", "max"), low=("low", "min"), close=("close", "last"))
    adr = rma_atr(daily["high"], daily["low"], daily["close"]).shift(1)

    n_bins = math.ceil(390 / tf)
    hist = []
    prev_close = None
    trades = []

    for day, g in df.groupby("day", sort=True):
        d_open = g["open"].iloc[0]
        day_hi, day_lo = -math.inf, math.inf
        cum_pv = cum_v = 0.0
        cur = [np.nan] * n_bins
        pos, entry, stop, risk, entry_time = 0, 0.0, 0.0, 0.0, None
        today, arm_l, arm_s = 0, True, True
        ready = len(hist) >= LOOK
        sigma = np.nanmean(np.array(hist[-LOOK:]), axis=0) * BAND_MULT if ready else None
        ref_hi = max(d_open, prev_close if prev_close is not None else d_open)
        ref_lo = min(d_open, prev_close if prev_close is not None else d_open)
        day_adr = adr.get(day, np.nan)

        for row in g.itertuples(index=False):
            b = min(int((row.mins - 570) / tf), n_bins - 1)
            day_hi, day_lo = max(day_hi, row.high), min(day_lo, row.low)
            w = row.volume if row.volume and row.volume > 0 else 1.0
            cum_pv += (row.high + row.low + row.close) / 3 * w
            cum_v += w
            vw = cum_pv / cum_v
            cur[b] = abs(row.close / d_open - 1)
            sig = sigma[b] if ready else np.nan
            up = ref_hi * (1 + sig) if not np.isnan(sig) else np.nan
            dn = ref_lo * (1 - sig) if not np.isnan(sig) else np.nan
            exited = False

            if pos != 0:
                hit = row.low <= stop if pos == 1 else row.high >= stop
                trail = row.close < vw if pos == 1 else row.close > vw
                eod = row.mins + tf >= 960
                if hit or trail or eod:
                    px = stop if hit else row.close
                    r = (pos * (px - entry) - cost) / risk
                    trades.append({
                        "entry_time": entry_time, "exit_time": row.dt, "side": "long" if pos == 1 else "short",
                        "entry": entry, "exit": px, "risk": risk, "r": r,
                        "exit_type": "stop" if hit else "vwap" if trail else "eod",
                    })
                    arm_l = arm_l and pos != 1
                    arm_s = arm_s and pos != -1
                    pos, exited = 0, True

            if not np.isnan(up) and row.close <= up:
                arm_l = True
            if not np.isnan(dn) and row.close >= dn:
                arm_s = True

            time_ok = 570 + START_MIN <= row.mins < 960 - NO_NEW_MIN
            range_ok = not np.isnan(day_adr) and day_hi - day_lo <= ADR_MAX * day_adr
            if pos == 0 and not exited and time_ok and range_ok and today < MAX_TRADES and not np.isnan(up):
                go_l = row.close > up and row.close > vw and arm_l
                go_s = row.close < dn and row.close < vw and arm_s
                if go_l or go_s:
                    pos = 1 if go_l else -1
                    entry = row.close
                    raw = vw - STOP_PAD * row.atr if go_l else vw + STOP_PAD * row.atr
                    risk = max(abs(row.close - raw), MIN_RISK * row.atr, 0.01)
                    stop = entry - pos * risk
                    entry_time = row.dt
                    today += 1

        hist.append(cur)
        hist = hist[-LOOK:]
        prev_close = g["close"].iloc[-1]

    return pd.DataFrame(trades)


def stats(r):
    n = len(r)
    if n == 0:
        return {"trades": 0}
    mean = float(r.mean())
    sd = float(r.std(ddof=0))
    se = sd / math.sqrt(n)
    eq = r.cumsum()
    dd = float((eq.cummax().clip(lower=0) - eq).max())
    streak = worst = 0
    for x in r:
        streak = streak + 1 if x <= 0 else 0
        worst = max(worst, streak)
    wins = r[r > 0]
    losses = r[r <= 0]
    gross_loss = float(-losses.sum())
    return {
        "trades": n, "win_pct": round(100 * float((r > 0).mean()), 1),
        "avg_r": round(mean, 3), "low95": round(mean - Z95 * se, 3), "high95": round(mean + Z95 * se, 3),
        "total_r": round(float(r.sum()), 1), "avg_win": round(float(wins.mean()), 2) if len(wins) else None,
        "avg_loss": round(float(losses.mean()), 2) if len(losses) else None,
        "profit_factor": round(float(wins.sum()) / gross_loss, 2) if gross_loss > 0 else None,
        "max_dd_r": round(dd, 1), "worst_streak": worst,
    }


def row_md(name, s):
    if not s.get("trades"):
        return f"| {name} | 0 | - | - | - | - | - | - |"
    return (f"| {name} | {s['trades']} | {s['win_pct']}% | {s['avg_r']} | {s['low95']} | "
            f"{s['total_r']} | {s['profit_factor']} | {s['max_dd_r']} |")


HEADER = "| Group | Trades | Win | Avg R | Low 95% | Total R | PF | Max DD R |\n|---|---|---|---|---|---|---|---|"


def main():
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    if not key:
        raise SystemExit("POLYGON_API_KEY is missing")
    results, lines = {}, [f"# Noise Band backtest on {SYMBOL}", "",
                          f"Run date: {date.today()}. Settings are the indicator defaults and were not tuned.", ""]
    for tf in TIMEFRAMES:
        bars = rth_only(fetch_bars(tf, key))
        days = bars["day"].nunique()
        lines += [f"## {tf} minutes", "", f"Data: {bars['day'].min()} to {bars['day'].max()}, {days} days.", ""]
        tf_res = {"days": days, "first_day": str(bars["day"].min()), "last_day": str(bars["day"].max())}
        cost_rows = []
        for c in COSTS:
            t = simulate(bars, tf, c)
            tf_res[f"cost_{c}"] = stats(t["r"]) if len(t) else {"trades": 0}
            cost_rows.append(row_md(f"Cost ${c:.2f}", tf_res[f"cost_{c}"]))
            if c == MAIN_COST:
                main_t = t
        t = main_t
        if len(t):
            t["year"] = pd.to_datetime(t["entry_time"], utc=True).dt.year
            half = len(t) // 2
            groups = {"All": t, "Long": t[t["side"] == "long"], "Short": t[t["side"] == "short"],
                      "First half": t.iloc[:half], "Second half": t.iloc[half:]}
            for y, g in t.groupby("year"):
                groups[str(y)] = g
            tf_res["groups"] = {k: stats(g["r"]) for k, g in groups.items()}
            tf_res["exit_types"] = t["exit_type"].value_counts().to_dict()
            lines += [HEADER] + [row_md(k, v) for k, v in tf_res["groups"].items()]
            lines += ["", f"Exit types: {tf_res['exit_types']}", ""]
            t.to_csv(OUT / f"trades_{tf}m.csv", index=False)
        lines += ["### Cost sensitivity", "", HEADER] + cost_rows + [""]
        results[f"{tf}m"] = tf_res
    (OUT / "results.json").write_text(json.dumps(results, indent=2, default=str))
    (OUT / "results.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
