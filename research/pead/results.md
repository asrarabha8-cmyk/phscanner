# Post-earnings drift

Run date: 2026-11-23. Rules fixed before the run. Holdout from 2025-11-23.
Earnings calendar: NOT available - testing all strong gaps.
Baseline 20-day return: development 0.50%, holdout 0.86%.

| Group | Part | Events | Avg 5d | Avg 20d | Avg 60d | Median 20d | Race won |
|---|---|---|---|---|---|---|---|
| Gap up, all gaps | development | 2895 | -0.80% | -2.20% | -3.39% | -0.81% | 33.1% |
| Gap up, all gaps | holdout | 846 | -3.15% | -6.21% | -11.79% | -6.00% | 29.8% |
| Gap down (short), all gaps | development | 2303 | -0.51% | -1.32% | -3.25% | -0.28% | 28.9% |
| Gap down (short), all gaps | holdout | 606 | -0.01% | 0.17% | -0.26% | 1.24% | 28.2% |

## 20-day excess over the baseline (signal-day averages; shorts use minus the baseline)

| Group | Dev days | Dev avg | Low 95% | Half 1 | Half 2 | Holdout avg | Verdict |
|---|---|---|---|---|---|---|---|
| Gap up, all gaps | 809 | -3.6% | -4.9% | -1.39% | -5.81% | -9.94% | FAIL |
|  | by year: {2022: 0.56, 2023: -3.13, 2024: -4.7, 2025: -6.26} | | | | | | |
| Gap down (short), all gaps | 702 | 1.06% | 0.1% | 1.27% | 0.85% | 4.02% | PASS |
|  | by year: {2022: 0.27, 2023: 2.05, 2024: 0.69, 2025: 1.09} | | | | | | |