# RSI on SPY next-day options

Run date: 2026-11-21. Rules were fixed before the run. Test from 2026-05-23.
Days planned: 480. Dollars per one contract after costs.

## V1 contract

| Group | Trades | Win | Avg | Low 95% | Total |
|---|---|---|---|---|---|
| Development | 483 | 40.0% | -12.8$ | -23.0$ | -6192$ |
| Dev first half | 241 | 39.8% | -12.6$ | -28.0$ | -3035$ |
| Dev second half | 242 | 40.1% | -13.0$ | -26.3$ | -3157$ |
| Calls (dev) | 238 | 41.6% | -13.6$ | -28.3$ | -3227$ |
| Puts (dev) | 245 | 38.4% | -12.1$ | -26.1$ | -2965$ |
| Test | 167 | 34.7% | -19.4$ | -31.2$ | -3232$ |
| Random entries (all) | 654 | 33.3% | -43.1$ | -51.5$ | -28160$ |

With 0.03 more slippage per side: average -20.5$.
Verdict: FAIL.

## V2 stock

| Group | Trades | Win | Avg | Low 95% | Total |
|---|---|---|---|---|---|
| Development | 403 | 37.5% | -12.1$ | -21.5$ | -4888$ |
| Dev first half | 201 | 36.8% | -9.8$ | -24.1$ | -1976$ |
| Dev second half | 202 | 38.1% | -14.4$ | -26.7$ | -2913$ |
| Calls (dev) | 190 | 39.5% | -11.6$ | -25.5$ | -2196$ |
| Puts (dev) | 213 | 35.7% | -12.6$ | -25.3$ | -2693$ |
| Test | 141 | 34.8% | -19.2$ | -32.7$ | -2706$ |
| Random entries (all) | 545 | 31.2% | -48.5$ | -57.9$ | -26411$ |

With 0.03 more slippage per side: average -20.0$.
Verdict: FAIL.

## V3 both

| Group | Trades | Win | Avg | Low 95% | Total |
|---|---|---|---|---|---|
| Development | 395 | 37.5% | -12.8$ | -22.0$ | -5048$ |
| Dev first half | 197 | 35.5% | -12.8$ | -26.8$ | -2518$ |
| Dev second half | 198 | 39.4% | -12.8$ | -24.9$ | -2530$ |
| Calls (dev) | 184 | 39.1% | -14.7$ | -28.5$ | -2711$ |
| Puts (dev) | 211 | 36.0% | -11.1$ | -23.5$ | -2337$ |
| Test | 140 | 35.0% | -17.4$ | -30.2$ | -2442$ |
| Random entries (all) | 553 | 31.5% | -51.5$ | -61.9$ | -28455$ |

With 0.03 more slippage per side: average -20.0$.
Verdict: FAIL.

## V4 decay-free

| Group | Trades | Win | Avg | Low 95% | Total |
|---|---|---|---|---|---|
| Development | 450 | 39.1% | -14.3$ | -24.3$ | -6450$ |
| Dev first half | 225 | 37.3% | -13.9$ | -29.0$ | -3137$ |
| Dev second half | 225 | 40.9% | -14.7$ | -27.9$ | -3313$ |
| Calls (dev) | 222 | 41.0% | -13.0$ | -27.7$ | -2886$ |
| Puts (dev) | 228 | 37.3% | -15.6$ | -29.3$ | -3564$ |
| Test | 158 | 36.1% | -16.1$ | -28.9$ | -2548$ |
| Random entries (all) | 612 | 34.8% | -42.3$ | -51.0$ | -25895$ |

With 0.03 more slippage per side: average -20.8$.
Verdict: FAIL.
