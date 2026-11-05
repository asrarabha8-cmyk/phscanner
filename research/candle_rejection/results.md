# Rejection-candle backtest on SPY

Run date: 2026-11-05. Rules and pass criteria were fixed before the run.

## 3 minutes

Data: 2021-11-11 to 2026-11-04, 1250 days.

| Group | Trades | Win | Avg R | Low 95% | Total R | PF | Max DD R |
|---|---|---|---|---|---|---|---|
| All base signals | 9121 | 40.7% | -0.135 | -0.16 | -1233.4 | 0.79 | 1240.2 |
| Hammer | 1392 | 42.9% | -0.087 | -0.145 | -121.3 | 0.85 | 129.0 |
| No hammer | 7729 | 40.3% | -0.144 | -0.171 | -1112.1 | 0.78 | 1118.7 |
| Hammer tops | 514 | 41.2% | -0.154 | -0.247 | -79.1 | 0.73 | 80.2 |
| Hammer bottoms | 878 | 43.8% | -0.048 | -0.122 | -42.2 | 0.91 | 62.5 |
| Hammer first hour | 247 | 43.3% | -0.028 | -0.175 | -6.9 | 0.95 | 25.6 |
| Hammer rest of day | 1145 | 42.8% | -0.1 | -0.163 | -114.3 | 0.82 | 120.7 |
| Hammer first half | 696 | 43.1% | -0.081 | -0.163 | -56.6 | 0.85 | 63.9 |
| Hammer second half | 696 | 42.7% | -0.093 | -0.176 | -64.7 | 0.84 | 71.9 |
| Hammer 2021 | 50 | 38.0% | -0.197 | -0.49 | -9.9 | 0.67 | 10.6 |
| Hammer 2022 | 226 | 42.5% | -0.061 | -0.203 | -13.8 | 0.89 | 25.3 |
| Hammer 2023 | 271 | 42.8% | -0.091 | -0.222 | -24.5 | 0.84 | 33.2 |
| Hammer 2024 | 302 | 41.4% | -0.153 | -0.277 | -46.1 | 0.75 | 48.7 |
| Hammer 2025 | 292 | 43.2% | -0.066 | -0.194 | -19.1 | 0.88 | 30.1 |
| Hammer 2026 | 251 | 45.8% | -0.031 | -0.168 | -7.9 | 0.94 | 16.6 |

Verdict: FAIL {'low95_above_zero': False, 'first_half_positive': False, 'second_half_positive': False, 'no_single_year_dominates': False, 'passed': False}

### Hammer cost sensitivity

| Group | Trades | Win | Avg R | Low 95% | Total R | PF | Max DD R |
|---|---|---|---|---|---|---|---|
| Cost $0.02 | 1392 | 43.1% | -0.034 | -0.092 | -47.0 | 0.94 | 67.4 |
| Cost $0.05 | 1392 | 42.9% | -0.087 | -0.145 | -121.3 | 0.85 | 129.0 |
| Cost $0.10 | 1392 | 42.0% | -0.176 | -0.234 | -245.2 | 0.71 | 246.0 |

## 5 minutes

Data: 2021-11-11 to 2026-11-04, 1250 days.

| Group | Trades | Win | Avg R | Low 95% | Total R | PF | Max DD R |
|---|---|---|---|---|---|---|---|
| All base signals | 5422 | 40.5% | -0.117 | -0.147 | -631.9 | 0.81 | 658.6 |
| Hammer | 911 | 46.2% | -0.002 | -0.07 | -1.6 | 1.0 | 32.5 |
| No hammer | 4511 | 39.3% | -0.14 | -0.174 | -630.3 | 0.78 | 646.2 |
| Hammer tops | 358 | 46.1% | 0.006 | -0.103 | 2.1 | 1.01 | 20.9 |
| Hammer bottoms | 553 | 46.3% | -0.007 | -0.094 | -3.6 | 0.99 | 22.4 |
| Hammer first hour | 242 | 46.7% | 0.051 | -0.094 | 12.3 | 1.1 | 13.3 |
| Hammer rest of day | 669 | 46.0% | -0.021 | -0.097 | -13.9 | 0.95 | 34.6 |
| Hammer first half | 455 | 46.4% | -0.012 | -0.106 | -5.4 | 0.97 | 30.8 |
| Hammer second half | 456 | 46.1% | 0.008 | -0.09 | 3.8 | 1.02 | 22.0 |
| Hammer 2021 | 37 | 56.8% | 0.294 | -0.034 | 10.9 | 1.89 | 3.9 |
| Hammer 2022 | 132 | 47.0% | -0.027 | -0.199 | -3.6 | 0.94 | 15.0 |
| Hammer 2023 | 208 | 44.7% | -0.036 | -0.174 | -7.5 | 0.92 | 15.8 |
| Hammer 2024 | 189 | 43.9% | -0.028 | -0.183 | -5.3 | 0.95 | 18.4 |
| Hammer 2025 | 191 | 48.2% | 0.037 | -0.115 | 7.0 | 1.08 | 17.3 |
| Hammer 2026 | 154 | 45.5% | -0.019 | -0.185 | -3.0 | 0.96 | 9.1 |

Verdict: FAIL {'low95_above_zero': False, 'first_half_positive': False, 'second_half_positive': True, 'no_single_year_dominates': False, 'passed': False}

### Hammer cost sensitivity

| Group | Trades | Win | Avg R | Low 95% | Total R | PF | Max DD R |
|---|---|---|---|---|---|---|---|
| Cost $0.02 | 911 | 47.1% | 0.039 | -0.029 | 35.2 | 1.08 | 19.1 |
| Cost $0.05 | 911 | 46.2% | -0.002 | -0.07 | -1.6 | 1.0 | 32.5 |
| Cost $0.10 | 911 | 45.4% | -0.069 | -0.137 | -62.9 | 0.87 | 78.8 |
