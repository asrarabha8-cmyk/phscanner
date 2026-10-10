# SPY 0DTE — Opening Range Breakout with a compression filter

Validated on **real SPY 0DTE contract prices** (Polygon 5-minute bars) from Oct 2024 to Oct 2026. Training: up to Jan 31 2026. Untouched test period: Feb 1 2026 onward.

## The rules
1. **Opening range:** the high and low of the first 15 minutes (9:30–9:45 New York time).
2. **Compression filter:** trade only if that range (as a % of the open price) is **less than 0.8× its average over the previous 20 days**. Otherwise no trading that day.
3. **Entry:** first 5-minute close above the range high = ATM Call. Below the range low = ATM Put. Enter on the open of the next candle. Last entry time 12:00. **One trade per day.**
4. **Strike:** nearest dollar to SPY's price at entry (ATM), expiring the same day.
5. **Stop:** −35% of the contract price.
6. **Target:** none fixed. Let the trade run.
7. **Exit:** at 13:00 New York time at the latest (8:00 pm Riyadh), or at the stop.
8. **Size:** $200 per trade (~1 contract, 5% of a $4,000 account).

## Results on real prices ($200 per trade, slippage $0.02 per side + $0.65 commission)
| | Trades | Win rate | Profit factor | Net P&L | Max drawdown |
|---|---|---|---|---|---|
| Strategy (with filter) | 204 | 32% | 1.74 | +$5,649 | −$746 |
| ORB without filter (comparison) | 495 | 27% | 1.11 | +$2,609 | −$3,003 |

- 8 of 9 quarters positive. Profit factor in the test period: about 2.
- Average winner is ~3.7× the average loser. Longest losing streak: 10 trades.
- The 5 best trades make up ~65% of the profit. The edge is real but **lumpy**.

## Caveats
- The final settings (−35% stop, 13:00 exit) were chosen after seeing results. That's mild selection bias. But all 12 settings tested on real prices came out positive.
- Prices are 5-minute trade bars, not bid/ask quotes. Real fills may be slightly worse.
- Next step: a forward paper test for 4–6 weeks before using real money.

## Files
- `research.py` — data loading + model engine (Black-Scholes calibrated at 0.43×VIX on a trading-time basis)
- `real_sim.py` — simulator on real contract prices
- `strategies.py` — entry signal generators
- `explore.py`, `explore2.py` — the search grid
- `validate_real.py` — final validation
- `fetch_data.py`, `fetch_targets.py`, `fetch_options.py` — Polygon data pulls (5 requests/minute)
- `results/` — results and trade logs
