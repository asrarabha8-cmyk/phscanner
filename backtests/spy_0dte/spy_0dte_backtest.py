"""
SPY 0DTE Backtest — مقارنة 3 إشارات:
  A) VWAP/EMA  : ارتداد إلى EMA21/VWAP في اتجاه الترند
  B) QQE MOD   : انقلاب لون QQE
  C) COMBO     : إشارة A بشرط أن QQE في نفس الاتجاه

قواعد مشتركة:
  - الدخول 10:00–14:00 نيويورك، على افتتاح الشمعة التالية
  - السترايك ATM (أقرب دولار)، عقد 0DTE
  - هدف +15% / وقف -25% على سعر العقد / كسر VWAP بإغلاق شمعة / خروج إجباري 15:30
  - حد أقصى صفقتين يوميًا، والتوقف بعد أول خسارة
  - فلتر اليوم العرضي: 3 عبورات VWAP أو أكثر قبل 10:30 = لا تداول
تسعير العقد: Black-Scholes مع VIX كتقلب ضمني (تقريب، ليس أسعار عقود حقيقية).

التشغيل:
  pip install yfinance pandas numpy scipy matplotlib
  python spy_0dte_backtest.py                 # آخر 60 يوم بفريم 5 دقائق من Yahoo
  python spy_0dte_backtest.py --csv spy5m.csv # بيانات أطول من مصدر آخر
     (أعمدة: datetime,open,high,low,close,volume — التوقيت بتوقيت نيويورك)
"""
import argparse
import math
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

# ---------------- الإعدادات ----------------
CFG = dict(
    capital=4000.0,
    alloc_pct=0.10,         # نسبة الحساب لكل صفقة
    tp=0.15, sl=-0.25,
    entry_start="10:00", entry_end="14:00", force_exit="15:30",
    chop_check="10:30", chop_crosses=3,
    max_trades_day=2, stop_after_loss=True,
    slip=0.02,              # انزلاق لكل جانب للعقد ($ لكل سهم)
    commission=0.65,        # لكل عقد لكل جانب
    iv_mult=1.0,            # مضاعف على VIX لتقريب تقلب 0DTE
    rate=0.04,
)


# ---------------- البيانات ----------------

def load_polygon(key, days=365):
    """SPY 5m من Polygon — سنة كاملة، شهر لكل طلب (حد 5 طلبات/دقيقة في الخطة المجانية)"""
    import time, requests
    end = pd.Timestamp.now(tz="America/New_York").normalize()
    start = end - pd.Timedelta(days=days)
    frames, cur = [], start
    while cur < end:
        nxt = min(cur + pd.Timedelta(days=30), end)
        url = (f"https://api.polygon.io/v2/aggs/ticker/SPY/range/5/minute/"
               f"{cur.date()}/{nxt.date()}?adjusted=true&sort=asc&limit=50000&apiKey={key}")
        for attempt in range(3):
            r = requests.get(url, timeout=30)
            if r.status_code == 429:
                time.sleep(15); continue
            break
        j = r.json()
        if j.get("results"):
            frames.append(pd.DataFrame(j["results"]))
        else:
            print("Polygon:", j.get("status"), j.get("message", "")[:120])
        cur = nxt + pd.Timedelta(days=1)
        time.sleep(13)
    if not frames:
        return None
    d = pd.concat(frames).drop_duplicates("t")
    d.index = pd.to_datetime(d.t, unit="ms", utc=True).dt.tz_convert("America/New_York")
    d = d.rename(columns=dict(o="open", h="high", l="low", c="close", v="volume"))
    print(f"مصدر البيانات: Polygon ({d.index[0].date()} → {d.index[-1].date()})")
    return d[["open", "high", "low", "close", "volume"]]

def load_data(csv=None):
    if csv:
        df = pd.read_csv(csv, parse_dates=["datetime"]).set_index("datetime")
        if df.index.tz is None:
            df.index = df.index.tz_localize("America/New_York")
        df.columns = [c.lower() for c in df.columns]
        vix = None
    else:
        import os
        import yfinance as yf
        key = os.environ.get("POLYGON_API_KEY", "").strip()
        df = load_polygon(key) if key else None
        if df is None or df.empty:
            print("مصدر البيانات: Yahoo (آخر 60 يوم)")
            df = yf.download("SPY", interval="5m", period="60d", progress=False, auto_adjust=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [c.lower() for c in df.columns]
            df.index = df.index.tz_convert("America/New_York")
        v = yf.download("^VIX", period="1y", interval="1d", progress=False)
        if isinstance(v.columns, pd.MultiIndex):
            v.columns = v.columns.get_level_values(0)
        vix = v["Close"]
        vix.index = pd.to_datetime(vix.index).date
    df = df.between_time("09:30", "15:55")[["open", "high", "low", "close", "volume"]].dropna()
    df["date"] = df.index.date
    if vix is not None:
        prev = vix.shift(1)  # VIX إغلاق اليوم السابق (بدون نظر للمستقبل)
        df["iv"] = df["date"].map(prev).astype(float).ffill().fillna(18.0) / 100
    else:
        df["iv"] = 0.18
    df["iv"] *= CFG["iv_mult"]
    return df


# ---------------- المؤشرات ----------------
def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def rsi(s, n):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def qqe_mod(close, rsi_len=6, sf=5, qqe=3.0, thresh=3.0):
    """QQE MOD (النسخة الأساسية): يرجع +1 أخضر / -1 أحمر / 0 رمادي"""
    rsima = ema(rsi(close, rsi_len), sf)
    atr_rsi = rsima.diff().abs()
    dar = ema(ema(atr_rsi, rsi_len * 2 - 1), rsi_len * 2 - 1) * qqe
    r, d = rsima.values, dar.values
    lb = np.zeros(len(r)); sb = np.zeros(len(r)); trend = np.ones(len(r)); fast = np.zeros(len(r))
    for i in range(1, len(r)):
        if np.isnan(r[i]) or np.isnan(d[i]):
            continue
        nl, ns = r[i] - d[i], r[i] + d[i]
        lb[i] = max(lb[i-1], nl) if (r[i-1] > lb[i-1] and r[i] > lb[i-1]) else nl
        sb[i] = min(sb[i-1], ns) if (r[i-1] < sb[i-1] and r[i] < sb[i-1]) else ns
        if r[i] > sb[i-1] and r[i-1] <= sb[i-1]:
            trend[i] = 1
        elif r[i] < lb[i-1] and r[i-1] >= lb[i-1]:
            trend[i] = -1
        else:
            trend[i] = trend[i-1]
        fast[i] = lb[i] if trend[i] == 1 else sb[i]
    state = np.where((r - 50 > thresh) & (r > fast), 1, np.where((r - 50 < -thresh) & (r < fast), -1, 0))
    return pd.Series(state, index=close.index)


def add_indicators(df):
    out = []
    for _, g in df.groupby("date"):
        g = g.copy()
        tp = (g.high + g.low + g.close) / 3
        g["vwap"] = (tp * g.volume).cumsum() / g.volume.replace(0, np.nan).cumsum()
        g["vwap"] = g["vwap"].ffill().fillna(g.close)
        side = np.sign(g.close - g.vwap)
        crosses = (side != side.shift()).astype(int).iloc[1:].cumsum().reindex(g.index).fillna(0)
        chk = g.between_time("09:30", CFG["chop_check"])
        n_cross = int(crosses.loc[chk.index].max()) if len(chk) else 0
        g["chop_day"] = n_cross >= CFG["chop_crosses"]
        out.append(g)
    df = pd.concat(out)
    # EMA وQQE مستمرة عبر الأيام (كما في TradingView)
    df["ema9"], df["ema21"] = ema(df.close, 9), ema(df.close, 21)
    df["qqe"] = qqe_mod(df.close)
    return df


# ---------------- الإشارات ----------------
def signals(df):
    up = (df.close > df.vwap) & (df.ema9 > df.ema21)
    dn = (df.close < df.vwap) & (df.ema9 < df.ema21)
    lvl_up = np.maximum(df.ema21, df.vwap)
    lvl_dn = np.minimum(df.ema21, df.vwap)
    pull_up = (df.low <= lvl_up * 1.0005) & (df.close > df.ema9) & (df.close > df.open)
    pull_dn = (df.high >= lvl_dn * 0.9995) & (df.close < df.ema9) & (df.close < df.open)
    a = np.where(up & pull_up, 1, np.where(dn & pull_dn, -1, 0))
    q = df.qqe
    b = np.where((q == 1) & (q.shift() != 1), 1, np.where((q == -1) & (q.shift() != -1), -1, 0))
    c = np.where((a == 1) & (q == 1), 1, np.where((a == -1) & (q == -1), -1, 0))
    return {"A_VWAP_EMA": pd.Series(a, df.index),
            "B_QQE": pd.Series(b, df.index),
            "C_COMBO": pd.Series(c, df.index)}


# ---------------- تسعير العقد ----------------
def bs(S, K, minutes_left, iv, call):
    T = max(minutes_left, 1) / (252 * 390)
    sd = iv * math.sqrt(T)
    d1 = (math.log(S / K) + (CFG["rate"] + iv * iv / 2) * T) / sd
    d2 = d1 - sd
    if call:
        return S * norm.cdf(d1) - K * math.exp(-CFG["rate"] * T) * norm.cdf(d2)
    return K * math.exp(-CFG["rate"] * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def mins_to_close(ts, bar_end=False):
    m = (16 * 60) - (ts.hour * 60 + ts.minute) - (5 if bar_end else 0)
    return max(m, 1)


# ---------------- المحرك ----------------
def run(df, sig, name):
    t_s, t_e = pd.to_datetime(CFG["entry_start"]).time(), pd.to_datetime(CFG["entry_end"]).time()
    t_x = pd.to_datetime(CFG["force_exit"]).time()
    equity, trades = CFG["capital"], []
    for day, g in df.groupby("date"):
        if g.chop_day.iloc[0]:
            continue
        idx, n_today, i = g.index, 0, 0
        while i < len(g) - 1:
            ts = idx[i]
            s = sig.loc[ts]
            if not (s != 0 and t_s <= ts.time() <= t_e and n_today < CFG["max_trades_day"]):
                i += 1
                continue
            call = s == 1
            e_bar = g.iloc[i + 1]
            S0, iv = e_bar.open, e_bar.iv
            K = round(S0)
            prem = bs(S0, K, mins_to_close(idx[i + 1]), iv, call) + CFG["slip"]
            if prem < 0.10:
                i += 1
                continue
            qty = max(1, int(equity * CFG["alloc_pct"] // (prem * 100)))
            exit_px, reason, j = None, None, i + 1
            while j < len(g):
                b, tb = g.iloc[j], idx[j]
                m = mins_to_close(tb, bar_end=True)
                worst = bs(b.low if call else b.high, K, m, iv, call)
                best = bs(b.high if call else b.low, K, m, iv, call)
                if worst <= prem * (1 + CFG["sl"]):          # الوقف أولًا (تحفّظ)
                    exit_px, reason = prem * (1 + CFG["sl"]), "SL"; break
                if best >= prem * (1 + CFG["tp"]):
                    exit_px, reason = prem * (1 + CFG["tp"]), "TP"; break
                closed_px = bs(b.close, K, m, iv, call)
                if (call and b.close < b.vwap) or (not call and b.close > b.vwap):
                    exit_px, reason = closed_px, "VWAP"; break
                if tb.time() >= t_x:
                    exit_px, reason = closed_px, "TIME"; break
                j += 1
            if exit_px is None:
                exit_px, reason = bs(g.iloc[-1].close, K, 1, iv, call), "EOD"
            exit_px = max(exit_px - CFG["slip"], 0.0)
            pnl = (exit_px - prem) * 100 * qty - 2 * CFG["commission"] * qty
            equity += pnl
            trades.append(dict(strategy=name, date=day, entry_time=idx[i + 1].strftime("%H:%M"),
                               type="Call" if call else "Put", strike=K, entry=round(prem, 2),
                               exit=round(exit_px, 2), qty=qty, reason=reason,
                               ret_pct=round((exit_px / prem - 1) * 100, 2),
                               pnl=round(pnl, 2), equity=round(equity, 2)))
            n_today += 1
            if pnl < 0 and CFG["stop_after_loss"]:
                break
            i = j + 1
    return pd.DataFrame(trades)


def stats(t):
    if t.empty:
        return dict(trades=0)
    w, l = t[t.pnl > 0], t[t.pnl <= 0]
    eq = pd.concat([pd.Series([CFG["capital"]]), t.equity])
    dd = ((eq - eq.cummax()) / eq.cummax()).min() * 100
    pf = w.pnl.sum() / abs(l.pnl.sum()) if len(l) and l.pnl.sum() != 0 else float("inf")
    return dict(trades=len(t), win_rate=round(len(w) / len(t) * 100, 1),
                net_pnl=round(t.pnl.sum(), 2),
                total_return=round((t.equity.iloc[-1] / CFG["capital"] - 1) * 100, 2),
                profit_factor=round(pf, 2), avg_win=round(w.pnl.mean(), 2) if len(w) else 0,
                avg_loss=round(l.pnl.mean(), 2) if len(l) else 0, max_dd=round(dd, 2),
                exits=dict(t.reason.value_counts()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    a = ap.parse_args()
    df = add_indicators(load_data(a.csv))
    days = df.date.nunique()
    print(f"البيانات: {days} يوم تداول | {df.index[0]} → {df.index[-1]}")
    print(f"أيام عرضية مستبعدة: {df.groupby('date').chop_day.first().sum()}\n")
    all_t, rows = [], []
    for name, s in signals(df).items():
        t = run(df, s, name)
        all_t.append(t)
        st = stats(t); st["strategy"] = name; rows.append(st)
    summary = pd.DataFrame(rows).set_index("strategy")
    pd.set_option("display.width", 200)
    print(summary.to_string())
    trades = pd.concat(all_t) if any(len(t) for t in all_t) else pd.DataFrame()
    trades.to_csv("spy_0dte_trades.csv", index=False)
    summary.to_csv("spy_0dte_summary.csv")
    import os
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("## SPY 0DTE backtest\n\n" + summary.drop(columns=["exits"], errors="ignore").to_markdown() + "\n")
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 5))
        for t in all_t:
            if len(t):
                ax.plot(range(len(t) + 1), [CFG["capital"]] + list(t.equity), label=t.strategy.iloc[0])
        ax.axhline(CFG["capital"], color="gray", lw=0.8, ls="--")
        ax.set_title("SPY 0DTE – Equity by signal"); ax.set_xlabel("Trade #"); ax.set_ylabel("$")
        ax.legend(); fig.tight_layout(); fig.savefig("spy_0dte_equity.png", dpi=120)
    except Exception as e:
        print("chart skipped:", e)
    print("\nالملفات: spy_0dte_summary.csv, spy_0dte_trades.csv, spy_0dte_equity.png")


if __name__ == "__main__":
    sys.exit(main())
