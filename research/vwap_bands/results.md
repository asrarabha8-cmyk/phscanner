# SPY VWAP bands on real option contracts

Run date: 2026-11-08. Rules were fixed before the run.
Signals: 844 from 2024-12-16 to 2026-11-03.

## Expiry 0 trading days

Not fetched yet: 0. Skipped for no trading or price under 0.10: 0.

### revert

| Group | Trades | Win | Avg return | Low 95% | Profit | PF |
|---|---|---|---|---|---|---|
| Development | 309 | 35.6% | -7.3% | -11.3% | -3649$ | 0.56 |
| Dev first half | 154 | 35.1% | -7.8% | -12.8% | -2136$ | 0.51 |
| Dev second half | 155 | 36.1% | -6.8% | -12.9% | -1513$ | 0.62 |
| Dev calls | 150 | 42.7% | -4.2% | -9.4% | -1127$ | 0.7 |
| Dev puts | 159 | 28.9% | -10.3% | -16.2% | -2522$ | 0.45 |
| Test | 122 | 34.4% | -7.9% | -13.6% | -1354$ | 0.56 |
Development profit with 0.03 more slippage per side: -5503$.
Exit reasons: {'stop': 216, 'target': 213, 'time': 2}.
Verdict: FAIL.

### breakout

| Group | Trades | Win | Avg return | Low 95% | Profit | PF |
|---|---|---|---|---|---|---|
| Development | 297 | 21.2% | -6.2% | -13.0% | -3940$ | 0.63 |
| Dev first half | 148 | 23.0% | -7.5% | -16.2% | -2603$ | 0.55 |
| Dev second half | 149 | 19.5% | -5.0% | -15.4% | -1337$ | 0.73 |
| Dev calls | 151 | 21.9% | -5.0% | -14.5% | -1491$ | 0.69 |
| Dev puts | 146 | 20.5% | -7.5% | -17.3% | -2449$ | 0.59 |
| Test | 116 | 26.7% | -7.1% | -14.1% | -1407$ | 0.56 |
Development profit with 0.03 more slippage per side: -5722$.
Exit reasons: {'fade': 314, 'stop': 85, 'time': 14}.
Verdict: FAIL.

## Expiry 1 trading days

Not fetched yet: 0. Skipped for no trading or price under 0.10: 0.

### revert

| Group | Trades | Win | Avg return | Low 95% | Profit | PF |
|---|---|---|---|---|---|---|
| Development | 309 | 34.0% | -4.5% | -6.4% | -4449$ | 0.48 |
| Dev first half | 154 | 33.8% | -4.8% | -7.3% | -2513$ | 0.45 |
| Dev second half | 155 | 34.2% | -4.2% | -6.9% | -1936$ | 0.53 |
| Dev calls | 150 | 42.0% | -2.9% | -5.4% | -1421$ | 0.62 |
| Dev puts | 159 | 26.4% | -6.0% | -8.7% | -3027$ | 0.38 |
| Test | 122 | 36.1% | -4.5% | -7.4% | -1517$ | 0.51 |
Development profit with 0.03 more slippage per side: -6303$.
Exit reasons: {'stop': 216, 'target': 213, 'time': 2}.
Verdict: FAIL.

### breakout

| Group | Trades | Win | Avg return | Low 95% | Profit | PF |
|---|---|---|---|---|---|---|
| Development | 297 | 23.2% | -4.4% | -7.7% | -4956$ | 0.56 |
| Dev first half | 148 | 24.3% | -5.5% | -9.8% | -3305$ | 0.46 |
| Dev second half | 149 | 22.1% | -3.3% | -8.2% | -1651$ | 0.68 |
| Dev calls | 151 | 25.8% | -3.0% | -7.3% | -1761$ | 0.64 |
| Dev puts | 146 | 20.5% | -6.0% | -10.8% | -3195$ | 0.5 |
| Test | 116 | 32.8% | -4.1% | -7.4% | -1457$ | 0.54 |
Development profit with 0.03 more slippage per side: -6738$.
Exit reasons: {'fade': 314, 'stop': 85, 'time': 14}.
Verdict: FAIL.

## Expiry 5 trading days

Not fetched yet: 0. Skipped for no trading or price under 0.10: 19.

### revert

| Group | Trades | Win | Avg return | Low 95% | Profit | PF |
|---|---|---|---|---|---|---|
| Development | 304 | 28.6% | -3.0% | -4.0% | -6000$ | 0.37 |
| Dev first half | 152 | 28.9% | -3.3% | -4.7% | -3460$ | 0.32 |
| Dev second half | 152 | 28.3% | -2.7% | -4.0% | -2541$ | 0.42 |
| Dev calls | 147 | 32.0% | -2.4% | -3.6% | -2285$ | 0.44 |
| Dev puts | 157 | 25.5% | -3.6% | -5.1% | -3715$ | 0.31 |
| Test | 117 | 30.8% | -3.5% | -4.9% | -2378$ | 0.33 |
Development profit with 0.03 more slippage per side: -7824$.
Exit reasons: {'stop': 212, 'target': 207, 'time': 2}.
Verdict: FAIL.

### breakout

| Group | Trades | Win | Avg return | Low 95% | Profit | PF |
|---|---|---|---|---|---|---|
| Development | 292 | 23.3% | -3.3% | -4.8% | -6098$ | 0.47 |
| Dev first half | 146 | 23.3% | -4.4% | -6.2% | -4102$ | 0.32 |
| Dev second half | 146 | 23.3% | -2.2% | -4.6% | -1996$ | 0.64 |
| Dev calls | 148 | 25.0% | -2.4% | -4.0% | -2018$ | 0.57 |
| Dev puts | 144 | 21.5% | -4.4% | -6.8% | -4081$ | 0.41 |
| Test | 112 | 31.2% | -2.8% | -4.5% | -1869$ | 0.46 |
Development profit with 0.03 more slippage per side: -7850$.
Exit reasons: {'fade': 306, 'stop': 84, 'time': 14}.
Verdict: FAIL.
