# Q8-A002 — Inner-Fold Influence Audit

**Analysis only. No model training.**

## Purpose

Determine whether a particular pair of source-validation subjects dominates the source-only selected training duration.

For each Q5/Q6 LOSO fold, the analysis removes one of the four validation pairs at a time and recomputes the earliest epoch minimizing mean validation cross-entropy across the remaining three folds.

## Validation-pair mapping

For each held-out target, the remaining eight source subjects are sorted and divided into four consecutive pairs, matching the Q5/Q6 protocol.

## Per-subject influence summary

| Exp | Target | Original | LOIFO range | Mean abs shift | Max abs shift | Most influential pair | Shift |
|---|---:|---:|---:|---:|---:|---|---:|
| Q5 | S1 | 27 | 26 | 15.00 | 26 | S8+S9 | -26 |
| Q5 | S2 | 1 | 12 | 5.00 | 12 | S6+S7 | +12 |
| Q5 | S3 | 2 | 18 | 4.50 | 17 | S4+S5 | +17 |
| Q5 | S4 | 10 | 0 | 0.00 | 0 | S1+S2 | +0 |
| Q5 | S5 | 13 | 12 | 3.25 | 6 | S1+S2 | -6 |
| Q5 | S6 | 7 | 5 | 1.25 | 5 | S3+S4 | -5 |
| Q5 | S7 | 6 | 11 | 2.75 | 10 | S5+S6 | +10 |
| Q5 | S8 | 1 | 22 | 5.75 | 22 | S5+S6 | +22 |
| Q5 | S9 | 7 | 6 | 1.50 | 6 | S5+S6 | +6 |
| Q6 | S1 | 27 | 26 | 15.25 | 26 | S2+S3 | -26 |
| Q6 | S2 | 1 | 18 | 7.50 | 18 | S6+S7 | +18 |
| Q6 | S3 | 16 | 18 | 8.25 | 15 | S1+S2 | -15 |
| Q6 | S4 | 10 | 6 | 1.50 | 6 | S8+S9 | +6 |
| Q6 | S5 | 12 | 6 | 1.50 | 5 | S1+S2 | -5 |
| Q6 | S6 | 7 | 34 | 8.50 | 28 | S8+S9 | +28 |
| Q6 | S7 | 6 | 10 | 2.50 | 10 | S5+S6 | +10 |
| Q6 | S8 | 1 | 22 | 5.50 | 22 | S5+S6 | +22 |
| Q6 | S9 | 7 | 6 | 1.50 | 6 | S5+S6 | +6 |

## Critical S2/S3/S8 leave-one-pair results

| Exp | Target | Omitted pair | Original | New epoch | Shift |
|---|---:|---|---:|---:|---:|
| Q5 | S2 | S1+S3 | 1 | 1 | +0 |
| Q5 | S2 | S4+S5 | 1 | 9 | +8 |
| Q5 | S2 | S6+S7 | 1 | 13 | +12 |
| Q5 | S2 | S8+S9 | 1 | 1 | +0 |
| Q5 | S3 | S1+S2 | 2 | 2 | +0 |
| Q5 | S3 | S4+S5 | 2 | 19 | +17 |
| Q5 | S3 | S6+S7 | 2 | 2 | +0 |
| Q5 | S3 | S8+S9 | 2 | 1 | -1 |
| Q5 | S8 | S1+S2 | 1 | 1 | +0 |
| Q5 | S8 | S3+S4 | 1 | 2 | +1 |
| Q5 | S8 | S5+S6 | 1 | 23 | +22 |
| Q5 | S8 | S7+S9 | 1 | 1 | +0 |
| Q6 | S2 | S1+S3 | 1 | 1 | +0 |
| Q6 | S2 | S4+S5 | 1 | 13 | +12 |
| Q6 | S2 | S6+S7 | 1 | 19 | +18 |
| Q6 | S2 | S8+S9 | 1 | 1 | +0 |
| Q6 | S3 | S1+S2 | 16 | 1 | -15 |
| Q6 | S3 | S4+S5 | 16 | 19 | +3 |
| Q6 | S3 | S6+S7 | 16 | 16 | +0 |
| Q6 | S3 | S8+S9 | 16 | 1 | -15 |
| Q6 | S8 | S1+S2 | 1 | 1 | +0 |
| Q6 | S8 | S3+S4 | 1 | 1 | +0 |
| Q6 | S8 | S5+S6 | 1 | 23 | +22 |
| Q6 | S8 | S7+S9 | 1 | 1 | +0 |

## Interpretation boundary

This analysis uses only source-validation losses. It diagnoses sensitivity of the existing model-selection procedure.

Target balanced accuracy must not be used to decide which source-validation pair should be ignored.
