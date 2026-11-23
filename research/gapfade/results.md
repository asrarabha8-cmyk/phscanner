# Gap-up fade, stage 1

Run date: 2026-11-23. Rules fixed before the run. Holdout from 2025-11-23.
Events: 3910. Short returns (positive = the stock fell).

| Group | Events | Avg 20d short | Median | Trimmed avg | Fell -10% first | Rose +15% first | Neither |
|---|---|---|---|---|---|---|---|
| All, development | 2981 | 2.26% | 0.66% | 2.76% | 40% | 28% | 33% |
| small, development | 552 | 1.71% | 1.94% | 2.66% | 45% | 32% | 23% |
| mid, development | 1350 | 2.85% | 0.85% | 3.29% | 41% | 28% | 31% |
| large, development | 1079 | 1.80% | 0.17% | 2.07% | 35% | 25% | 40% |
| gap 5-10%, development | 1405 | 0.03% | 0.00% | 0.55% | 37% | 24% | 38% |
| gap 10-20%, development | 955 | 1.61% | 1.08% | 1.97% | 42% | 27% | 31% |
| gap >20%, development | 621 | 8.30% | 1.79% | 9.25% | 42% | 36% | 23% |
| All, holdout | 929 | 7.14% | 5.98% | 7.66% | 53% | 30% | 17% |
| small, holdout | 155 | 7.00% | 6.54% | 7.57% | 60% | 30% | 10% |
| mid, holdout | 406 | 8.39% | 8.20% | 9.17% | 55% | 30% | 15% |
| large, holdout | 368 | 5.83% | 3.26% | 5.94% | 48% | 31% | 21% |
| gap 5-10%, holdout | 380 | 0.84% | 2.78% | 1.45% | 51% | 29% | 20% |
| gap 10-20%, holdout | 279 | 6.11% | 5.33% | 6.33% | 56% | 27% | 18% |
| gap >20%, holdout | 270 | 17.08% | 14.70% | 17.69% | 54% | 34% | 12% |

## Timing: average short return after N days (all events)

| Part | 1d | 2d | 3d | 5d | 10d | 15d | 20d |
|---|---|---|---|---|---|---|---|
| development | 0.55% | 0.60% | 0.43% | 0.83% | 1.86% | 2.61% | 2.26% |
| holdout | 0.42% | 1.31% | 1.47% | 3.45% | 5.14% | 5.59% | 7.14% |
| large, all years | 0.18% | 0.53% | 0.48% | 1.27% | 1.71% | 2.46% | 2.82% |
| mid, all years | 0.90% | 1.32% | 1.17% | 2.40% | 3.75% | 3.96% | 4.13% |

## Daily excess of the 20-day short return over the baseline

| Group | Dev days | Dev avg | Low 95% | Half 1 | Half 2 | Holdout | Verdict |
|---|---|---|---|---|---|---|---|
| All | 817 | 3.61% | 2.34% | 1.27% | 5.94% | 10.64% | PASS |
|  | by year: {2022: -0.68, 2023: 3.07, 2024: 4.68, 2025: 6.45} | | | | | | |
| small | 386 | 2.96% | 0.38% | -0.53% | 6.46% | 7.71% | FAIL |
|  | by year: {2022: -4.64, 2023: 2.1, 2024: 5.63, 2025: 6.15} | | | | | | |
| mid | 628 | 4.33% | 2.51% | 2.25% | 6.42% | 11.32% | PASS |
|  | by year: {2022: 1.08, 2023: 3.59, 2024: 4.07, 2025: 7.72} | | | | | | |
| large | 538 | 1.64% | -0.03% | -0.07% | 3.35% | 9.18% | FAIL |
|  | by year: {2022: 0.96, 2023: -0.62, 2024: 1.23, 2025: 4.28} | | | | | | |

Large group, worst squeezes (20-day short return): SBET 2025-06-16 -174%, DJT 2024-09-25 -164%, CONL 2024-10-14 -135%, AGQ 2025-12-26 -124%, MSTR 2024-02-28 -92%, QBTS 2025-05-08 -89%, CONL 2025-06-20 -80%, OKLO 2025-05-14 -79%
