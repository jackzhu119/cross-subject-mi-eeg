# Supplementary experiment inventory — Q15 and separate BNCI physiology

The machine-readable companion `tables/completed_experiment_inventory.csv` contains **105 records: 61 historical Q4–Q14 condition rows, 34 earlier binary pipeline/QC endpoint rows, six Q15 external model-by-cohort endpoints, three Q15 source-model freeze records, and one separate descriptive Q16 BNCI component**. Of these, 101 carry accuracy endpoints. They are descriptive records, not independent hypotheses, fresh replications, or a cumulative fit budget. The three source-freeze records and Q16 physiological component have blank decoder-performance fields because they are not new accuracy endpoints. Blank counts in inherited rows mean the inventory did not establish that accounting scope, not zero fits.

Historical rows are retained from the paper-draft delivery at `ac75a339c8db2861ff8e7d072e50690c79c602c4`, including their original validation-scope and reuse notes. Q15 additions use results snapshot `7af1a137e2676a018e1e880ab076de6cae4ce30b`. No training or new decoder inference was performed to assemble this inventory. Q16 newly computes native EEG power under a separately committed recipe; it is a signal-analysis component, not another model arm. Values below are equal-person balanced accuracy; neural seeds and predefined source subsets are averaged within person. Four-class and binary results remain separate.

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

## Q15 source stage and external endpoints

| Stage / arm | Dataset | People | Distinct trials | BA (%) | Fit accounting / validation |
|---|---|---:|---:|---:|---|
| Q15-E005 / broad EEGNet | BNCI source | 9 | 2,592 source | — | 4 inner + 3 final deep fits; selected epoch 14; source validation passed |
| Q15-E005 / shared μ/β | BNCI source | 9 | 2,592 source | — | 4 inner + 3 final deep fits; selected epoch 19; source validation passed |
| Q15-E005 / CSP4+LDA | BNCI source | 9 | 2,592 source | — | 1 source shallow fit; fixed 21→20 CAR coordinates |
| Q15-E006 / broad EEGNet | Cho2017 | 52 | 10,520 | 59.8237 | Frozen source reuse; independent raw/checkpoint/statistical replay passed |
| Q15-E006 / shared μ/β | Cho2017 | 52 | 10,520 | 58.3104 | Same 52 people and trials, three source-trained seeds |
| Q15-E006 / CSP4+LDA | Cho2017 | 52 | 10,520 | 51.9904 | Deterministic frozen source model |
| Q15-E007 / broad EEGNet | Lee2019_MI | 54 | 10,800 | 65.5123 | Frozen source reuse; both `EEG_MI_train` sessions pooled within person |
| Q15-E007 / shared μ/β | Lee2019_MI | 54 | 10,800 | 65.7160 | Same 54 people and trials, three source-trained seeds |
| Q15-E007 / CSP4+LDA | Lee2019_MI | 54 | 10,800 | 52.7685 | Deterministic frozen source model |

The source fit budget is **15 original source fits**, with zero additional source fits during migration and zero target fits. There are six neural final checkpoints, not six source-fitting programmes. Q15 external prediction tables have seven rows per distinct trial and do not increase the participant sample size. Q15-E006/E007 are separate from the Q14 PhysioNet 109-person endpoint.

The primary paired shared-minus-broad contrast is −1.5134 percentage points in Cho2017, 95% CI [−2.2490,−0.8045], Holm-adjusted p=0.000099995; in Lee2019_MI it is +0.2037, CI [−0.5154,+0.9691], p=0.60367. The two-cohort family, person-level resampling and seed/session aggregation were frozen before target inference. CSP is a descriptive context comparator.

The Q15 final validator passes raw metadata, raw-to-epoch, checkpoint probability, coverage, state-immutability, and independent statistic reconstruction. Its terminal status is `completed_with_calibration_limitations`: raw voltage calibration, original Cho hardware reference, and hardware cue latency remain unverified. The actual execution/inference contracts take precedence over obsolete planned/PhysioNet fields inherited in the source configuration.

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

No failed/unrun record is assigned invented performance. These records remain in the integrated manuscript archive. Q15 metadata preparation is now linked to completed external outcomes without reclassifying preparatory gates as separate accuracy experiments.


## Q15 operational interruptions and migration scope

The old startup attempt `20261004T004000Z-98f40947c306` is distinct from the validated source origin job `20261004T005335Z-9b3bce30277a`. RunPod credential, filesystem-permission, and account-API startup failures are operational attempts, not failed scientific hypotheses or target results. The migration job `20261005T050511Z-migration-from-r2-b82ad79b` ultimately completed under manual-stop mode, with scientific validation and GitHub backup verified. An API error from a preceding attempt must not be substituted for the final job's science status.

The published restoration provenance binds 160 external originals and 106 epoch-person artifacts. The broader 178-file download inventory additionally contains the 18 BNCI originals. No paper conclusion depends on an assumed physical shutdown or an automatically authenticated Pod identity; final manual-mode status does not verify either.

## Q16-P001-BNCI-20261006: separate descriptive physiology

This component uses 18 original BNCI MAT files, nine people and both sessions: 108 labeled runs, 5,184 four-class trials and 2,592 hand trials. Provider flags are retained (488 all-class and 246 hand trials). The recipe computes native 250-Hz, 22-channel Welch powers, baseline cue [−1.5,−0.5) s and task [0.5,2.5) s, without additional filter, CAR, resampling, source scaler or decoder transform. The power-table grain is trial × channel × band, not independent participants.

The committed pre-power gate is `050e01b028aaab8e3d745934b13b2d17e9bb0a7a`. The original September window proposal and this October estimator/aggregation amendment are not an independent prospective registration: decoder outcomes were already known. Actual output hashes, timing, runtime, counts and independent checks are recorded under `../Q16-P001-BNCI-20261006/`.

Primary summaries average trial-level dB within hand/session and weight both sessions equally per person. Laterality retains paired C3/C4 eligibility and absolute contra/ipsilateral terms. Six descriptive Spearman contexts link μ/β descriptors to saved Q14 binary source-LOSO Broad/Shared/CSP scores (n=9); no p-values, high/low-BA groups or outcome-based decoder changes were added. Q14 decoder windows are three seconds, while Q16 physiology uses two. Unflagged descriptions are sensitivity summaries, not replacement primary populations.

Unequal Welch segment counts, sensor-reference uncertainty, template sensor positions and retrospective analysis limit interpretation. A negative lateralization contrast alone does not establish absolute ERD, and an association does not establish learned features or generalizable biomarkers. External physiology was not computed; this BNCI component does not complete the proposed external physiological programme. New decoder fits=0 and new checkpoint inference=0.
