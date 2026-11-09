# Completed experiment inventory — 2 October 2026

This inventory covers completed pre-Q15 research. All values are equal-person balanced accuracy; neural seeds and predefined source subsets are averaged within person. It is a descriptive record, not a target-selected leaderboard. The inventory counts rows/conditions, not independent hypotheses or a cumulative training budget. No training, preprocessing or new prediction was run to create it.

## Four-class development, binary source development, and external evaluation

| arm | classes | n_subjects | BA (%) | reuse_note |
| --- | --- | --- | --- | --- |
| Q4-E001/BroadCSP_LDA | 4 | 9 | 39.04 |  |
| Q4-E001/BroadCSP_SVM | 4 | 9 | 37.50 |  |
| Q4-E001/FBCSP_LDA | 4 | 9 | 38.12 |  |
| Q4-E001/FBCSP_MI8_LDA | 4 | 9 | 31.37 |  |
| Q4-A001/FBCSP_MI16_LDA | 4 | 9 | 34.65 |  |
| Q4-A001/FBCSP_MI32_LDA | 4 | 9 | 36.75 |  |
| Q4-A001/FBCSP_MI72_LDA | 4 | 9 | 38.12 | Predictions reproduce the Q4 MI8/full-bank endpoint; not an independent outcome |
| Q4-A001/FBCSP_MI8_LDA | 4 | 9 | 31.37 | Predictions reproduce the Q4 MI8/full-bank endpoint; not an independent outcome |
| Q5-E001 | 4 | 9 | 33.72 |  |
| Q6-E001 | 4 | 9 | 37.93 |  |
| Q7-E001/B | 4 | 1 | 25.69 |  |
| Q7-E001/C | 4 | 1 | 67.71 |  |
| Q8-E001 | 4 | 9 | 42.67 |  |
| Q9-A001/PSD44_LDA | 4 | 9 | 36.28 |  |
| Q9-A001/PSD44_LINEAR_SVM | 4 | 9 | 35.78 |  |
| Q10-A001/BROAD_LOGE_LOGREG | 4 | 9 | 35.32 |  |
| Q10-A001/BROAD_LOGE_MDM | 4 | 9 | 29.49 |  |
| Q10-A001/MUBETA_LOGE_LDA | 4 | 9 | 36.00 |  |
| Q10-A001/MUBETA_LOGE_SVM | 4 | 9 | 35.47 |  |
| Q9-E001/BETA_13_30 | 4 | 9 | 31.53 |  |
| Q9-E001/MID_8_30 | 4 | 9 | 44.55 |  |
| Q9-E001/MU_8_13 | 4 | 9 | 43.30 |  |
| Q9-E001/MU_BETA_SHARED | 4 | 9 | 42.19 |  |
| Q9-E002/MID_8_30_Q8_EPOCHS | 4 | 9 | 42.73 |  |
| Q9-E002/MU_BETA_SHARED_Q8_EPOCHS | 4 | 9 | 43.50 |  |
| Q9-E004/MU_BETA_SHARED_SOURCE_CLEAN | 4 | 9 | 42.11 |  |
| Q9-E005/MU_BETA_SHARED_SOURCE_NORM | 4 | 9 | 41.53 |  |
| Q10-E001/MU_BETA_CSP8_EEGNET | 4 | 9 | 41.48 |  |
| Q10-E001/MU_BETA_PCA8_EEGNET | 4 | 9 | 42.06 |  |
| Q11-E001/BROAD_CAPACITY_MATCHED | 4 | 9 | 42.19 |  |
| Q11-E001/FOUR_BAND_SHARED | 4 | 9 | 39.80 |  |
| Q11-E001/TWO_BAND_EARLY_STACK | 4 | 9 | 42.66 |  |
| Q11-E001/TWO_BAND_INDEPENDENT | 4 | 9 | 42.99 |  |
| Q7-E001/A_reused_Q5_S3 | 4 | 1 | 26.10 | Q5-E001 |
| Q7-E001/D_reused_Q6_S3 | 4 | 1 | 65.86 | Q6-E001 |
| Q12-E001/SOURCE_BALANCED_ERM | 4 | 9 | 43.18 |  |
| Q12-E001/SOURCE_GROUP_DRO | 4 | 9 | 36.73 |  |
| Q12-E001/SOURCE_POOLED_WHITEN | 4 | 9 | 44.34 |  |
| Q12-E002/CHANNEL_AND_GAIN | 4 | 9 | 40.92 |  |
| Q12-E002/CHANNEL_DROPOUT | 4 | 9 | 41.00 |  |
| Q12-E002/GAIN_PERTURB | 4 | 9 | 43.42 |  |
| Q13-E001/Q8_FIXED20 | 4 | 9 | 43.99 |  |
| Q13-E001/Q9_SHARED_FIXED20 | 4 | 9 | 43.98 |  |
| Q13-E001/Q9_SHARED_RAW_CE | 4 | 9 | 40.07 |  |
| Q13-E004/Q8_SRC2 | 4 | 9 | 32.96 |  |
| Q13-E004/Q8_SRC4 | 4 | 9 | 38.89 |  |
| Q13-E004/Q8_SRC6 | 4 | 9 | 43.16 |  |
| Q13-E004/Q9_SHARED_SRC2 | 4 | 9 | 34.74 |  |
| Q13-E004/Q9_SHARED_SRC4 | 4 | 9 | 38.89 |  |
| Q13-E004/Q9_SHARED_SRC6 | 4 | 9 | 42.48 |  |
| Q13-E005/Q8_SOURCE_SESSION_E | 4 | 9 | 41.40 |  |
| Q13-E005/Q8_SOURCE_SESSION_T | 4 | 9 | 42.25 |  |
| Q13-E005/Q9_SHARED_SOURCE_SESSION_E | 4 | 9 | 41.89 |  |
| Q13-E005/Q9_SHARED_SOURCE_SESSION_T | 4 | 9 | 41.81 |  |
| Q13-E006/Q8_RAW_CE_MATCHED | 4 | 9 | 33.92 |  |
| Q14-E001/BROAD_EEGNET | 2 | 9 | 68.21 |  |
| Q14-E001/CSP4_LDA | 2 | 9 | 61.54 |  |
| Q14-E001/MU_BETA_SHARED | 2 | 9 | 67.35 |  |
| Q14-E002R2/BROAD_EEGNET | 2 | 109 | 61.81 | 87 prior subjects retained; 22 completed under rate amendment |
| Q14-E002R2/CSP4_LDA | 2 | 109 | 54.46 | 87 prior subjects retained; 22 completed under rate amendment |
| Q14-E002R2/MU_BETA_SHARED | 2 | 109 | 62.39 | 87 prior subjects retained; 22 completed under rate amendment |

The CSV retains subject SD, evaluation-cell counts, validation scope and evidence paths. Q4-A001 reuses source-fitted CSP feature caches but refits scaler/LDA nine times per arm; k8/k72 endpoints reproduce prior Q4 predictions. Q7 A/D reuse saved S3 fits. Q13 k8 points reuse fixed20 anchors and its historical raw-CE comparator reuses Q5. These repeated endpoints do not provide independent replications.

Q9 top-level batch status proves orchestration only. Its archived prediction/partition/statistical audit and present arithmetic checks are recorded separately; do not infer full raw/checkpoint replay from a batch-success label. Q12/Q13 have experiment-specific passing historical scientific replay receipts. Q14 source receipts and external portable saved-probability/event checks have narrower scopes, described in the paper.

## Earlier binary pipeline and artifact/EOG checks

| experiment | mode | condition | model | test_stratum | n_subjects | BA (%) |
| --- | --- | --- | --- | --- | --- | --- |
| P2-E001 | cross_session | expert_clean_only | CSP+LDA | clean | 9 | 76.06 |
| P2-E001 | cross_session | expert_clean_only | CSP+linearSVM | clean | 9 | 75.05 |
| P2-E001 | cross_subject | expert_clean_only | CSP+LDA | clean | 9 | 62.76 |
| P2-E001 | cross_subject | expert_clean_only | CSP+linearSVM | clean | 9 | 62.09 |
| P2-E001 | within_session | expert_clean_only | CSP+LDA | clean | 9 | 78.06 |
| P2-E001 | within_session | expert_clean_only | CSP+linearSVM | clean | 9 | 78.21 |
| P2-E002-ALLTRIALS | cross_subject | all_trials | CSP+LDA | all | 9 | 61.50 |
| P2-E002-ALLTRIALS | cross_subject | all_trials | CSP+linearSVM | all | 9 | 60.57 |
| P3-E001 | cross_subject | all_trials | CSP4+WelchPSD88+shrinkageLDA | all | 9 | 64.08 |
| P3-E001 | cross_subject | all_trials | CSP4+WelchPSD88+shrinkageLDA | clean | 9 | 64.10 |
| P3-E001 | cross_subject | all_trials | CSP4+WelchPSD88+shrinkageLDA | flagged | 9 | 65.89 |
| P3-E001 | cross_subject | all_trials | CSP4+shrinkageLDA | all | 9 | 61.65 |
| P3-E001 | cross_subject | all_trials | CSP4+shrinkageLDA | clean | 9 | 61.92 |
| P3-E001 | cross_subject | all_trials | CSP4+shrinkageLDA | flagged | 9 | 59.41 |
| P3-E001 | cross_subject | all_trials | WelchPSD88+shrinkageLDA | all | 9 | 58.41 |
| P3-E001 | cross_subject | all_trials | WelchPSD88+shrinkageLDA | clean | 9 | 58.55 |
| P3-E001 | cross_subject | all_trials | WelchPSD88+shrinkageLDA | flagged | 9 | 56.15 |
| P3-E001 | cross_subject | expert_clean_only | CSP4+WelchPSD88+shrinkageLDA | all | 9 | 64.51 |
| P3-E001 | cross_subject | expert_clean_only | CSP4+WelchPSD88+shrinkageLDA | clean | 9 | 64.63 |
| P3-E001 | cross_subject | expert_clean_only | CSP4+WelchPSD88+shrinkageLDA | flagged | 9 | 64.24 |
| P3-E001 | cross_subject | expert_clean_only | CSP4+shrinkageLDA | all | 9 | 62.46 |
| P3-E001 | cross_subject | expert_clean_only | CSP4+shrinkageLDA | clean | 9 | 62.85 |
| P3-E001 | cross_subject | expert_clean_only | CSP4+shrinkageLDA | flagged | 9 | 58.82 |
| P3-E001 | cross_subject | expert_clean_only | WelchPSD88+shrinkageLDA | all | 9 | 58.06 |
| P3-E001 | cross_subject | expert_clean_only | WelchPSD88+shrinkageLDA | clean | 9 | 58.19 |
| P3-E001 | cross_subject | expert_clean_only | WelchPSD88+shrinkageLDA | flagged | 9 | 55.77 |
| P4-E001B | cross_subject | source_train_fitted_EOG_regression | CSP4 + shrinkage LDA | all | 9 | 62.08 |
| P4-E001B | cross_subject | source_train_fitted_EOG_regression | CSP4 + shrinkage LDA | clean | 9 | 62.57 |
| P4-E001B | cross_subject | source_train_fitted_EOG_regression | CSP4 + shrinkage LDA | flagged | 9 | 56.78 |
| P4-E001B | cross_subject | uncorrected | CSP4 + shrinkage LDA | all | 9 | 62.46 |
| P4-E001B | cross_subject | uncorrected | CSP4 + shrinkage LDA | clean | 9 | 62.85 |
| P4-E001B | cross_subject | uncorrected | CSP4 + shrinkage LDA | flagged | 9 | 58.82 |
| P2-SMOKE-S1B | cross_session | expert_clean_only | CSP+LDA | clean | 1 | 92.16 |
| P2-SMOKE-S1B | cross_session | expert_clean_only | CSP+linearSVM | clean | 1 | 80.71 |

P2 within-session and cross-session modes use labeled calibration from the evaluated person. Only cross-subject LOSO excludes both target sessions. P2-E001 uses 2,346 expert-clean left/right trials: within-session/LOSO each evaluate all 2,346, whereas cross-session evaluates 1,183 trials from the later session. P2-E002-ALLTRIALS scores 2,592 and changes both source and target populations. Some archived all-trial metadata retains earlier clean-name fields; the effective population is 2,592.

P3 scores clean targets as primary and reports all/flagged strata as secondary. Its source-all versus source-clean conditions share target identities. P4-E001B is the successful retry: regression coefficients are fit on clean source data, then applied using three synchronous target EOG channels. That condition is EOG-assisted, and neither lower correlation nor its scores proves selective ocular-artifact removal. The S1B single-person smoke uses labeled within-person data and has no located independent scientific validator.

## Completed audits and source-only analyses

- **P1-E001**: Single-subject acquisition/data audit; no decoder endpoint. Source: `outputs/P1-E001/data_audit.json`.
- **Q8-A001**: Post-hoc source validation-curve and epoch-selection stability audit; no new fit. Source: `research_runs/Q8-A001/analysis/analysis_summary.json`.
- **Q8-A002**: Leave-one-inner-fold-out selection sensitivity on archived curves; no new fit. Source: `research_runs/Q8-A002/analysis/inner_fold_influence_summary.csv`.
- **Q8-A003**: Six candidate aggregation rules, archived curve stability only; not six newly evaluated target models. Source: `research_runs/Q8-A003/analysis/candidate_rule_stability_summary.csv`.
- **Q10-V001**: Independent archived prediction/partition/statistics audit; not an additional decoder arm. Source: `results/Q10-V001/audit_report.json`.
- **Q14-E002**: All-nine-source frozen models;8 inner deep fits,6 final deep fits,1 shallow fit;no target BA at source freeze. Source: `results/Q14-E002/freeze_receipt.json`.

## Retained failures, partial runs, and unrun branches

- **P2-SMOKE-S1**: Failed CSP API smoke; successful S1B kept separately. Source: `outputs/P2-SMOKE-S1/run_status.json`.
- **P4-E001**: Failed EOG channel selection; successful P4-E001B kept separately. Source: `outputs/P4-E001/run_status.json`.
- **Q13-E002/Q13-E003**: Superseded unrun branches; no performance invented. See versioned protocol review.
- **Q14-E002R1**: Partial87-person external attempt; superseded by amended full109-person R2 without double counting. See versioned protocol review.
- **Q14 original aggregate validator**: Retained CSV floating-point serialization failure; separate from later portability amendment. See versioned protocol review.
- **Q14-E003**: Unrun external branch; no outcome. See versioned protocol review.

No failed/unrun record is assigned invented performance. Q15 and its raw-data transfer/contract work do not enter this manuscript.
