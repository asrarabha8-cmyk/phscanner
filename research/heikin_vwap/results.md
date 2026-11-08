# VWAP + Heikin Ashi backtest

Run date: 2026-11-08. Rules were fixed before the run.

## 3 minutes

Median bars held: 12.

| Group | Trades | Win | Avg R | Low 95% | Total R | PF | Max DD R |
|---|---|---|---|---|---|---|---|
| Development | 2358 | 27.8% | -0.096 | -0.158 | -225.7 | 0.84 | 248.2 |
| Dev first half | 1179 | 27.4% | -0.057 | -0.148 | -67.4 | 0.9 | 91.3 |
| Dev second half | 1179 | 28.2% | -0.134 | -0.221 | -158.3 | 0.78 | 174.6 |
| Dev SPY | 1191 | 26.1% | -0.106 | -0.198 | -126.8 | 0.83 | 129.9 |
| Dev QQQ | 1167 | 29.6% | -0.085 | -0.17 | -98.9 | 0.85 | 127.4 |
| Dev 2021 | 82 | 26.8% | -0.201 | -0.493 | -16.5 | 0.68 | 25.6 |
| Dev 2022 | 570 | 28.2% | -0.002 | -0.136 | -1.2 | 1.0 | 42.4 |
| Dev 2023 | 586 | 26.8% | -0.11 | -0.234 | -64.5 | 0.82 | 101.9 |
| Dev 2024 | 608 | 28.9% | -0.072 | -0.204 | -44.0 | 0.88 | 79.7 |
| Dev 2025 | 512 | 27.3% | -0.194 | -0.313 | -99.5 | 0.68 | 103.7 |
| Holdout | 552 | 27.0% | -0.161 | -0.283 | -88.7 | 0.72 | 99.6 |
| Dev random | 2358 | 34.4% | -0.101 | -0.116 | -238.8 | 0.45 | 239.3 |
| Dev excess | 2358 | 31.3% | 0.006 | -0.059 | 13.1 | 1.01 | 74.2 |
| Holdout excess | 552 | 31.7% | -0.012 | -0.137 | -6.6 | 0.98 | 42.4 |

Development: FAIL {'low95_above_zero': False, 'first_half_positive': False, 'second_half_positive': False, 'no_single_year_dominates': False, 'beats_random': False, 'passed': False}
Holdout: FAIL. Final: FAIL.

### Cost sensitivity, development

| Group | Trades | Win | Avg R | Low 95% | Total R | PF | Max DD R |
|---|---|---|---|---|---|---|---|
| Cost 1.0 bps | 2358 | 28.7% | -0.037 | -0.1 | -87.6 | 0.93 | 140.3 |
| Cost 2.0 bps | 2358 | 27.8% | -0.096 | -0.158 | -225.7 | 0.84 | 248.2 |
| Cost 5.0 bps | 2358 | 25.3% | -0.271 | -0.335 | -640.0 | 0.63 | 640.6 |

## 5 minutes

Median bars held: 12.

| Group | Trades | Win | Avg R | Low 95% | Total R | PF | Max DD R |
|---|---|---|---|---|---|---|---|
| Development | 1582 | 35.2% | -0.024 | -0.086 | -38.7 | 0.95 | 110.2 |
| Dev first half | 791 | 36.9% | 0.079 | -0.015 | 62.5 | 1.18 | 17.3 |
| Dev second half | 791 | 33.5% | -0.128 | -0.206 | -101.2 | 0.75 | 102.5 |
| Dev SPY | 801 | 34.6% | -0.061 | -0.146 | -48.8 | 0.88 | 72.4 |
| Dev QQQ | 781 | 35.9% | 0.013 | -0.075 | 10.1 | 1.03 | 62.4 |
| Dev 2021 | 58 | 24.1% | -0.186 | -0.502 | -10.8 | 0.69 | 12.6 |
| Dev 2022 | 328 | 38.7% | 0.129 | -0.013 | 42.4 | 1.31 | 15.3 |
| Dev 2023 | 422 | 36.7% | 0.057 | -0.073 | 24.2 | 1.12 | 17.3 |
| Dev 2024 | 423 | 32.4% | -0.132 | -0.242 | -55.6 | 0.75 | 67.8 |
| Dev 2025 | 351 | 35.3% | -0.111 | -0.224 | -38.8 | 0.77 | 39.8 |
| Holdout | 376 | 30.9% | -0.109 | -0.218 | -41.2 | 0.76 | 45.1 |
| Dev random | 1582 | 33.5% | -0.089 | -0.104 | -141.3 | 0.43 | 141.3 |
| Dev excess | 1582 | 37.3% | 0.065 | 0.002 | 102.6 | 1.15 | 54.7 |
| Holdout excess | 376 | 35.4% | -0.017 | -0.136 | -6.5 | 0.96 | 24.5 |

Development: FAIL {'low95_above_zero': False, 'first_half_positive': True, 'second_half_positive': False, 'no_single_year_dominates': False, 'beats_random': True, 'passed': False}
Holdout: FAIL. Final: FAIL.

### Cost sensitivity, development

| Group | Trades | Win | Avg R | Low 95% | Total R | PF | Max DD R |
|---|---|---|---|---|---|---|---|
| Cost 1.0 bps | 1582 | 35.7% | 0.02 | -0.042 | 30.9 | 1.04 | 73.4 |
| Cost 2.0 bps | 1582 | 35.2% | -0.024 | -0.086 | -38.7 | 0.95 | 110.2 |
| Cost 5.0 bps | 1582 | 32.2% | -0.156 | -0.218 | -247.4 | 0.73 | 264.0 |

## 15 minutes

Median bars held: 7.

| Group | Trades | Win | Avg R | Low 95% | Total R | PF | Max DD R |
|---|---|---|---|---|---|---|---|
| Development | 659 | 41.4% | 0.014 | -0.048 | 9.5 | 1.05 | 23.5 |
| Dev first half | 329 | 41.6% | 0.029 | -0.061 | 9.4 | 1.1 | 9.7 |
| Dev second half | 330 | 41.2% | 0.0 | -0.087 | 0.1 | 1.0 | 23.5 |
| Dev SPY | 313 | 41.9% | -0.002 | -0.093 | -0.5 | 0.99 | 19.9 |
| Dev QQQ | 346 | 41.0% | 0.029 | -0.057 | 10.1 | 1.1 | 8.2 |
| Dev 2021 | 16 | 50.0% | 0.1 | -0.175 | 1.6 | 1.52 | 1.1 |
| Dev 2022 | 148 | 45.3% | 0.075 | -0.052 | 11.1 | 1.29 | 6.0 |
| Dev 2023 | 180 | 40.0% | 0.014 | -0.114 | 2.6 | 1.05 | 9.7 |
| Dev 2024 | 173 | 36.4% | -0.086 | -0.191 | -14.8 | 0.73 | 23.2 |
| Dev 2025 | 142 | 44.4% | 0.064 | -0.087 | 9.1 | 1.21 | 6.1 |
| Holdout | 193 | 30.1% | -0.164 | -0.263 | -31.7 | 0.55 | 34.6 |
| Dev random | 659 | 38.7% | -0.031 | -0.047 | -20.4 | 0.65 | 22.4 |
| Dev excess | 659 | 44.5% | 0.045 | -0.018 | 30.0 | 1.16 | 16.9 |
| Holdout excess | 193 | 35.8% | -0.115 | -0.216 | -22.2 | 0.66 | 24.6 |

Development: FAIL {'low95_above_zero': False, 'first_half_positive': True, 'second_half_positive': True, 'no_single_year_dominates': False, 'beats_random': False, 'passed': False}
Holdout: FAIL. Final: FAIL.

### Cost sensitivity, development

| Group | Trades | Win | Avg R | Low 95% | Total R | PF | Max DD R |
|---|---|---|---|---|---|---|---|
| Cost 1.0 bps | 659 | 42.6% | 0.038 | -0.025 | 24.7 | 1.13 | 19.9 |
| Cost 2.0 bps | 659 | 41.4% | 0.014 | -0.048 | 9.5 | 1.05 | 23.5 |
| Cost 5.0 bps | 659 | 38.5% | -0.055 | -0.118 | -36.0 | 0.84 | 50.6 |
