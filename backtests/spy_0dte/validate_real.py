"""التحقق النهائي على أسعار العقود الحقيقية: ORB15 الضيق (المرشح) مقابل ORB15 بدون فلتر."""
import numpy as np
import pandas as pd
from research import load, simulate, metrics, split
from real_sim import simulate_real
import strategies as S

days = load()
pd.set_option("display.width", 230)
cands = {
    "ORB15 بدون فلتر": S.orb(days, 15, last_entry=12 * 60, stop="mid"),
    "ORB15 ضيق (المرشح)": S.orb_narrow(days),
}
settings = [dict(tp=0, sl=0.25, exit_t=930), dict(tp=0, sl=0.35, exit_t=930),
            dict(tp=0, sl=0.25, exit_t=780), dict(tp=1.0, sl=0.4, exit_t=930)]
rows, keep = [], {}
for name, E in cands.items():
    for st in settings:
        for slip in (0.01, 0.02, 0.03):
            tr = simulate_real(days, E, slip=slip, **st)
            mod = simulate(days, E, iv_mult=0.43, slip=slip, **st)
            a, b = split(tr)
            m, ma, mb = metrics(tr), metrics(a), metrics(b)
            rows.append(dict(strategy=name, tp=st["tp"], sl=st["sl"], exit=st["exit_t"] // 60 * 100 + st["exit_t"] % 60,
                             slip=slip, n=m.get("n"), skipped=tr.attrs["skipped"], win=m.get("win"),
                             avg_ret=m.get("avg_ret"), pf=m.get("pf"), pnl=m.get("pnl"), mdd=m.get("mdd"),
                             train_pf=ma.get("pf"), test_pf=mb.get("pf"), model_pf=metrics(mod).get("pf")))
            if st == settings[0] and slip == 0.02:
                keep[name] = tr
R = pd.DataFrame(rows)
R.to_csv("results/real_validation.csv", index=False)
print(R.to_string(index=False))
for name, tr in keep.items():
    tr = tr.copy()
    tr["q"] = pd.to_datetime(tr.date).dt.to_period("Q").astype(str)
    print("\n", name, "— by quarter (sl25, noTP, exit 15:30, slip .02)")
    print(tr.groupby("q").agg(n=("pnl", "size"), pnl=("pnl", "sum"),
                              win=("pnl", lambda x: (x > 0).mean() * 100)).round(0).T.to_string())
    s = mx = 0
    for v in (tr.pnl <= 0):
        s = s + 1 if v else 0
        mx = max(mx, s)
    top5 = tr.pnl.nlargest(5).sum() / tr.pnl.sum() * 100 if tr.pnl.sum() > 0 else float("nan")
    print("max losing streak", mx, "| top-5 share of profit %", round(top5), "| exits", tr.why.value_counts().to_dict())
    tr.to_csv(f"results/real_trades_{'narrow' if 'ضيق' in name else 'all'}.csv", index=False)
