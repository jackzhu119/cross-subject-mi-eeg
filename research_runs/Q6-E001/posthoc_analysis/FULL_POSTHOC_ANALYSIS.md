# Q6-E001 Complete Post-hoc Analysis

## Scope

This report analyzes the validated Q6-E001 source-only per-channel z-score experiment relative to Q5-E001. No model retraining was performed.

Target-subject distribution statistics below are post-hoc diagnostics only. They were never used during Q6 fitting, epoch selection, normalization, or hyperparameter tuning.

## Primary Q5 vs Q6 result

- Q5 mean subject BA: **0.3372**
- Q6 mean subject BA: **0.3793**
- Mean change: **+4.21 pp**
- Median change: **+0.23 pp**
- Improved subjects: **6/9**
- Worsened subjects: **3/9**
- Wilcoxon p: **0.203125**
- Paired t-test p: **0.374301**
- Sign-test p: **0.507812**
- Paired Cohen dz: **0.3136**
- Bootstrap 95% CI for mean delta: **[-1.12, +13.49] pp**

## Per-subject performance

| Subject | Q5 BA | Q6 BA | Delta pp | Seeds improved |
|---:|---:|---:|---:|---:|
| S1 | 0.5700 | 0.5689 | -0.12 | 1/3 |
| S2 | 0.2448 | 0.2471 | +0.23 | 2/3 |
| S3 | 0.2610 | 0.6586 | +39.76 | 3/3 |
| S4 | 0.3692 | 0.3738 | +0.46 | 2/3 |
| S5 | 0.2413 | 0.2465 | +0.52 | 2/3 |
| S6 | 0.2836 | 0.2830 | -0.06 | 1/3 |
| S7 | 0.2847 | 0.2865 | +0.17 | 2/3 |
| S8 | 0.2969 | 0.2529 | -4.40 | 0/3 |
| S9 | 0.4832 | 0.4965 | +1.33 | 3/3 |

## Interpretation boundary

Nine subjects, not 27 seed fits, are the independent units for subject-level inference.

The overall mean improvement must not be interpreted as a uniform benefit without examining subject-level heterogeneity and leave-one-subject-out sensitivity.

## Prediction-collapse analysis

### Subject 3

- Q5: mean dominant-prediction share = 0.9416; normalized prediction entropy = 0.1304; mean active classes = 2.33
- Q6: mean dominant-prediction share = 0.4387; normalized prediction entropy = 0.9037; mean active classes = 4.00

| Class | Q5 recall | Q6 recall |
|---|---:|---:|
| left_hand | 0.9722 | 0.7037 |
| right_hand | 0.0718 | 0.6782 |
| feet | 0.0000 | 0.4074 |
| tongue | 0.0000 | 0.8449 |

### Subject 8

- Q5: mean dominant-prediction share = 0.5978; normalized prediction entropy = 0.6480; mean active classes = 4.00
- Q6: mean dominant-prediction share = 0.8646; normalized prediction entropy = 0.2627; mean active classes = 2.33

| Class | Q5 recall | Q6 recall |
|---|---:|---:|
| left_hand | 0.6181 | 0.9005 |
| right_hand | 0.3912 | 0.1111 |
| feet | 0.0648 | 0.0000 |
| tongue | 0.1134 | 0.0000 |

## Target/source distribution diagnostics

The source-derived affine z-score does not by itself prove that source-target domain shift is reduced. The values below instead quantify how unusual each held-out target appears in its corresponding source-derived coordinate system.

| Subject | mean-shift | scale-shift | combined mismatch | Q5→Q6 pp |
|---:|---:|---:|---:|---:|
| S1 | 0.0010 | 0.2544 | 0.2544 | -0.12 |
| S2 | 0.0011 | 0.0860 | 0.0860 | +0.23 |
| S3 | 0.0012 | 0.0512 | 0.0512 | +39.76 |
| S4 | 0.0004 | 0.3239 | 0.3239 | +0.46 |
| S5 | 0.0005 | 0.4324 | 0.4324 | +0.52 |
| S6 | 0.0014 | 0.1500 | 0.1500 | -0.06 |
| S7 | 0.0006 | 0.3599 | 0.3599 | +0.17 |
| S8 | 0.0003 | 0.2459 | 0.2459 | -4.40 |
| S9 | 0.0008 | 0.3950 | 0.3950 | +1.33 |

## Exploratory mismatch-performance associations

These correlations are descriptive only. n=9 is very small, and S3 is highly influential.

| Subset | Metric | n | Pearson r | Spearman rho |
|---|---|---:|---:|---:|
| all_S1-S9 | target_z_mean_abs | 9 | 0.5162 | 0.2833 |
| all_S1-S9 | target_z_mean_rms | 9 | 0.4513 | 0.1833 |
| all_S1-S9 | abs_log_std_ratio_mean | 9 | -0.5306 | 0.1333 |
| all_S1-S9 | log_scale_shift_rms | 9 | -0.5326 | 0.1333 |
| all_S1-S9 | combined_mismatch | 9 | -0.5325 | 0.1333 |
| excluding_S3 | target_z_mean_abs | 8 | 0.4162 | -0.0238 |
| excluding_S3 | target_z_mean_rms | 8 | 0.3847 | -0.0238 |
| excluding_S3 | abs_log_std_ratio_mean | 8 | 0.2444 | 0.6190 |
| excluding_S3 | log_scale_shift_rms | 8 | 0.2618 | 0.6190 |
| excluding_S3 | combined_mismatch | 8 | 0.2618 | 0.6190 |
| excluding_S8 | target_z_mean_abs | 8 | 0.4724 | -0.0238 |
| excluding_S8 | target_z_mean_rms | 8 | 0.3939 | -0.1667 |
| excluding_S8 | abs_log_std_ratio_mean | 8 | -0.5511 | 0.0952 |
| excluding_S8 | log_scale_shift_rms | 8 | -0.5553 | 0.0952 |
| excluding_S8 | combined_mismatch | 8 | -0.5553 | 0.0952 |
| excluding_S3_and_S8 | target_z_mean_abs | 7 | -0.4880 | -0.5357 |
| excluding_S3_and_S8 | target_z_mean_rms | 7 | -0.4201 | -0.5357 |
| excluding_S3_and_S8 | abs_log_std_ratio_mean | 7 | 0.5481 | 0.6429 |
| excluding_S3_and_S8 | log_scale_shift_rms | 7 | 0.5745 | 0.6429 |
| excluding_S3_and_S8 | combined_mismatch | 7 | 0.5745 | 0.6429 |

## Leave-one-subject-out sensitivity of Q6-Q5 difference

| Omitted | Mean delta pp | Median delta pp | Improved | Wilcoxon p |
|---:|---:|---:|---:|---:|
| S1 | +4.75 | +0.35 | 6/8 | 0.195312 |
| S2 | +4.71 | +0.32 | 5/8 | 0.312500 |
| S3 | -0.23 | +0.20 | 5/8 | 0.382812 |
| S4 | +4.68 | +0.20 | 5/8 | 0.312500 |
| S5 | +4.67 | +0.20 | 5/8 | 0.312500 |
| S6 | +4.75 | +0.35 | 6/8 | 0.195312 |
| S7 | +4.72 | +0.35 | 5/8 | 0.312500 |
| S8 | +5.29 | +0.35 | 6/8 | 0.039062 |
| S9 | +4.57 | +0.20 | 5/8 | 0.312500 |

## Epoch-selection changes

| Subject | Q5 epochs | Q6 epochs | Delta |
|---:|---:|---:|---:|
| S1 | 27 | 27 | +0 |
| S2 | 1 | 1 | +0 |
| S3 | 2 | 16 | +14 |
| S4 | 10 | 10 | +0 |
| S5 | 13 | 12 | -1 |
| S6 | 7 | 7 | +0 |
| S7 | 6 | 6 | +0 |
| S8 | 1 | 1 | +0 |
| S9 | 7 | 7 | +0 |

## Current scientific conclusion

Q6 is a validated exploratory ablation showing strong subject-specific effects rather than evidence of a uniform source-normalization benefit. The mean BA increase must be interpreted together with the subject-level paired statistics, S3/S8 collapse patterns, distribution diagnostics, and sensitivity analysis.

The next model-development decision should be based on this complete post-hoc evidence rather than on the overall mean BA alone.
