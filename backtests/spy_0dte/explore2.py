import itertools, numpy as np, pandas as pd
from research import load, simulate, metrics, split
import strategies as S
days=load()
# مؤشرات يومية للفلاتر
vol15=np.array([D["v"][:3].sum() for D in days]); rv20=pd.Series(vol15).rolling(20).mean().shift(1).values
rng15=np.array([(D["h"][:3].max()-D["l"][:3].min())/D["o"][0] for D in days]); rr20=pd.Series(rng15).rolling(20).mean().shift(1).values
gap=np.array([D["o"][0]/D["pc"]-1 for D in days])
def filt(E, kind):
    out={}
    for di,l in E.items():
        dr=l[0][1]
        ok={"none":True,
            "rvol1.5": rv20[di]==rv20[di] and vol15[di]>1.5*rv20[di],
            "rvol1.2": rv20[di]==rv20[di] and vol15[di]>1.2*rv20[di],
            "narrow": rr20[di]==rr20[di] and rng15[di]<0.8*rr20[di],
            "wide": rr20[di]==rr20[di] and rng15[di]>1.2*rr20[di],
            "gap_with": np.sign(gap[di])==dr and abs(gap[di])>0.002,
            "gap_against": np.sign(gap[di])==-dr and abs(gap[di])>0.002,
            "vix_hi": days[di]["iv"]>0.18, "vix_lo": days[di]["iv"]<=0.18}[kind]
        if ok: out[di]=l
    return out
rows=[]
for mins,last in itertools.product([5,15,30],[11*60,12*60]):
    base=S.orb(days,mins,last_entry=last,stop="mid")
    for kind in ["none","rvol1.5","rvol1.2","narrow","wide","gap_with","gap_against","vix_hi","vix_lo"]:
        E=filt(base,kind)
        for tp,sl in itertools.product([0,1.0],[0.25,0.4]):
            tr=simulate(days,E,tp=tp,sl=sl,exit_t=930,iv_mult=0.43)
            a,b=split(tr); m=metrics(a,f"orb{mins}_{last//60}_{kind}"); mb=metrics(b)
            m.update(tp=tp,sl=sl,test_n=mb.get("n"),test_win=mb.get("win"),test_avg=mb.get("avg_ret"),test_pf=mb.get("pf"),test_pnl=mb.get("pnl"))
            rows.append(m)
R=pd.DataFrame(rows); R.to_csv("explore2_results.csv",index=False)
R=R[R.n>=40]
pd.set_option("display.width",230)
print("train top 20:"); print(R.sort_values("pf",ascending=False).head(20).to_string(index=False))
print("\nfilters averaged across settings (train pf / test pf):")
R["filter"]=R.label.str.split("_",n=2).str[2]
print(R.groupby("filter")[["pf","test_pf"]].median().round(2).sort_values("pf",ascending=False).to_string())
