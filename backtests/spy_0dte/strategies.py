"""مولّدات إشارات الدخول. كل دالة: days -> {day_index: [(bar_i, dir, stop_level|None), ...]}"""
import numpy as np
from research import ema_np, bar_at


def _hm(h, m):
    return h * 60 + m


def orb(days, minutes=15, last_entry=_hm(12, 0), stop="mid", only=None):
    """اختراق نطاق الافتتاح: إغلاق شمعة 5د فوق/تحت النطاق"""
    E = {}
    nb = minutes // 5
    for di, D in enumerate(days):
        hi, lo = D["h"][:nb].max(), D["l"][:nb].min()
        mid = (hi + lo) / 2
        for i in range(nb, len(D["t"])):
            if D["t"][i] > last_entry:
                break
            dr = 1 if D["c"][i] > hi else (-1 if D["c"][i] < lo else 0)
            if dr and (only is None or dr == only):
                lvl = mid if stop == "mid" else (lo if dr == 1 else hi) if stop == "range" else None
                E[di] = [(i, dr, lvl)]
                break
    return E


def gap(days, th=0.004, mode="fade", confirm=True, entry=_hm(9, 35), only=None):
    """فجوة الافتتاح: fade = عكس الفجوة، go = مع الفجوة. confirm = أول شمعة بنفس الاتجاه المطلوب"""
    E = {}
    for di, D in enumerate(days):
        g = D["o"][0] / D["pc"] - 1
        if abs(g) < th:
            continue
        dr = -np.sign(g) if mode == "fade" else np.sign(g)
        i = bar_at(D["t"], entry) - 1
        i = max(i, 0)
        if confirm:
            move = D["c"][i] - D["o"][0]
            if np.sign(move) != dr:
                continue
        if only is not None and dr != only:
            continue
        lvl = D["h"][:i + 1].max() if dr == -1 else D["l"][:i + 1].min()
        E[di] = [(i, int(dr), lvl)]
    return E


def intraday_momentum(days, th=0.003, signal_end=_hm(10, 0), entry=_hm(15, 0), ref="prev_close", only=None):
    """زخم اليوم (Gao et al.): عائد أول نصف ساعة يتنبأ بآخر جزء من الجلسة"""
    E = {}
    for di, D in enumerate(days):
        k = bar_at(D["t"], signal_end) - 1
        base = D["pc"] if ref == "prev_close" else D["o"][0]
        r = D["c"][k] / base - 1
        if abs(r) < th:
            continue
        dr = int(np.sign(r))
        i = bar_at(D["t"], entry) - 1
        # تأكيد: السعر عند الدخول في نفس الجهة من VWAP
        if np.sign(D["c"][i] - D["vwap"][i]) != dr:
            continue
        if only is not None and dr != only:
            continue
        E[di] = [(i, dr, None)]
    return E


def trend_day(days, check=_hm(10, 30), th=0.003, only=None):
    """يوم ترند: عند 10:30 السعر بعيد عن الافتتاح وفوق/تحت VWAP طوال الساعة"""
    E = {}
    for di, D in enumerate(days):
        k = bar_at(D["t"], check) - 1
        r = D["c"][k] / D["o"][0] - 1
        if abs(r) < th:
            continue
        dr = int(np.sign(r))
        seg = (D["c"][:k + 1] - D["vwap"][:k + 1]) * dr
        if (seg[3:] <= 0).any():
            continue
        if only is not None and dr != only:
            continue
        E[di] = [(k, dr, D["o"][0])]
    return E


def vwap_pullback(days, start=_hm(10, 0), end=_hm(14, 0), only=None):
    """إشارة A من الاختبار الأول (EMA مستمرة عبر الأيام)"""
    closes = np.concatenate([D["c"] for D in days])
    e9, e21 = ema_np(closes, 9), ema_np(closes, 21)
    E, off = {}, 0
    for di, D in enumerate(days):
        n = len(D["t"])
        a9, a21 = e9[off:off + n], e21[off:off + n]
        off += n
        lst = []
        for i in range(1, n):
            if not (start <= D["t"][i] <= end):
                continue
            c, o, lo, hi, vw = D["c"][i], D["o"][i], D["l"][i], D["h"][i], D["vwap"][i]
            if c > vw and a9[i] > a21[i] and lo <= max(a21[i], vw) * 1.0005 and c > a9[i] and c > o:
                dr = 1
            elif c < vw and a9[i] < a21[i] and hi >= min(a21[i], vw) * 0.9995 and c < a9[i] and c < o:
                dr = -1
            else:
                continue
            if only is None or dr == only:
                lst.append((i, dr, vw))
        if lst:
            E[di] = lst
    return E


def random_entries(days, seed=0, start=_hm(10, 0), end=_hm(14, 0)):
    """خط أساس: دخول عشوائي — يقيس كم تأكل التكاليف والتآكل"""
    rng = np.random.default_rng(seed)
    E = {}
    for di, D in enumerate(days):
        idx = np.where((D["t"] >= start) & (D["t"] <= end))[0]
        E[di] = [(int(rng.choice(idx)), int(rng.choice([-1, 1])), None)]
    return E
