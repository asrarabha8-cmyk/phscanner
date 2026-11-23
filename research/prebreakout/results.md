# Pre-breakout filters

Run date: 2026-11-23. Rules fixed before the run. Holdout from 2025-11-23.
Baseline stock-days: 1937187 (40,000 sampled for the +20%/-10% race).

| Filter | Group | Signals | +20% before -10% | Avg 20d | Avg 60d | Median 60d |
|---|---|---|---|---|---|---|
| Baseline | development | 30365 | 32.9% | 0.84% | 2.87% | 1.43% |
| Baseline | holdout | 9635 | 34.2% | 1.11% | 2.04% | -0.02% |
| A squeeze near highs | development | 4546 | 29.8% | 0.38% | 1.08% | 0.27% |
| A squeeze near highs | holdout | 1137 | 21.4% | 0.05% | -3.99% | -0.10% |
| B dry-up then pocket pivot | development | 4904 | 31.8% | 0.83% | 2.57% | 1.34% |
| B dry-up then pocket pivot | holdout | 1803 | 29.4% | 0.95% | 0.31% | -0.18% |
| C quiet accumulation | development | 48382 | 27.3% | 0.57% | 1.70% | 0.65% |
| C quiet accumulation | holdout | 11618 | 21.5% | 0.13% | 0.23% | -0.06% |
| D leader in tight base | development | 22651 | 35.6% | 1.02% | 3.95% | 2.23% |
| D leader in tight base | holdout | 1663 | 26.9% | 0.38% | -1.94% | -0.27% |

## 60-day excess over the baseline, averaged by signal day

| Filter | Dev days | Dev avg | Dev low 95% | Half 1 | Half 2 | Holdout avg | Verdict |
|---|---|---|---|---|---|---|---|
| A squeeze near highs | 683 | -2.26% | -3.31% | -1.59% | -2.92% | -3.53% | FAIL |
|  | by year (+20% before -10%): {2022: 8.8, 2023: 32.3, 2024: 29.5, 2025: 31.9} | | | | | | |
| B dry-up then pocket pivot | 651 | 0.58% | -0.57% | -0.27% | 1.42% | -1.31% | FAIL |
|  | by year (+20% before -10%): {2022: 11.3, 2023: 23.8, 2024: 35.1, 2025: 36.7} | | | | | | |
| C quiet accumulation | 751 | -1.10% | -1.41% | -1.01% | -1.19% | -1.23% | FAIL |
|  | by year (+20% before -10%): {2022: 24.2, 2023: 19.9, 2024: 31.0, 2025: 28.5} | | | | | | |
| D leader in tight base | 751 | 1.07% | 0.68% | 0.59% | 1.54% | -2.23% | FAIL |
|  | by year (+20% before -10%): {2022: 16.6, 2023: 30.9, 2024: 39.3, 2025: 41.0} | | | | | | |