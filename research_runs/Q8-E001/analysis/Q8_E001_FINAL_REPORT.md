# Q8-E001 — Mean-Rank Source-Only Model Selection

## Experiment

Q8-E001 is a single-factor follow-up to Q5-E001.

All Q5 data, preprocessing, EEGNet architecture, optimization, LOSO folds, source subjects and final seeds were preserved.

The only methodological change was the source-only epoch-selection rule.

- Q5: earliest epoch minimizing mean validation CE.
- Q8-E001: rank epochs independently inside each of four source-validation folds, average the four ranks, then choose the earliest epoch with minimum mean rank.

The 36 Q5 inner fits were not retrained. Their frozen 40-epoch validation trajectories were reused.

## Frozen selections

| Subject | Q5 mean-CE epoch | Q8 mean-rank epoch | Delta |
|---:|---:|---:|---:|
| S1 | 27 | 27 | +0 |
| S2 | 1 | 13 | +12 |
| S3 | 2 | 10 | +8 |
| S4 | 10 | 10 | +0 |
| S5 | 13 | 17 | +4 |
| S6 | 7 | 15 | +8 |
| S7 | 6 | 16 | +10 |
| S8 | 1 | 23 | +22 |
| S9 | 7 | 9 | +2 |

## Subject-level performance

| Subject | Q5 BA | Q8 BA | Delta pp |
|---:|---:|---:|---:|
| S1 | 0.5700 | 0.5700 | +0.00 |
| S2 | 0.2448 | 0.2784 | +3.36 |
| S3 | 0.2610 | 0.6088 | +34.78 |
| S4 | 0.3692 | 0.3692 | +0.00 |
| S5 | 0.2413 | 0.2506 | +0.93 |
| S6 | 0.2836 | 0.2853 | +0.17 |
| S7 | 0.2847 | 0.3032 | +1.85 |
| S8 | 0.2969 | 0.6545 | +35.76 |
| S9 | 0.4832 | 0.5203 | +3.70 |

## Aggregate paired results

- Q5 mean BA: **0.3372**
- Q8 mean BA: **0.4267**
- Mean difference: **+8.95 pp**
- Median difference: **+1.85 pp**
- Improved subjects: **7/9**
- Worsened subjects: **0/9**
- Wilcoxon p: **0.015625**
- Paired t-test p: **0.110964**
- Sign-test p: **0.179688**
- Paired Cohen dz: **0.5972**
- Bootstrap 95% CI for mean difference: **[+1.05, +19.96] pp**

## Interpretation boundary

Q8-E001 must not be described as independent confirmation. The mean-rank candidate was motivated by prior exploratory analysis of the same BNCI2014_001 research program.

However, the Q8-E001 final models were trained only after the mean-rank selections had been frozen from source-validation curves, with no target-derived fitting or epoch adjustment.

Nine held-out subjects are the subject-level inference units. The 27 final seed fits are repeated fits, not 27 independent subjects.
