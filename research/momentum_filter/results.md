# Momentum + VWAP screen test

Run date: 2026-11-23. Rules fixed before the run. Holdout from 2025-11-23.
Signals: 27893 on 986 days. Baseline stock-days: 2049873.

| Group | Count | Avg 5d | Avg 20d | Avg 60d | Median 20d | Reached +10% in 60d | +20% | +50% |
|---|---|---|---|---|---|---|---|---|
| Signals, development | 20612 | -0.02% | 0.87% | 2.77% | 0.28% | 54% | 28% | 6% |
| Signals, holdout | 7281 | 0.22% | 1.11% | 0.88% | 0.55% | 59% | 34% | 9% |
| Baseline, development | 1582448 | 0.16% | 0.89% | 2.86% | 0.43% | 51% | 25% | 5% |
| Baseline, holdout | 467425 | 0.25% | 0.92% | 1.57% | 0.21% | 54% | 30% | 7% |

+10% reached before -10% (signals with a full 60 days): 53% of 23930.

## 20-day excess over the baseline, averaged by signal day

| Group | Days | Avg excess | Low 95% | Days positive |
|---|---|---|---|---|
| Development | 796 | -0.26% | -0.62% | 48.5% |
| Dev first half | 398 | -0.73% | -1.23% | 44.5% |
| Dev second half | 398 | 0.21% | -0.32% | 52.5% |
| Holdout | 190 | 0.44% | -0.34% | 52.6% |
| Dev 2022 | 77 | -1.13% | -2.93% | 45.5% |
| Dev 2023 | 247 | -0.66% | -1.16% | 43.3% |
| Dev 2024 | 249 | -0.23% | -0.79% | 47.0% |
| Dev 2025 | 223 | 0.45% | -0.32% | 57.0% |

Verdict: FAIL.

## Day trading the next day (open to close)

| Group | Count | Avg open-to-close | Win | Avg best high | Avg worst low | High reached +3% | +5% |
|---|---|---|---|---|---|---|---|
| Signals, development | 20612 | -0.04% | 50% | 1.92% | -1.96% | 18% | 7% |
| Signals, holdout | 7281 | 0.10% | 51% | 2.44% | -2.31% | 26% | 12% |
| Baseline, development | 1582448 | 0.00% | 50% | 1.44% | -1.44% | 12% | 4% |
| Baseline, holdout | 467425 | 0.03% | 50% | 1.75% | -1.69% | 17% | 6% |

Day-trading excess over the baseline, averaged by signal day:

| Group | Days | Avg excess | Low 95% | Days positive |
|---|---|---|---|---|
| Development | 796 | -0.08% | -0.17% | 45.9% |
| Dev first half | 398 | -0.07% | -0.21% | 47.0% |
| Dev second half | 398 | -0.09% | -0.21% | 44.7% |
| Holdout | 190 | -0.03% | -0.18% | 46.8% |

Day-trading verdict: FAIL.

Most frequent symbols: RVMD (41), CLS (38), FTAI (37), ANET (36), APG (34), FROG (34), TMV (33), COPX (33), SLV (33), CRDO (32)
