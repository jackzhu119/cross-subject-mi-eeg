# Q8-A001 — Source-only Epoch-Selection Stability Audit

## Status

**Analysis only. No EEGNet model was trained or refit.**

This audit analyzes the frozen Q5-E001 and Q6-E001 40-epoch inner source-validation trajectories after Q7-E001 demonstrated that S3 recovery was primarily associated with training duration.

## Scientific question

How stable is the source-only rule `earliest epoch minimizing equal-inner-fold mean validation CE`, particularly for S2, S3 and S8?

## Q5/Q6 selection summary

| Subject | Q5 epoch | Q6 epoch | Delta | Q5 BA | Q6 BA | BA delta pp |
|---:|---:|---:|---:|---:|---:|---:|
| S1 | 27 | 27 | +0 | 0.5700 | 0.5689 | -0.12 |
| S2 | 1 | 1 | +0 | 0.2448 | 0.2471 | +0.23 |
| S3 | 2 | 16 | +14 | 0.2610 | 0.6586 | +39.76 |
| S4 | 10 | 10 | +0 | 0.3692 | 0.3738 | +0.46 |
| S5 | 13 | 12 | -1 | 0.2413 | 0.2465 | +0.52 |
| S6 | 7 | 7 | +0 | 0.2836 | 0.2830 | -0.06 |
| S7 | 6 | 6 | +0 | 0.2847 | 0.2865 | +0.17 |
| S8 | 1 | 1 | +0 | 0.2969 | 0.2529 | -4.40 |
| S9 | 7 | 7 | +0 | 0.4832 | 0.4965 | +1.33 |

## Selection-stability diagnostics

The following quantities are descriptive diagnostics, not a newly validated model-selection rule.

- `inner_optimum_epoch_range`: spread between the earliest and latest optimum among the four source-validation folds.
- `near_min_005_count`: number of epochs whose mean validation CE lies within 0.005 of the global minimum.
- `margin_to_second_best`: difference between the best and second-best mean-validation CE.
- Very early selection, wide fold disagreement, and a large near-minimum region can indicate a fragile earliest-minimum decision.

## Critical subjects

| Subject | Exp | Selected | Fold optima | Fold range | Near-min ±0.005 count | Near-min latest | CE(16)-selected |
|---:|---|---:|---|---:|---:|---:|---:|
| S2 | Q5 | 1 | 24,1,5,9 | 23 | 1 | 1 | +0.072204 |
| S2 | Q6 | 1 | 24,1,5,9 | 23 | 1 | 1 | +0.046486 |
| S3 | Q5 | 2 | 12,1,6,20 | 19 | 2 | 2 | +0.026094 |
| S3 | Q6 | 16 | 24,1,6,19 | 23 | 4 | 16 | +0.000000 |
| S8 | Q5 | 1 | 22,24,1,26 | 25 | 2 | 2 | +0.110879 |
| S8 | Q6 | 1 | 17,28,1,26 | 27 | 1 | 1 | +0.109767 |

## Q7 mechanistic anchor

Q7-E001 reconstructed S3 as:

| Cell | Normalization | Epochs | Mean BA | Entropy | Dominant prediction share |
|---|---:|---:|---:|---:|---:|
| A | False | 2 | 0.2610 | 0.1304 | 0.9416 |
| B | True | 2 | 0.2569 | 0.0827 | 0.9751 |
| C | False | 16 | 0.6771 | 0.9561 | 0.3669 |
| D | True | 16 | 0.6586 | 0.9037 | 0.4387 |

Q7 showed that Raw + 16 epochs recovered S3 while SourceNorm + 2 epochs did not. Therefore the present audit focuses on the stability of source-only training-duration selection.

## Interpretation boundary

This analysis is post-hoc. Q5, Q6 and Q7 target outcomes have already been observed. Any new robust selection rule suggested by these curves must be treated as hypothesis generation unless it is subsequently frozen and tested on independent subjects/data.

S2 and S8 may be identified as candidates for additional mechanistic duration experiments if their source-validation selection is fragile, but their target outcomes must not be used to tune the duration itself.

## Recommended decision process after this audit

1. Determine whether epoch-1/2 selections show fold disagreement or broad near-minimum plateaus.
2. Do not immediately invent a new selection rule from target BA.
3. If instability is evident, define a source-only robust selection principle using only source-validation behavior.
4. Treat any additional S2/S8 duration ablation as exploratory mechanism testing because their target performance is already known.
5. Require later independent/external confirmation before claiming that a new selection rule generalizes.
6. Resolve training/model-selection robustness before using a new spatial-spectral representation, otherwise training-duration changes could confound Q9.
