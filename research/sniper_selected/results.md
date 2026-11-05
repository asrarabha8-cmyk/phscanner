# Options Sniper on selected stocks

Run date: 2026-11-05. Rules were fixed before the run.
Picks: 12290. Fetch status: {'ok': 12290}.

| Group | Trades | Win | Avg R | Low 95% | Total R | PF | Max DD R |
|---|---|---|---|---|---|---|---|
| Development | 2142 | 40.5% | -0.026 | -0.075 | -55.6 | 0.95 | 85.6 |
| Dev first half | 1071 | 41.8% | 0.006 | -0.064 | 6.0 | 1.01 | 28.9 |
| Dev second half | 1071 | 39.1% | -0.058 | -0.126 | -61.6 | 0.89 | 83.8 |
| Holdout | 533 | 41.5% | -0.062 | -0.156 | -32.9 | 0.88 | 48.7 |
| Dev 2021 | 27 | 40.7% | 0.021 | -0.412 | 0.6 | 1.04 | 6.3 |
| Dev 2022 | 568 | 42.3% | 0.02 | -0.078 | 11.1 | 1.04 | 17.1 |
| Dev 2023 | 522 | 41.8% | 0.004 | -0.095 | 2.2 | 1.01 | 23.1 |
| Dev 2024 | 565 | 38.4% | -0.08 | -0.173 | -45.0 | 0.85 | 69.0 |
| Dev 2025 | 460 | 39.3% | -0.053 | -0.158 | -24.5 | 0.9 | 41.0 |
| Dev random | 2142 | 71.2% | 0.38 | 0.353 | 814.4 | 4.43 | 5.0 |
| Dev excess | 2142 | 29.0% | -0.406 | -0.452 | -870.0 | 0.41 | 871.2 |
| Holdout random | 533 | 61.4% | 0.282 | 0.226 | 150.2 | 2.9 | 3.3 |
| Holdout excess | 533 | 28.3% | -0.344 | -0.43 | -183.1 | 0.44 | 183.5 |

Development verdict: FAIL {'low95_above_zero': False, 'first_half_positive': True, 'second_half_positive': False, 'no_single_year_dominates': False, 'beats_random': False, 'passed': False}
Holdout verdict: FAIL.
Final: FAIL.

Top symbols by total R: {'GME': 12.2, 'OKLO': 9.2, 'DJT': 7.4, 'AFRM': 6.3, 'NKLA': 6.2, 'SYM': 6.2, 'LUNR': 5.1, 'ZS': 5.0, 'GTLB': 4.9, 'SERV': 4.7}

### Cost sensitivity, development

| Group | Trades | Win | Avg R | Low 95% | Total R | PF | Max DD R |
|---|---|---|---|---|---|---|---|
| Cost 2.0 bps | 2142 | 41.2% | 0.0 | -0.049 | 0.8 | 1.0 | 66.3 |
| Cost 5.0 bps | 2142 | 40.5% | -0.026 | -0.075 | -55.6 | 0.95 | 85.6 |
| Cost 10.0 bps | 2142 | 39.6% | -0.07 | -0.119 | -149.7 | 0.87 | 158.7 |
