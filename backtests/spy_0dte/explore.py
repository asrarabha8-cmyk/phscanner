import itertools, time, pandas as pd
from research import load, simulate, metrics, split
import strategies as S
days = load()
print(len(days), "days", days[0]["date"], days[-1]["date"])
H = lambda h,m: h*60+m
gens = {
 "random": lambda: S.random_entries(days),
 "vwap_pb": lambda: S.vwap_pullback(days),
 "orb15": lambda: S.orb(days,15), "orb30": lambda: S.orb(days,30),
 "orb15_nostop": lambda: S.orb(days,15,stop=None),
 "gapfade.3": lambda: S.gap(days,0.003,"fade"), "gapfade.6": lambda: S.gap(days,0.006,"fade"),
 "gapgo.3": lambda: S.gap(days,0.003,"go"), "gapgo.6": lambda: S.gap(days,0.006,"go"),
 "mom1500.2": lambda: S.intraday_momentum(days,0.002), "mom1500.4": lambda: S.intraday_momentum(days,0.004),
 "mom1400.3": lambda: S.intraday_momentum(days,0.003,entry=H(14,0)),
 "mom1200.3": lambda: S.intraday_momentum(days,0.003,entry=H(12,0)),
 "trend1030.3": lambda: S.trend_day(days,th=0.003), "trend1030.5": lambda: S.trend_day(days,th=0.005),
}
grid = dict(tp=[0.15,0.3,0.5,1.0,0], sl=[0.25,0.4,0.6], exit_t=[H(15,30),H(15,50)])
rows=[]; t0=time.time()
for name,g in gens.items():
    E=g()
    for tp,sl,ex in itertools.product(*grid.values()):
        tr=simulate(days,E,tp=tp,sl=sl,exit_t=ex)
        a,b=split(tr); m=metrics(a,name); m.update(tp=tp,sl=sl,ex=ex//60*100+ex%60)
        mb=metrics(b); m.update(test_n=mb.get("n"),test_pf=mb.get("pf"),test_avg=mb.get("avg_ret"))
        rows.append(m)
R=pd.DataFrame(rows); R.to_csv("explore_results.csv",index=False)
print(f"{len(R)} configs in {time.time()-t0:.0f}s")
pd.set_option("display.width",220)
best=R[R.n>=40].sort_values("pf",ascending=False).groupby("label").head(1)
print(best[["label","n","win","avg_ret","pf","pnl","mdd","tp","sl","ex"]].to_string(index=False))
