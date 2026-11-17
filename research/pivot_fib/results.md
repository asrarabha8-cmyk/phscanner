# Fibonacci pivot points on SPY

Run date: 2026-11-17. Rules were fixed before the run.
Data: 2021-11-23 to 2026-11-16. Holdout from 2025-11-17. Results in SPY bps after 1 bp cost.

## A open side

| Group | Trades | Avg bps | Low 95% | Win | Total bps |
|---|---|---|---|---|---|
| Development | 506 | 0.14 | -2.43 | 55.1% | 70 |
| Dev first half | 253 | 2.02 | -2.01 | 56.1% | 512 |
| Dev second half | 253 | -1.75 | -4.92 | 54.2% | -442 |
| Dev long | 268 | 0.93 | -2.1 | 58.6% | 250 |
| Dev short | 238 | -0.76 | -5.03 | 51.3% | -181 |
| Holdout | 124 | -1.25 | -4.96 | 55.6% | -155 |

Exit reasons: {'target': 354, 'stop': 267, 'close': 9}.
Verdict: FAIL.

## B rejection

| Group | Trades | Avg bps | Low 95% | Win | Total bps |
|---|---|---|---|---|---|
| Development | 439 | -0.42 | -2.86 | 28.0% | -185 |
| Dev first half | 219 | -0.75 | -4.71 | 24.2% | -164 |
| Dev second half | 220 | -0.09 | -2.95 | 31.8% | -21 |
| Dev long | 218 | -2.55 | -5.58 | 27.5% | -557 |
| Dev short | 221 | 1.68 | -2.11 | 28.5% | 372 |
| Holdout | 105 | 1.3 | -2.1 | 37.1% | 136 |

Exit reasons: {'stop': 382, 'target': 156, 'close': 6}.
Verdict: FAIL.

## How often price reaches each level on the side of the first bar

| Level | Days reached |
|---|---|
| R1 | 89.1% |
| R2 | 69.6% |
| R3 | 38.4% |
| S1 | 86.4% |
| S2 | 69.2% |
| S3 | 42.9% |
