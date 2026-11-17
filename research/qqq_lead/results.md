# QQQ leadership rule

Run date: 2026-11-17. Rules were fixed before the run.
Data: 2021-11-23 to 2026-11-16, 1240 days. Holdout from 2025-11-17.
Returns are SPY basis points signed by the favored direction (1 bp = 0.01%).

## Part A: does QQQ's lead predict SPY's next move?

### SPY next 30 minutes

| Group | Days | Checks | Avg bps | Low 95% | Right direction |
|---|---|---|---|---|---|
| Loose rule, development | 991 | 5946 | 0.68 | 0.05 | 51.3% |
| Loose rule, dev first half | 495 | 2970 | 0.96 | -0.01 | 52.1% |
| Loose rule, dev second half | 496 | 2976 | 0.4 | -0.4 | 50.5% |
| Loose rule, holdout | 249 | 1494 | -0.31 | -1.13 | 48.9% |
| Strict rule, development | 930 | 4019 | -0.65 | -1.57 | 52.3% |
| Strict rule, holdout | 235 | 1024 | -2.0 | -3.39 | 49.1% |
| SPY own move, development | 991 | 5935 | 0.37 | -0.26 | 51.8% |
| SPY own move, holdout | 249 | 1494 | -0.39 | -1.25 | 49.8% |
| Disagree subset, development | 667 | 1927 | 1.58 | 0.15 | 49.2% |
| Disagree subset, holdout | 156 | 470 | 1.4 | -0.75 | 48.3% |
| Lead >= 0.10%, development | 959 | 4537 | -0.01 | -0.8 | 52.0% |
| Lead >= 0.10%, holdout | 238 | 1128 | -0.81 | -1.83 | 50.0% |
| Loose rule, 2021 | 26 | 156 | -0.81 | -3.49 | 48.7% |
| Loose rule, 2022 | 250 | 1500 | 1.69 | 0.01 | 53.1% |
| Loose rule, 2023 | 248 | 1488 | 0.39 | -0.5 | 51.3% |
| Loose rule, 2024 | 249 | 1494 | 0.98 | 0.23 | 52.1% |
| Loose rule, 2025 | 218 | 1308 | -0.32 | -1.91 | 48.6% |

### SPY to 15:55

| Group | Days | Checks | Avg bps | Low 95% | Right direction |
|---|---|---|---|---|---|
| Loose rule, development | 991 | 5946 | 4.68 | 1.79 | 53.9% |
| Loose rule, dev first half | 495 | 2970 | 6.78 | 2.57 | 55.7% |
| Loose rule, dev second half | 496 | 2976 | 2.58 | -1.36 | 52.0% |
| Loose rule, holdout | 249 | 1494 | 2.31 | -1.44 | 51.7% |
| Strict rule, development | 930 | 4019 | -0.08 | -3.32 | 54.6% |
| Strict rule, holdout | 235 | 1024 | -3.01 | -7.38 | 49.9% |
| SPY own move, development | 991 | 5935 | 2.16 | -0.57 | 52.3% |
| SPY own move, holdout | 249 | 1494 | -0.1 | -3.25 | 48.1% |
| Disagree subset, development | 667 | 1927 | 7.51 | 2.63 | 52.4% |
| Disagree subset, holdout | 156 | 470 | 7.93 | 0.6 | 55.7% |
| Lead >= 0.10%, development | 959 | 4537 | 3.17 | -0.01 | 55.3% |
| Lead >= 0.10%, holdout | 238 | 1128 | 0.54 | -3.66 | 52.0% |
| Loose rule, 2021 | 26 | 156 | -0.02 | -19.18 | 56.4% |
| Loose rule, 2022 | 250 | 1500 | 11.17 | 4.09 | 57.7% |
| Loose rule, 2023 | 248 | 1488 | 2.05 | -2.03 | 53.4% |
| Loose rule, 2024 | 249 | 1494 | 3.6 | -0.09 | 52.9% |
| Loose rule, 2025 | 218 | 1308 | 2.0 | -5.8 | 50.8% |

### Control for SPY's own move

Regression of SPY's next 30 minutes on QQQ's lead and on SPY's own move since open,
with errors grouped by day. A real QQQ effect needs a positive lead coefficient.

| Sample | Lead coef (bps per 1% lead) | t | SPY move coef | t |
|---|---|---|---|---|
| Development | 2.19 | 1.63 | 0.59 | 0.42 |
| Holdout | -1.31 | -0.96 | -0.17 | -0.17 |

Verdict for the rule as a direction signal: FAIL.

## Part B: filter on the SPY 0DTE opening-range trades

| Group | Trades | Win | Avg profit | Total profit |
|---|---|---|---|---|
| All trades | 204 | 32.4% | 27.7$ | 5649$ |
| Rule agrees | 128 | 33.6% | 41.3$ | 5291$ |
| Rule says skip | 76 | 30.3% | 4.7$ | 358$ |

Difference in average profit (agree minus skip): 36.6$, 95% range -5.7$ to 78.9$.
