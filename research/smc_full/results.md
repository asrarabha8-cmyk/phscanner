# SMC daily full-market check

Run date: 2026-11-05. Rules were fixed before the run.
Common stocks in reference list: 11989. Tickers with bars: 8332.

## Part one: stored lookback signals

```
symbol,signal,status,reason,days,r
ACN,2026-10-01,closed,target,24,1.81
ADSK,2026-08-27,closed,stop,4,-1.03
COIN,2026-09-18,closed,stop,14,-1.01
CRL,2026-08-05,closed,time,40,0.42
CRWD,2026-09-14,open,last_bar,37,0.23
CSX,2026-07-23,closed,stop,28,-1.03
INCY,2026-07-28,closed,time,40,-0.31
JBHT,2026-07-16,closed,stop,9,-1.02
JKHY,2026-08-19,closed,stop,22,-1.03
MMM,2026-07-21,closed,time,40,-0.53
NET,2026-08-07,closed,time,40,1.41
NSC,2026-07-23,closed,stop,33,-1.02
NVDA,2026-08-27,closed,time,40,-0.84
RTX,2026-07-23,closed,stop,39,-1.02
RVTY,2026-09-15,closed,target,35,1.46
SNOW,2026-09-03,closed,stop,30,-1.01
URI,2026-07-23,closed,stop,25,-1.02
ZS,2026-09-14,closed,target,29,1.9
```

Closed: 17. Average R: -0.23. Wins: 29%.

## Part two: full market

Cancelled at the open: 4.
Exit reasons: {'stop': 563, 'time': 456, 'target': 208, 'last_bar': 15}. Median days: 27.

| Group | Trades | Win | Avg R | Low 95% | Total R | PF | Max DD R |
|---|---|---|---|---|---|---|---|
| Development | 905 | 42.0% | 0.001 | -0.082 | 0.9 | 1.0 | 84.3 |
| Dev first half | 452 | 37.6% | -0.114 | -0.222 | -51.4 | 0.79 | 84.3 |
| Dev second half | 453 | 46.4% | 0.115 | -0.009 | 52.3 | 1.23 | 59.1 |
| Dev scanner list | 100 | 52.0% | 0.457 | 0.147 | 45.7 | 2.03 | 9.7 |
| Dev other stocks | 805 | 40.7% | -0.056 | -0.14 | -44.8 | 0.9 | 95.6 |
| Holdout | 337 | 39.8% | 0.003 | -0.133 | 1.0 | 1.01 | 39.7 |
| Holdout scanner list | 27 | 40.7% | -0.088 | -0.526 | -2.4 | 0.85 | 10.3 |
| Dev 2022 | 137 | 29.2% | -0.367 | -0.548 | -50.2 | 0.46 | 53.8 |
| Dev 2023 | 227 | 40.1% | -0.046 | -0.2 | -10.3 | 0.91 | 38.2 |
| Dev 2024 | 287 | 47.4% | 0.124 | -0.033 | 35.7 | 1.25 | 18.4 |
| Dev 2025 | 254 | 44.5% | 0.102 | -0.06 | 25.8 | 1.2 | 41.0 |
| Dev random | 905 | 60.4% | 0.111 | 0.085 | 100.5 | 2.13 | 6.6 |
| Dev excess | 905 | 40.1% | -0.11 | -0.198 | -99.6 | 0.82 | 140.6 |
| Holdout random | 337 | 58.5% | 0.097 | 0.058 | 32.7 | 2.04 | 3.2 |
| Holdout excess | 337 | 36.2% | -0.094 | -0.239 | -31.7 | 0.85 | 66.2 |

Development verdict: FAIL {'low95_above_zero': False, 'first_half_positive': False, 'second_half_positive': True, 'no_single_year_dominates': False, 'beats_random': False, 'passed': False}
Holdout verdict: FAIL.
Final: FAIL.

Top symbols by total R: {'DELL': 7.8, 'SYM': 7.6, 'AMD': 5.9, 'AVAV': 5.5, 'FOLD': 5.5, 'MMSI': 5.2, 'AMPX': 5.1, 'HUT': 4.9, 'RKLB': 4.7, 'BKD': 4.6}
