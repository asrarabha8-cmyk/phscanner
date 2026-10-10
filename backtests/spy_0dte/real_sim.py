"""محاكي على أسعار عقود SPY 0DTE الحقيقية (شموع 5 دقائق من Polygon).
نفس واجهة research.simulate لكن السعر من data/options/<date>.csv.
- الدخول: افتتاح شمعة العقد عند وقت الدخول (أو آخر إغلاق قبله إن لم يكن فيها تداول) + انزلاق
- المسار: high/low/close لكل شمعة؛ الشمعة بلا تداول = آخر إغلاق
- يختار أقرب سترايك متوفر لسعر SPY عند الدخول؛ يتخطى الصفقة إن ابتعد أكثر من 1.5$
"""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
_cache = {}


def day_options(d):
    if d in _cache:
        return _cache[d]
    f = f"{HERE}/data/options/{d}.csv"
    if not os.path.exists(f):
        _cache[d] = None
        return None
    x = pd.read_csv(f)
    if len(x) == 0:
        _cache[d] = None
        return None
    dt = pd.to_datetime(x.t, unit="ms", utc=True).dt.tz_convert("America/New_York")
    x["hm"] = dt.dt.hour * 60 + dt.dt.minute
    _cache[d] = x
    return x


def contract_path(x, cp, k, grid_t):
    """يرجع o,h,l,c على شبكة أوقات اليوم (ffill للشموع الفارغة)"""
    s = x[(x.cp == cp) & (x.strike == k)].set_index("hm")[["o", "h", "l", "c"]]
    s = s[~s.index.duplicated()]
    s = s.reindex(grid_t)
    traded = s.c.notna().values
    c = s.c.ffill()
    o = s.o.fillna(c.shift()).fillna(c)
    h = s.h.fillna(c)
    l = s.l.fillna(c)
    return o.values, h.values, l.values, c.values, traded


def simulate_real(days, entries, tp=0.15, sl=0.25, exit_t=15 * 60 + 30, slip=0.02, comm=0.65,
                  budget=400.0, under_stop=True, max_per_day=2, stop_after_loss=True,
                  max_strike_gap=1.5, **_):
    out, skipped = [], 0
    for di, lst in entries.items():
        D = days[di]
        x = day_options(D["date"])
        if x is None:
            skipped += len(lst)
            continue
        t, c_u = D["t"], D["c"]
        n_done, busy_until = 0, -1
        for (bi, dr, lvl) in lst:
            if n_done >= max_per_day or bi <= busy_until or bi + 1 >= len(t):
                continue
            call = dr == 1
            cp = "C" if call else "P"
            e = bi + 1
            S0 = D["o"][e]
            ks = np.array(sorted(x[x.cp == cp].strike.unique()))
            if len(ks) == 0:
                skipped += 1; continue
            k = int(ks[np.argmin(np.abs(ks - S0))])
            if abs(k - S0) > max_strike_gap:
                skipped += 1; continue
            o, h, l, c, traded = contract_path(x, cp, k, t)
            if np.isnan(o[e]) or not traded[max(0, e - 2):e + 2].any():
                skipped += 1; continue            # عقد بلا سيولة حول وقت الدخول
            prem = float(o[e]) + slip
            if prem < 0.15:
                skipped += 1; continue
            qty = max(1, int(budget // (prem * 100)))
            hh, ll, cc = h[e:], l[e:], c[e:]
            n = len(cc)
            hit_sl = np.where(ll <= prem * (1 - sl))[0] if sl else np.array([], int)
            hit_tp = np.where(hh >= prem * (1 + tp))[0] if tp else np.array([], int)
            if lvl is not None and under_stop:
                cu = c_u[e:]
                brk = np.where(cu < lvl if call else cu > lvl)[0]
            else:
                brk = np.array([], int)
            tex = np.where(t[e:] >= exit_t)[0]
            cand = [(hit_sl[0] if len(hit_sl) else 10**9, 0, "SL"),
                    (hit_tp[0] if len(hit_tp) else 10**9, 1, "TP"),
                    (brk[0] if len(brk) else 10**9, 2, "STOP"),
                    (tex[0] if len(tex) else n - 1, 3, "TIME")]
            kk, _, why = min(cand, key=lambda z: (z[0], z[1]))
            kk = min(kk, n - 1)
            if why == "SL":
                # فجوة سعرية: إن افتتحت الشمعة تحت الوقف نخرج بسعر الافتتاح
                px = min(prem * (1 - sl), float(o[e + kk])) if kk > 0 else prem * (1 - sl)
            elif why == "TP":
                px = prem * (1 + tp)
            else:
                px = float(cc[kk])
            px = max(px - slip, 0.0)
            pnl = (px - prem) * 100 * qty - 2 * comm * qty
            out.append(dict(date=D["date"], t=int(t[e]), dir=dr, strike=k, prem=round(prem, 2),
                            exit=round(px, 2), qty=qty, why=why, ret=px / prem - 1, pnl=pnl))
            n_done += 1
            busy_until = e + kk
            if pnl < 0 and stop_after_loss:
                break
    df = pd.DataFrame(out)
    df.attrs["skipped"] = skipped
    return df
