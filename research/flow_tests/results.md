# Flow hypothesis tests

Run date: 2026-11-05. Rules were fixed before the run.
SPY data: 2021-11-11 to 2026-11-04, 1250 days.
SPY prices are split adjusted, without dividends.

## Last half hour

| Group | Trades | Win | Avg bps | Low 95% | Total bps | PF | Max DD bps |
|---|---|---|---|---|---|---|---|
| All | 567 | 46.6% | -0.81 | -2.94 | -461 | 0.91 | 1347 |
| First half | 283 | 53.0% | 1.26 | -2.11 | 356 | 1.13 | 531 |
| Second half | 284 | 40.1% | -2.88 | -5.46 | -816 | 0.68 | 896 |
| Long | 318 | 45.9% | -0.66 | -3.09 | -210 | 0.91 | 861 |
| Short | 249 | 47.4% | -1.01 | -4.73 | -251 | 0.91 | 564 |
| 2021 | 14 | 64.3% | 7.78 | -4.60 | 109 | 2.12 | 64 |
| 2022 | 114 | 57.9% | 3.85 | -2.93 | 440 | 1.33 | 205 |
| 2023 | 112 | 49.1% | 1.49 | -1.58 | 167 | 1.27 | 229 |
| 2024 | 112 | 50.9% | -2.67 | -7.54 | -299 | 0.73 | 466 |
| 2025 | 109 | 37.6% | -4.48 | -9.32 | -488 | 0.59 | 504 |
| 2026 | 106 | 34.0% | -3.68 | -6.76 | -390 | 0.54 | 390 |

Verdict: FAIL {'low95_above_zero': False, 'first_half_positive': True, 'second_half_positive': False, 'no_single_year_dominates': False, 'passed': False}

### Cost sensitivity

| Group | Trades | Win | Avg bps | Low 95% | Total bps | PF | Max DD bps |
|---|---|---|---|---|---|---|---|
| Cost 0.5 bps | 567 | 47.8% | -0.31 | -2.44 | -177 | 0.97 | 1148 |
| Cost 1.0 bps | 567 | 46.6% | -0.81 | -2.94 | -461 | 0.91 | 1347 |
| Cost 2.0 bps | 567 | 43.7% | -1.81 | -3.94 | -1028 | 0.81 | 1746 |

## Turn of month, excess over normal days

| Group | Trades | Win | Avg bps | Low 95% | Total bps | PF | Max DD bps |
|---|---|---|---|---|---|---|---|
| All | 60 | 51.7% | -0.65 | -47.03 | -39 | 0.99 | 1277 |
| First half | 30 | 50.0% | -18.44 | -86.54 | -553 | 0.78 | 826 |
| Second half | 30 | 53.3% | 17.13 | -45.19 | 514 | 1.3 | 1009 |
| 2021 | 2 | 0.0% | -221.41 | -275.51 | -443 | 0.0 | 443 |
| 2022 | 12 | 50.0% | -31.93 | -150.74 | -383 | 0.68 | 513 |
| 2023 | 12 | 58.3% | 28.74 | -79.06 | 345 | 1.45 | 430 |
| 2024 | 12 | 50.0% | -30.29 | -125.59 | -364 | 0.6 | 807 |
| 2025 | 12 | 50.0% | -7.33 | -80.74 | -88 | 0.86 | 433 |
| 2026 | 10 | 60.0% | 89.33 | -16.89 | 893 | 4.05 | 212 |

Verdict: FAIL {'low95_above_zero': False, 'first_half_positive': False, 'second_half_positive': True, 'no_single_year_dominates': False, 'passed': False}

### Cost sensitivity

| Group | Trades | Win | Avg bps | Low 95% | Total bps | PF | Max DD bps |
|---|---|---|---|---|---|---|---|
| Cost 0.5 bps | 60 | 53.3% | -0.15 | -46.53 | -9 | 1.0 | 1257 |
| Cost 1.0 bps | 60 | 51.7% | -0.65 | -47.03 | -39 | 0.99 | 1277 |
| Cost 2.0 bps | 60 | 51.7% | -1.65 | -48.03 | -99 | 0.98 | 1318 |

Raw average per trade: 17.7 bps.

## Loser reversal, excess over SPY

| Group | Trades | Win | Avg bps | Low 95% | Total bps | PF | Max DD bps |
|---|---|---|---|---|---|---|---|
| All | 409 | 44.3% | -38.76 | -77.30 | -15853 | 0.76 | 16574 |
| First half | 204 | 44.6% | -35.11 | -85.50 | -7162 | 0.77 | 10431 |
| Second half | 205 | 43.9% | -42.40 | -100.67 | -8692 | 0.75 | 8977 |
| 2021 | 5 | 40.0% | -123.28 | -377.50 | -616 | 0.29 | 646 |
| 2022 | 84 | 38.1% | -84.15 | -168.00 | -7069 | 0.55 | 8122 |
| 2023 | 83 | 47.0% | -1.62 | -76.16 | -134 | 0.99 | 4257 |
| 2024 | 84 | 51.2% | -35.61 | -102.86 | -2991 | 0.75 | 3649 |
| 2025 | 84 | 42.9% | -26.09 | -140.75 | -2192 | 0.86 | 3751 |
| 2026 | 69 | 42.0% | -41.31 | -124.48 | -2850 | 0.73 | 3970 |

Verdict: FAIL {'low95_above_zero': False, 'first_half_positive': False, 'second_half_positive': False, 'no_single_year_dominates': False, 'passed': False}

### Cost sensitivity

| Group | Trades | Win | Avg bps | Low 95% | Total bps | PF | Max DD bps |
|---|---|---|---|---|---|---|---|
| Cost 5.0 bps | 409 | 44.5% | -33.76 | -72.30 | -13808 | 0.79 | 14664 |
| Cost 10.0 bps | 409 | 44.3% | -38.76 | -77.30 | -15853 | 0.76 | 16574 |
| Cost 20.0 bps | 409 | 42.3% | -48.76 | -87.30 | -19943 | 0.71 | 20394 |

Raw average per trade: -31.5 bps.
