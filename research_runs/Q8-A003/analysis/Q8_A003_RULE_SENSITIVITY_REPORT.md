# Q8-A003 — Source-only Selection Rule Sensitivity

**Analysis only. No model training.**

## Purpose

Compare several source-only aggregation rules for stability to source-validation fold composition.

No rule is selected using held-out target performance.

## Rules

- `mean_ce`
- `median_ce`
- `trimmed_mean_ce`
- `worst_fold_ce`
- `mean_rank`
- `median_rank`

## Leave-one-inner-fold-out stability

| Exp | Rule | Mean epoch range | Mean abs shift | Max abs shift |
|---|---|---:|---:|---:|
| Q5 | mean_ce | 12.44 | 4.33 | 26 |
| Q5 | mean_rank | 10.56 | 3.81 | 21 |
| Q5 | median_ce | 11.56 | 5.25 | 24 |
| Q5 | median_rank | 14.11 | 5.61 | 21 |
| Q5 | trimmed_mean_ce | 11.56 | 5.25 | 24 |
| Q5 | worst_fold_ce | 11.00 | 2.83 | 25 |
| Q6 | mean_ce | 16.22 | 5.78 | 28 |
| Q6 | mean_rank | 11.00 | 3.42 | 23 |
| Q6 | median_ce | 12.22 | 6.03 | 25 |
| Q6 | median_rank | 12.11 | 5.58 | 18 |
| Q6 | trimmed_mean_ce | 12.22 | 6.03 | 25 |
| Q6 | worst_fold_ce | 11.33 | 2.94 | 25 |

## Q5 versus Q6 consistency

| Rule | Mean abs epoch difference | Median | Max | Same epoch subjects |
|---|---:|---:|---:|---:|
| mean_ce | 1.67 | 0.00 | 14 | 7/9 |
| mean_rank | 1.33 | 0.00 | 6 | 5/9 |
| median_ce | 1.00 | 0.00 | 7 | 7/9 |
| median_rank | 3.11 | 3.00 | 7 | 2/9 |
| trimmed_mean_ce | 1.00 | 0.00 | 7 | 7/9 |
| worst_fold_ce | 0.00 | 0.00 | 0 | 9/9 |

## Methodological boundary

These comparisons are retrospective sensitivity analyses. They may identify candidate families for a future frozen source-only selection rule.

They do not justify choosing whichever rule would have produced the best already-known target performance.
