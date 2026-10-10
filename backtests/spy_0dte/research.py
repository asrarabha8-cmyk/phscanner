"""
محرك بحث سريع لاستراتيجيات SPY 0DTE.
- يقرأ data/spy_5m.csv و data/vix_daily.csv
- كل استراتيجية = دالة ترجع قائمة دخول: (يوم، رقم الشمعة، اتجاه +1 Call / -1 Put، مستوى إبطال اختياري)
- الخروج: هدف/وقف على سعر العقد، وقف زمني، ووقف سعري اختياري على SPY
- التسعير: Black-Scholes بتقلب = VIX إغلاق اليوم السابق × مضاعف
- التقسيم: تدريب حتى 2026-01-31، اختبار من 2026-02-01 (لا يُستخدم في الضبط)
"""
import math
import numpy as np
import pandas as pd
from scipy.special import ndtr

HERE = __file__.rsplit("/", 1)[0] if "/" in __file__ else "."
SPLIT = pd.Timestamp("2026-02-01").date()
RATE = 0.04


def load():
    df = pd.read_csv(f"{HERE}/data/spy_5m.csv", parse_dates=["datetime"])
    df["datetime"] = pd.to_datetime(df.datetime, utc=True).dt.tz_convert("America/New_York")
    df = df.set_index("datetime")
    vix = pd.read_csv(f"{HERE}/data/vix_daily.csv", parse_dates=["Date"]).set_index("Date")
    vix.index = vix.index.date
    prev_close = vix.Close.shift(1)
    days = []
    for d, g in df.groupby(df.index.date):
        if len(g) < 70:          # أيام ناقصة/نصف يوم
            continue
        t = g.index.hour * 60 + g.index.minute
        tp = (g.high + g.low + g.close) / 3
        vwap = (tp * g.volume).cumsum() / g.volume.cumsum().replace(0, np.nan)
        iv = prev_close.get(d, np.nan)
        days.append(dict(date=d, t=t.values, o=g.open.values, h=g.high.values, l=g.low.values,
                         c=g.close.values, v=g.volume.values, vwap=vwap.ffill().values,
                         iv=float(iv) / 100 if not np.isnan(iv) else 0.17))
    for i in range(1, len(days)):
        days[i]["pc"] = days[i - 1]["c"][-1]           # إغلاق اليوم السابق
    days[0]["pc"] = days[0]["o"][0]
    return days


def bs_vec(S, K, mins, iv, call):
    T = np.maximum(mins, 1.0) / (252 * 390)
    sd = iv * np.sqrt(T)
    d1 = (np.log(S / K) + (RATE + iv * iv / 2) * T) / sd
    d2 = d1 - sd
    disc = np.exp(-RATE * T)
    if call:
        return S * ndtr(d1) - K * disc * ndtr(d2)
    return K * disc * ndtr(-d2) - S * ndtr(-d1)


def simulate(days, entries, tp=0.15, sl=0.25, exit_t=15 * 60 + 30, iv_mult=1.0,
             slip=0.02, comm=0.65, otm=0, budget=400.0, under_stop=True, max_per_day=2,
             stop_after_loss=True):
    """entries: dict date_index -> list of (bar_i, dir, stop_level|None) مرتبة زمنيًا"""
    out = []
    for di, lst in entries.items():
        D = days[di]
        t, o, h, l, c = D["t"], D["o"], D["h"], D["l"], D["c"]
        iv = D["iv"] * iv_mult
        n_done, busy_until = 0, -1
        for (bi, dr, lvl) in lst:
            if n_done >= max_per_day or bi <= busy_until or bi + 1 >= len(t):
                continue
            call = dr == 1
            e = bi + 1
            S0 = o[e]
            K = round(S0) + (otm if call else -otm)
            m0 = 16 * 60 - t[e]
            prem = float(bs_vec(S0, K, m0, iv, call)) + slip
            if prem < 0.15:
                continue
            qty = max(1, int(budget // (prem * 100)))
            rng = slice(e, len(t))
            mins = 16 * 60 - t[rng] - 5
            fav = h[rng] if call else l[rng]
            adv = l[rng] if call else h[rng]
            best = bs_vec(fav, K, mins, iv, call)
            worst = bs_vec(adv, K, mins, iv, call)
            close_px = bs_vec(c[rng], K, mins, iv, call)
            n = len(best)
            hit_sl = np.where(worst <= prem * (1 - sl))[0] if sl else np.array([], int)
            hit_tp = np.where(best >= prem * (1 + tp))[0] if tp else np.array([], int)
            if lvl is not None and under_stop:
                cc = c[rng]
                brk = np.where(cc < lvl if call else cc > lvl)[0]
            else:
                brk = np.array([], int)
            tex = np.where(t[rng] >= exit_t)[0]
            cand = [(hit_sl[0] if len(hit_sl) else 10**9, 0, "SL"),
                    (hit_tp[0] if len(hit_tp) else 10**9, 1, "TP"),
                    (brk[0] if len(brk) else 10**9, 2, "STOP"),
                    (tex[0] if len(tex) else n - 1, 3, "TIME")]
            k, _, why = min(cand, key=lambda x: (x[0], x[1]))
            k = min(k, n - 1)
            if why == "SL":
                px = prem * (1 - sl)
            elif why == "TP":
                px = prem * (1 + tp)
            else:
                px = float(close_px[k])
            px = max(px - slip, 0.0)
            pnl = (px - prem) * 100 * qty - 2 * comm * qty
            out.append(dict(date=D["date"], t=int(t[e]), dir=dr, prem=round(prem, 2), exit=round(px, 2),
                            qty=qty, why=why, ret=px / prem - 1, pnl=pnl))
            n_done += 1
            busy_until = e + k
            if pnl < 0 and stop_after_loss:
                break
    return pd.DataFrame(out)


def metrics(tr, label=""):
    if tr is None or len(tr) == 0:
        return dict(label=label, n=0)
    w = tr.pnl > 0
    gl = -tr.pnl[~w].sum()
    return dict(label=label, n=len(tr), win=round(w.mean() * 100, 1),
                avg_ret=round(tr.ret.mean() * 100, 2),
                pf=round(tr.pnl[w].sum() / gl, 2) if gl > 0 else 99,
                pnl=round(tr.pnl.sum(), 0),
                mdd=round(max_dd(tr.pnl.values), 0))


def max_dd(p):
    eq = np.cumsum(p)
    return float((eq - np.maximum.accumulate(np.concatenate([[0], eq]))[1:]).min()) if len(p) else 0.0


def split(tr):
    if len(tr) == 0:
        return tr, tr
    return tr[tr.date < SPLIT], tr[tr.date >= SPLIT]


# ---------------- مؤشرات مساعدة ----------------
def ema_np(x, n):
    a, out = 2 / (n + 1), np.empty_like(x)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def bar_at(t, hhmm):
    return int(np.searchsorted(t, hhmm))
