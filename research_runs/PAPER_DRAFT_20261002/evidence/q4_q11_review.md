# Q4–Q11 frozen evidence review

Read-only audit for the manuscript, excluding Q15. No fits or new model predictions were run. Readiness: share with caveats; these are exploratory single-dataset development results.

## Scope and protocol

Recomputed 35 arms from 22 distinct frozen prediction CSVs, including reused Q7 cells and duplicated Q4 sensitivity endpoints. Every subject × seed evaluation has 576 targets, 144 per class. Target IDs and labels match Q5, with no duplicate fit/sample rows. This review checks predictions, recorded source manifests and prior validators; it does not replay raw EEG or checkpoints.

Four-class BNCI2014_001 labels are 1 = left hand, 2 = right hand, 3 = feet, and 4 = tongue. Nine people have both sessions held out. Inputs contain 22 EEG channels at 250 Hz, using [2.5, 5.5) s epochs and 750 samples. All target trials are retained, including 488 expert flags. Zero-phase filters are offline and acausal. Seeds are repeated fits. Bands, representation, scaling and epoch selection vary by arm. Q7 contains only S3. Do not pool these results with early binary protocols, other class/epoch/channel contracts, or external datasets.

Historical Q10-V001 prediction hashes use CRLF for Q5–Q9; cloud files use LF. All 19 cited source references match either exact bytes (four Q4 arm references) or CRLF canonicalization (15 others). JSON records actual and archived/canonical SHA-256 separately. Parsed trial identity is checked independently.

## Arm results

| Arm | People | Fits represented | Mean BA (%) | Subject SD (pp) | Scientific validator status |
|---|---:|---:|---:|---:|---|
| Q4-E001/BroadCSP_LDA | 9 | 9 | 39.0432 | 14.1768 | passed |
| Q4-E001/BroadCSP_SVM | 9 | 9 | 37.5000 | 12.6570 | passed |
| Q4-E001/FBCSP_LDA | 9 | 9 | 38.1173 | 7.6871 | passed |
| Q4-E001/FBCSP_MI8_LDA | 9 | 9 | 31.3657 | 4.2614 | passed |
| Q4-A001/FBCSP_MI16_LDA | 9 | 9 | 34.6451 | 8.4541 | passed |
| Q4-A001/FBCSP_MI32_LDA | 9 | 9 | 36.7477 | 8.8550 | passed |
| Q4-A001/FBCSP_MI72_LDA | 9 | 9 | 38.1173 | 7.6871 | passed |
| Q4-A001/FBCSP_MI8_LDA | 9 | 9 | 31.3657 | 4.2614 | passed |
| Q5-E001 | 9 | 27 | 33.7191 | 11.5839 | passed |
| Q6-E001 | 9 | 27 | 37.9308 | 15.6794 | passed |
| Q7-E001/B | 1 | 3 | 25.6944 | N/A | passed |
| Q7-E001/C | 1 | 3 | 67.7083 | N/A | passed |
| Q8-E001 | 9 | 27 | 42.6698 | 16.0436 | passed |
| Q9-A001/PSD44_LDA | 9 | 9 | 36.2847 | 8.1657 | passed_with_caveats |
| Q9-A001/PSD44_LINEAR_SVM | 9 | 9 | 35.7832 | 8.3876 | passed_with_caveats |
| Q10-A001/BROAD_LOGE_LOGREG | 9 | 9 | 35.3202 | 10.7401 | passed_scientific_artifact_validation |
| Q10-A001/BROAD_LOGE_MDM | 9 | 9 | 29.4946 | 8.7331 | passed_scientific_artifact_validation |
| Q10-A001/MUBETA_LOGE_LDA | 9 | 9 | 35.9954 | 10.7537 | passed_scientific_artifact_validation |
| Q10-A001/MUBETA_LOGE_SVM | 9 | 9 | 35.4745 | 8.8329 | passed_scientific_artifact_validation |
| Q9-E001/BETA_13_30 | 9 | 27 | 31.5329 | 10.0463 | passed_with_caveats |
| Q9-E001/MID_8_30 | 9 | 27 | 44.5538 | 17.1716 | passed_with_caveats |
| Q9-E001/MU_8_13 | 9 | 27 | 43.2999 | 16.2225 | passed_with_caveats |
| Q9-E001/MU_BETA_SHARED | 9 | 27 | 42.1875 | 14.0954 | passed_with_caveats |
| Q9-E002/MID_8_30_Q8_EPOCHS | 9 | 27 | 42.7276 | 15.7324 | passed_with_caveats |
| Q9-E002/MU_BETA_SHARED_Q8_EPOCHS | 9 | 27 | 43.4992 | 15.8216 | passed_with_caveats |
| Q9-E004/MU_BETA_SHARED_SOURCE_CLEAN | 9 | 27 | 42.1103 | 15.2327 | passed_with_caveats |
| Q9-E005/MU_BETA_SHARED_SOURCE_NORM | 9 | 27 | 41.5252 | 13.8797 | passed_with_caveats |
| Q10-E001/MU_BETA_CSP8_EEGNET | 9 | 27 | 41.4802 | 16.0363 | passed_scientific_checks |
| Q10-E001/MU_BETA_PCA8_EEGNET | 9 | 27 | 42.0589 | 15.5050 | passed_scientific_checks |
| Q11-E001/BROAD_CAPACITY_MATCHED | 9 | 27 | 42.1939 | 14.0513 | passed_scientific_checks |
| Q11-E001/FOUR_BAND_SHARED | 9 | 27 | 39.8020 | 11.5808 | passed_scientific_checks |
| Q11-E001/TWO_BAND_EARLY_STACK | 9 | 27 | 42.6569 | 16.2306 | passed_scientific_checks |
| Q11-E001/TWO_BAND_INDEPENDENT | 9 | 27 | 42.9913 | 17.3780 | passed_scientific_checks |
| Q7-E001/A_reused_Q5_S3 | 1 | 3 | 26.0995 | N/A | passed |
| Q7-E001/D_reused_Q6_S3 | 1 | 3 | 65.8565 | N/A | passed |

Q9 scientific evidence comes from the Q10-V001 prediction-level audit (`passed_with_caveats`); its batch validator checks orchestration only. Q10-E001 and Q11 validators passed scientific checks. Q10-A001 has `complete_validated` status and scientific artifact validation. Historical protocol and erratum wording from before completion is preserved.

## Paired subject comparisons

Mean differences and intervals use percentage points (pp). The new paired percentile bootstrap uses 200,000 subject resamples and seed 20261002. The exact sign-flip test enumerates all 2^n subject sign patterns. Q11 Holm correction covers four arms separately for each baseline. All tests are exploratory: repeated development comparisons and overlapping LOSO source fits limit inference.

| Contrast | n | Mean delta pp | Subject bootstrap 95% CI pp | Exact sign-flip p | Holm p |
|---|---:|---:|---|---:|---|
| Q4-E001/FBCSP_LDA minus Q4-E001/BroadCSP_LDA (exploratory_unadjusted) | 9 | -0.9259 | [-7.3881,+5.4784] | 0.851562 | — |
| Q4-E001/FBCSP_MI8_LDA minus Q4-E001/FBCSP_LDA (exploratory_unadjusted) | 9 | -6.7515 | [-9.5486,-3.7037] | 0.007812 | — |
| Q4-A001/FBCSP_MI16_LDA minus Q4-A001/FBCSP_MI8_LDA (posthoc_feature_count) | 9 | +3.2793 | [+0.6173,+6.6744] | 0.046875 | — |
| Q4-A001/FBCSP_MI32_LDA minus Q4-A001/FBCSP_MI8_LDA (posthoc_feature_count) | 9 | +5.3819 | [+2.1605,+8.7770] | 0.023438 | — |
| Q4-A001/FBCSP_MI72_LDA minus Q4-A001/FBCSP_MI8_LDA (posthoc_feature_count) | 9 | +6.7515 | [+3.7037,+9.5486] | 0.007812 | — |
| Q5-E001 minus Q4-E001/BroadCSP_LDA (exploratory_unadjusted) | 9 | -5.3241 | [-15.3935,+4.5012] | 0.292969 | — |
| Q6-E001 minus Q5-E001 (exploratory_unadjusted) | 9 | +4.2117 | [-1.1574,+13.4838] | 0.519531 | — |
| Q8-E001 minus Q5-E001 (exploratory_unadjusted) | 9 | +8.9506 | [+1.0674,+19.9524] | 0.015625 | — |
| Q8-E001 minus Q5-E001 (posthoc_exclude_S3_S8) | 7 | +1.4302 | [+0.4216,+2.5550] | 0.062500 | — |
| Q7-E001/B minus Q7-E001/A_reused_Q5_S3 (S3_only_mechanism) | 1 | -0.4051 | N/A: S3 case | N/A | — |
| Q7-E001/C minus Q7-E001/A_reused_Q5_S3 (S3_only_mechanism) | 1 | +41.6088 | N/A: S3 case | N/A | — |
| Q7-E001/D_reused_Q6_S3 minus Q7-E001/B (S3_only_mechanism) | 1 | +40.1620 | N/A: S3 case | N/A | — |
| Q7-E001/D_reused_Q6_S3 minus Q7-E001/C (S3_only_mechanism) | 1 | -1.8519 | N/A: S3 case | N/A | — |
| Q9-E001/MID_8_30 minus Q8-E001 (Q9_completed_frequency_secondary) | 9 | +1.8840 | [-1.4339,+5.0604] | 0.328125 | 0.656250 |
| Q9-E001/MU_8_13 minus Q8-E001 (Q9_completed_frequency_secondary) | 9 | +0.6301 | [-1.4082,+2.9450] | 0.644531 | 0.656250 |
| Q9-E001/BETA_13_30 minus Q8-E001 (Q9_completed_frequency_secondary) | 9 | -11.1368 | [-19.8881,-3.5622] | 0.015625 | 0.046875 |
| Q9-E001/MU_BETA_SHARED minus Q8-E001 (Q9_primary) | 9 | -0.4823 | [-3.2086,+1.4339] | 0.914062 | — |
| Q9-E002/MID_8_30_Q8_EPOCHS minus Q8-E001 (Q9_sensitivity) | 9 | +0.0579 | [-1.4275,+1.5111] | 0.945312 | — |
| Q9-E002/MID_8_30_Q8_EPOCHS minus Q9-E001/MID_8_30 (Q9_sensitivity) | 9 | -1.8261 | [-4.9447,+0.9838] | 0.285156 | — |
| Q9-E002/MU_BETA_SHARED_Q8_EPOCHS minus Q8-E001 (Q9_sensitivity) | 9 | +0.8295 | [-0.2958,+1.9612] | 0.218750 | — |
| Q9-E002/MU_BETA_SHARED_Q8_EPOCHS minus Q9-E001/MU_BETA_SHARED (Q9_sensitivity) | 9 | +1.3117 | [-0.1543,+3.2536] | 0.375000 | — |
| Q9-E004/MU_BETA_SHARED_SOURCE_CLEAN minus Q8-E001 (Q9_sensitivity) | 9 | -0.5594 | [-2.0576,+1.0352] | 0.507812 | — |
| Q9-E004/MU_BETA_SHARED_SOURCE_CLEAN minus Q9-E001/MU_BETA_SHARED (Q9_sensitivity) | 9 | -0.0772 | [-1.3053,+1.4982] | 0.933594 | — |
| Q9-E005/MU_BETA_SHARED_SOURCE_NORM minus Q8-E001 (Q9_sensitivity) | 9 | -1.1445 | [-3.6073,+0.9002] | 0.437500 | — |
| Q9-E005/MU_BETA_SHARED_SOURCE_NORM minus Q9-E001/MU_BETA_SHARED (Q9_sensitivity) | 9 | -0.6623 | [-2.6235,+0.9774] | 0.621094 | — |
| Q9-A001/PSD44_LDA minus Q4-E001/BroadCSP_LDA (spectral_shallow_control) | 9 | -2.7585 | [-8.0054,+2.2184] | 0.351562 | — |
| Q9-A001/PSD44_LINEAR_SVM minus Q4-E001/BroadCSP_LDA (spectral_shallow_control) | 9 | -3.2600 | [-8.7963,+1.9676] | 0.296875 | — |
| Q10-E001/MU_BETA_CSP8_EEGNET minus Q9-E001/MU_BETA_SHARED (Q10_spatial) | 9 | -0.7073 | [-3.3243,+2.3791] | 0.644531 | — |
| Q10-E001/MU_BETA_PCA8_EEGNET minus Q9-E001/MU_BETA_SHARED (Q10_spatial) | 9 | -0.1286 | [-3.3951,+3.4915] | 0.945312 | — |
| Q10-E001/MU_BETA_CSP8_EEGNET minus Q10-E001/MU_BETA_PCA8_EEGNET (Q10_spatial_declared_pair) | 9 | -0.5787 | [-2.6620,+1.2088] | 0.628906 | — |
| Q10-A001/BROAD_LOGE_MDM minus Q4-E001/BroadCSP_LDA (Q10_geometry) | 9 | -9.5486 | [-18.3063,-2.1026] | 0.042969 | — |
| Q10-A001/BROAD_LOGE_LOGREG minus Q4-E001/BroadCSP_LDA (Q10_geometry) | 9 | -3.7230 | [-8.0440,-0.0193] | 0.121094 | — |
| Q10-A001/MUBETA_LOGE_LDA minus Q4-E001/BroadCSP_LDA (Q10_geometry) | 9 | -3.0478 | [-7.4267,+1.0995] | 0.226562 | — |
| Q10-A001/MUBETA_LOGE_SVM minus Q4-E001/BroadCSP_LDA (Q10_geometry) | 9 | -3.5687 | [-8.6227,+1.4275] | 0.253906 | — |
| Q10-A001/BROAD_LOGE_LOGREG minus Q10-A001/BROAD_LOGE_MDM (Q10_same_representation_classifier) | 9 | +5.8256 | [-1.2346,+13.9082] | 0.210938 | — |
| Q11-E001/FOUR_BAND_SHARED minus Q8-E001 (Q11_four_vs_Q8) | 9 | -2.8678 | [-6.1600,+0.0129] | 0.164062 | 0.656250 |
| Q11-E001/FOUR_BAND_SHARED minus Q9-E001/MU_BETA_SHARED (Q11_four_vs_Q9_shared) | 9 | -2.3855 | [-4.9769,-0.3922] | 0.058594 | 0.234375 |
| Q11-E001/TWO_BAND_INDEPENDENT minus Q8-E001 (Q11_four_vs_Q8) | 9 | +0.3215 | [-2.0705,+2.8549] | 0.808594 | 1.000000 |
| Q11-E001/TWO_BAND_INDEPENDENT minus Q9-E001/MU_BETA_SHARED (Q11_four_vs_Q9_shared) | 9 | +0.8038 | [-1.9869,+3.4336] | 0.609375 | 1.000000 |
| Q11-E001/TWO_BAND_EARLY_STACK minus Q8-E001 (Q11_four_vs_Q8) | 9 | -0.0129 | [-2.1026,+2.3598] | 1.000000 | 1.000000 |
| Q11-E001/TWO_BAND_EARLY_STACK minus Q9-E001/MU_BETA_SHARED (Q11_four_vs_Q9_shared) | 9 | +0.4694 | [-2.0062,+3.0157] | 0.730469 | 1.000000 |
| Q11-E001/BROAD_CAPACITY_MATCHED minus Q8-E001 (Q11_four_vs_Q8) | 9 | -0.4758 | [-2.1476,+1.0867] | 0.605469 | 1.000000 |
| Q11-E001/BROAD_CAPACITY_MATCHED minus Q9-E001/MU_BETA_SHARED (Q11_four_vs_Q9_shared) | 9 | +0.0064 | [-1.9419,+2.0319] | 1.000000 | 1.000000 |
| Q11-E001/TWO_BAND_INDEPENDENT minus Q11-E001/BROAD_CAPACITY_MATCHED (Q11_capacity) | 9 | +0.7973 | [-1.7361,+3.6844] | 0.613281 | — |

## Scientific interpretation

Q5 EEGNet has mean BA 33.72%; source-normalized Q6 has 37.93%, a paired +4.21 pp with an interval crossing zero. Q6 also changes the S3 selected duration from 2 to 16 epochs and gains 39.76 pp on S3. Q7 tests that single case: raw input at 2 epochs gives 26.10%, normalized input at 2 epochs 25.69%, raw input at 16 epochs 67.71%, and normalized input at 16 epochs 65.86%. Longer training rescues S3 while normalization at 2 epochs does not. This is a computational mechanism case study, with no population causal claim.

Q8 freezes mean-rank selections from existing Q5 source-validation curves before new final fits, preserving data, preprocessing and architecture. BA is 42.67%, a +8.9506 pp difference from Q5, with a new bootstrap interval [1.0674, 19.9524] pp. Seven subjects improve and two tie. S3 and S8 account for 87.57% of the total gain. The posthoc analysis excluding S3/S8 is diagnostic only. Mean rank is a development repair, without independent confirmation or evidence of universal optimality. Source-loss audits show validation-fold influence and candidate-rule sensitivity.

Q9 shared mu/beta BA is 42.19% and does not outperform Q8 (−0.4823 pp). Keep every frequency, fixed-duration, source-clean and source-normalized control visible. Q10 CSP/PCA contrasts do not establish superiority and also change projected width, architecture and scaling compared with shared fusion. Geometry is in-house log-Euclidean; affine-invariant MDM/tangent-space terminology would be inaccurate. MDM similarity scores are not calibrated probabilities. Q11 gives 39.80% for four-band sharing, 42.99% for independent branches, 42.66% for early stacking, and 42.19% for approximate capacity matching. None establishes spectral-network superiority. The capacity comparison has 5,914 versus 5,864 parameters, differing by 50 (0.8527%).

Recommended mainline: source-only duration selection can be fragile under cross-subject validation; mechanism diagnosis changes interpretation of apparent normalization/representation gains. Q8 provides an exploratory repair; Q9–Q11 show its representation/architecture limits and negative results. Task-matched independent confirmation belongs to future work.

## Statistical naming and material findings

- **P1 Q8 archived sign_test_p**: The original Q8 script uses binomtest(sum(delta > 0), n = len(delta) = 9), including two ties in the denominator. Archived nine-subject sign sensitivity: p = 0.1796875. Conventional tie-excluding sensitivity: p = 0.015625 (7 positive, 0 negative, 2 tied). Proposed remedy: Report both transparently with their exact definitions; do not choose a favorable p or modify frozen statistics. Q6 has 6 positive, 3 negative and no ties; both calculations give p = 0.5078125.
- **P1 Q10-V001 archived prediction hashes**: Current Linux Q5-Q9 CSVs are LF, historical hashes are CRLF. All cited19 sources match either exact bytes (four Q4 arm references) or only LF-to-CRLF canonicalization (15 other references). Proposed remedy: Record actual byte SHA and archived/canonicalized SHA separately; no claim of unchanged raw CSV bytes. Parsed trial identities checked independently.
- **P1 Q9 scientific validation**: Q9 batch pass is orchestration-only; Q10-V001 later independently validated predictions/source manifests/selection artifacts without raw EEG/checkpoint replay. Recorded runtime commit lacks Q9 protocol/matrix/runner. Proposed remedy: Cite actual scope; no preregistration or external confirmation claim.
- **P1 Q7 S3 factorial**: OnlyS3 B/C newlyfit; A/D reusedQ5/Q6. Three seeds do not increase subject n. Proposed remedy: Mechanism case study, no population CI/test or nine-person pooling.
- **P1 Q10 geometry**: Completed validation now exists despite stale not-run protocol/erratum. In-house log-Euclidean geometry differs from affine-invariant tangent space/MDM. MDM scores not calibrated probabilities; band/classifier changes confound geometry comparison. Proposed remedy: Use complete_validated and validator; describe exact geometry and limitations.
- **P1 Q11 capacity**: 5914 broadband parameters versus5864 independent branches: +50,+.8526603%, approximate match. Proposed remedy: Disclose mismatch, retain all4 conditions and Holm values; no established spectral/network superiority.

The original Q8 script sets n = 9 in binomtest, including two zero differences in the denominator. Keep the archived nine-subject sign sensitivity (0.1796875) and conventional tie-excluding sensitivity (0.015625) transparently named. Do not select the favorable p. Q6 has six positive, three negative and no ties: both sign calculations are 0.5078125; paired t p = 0.374301 and exact sign-flip p = 0.519531. No frozen statistic was changed.

## Early binary method QC supplement inventory

| Artifact | Task and target population | Target information and sensors | Validation/run | Placement |
|---|---|---|---|
| outputs/P2-E001 | Binary left/right hand; expert-clean targets; within-session leave-run-out, cross-session training-session to evaluation-session, and cross-subject LOSO. | Within/cross-session models use labelled trials from the evaluated person; cross-subject models exclude both target sessions. | validated/complete | Early split and method QC supplement; modes kept separate from each other and from four-class primary results. |
| outputs/P2-E002-ALLTRIALS | Binary left/right hand; all 2,592 trials; cross-subject LOSO only. | Source-only LOSO; both target sessions excluded. Training and testing composition both change relative to P2 clean targets. | validated/complete | Posthoc population sensitivity supplement; no causal artifact-removal conclusion. |
| outputs/P3-E001 | Binary left/right hand; nine-subject LOSO; 2,346 expert-clean targets primary; all/flagged strata secondary; CSP4, PSD88 and fusion92 under two source training policies. | CSP, scaler and classifier fit on source subjects. Expert target flags define the primary clean endpoint. | validated/complete | Exploratory spectral and artifact QC supplement; no four-class confirmation or deployable artifact detection claim. |
| outputs/P4-E001B | Binary left/right hand; nine-subject LOSO; source-fitted EOG correction versus the P3-identical uncorrected comparator; clean targets primary. | Coefficients fit on clean source subjects. Apply them to three synchronous target EOG channels per trial, with no target parameter fit. | validated/complete | Exploratory EOG-assisted QC supplement; three extra sensors; lower correlation does not prove selective ocular removal. |

P2 clean-target LOSO gives LDA 62.76% and SVM 62.09%; all-trial LOSO gives LDA 61.50% and SVM 60.57%. Within-session and cross-session scores use labelled information from the evaluated person and belong in separate calibration-setting rows. The all-trial comparison changes both training and testing populations, so it does not identify a causal artifact effect.

P3 expert-clean primary BA is CSP 62.85%, PSD 58.19%, and fusion 64.63%, with identical clean target IDs across training policies. This is binary spectral-feature QC after P2 exploration, without four-class confirmation. The successful P4 EOG retry changes clean-target BA from 62.85% to 62.57%, a paired −0.2807 pp, with archived CI [−1.0916, +0.5937] pp. It uses three synchronous EOG sensors and frozen source coefficients. Lower EEG–EOG correlation does not prove selective ocular removal. Keep the initial P4 interface failure as a failure record.

P2-E002 retains the copied experiment_id P2-E001 and legacy n_clean_epochs = 2592; effective_artifact_policy = include describes its actual population. P4-E001B retains protocol ID P4-E001 and is the successful retry after an explicit MNE picks=eog repair. Historical names and source files remain unchanged.

## Exact input provenance

Every arm lists precise prediction, config, validation, selection and source-manifest hashes, with subject × seed confusion matrices in JSON. Early binary cross-subject summary BA was independently recomputed from predictions. Within-session and cross-session rows are archived inventory only. Bootstrap limits may differ slightly from old reports because the fresh seed and draw count are disclosed.

| Input | Actual SHA-256 |
|---|---|
| /workspace/cross-subject-mi-eeg/results/Q10-E001/MU_BETA_CSP8_EEGNET/predictions.csv | 32e7d2b3ce9ce277b6bbd9073de001db9444b19232324cd2d752bc6e30b25def |
| /workspace/cross-subject-mi-eeg/results/Q10-E001/MU_BETA_CSP8_EEGNET/run_config.json | 295f27bce12178f97d60d8b562ab4d3da96dc28042037607097f82773a0d4b7d |
| /workspace/cross-subject-mi-eeg/results/Q10-E001/MU_BETA_CSP8_EEGNET/selection.csv | 9787d5e0e826fff3d29c3913f1a1ddcb4219f269d49bddb0f0a2421dbe84ddc1 |
| /workspace/cross-subject-mi-eeg/results/Q10-E001/MU_BETA_CSP8_EEGNET/selection_provenance.json | 5c71eba7c582bc01b6facca75d781757a1a11c0b8de87c80634eaf95273e9d82 |
| /workspace/cross-subject-mi-eeg/results/Q10-E001/MU_BETA_CSP8_EEGNET/source_files.json | 273c6ad7b456a01fecc9982d537e178fa50734b45795c1b6d62477f422475652 |
| /workspace/cross-subject-mi-eeg/results/Q10-E001/MU_BETA_CSP8_EEGNET/status.json | 2628b1eca13034e80d248f43c2504b5a9ddfcf35028e3db6bbe1959c97b801c2 |
| /workspace/cross-subject-mi-eeg/results/Q10-E001/MU_BETA_PCA8_EEGNET/predictions.csv | bdc160fd328c4ebd97062b071e271c5723398c3fa9646a5210d479ea29a5a5bc |
| /workspace/cross-subject-mi-eeg/results/Q10-E001/MU_BETA_PCA8_EEGNET/run_config.json | 21762fdef5f072b0c6e3680c541344f0be859243a8b923824e7a68f339ec7d28 |
| /workspace/cross-subject-mi-eeg/results/Q10-E001/MU_BETA_PCA8_EEGNET/selection.csv | 10f750302d06e8f76d3502648a42bab6edeb13e404e785a77ffec529aa803f84 |
| /workspace/cross-subject-mi-eeg/results/Q10-E001/MU_BETA_PCA8_EEGNET/selection_provenance.json | 17b810767fd2ac8faf2557012ee85e349b303972121f17d140778487863838ec |
| /workspace/cross-subject-mi-eeg/results/Q10-E001/MU_BETA_PCA8_EEGNET/source_files.json | 273c6ad7b456a01fecc9982d537e178fa50734b45795c1b6d62477f422475652 |
| /workspace/cross-subject-mi-eeg/results/Q10-E001/MU_BETA_PCA8_EEGNET/status.json | d6041b456ed14a98fb38fcc4fc0bcb945ba88aa1a3999c596404379ec935fb4c |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/BROAD_CAPACITY_MATCHED/predictions.csv | 8b24df4baf88950f321ecfd1bd3163f0a57f4306978e4aae25872a88ceb93b21 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/BROAD_CAPACITY_MATCHED/run_config.json | 0bbe3cead1136ad66588ef3cbe8f983802e14a991404a814de58efd98ec58f4c |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/BROAD_CAPACITY_MATCHED/selection.csv | 587cf233b74c84fcdef89c4c10152d03b8a91d43fee8ca91d28b872f927afcf4 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/BROAD_CAPACITY_MATCHED/selection_provenance.json | bef925429d3b0e8659d16ac4c2bb3cb2378b5775bbda7f0d4c77d23092400fa3 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/BROAD_CAPACITY_MATCHED/source_files.json | 273c6ad7b456a01fecc9982d537e178fa50734b45795c1b6d62477f422475652 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/BROAD_CAPACITY_MATCHED/status.json | 842ed0b4eebc9c712a091d136757a214ee68a101b9dce77516ce265d87056b91 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/FOUR_BAND_SHARED/predictions.csv | 05dae6bbb4ac6aac6215604bbd38b8acd0dd3629b4eba0387c1fa2217aa538dc |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/FOUR_BAND_SHARED/run_config.json | bd405ea5c5f19093770578fe2c6cee5cd7a316e541ad7338cc6f772a3fd40d21 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/FOUR_BAND_SHARED/selection.csv | 15ca58d8487bc823f441b8da3272f42a9277f515525652c4c7d80871348f1da6 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/FOUR_BAND_SHARED/selection_provenance.json | 89d7f7a928ccff31806ce12bc4728f9d437d5a963b3d1f1cd0fa4f18980e78cb |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/FOUR_BAND_SHARED/source_files.json | 273c6ad7b456a01fecc9982d537e178fa50734b45795c1b6d62477f422475652 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/FOUR_BAND_SHARED/status.json | 91471ab7768f8648cf899a3d29a822dc02b642dac45d0a3db37862cd1958b202 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/TWO_BAND_EARLY_STACK/predictions.csv | 1baef6cbdf5af117ea3838e2acf509fc4069d9c4a17c4982f9a998aa2976f764 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/TWO_BAND_EARLY_STACK/run_config.json | 8f873b18190a234bd68972cd06b6f1827fa982ab5329ce5a1d80c7bb4cc091b5 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/TWO_BAND_EARLY_STACK/selection.csv | 16d9a0411593c742f723d7aef462a4c199510bf57542b088dafabe851bf054a3 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/TWO_BAND_EARLY_STACK/selection_provenance.json | 57a2c6718ba178e28e169ffc0f957d6907b67639cf1ba5d441c84df4d105288e |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/TWO_BAND_EARLY_STACK/source_files.json | 273c6ad7b456a01fecc9982d537e178fa50734b45795c1b6d62477f422475652 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/TWO_BAND_EARLY_STACK/status.json | a4aa477e2eb52acd8b0780b5fb20a551992dc9aafbec9b7a509435291de5b0b1 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/TWO_BAND_INDEPENDENT/predictions.csv | ed2f41eca0a8e15b544aab26c6a1fc9cbd5e9475840f905780d669a70d93df98 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/TWO_BAND_INDEPENDENT/run_config.json | b3c2a7bc36f49212435dbf8f9ca9e1e8facb08684e16fa0b2756c2694313a616 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/TWO_BAND_INDEPENDENT/selection.csv | 3283beef69e3195947c4a49ef9fcf3565c1c31e1f97e13ea7077ec6d069f6956 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/TWO_BAND_INDEPENDENT/selection_provenance.json | af9ca0507e60a54363030b76d3b9a07f4fc054baf3c962c8f60ba880c6d8f797 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/TWO_BAND_INDEPENDENT/source_files.json | 273c6ad7b456a01fecc9982d537e178fa50734b45795c1b6d62477f422475652 |
| /workspace/cross-subject-mi-eeg/results/Q11-E001/TWO_BAND_INDEPENDENT/status.json | 18567f48d0ad3fe9ebb651efc566396cee9563ee9e05fac453b6e8a51e2d460c |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/BETA_13_30/predictions.csv | 891259ea9a295d0759c2ac0b95cccba0fd85ddc53530cff07975e17a2c90a21a |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/BETA_13_30/run_config.json | ba8af0b8f85954bcb54070f28de1540f29e36d8591f562c79be52fe1f4c5ba90 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/BETA_13_30/selection.csv | c30545ed762834d60f39882067cfe82b5ba5825fd2cac935bb13c1c5068238d1 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/BETA_13_30/selection_provenance.json | 75d93c40c04ce453575b4393064c69ee1a35a964a646d2893127ec2eee179073 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/BETA_13_30/source_files.json | 273c6ad7b456a01fecc9982d537e178fa50734b45795c1b6d62477f422475652 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/BETA_13_30/status.json | 729d9eb33f8db4fe128114c836b466b560181d350a41b875584c5d29f8355bc6 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/MID_8_30/predictions.csv | 98b9b2508b410d589a9b7a2ca05d24a58fba4a6325654d0923bb28f1c6889570 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/MID_8_30/run_config.json | 946182fee91e52116f63b67203bfbaec3b67008cfe8abe5fb04cad4ad2bd6665 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/MID_8_30/selection.csv | 47fb38af882509bc6ad76d3320ff808f4b4a1d8184ce2965552925d8c15ed850 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/MID_8_30/selection_provenance.json | fd410ab17d34ade9126ca032729c5ecf30e679b2a4d03f964fc25982e8da8873 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/MID_8_30/source_files.json | 273c6ad7b456a01fecc9982d537e178fa50734b45795c1b6d62477f422475652 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/MID_8_30/status.json | bd975194ae210a22b035014caf89c82869f96c4842a61d270715b8cbf12e3496 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/MU_8_13/predictions.csv | d4b74745f300f3c7a90d215e8077d6ac87de6fe96a22cd95c43976d21f96a298 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/MU_8_13/run_config.json | e91d43c155697bc0d12da5a38d8295dfb7a138560b8cd41933d3d3e6bfe44334 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/MU_8_13/selection.csv | cc50158fad20971b0e84f01227307aa0f2fc161eb33181bf87723a243799fa62 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/MU_8_13/selection_provenance.json | 77a636c8cee88d80d4c46bb68ec87e5eac9307aab31849dad045d215f174b3c3 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/MU_8_13/source_files.json | 273c6ad7b456a01fecc9982d537e178fa50734b45795c1b6d62477f422475652 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/MU_8_13/status.json | 174127068c8ddb2fb9e63227c5e5929db4042df1676e44b5aeacd4d8e887a462 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/MU_BETA_SHARED/predictions.csv | 9774b3db174d2510d466bf034165331bf697ddf0344af110d64e040dff3ce488 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/MU_BETA_SHARED/run_config.json | 3454cbc0b89e0b0786a256681224f3f03686200a9f5a62d5464f12c29db9cd92 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/MU_BETA_SHARED/selection.csv | 0aa3ea2dbd03d1328176fd4cafd2221a7ad205f1cfdd02db6c86f39fd5a44b61 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/MU_BETA_SHARED/selection_provenance.json | 210cc0d50811d1a8d661543e25cacc0579bd522db82758b0f419615e70f3da3b |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/MU_BETA_SHARED/source_files.json | 273c6ad7b456a01fecc9982d537e178fa50734b45795c1b6d62477f422475652 |
| /workspace/cross-subject-mi-eeg/results/Q9-E001/MU_BETA_SHARED/status.json | eb5c0732c0288e6d7c082d47dea446542ba2e8827a93591ccd4d9b7ceeb02b4a |
| /workspace/cross-subject-mi-eeg/results/Q9-E002/MID_8_30_Q8_EPOCHS/predictions.csv | fb7e86ad560ee4b0e0da36279f61f9871b2509dbaba57b81686ac765e7064452 |
| /workspace/cross-subject-mi-eeg/results/Q9-E002/MID_8_30_Q8_EPOCHS/run_config.json | a99ad17dc3c41f6f4c9c141b16a4515b84e02a4a36e0444f6d47ea462ee06989 |
| /workspace/cross-subject-mi-eeg/results/Q9-E002/MID_8_30_Q8_EPOCHS/source_files.json | 273c6ad7b456a01fecc9982d537e178fa50734b45795c1b6d62477f422475652 |
| /workspace/cross-subject-mi-eeg/results/Q9-E002/MID_8_30_Q8_EPOCHS/status.json | c1b9abe4755e38272583614aee425bc10d5e1e0edd09b83366491c0fd20ee479 |
| /workspace/cross-subject-mi-eeg/results/Q9-E002/MU_BETA_SHARED_Q8_EPOCHS/predictions.csv | 113a8af21c62df3e1898b2b8f471d93147017ca126d1367e6a16bedd8a292352 |
| /workspace/cross-subject-mi-eeg/results/Q9-E002/MU_BETA_SHARED_Q8_EPOCHS/run_config.json | b231c638a1fe222478662b2c09af32ee6fa7d9d6e54988bc0ff82fdb22d73d25 |
| /workspace/cross-subject-mi-eeg/results/Q9-E002/MU_BETA_SHARED_Q8_EPOCHS/source_files.json | 273c6ad7b456a01fecc9982d537e178fa50734b45795c1b6d62477f422475652 |
| /workspace/cross-subject-mi-eeg/results/Q9-E002/MU_BETA_SHARED_Q8_EPOCHS/status.json | 0f75d6b10069d88a5f5d123c33aa75f7628030e1162e2d22d24e20f329693b71 |
| /workspace/cross-subject-mi-eeg/results/Q9-E004/MU_BETA_SHARED_SOURCE_CLEAN/predictions.csv | 389d5b4c23f9dfe2dc9ea9170c280f213d2bd66612ee3a1311da15943ceeeb9c |
| /workspace/cross-subject-mi-eeg/results/Q9-E004/MU_BETA_SHARED_SOURCE_CLEAN/run_config.json | d355d5faff63bb2831c67d320c41e9e44c275213ff3a2378c9e2ebf346b90cc6 |
| /workspace/cross-subject-mi-eeg/results/Q9-E004/MU_BETA_SHARED_SOURCE_CLEAN/selection.csv | eafc9277f1f3e610746c7d8b10304c362382f44029aa03d04d4e03f0874ea4e2 |
| /workspace/cross-subject-mi-eeg/results/Q9-E004/MU_BETA_SHARED_SOURCE_CLEAN/selection_provenance.json | 97947fc4c2a572f87cef562e57eb90f0167fe83fa59add7db9bf8751d0e095e8 |
| /workspace/cross-subject-mi-eeg/results/Q9-E004/MU_BETA_SHARED_SOURCE_CLEAN/source_files.json | 273c6ad7b456a01fecc9982d537e178fa50734b45795c1b6d62477f422475652 |
| /workspace/cross-subject-mi-eeg/results/Q9-E004/MU_BETA_SHARED_SOURCE_CLEAN/status.json | ed185ebb1682b08fcd1991b1ef67b42de605601b42df175a8e95e42f93ee2eb2 |
| /workspace/cross-subject-mi-eeg/results/Q9-E005/MU_BETA_SHARED_SOURCE_NORM/predictions.csv | c4c33b156d3a8bf583246e5181d6f0bd77b3f92e06a765a017a5ff97db26401c |
| /workspace/cross-subject-mi-eeg/results/Q9-E005/MU_BETA_SHARED_SOURCE_NORM/run_config.json | d48513c6a9d272d6d846cef6ff3a4cc2d3f1e2ecfd90bfcbddc347debdf17ade |
| /workspace/cross-subject-mi-eeg/results/Q9-E005/MU_BETA_SHARED_SOURCE_NORM/selection.csv | f0d9fc9fa0ece9a08f381e03cf0582013b968598ba657d41c683850e60af4121 |
| /workspace/cross-subject-mi-eeg/results/Q9-E005/MU_BETA_SHARED_SOURCE_NORM/selection_provenance.json | 3fd7555e4cf74f990ac60b53688d245c150307595437ca1db8957e3d3b7fb8a7 |
| /workspace/cross-subject-mi-eeg/results/Q9-E005/MU_BETA_SHARED_SOURCE_NORM/source_files.json | 273c6ad7b456a01fecc9982d537e178fa50734b45795c1b6d62477f422475652 |
| /workspace/cross-subject-mi-eeg/results/Q9-E005/MU_BETA_SHARED_SOURCE_NORM/status.json | 0e755cbb1e284c4ed62be3a9e8f93ce33da74b871d63c97f26f7e93b4a8d0ae0 |
| docs/expanded_manuscript_sample.md | 610b8bea35a31e9c959a1db539c95c5af30fcdbe892539f0a42fe1729580e72a |
| docs/research_progress.md | 256025ae30264cfd88334cc2d7d7a615d1ceba4f21e83161bcc08625ef130f20 |
| outputs/P2-E001/config.json | 6bc10b0de0f95f8a6df1ff510f15a7affbd1c4c5da0b0e6f38afad49a13704ff |
| outputs/P2-E001/predictions.csv | d8d0ad26ef6704845e75d494b08dc35cf1afd66fd438cebbc5d8b1ebb2babdd8 |
| outputs/P2-E001/run_status.json | c7a75e702b92c97dbc10bd3fed45648dc976714f7e446f41687dc63920867904 |
| outputs/P2-E001/source_files.json | 5e709fe501f2cbd583219a15be4156ae1a62b025f4eca0819b483b38a96ab0fd |
| outputs/P2-E001/summary.csv | 70bea45335de62ffd3511d8175f13a5a94108a1cb8828a0c6df803e0fc4142c0 |
| outputs/P2-E001/validation_report.json | 1c96ea716b6cc3c1491b8200457770c4851e71582f2d95fc6f6bf7aa89fa9d23 |
| outputs/P2-E002-ALLTRIALS/config.json | dcbe28ee90569630a96b5e87160b74a50852fac767337282cb5dd6239c866d09 |
| outputs/P2-E002-ALLTRIALS/predictions.csv | 42eaaee9815865cf50fc9daaea85e7b6515734dbf09a84bcfa2491ab2fbf6b98 |
| outputs/P2-E002-ALLTRIALS/run_status.json | dc9275f69404e3eda6ec336fd8c4dc67061d6ab285f805699b5b69d5852079f0 |
| outputs/P2-E002-ALLTRIALS/source_files.json | 5e709fe501f2cbd583219a15be4156ae1a62b025f4eca0819b483b38a96ab0fd |
| outputs/P2-E002-ALLTRIALS/summary.csv | 39dac30dfa8f37c5bef640134ec9dd1f4c630fb6b0a29ee6812cb744205d48ba |
| outputs/P2-E002-ALLTRIALS/validation_report.json | 5e4d05cbde55eb49255ef9727f0fb7cc06f1918281e2e621f88f6fbe665641db |
| outputs/P3-E001/predictions.csv | b02e7f112229ab6d3b4edbfb7c7365192c2b279012695ea651aef7b5f87ef084 |
| outputs/P3-E001/protocol.json | 11cc40dc383b426e2e7ee75f07eefdb77711f43c01ed47fe7bb390b9594e5ca9 |
| outputs/P3-E001/run_status.json | e7a2db95fc7667204b5b62437c53d2a6064383229865729eec5416c71fd74179 |
| outputs/P3-E001/source_files.json | 5e709fe501f2cbd583219a15be4156ae1a62b025f4eca0819b483b38a96ab0fd |
| outputs/P3-E001/summary.csv | dcad511de167cc9637dccc41a9d30f54b48305fa292ae6d77973ffd1ec610d4e |
| outputs/P3-E001/validation_report.json | 3e83473d64e6abaca3a6cdcb441447ee7524ff55be41c6af46947c57fa5c9981 |
| outputs/P4-E001B/predictions.csv | 1a33dfcad6cb9a705d82ef3f4a2d8af594e8dfb6438991663863fecc3df28975 |
| outputs/P4-E001B/protocol.json | f39299a885bed1ee71fd4b72dd08829b24bdce81358427c3ea696688cb94b2a2 |
| outputs/P4-E001B/run_status.json | d0946a75609f809766adba9727ca84542b46b9b1c6344873d479a05e22bff4ea |
| outputs/P4-E001B/source_files.json | 5e709fe501f2cbd583219a15be4156ae1a62b025f4eca0819b483b38a96ab0fd |
| outputs/P4-E001B/summary.csv | 0a36dae47f66724a81693c32b6271c99993626fc67bd6b2ad72116556dad1f6c |
| outputs/P4-E001B/validation_report.json | 3fcebf65c52cefd8d057c7a22d97342e26636b3f094e079b2ca5749cb394c3f4 |
| outputs/Q4-A001/config.json | 72f50664a7b25618cd37c6a78d0e258bf1d6cead82370b84852c99071b9251b1 |
| outputs/Q4-A001/parent_inputs.json | 9475aa4c523dba1238fc0ee155ccb612d3029c5499d34dff48ed526ee0e02844 |
| outputs/Q4-A001/predictions.csv | f91ad580bedd5af403bb760e1b17f433c85bbf80977a8cd401e2ba97967af834 |
| outputs/Q4-A001/status.json | 2f8068e5ecf27b0677b0249e04ad9a3b26705c918a6a8c83132b592a9d7234a1 |
| outputs/Q4-A001/validation_report.json | 693fdc2aec731439755e936770a391e34b733733a76b74a293c6abb930473acb |
| outputs/Q4-E001/config.json | 9ff8e1f74fc9113713adfdfa7f0f029abd4f9142a41afe4e33738fe3a17a3979 |
| outputs/Q4-E001/predictions.csv | f2652a7e9096bad57bfe1ae53fdd44f20fb02b4346d15858c92fb0bd36fbd887 |
| outputs/Q4-E001/source_files.json | d782c59eb4534c82dd2293a9f28e0c22f8d6927605ea505296a500450fa36108 |
| outputs/Q4-E001/status.json | 6897bab36eed703076bc43256200e70168d37e7d0c2d112f360bd25380095cb9 |
| outputs/Q4-E001/validation_report.json | 63f8075b20fc8e894964f592294aa84382012bc5f1e05a79df50d4c24fd117f2 |
| research_runs/Q10-A001/PROTOCOL.md | 5b24c73e7c2484fa86422f315392e13557e29f69a32e0b820f9f7ec841d6b510 |
| research_runs/Q10-A001/TECHNICAL_ERRATUM_2026-09-25.md | c766a6637161e61ceb909c9a19dd3a155e5aa72b46f6a393f7f8be9a6cbc8526 |
| research_runs/Q10-E001/MATRIX.json | fab024fddfdcf3103c4025690380088ce15b74b97b629ccd6d9ad3d28a0adeda |
| research_runs/Q10-E001/PROTOCOL.md | 886bd35d1a205f04bf15b643e0c7cd13711d71d3dd940f91636ef56a19aade9f |
| research_runs/Q11-E001/MATRIX.json | 21a728ae27908d911a5e27ed5d7818478bee36c10a9159d5b04259a4d4512d0a |
| research_runs/Q11-E001/PROTOCOL.md | 46caae7cd75a51896bf8d20f3e32f15352d4d24639f6764307e291cd8bc50a66 |
| research_runs/Q6-E001/posthoc_analysis/paired_subject_statistics.json | 4ebf3abff642473675befd36a2844260f371edb9e495ce857c29b914b1d555d7 |
| research_runs/Q6-E001/results/config.json | 670a2dc8b5060e77c64f3674f215351b244a59760e8dd2cbc898b913f4afe8f5 |
| research_runs/Q6-E001/results/normalization_receipts.json | 5dc22e720160baf43d0b9ca6a585b7da2efb8cad5a28b192184576f68c68cb98 |
| research_runs/Q6-E001/results/predictions.csv | 08058539746b14fe21a9a8bbfdabbec15f5ddb5b9790790fadabf5bd8293f8a1 |
| research_runs/Q6-E001/results/selection.csv | 84fb853cb4d67376c82b675df0c2500b7ac8ccb974c421583b53d87482d9ee08 |
| research_runs/Q6-E001/results/source_files.json | 0ccef780ed5bfbc2d430b8caf0c108641fb230a2dc27e4189e7e771c999f64a6 |
| research_runs/Q6-E001/results/status.json | 137035543da456984e4ce8bccddda34ab72813ec9d9f91a2def986b87a376cfe |
| research_runs/Q6-E001/results/validation_report.json | f954c4b3bd1466f81bf3a3264d5a4f8adcfb3fb7ee99764a7c38d2066d5a9cce |
| research_runs/Q7-E001/analysis/Q7_MECHANISTIC_REPORT.md | 58d4323c5ed9acc677e797df75c8512acced8be004e2ad80705e3124814d2165 |
| research_runs/Q7-E001/analysis/validation_report.json | 266dec76409d8ff65c53cd1a58839316fec6edb18d911ebd40b862c58f2aba64 |
| research_runs/Q7-E001/results/condition_B_source_normalizer.json | 954953759b3fe921dcb413ae6cefa42e30e22c911036127add061afdaf05a606 |
| research_runs/Q7-E001/results/predictions.csv | 3d31a284ab1da0801246330118249fc32c62407a0d4a2aec8969466fd59d29f5 |
| research_runs/Q7-E001/results/protocol.json | 218ec24264aa0f2a47df270d2ae85cf61e8e7c30fea319317cea9f173ac5b03f |
| research_runs/Q7-E001/results/status.json | 21fa9bbd21ed7e23a8cb915b392c558dc3782af22d533a653a15968b5955c763 |
| research_runs/Q8-A001/analysis/Q8_SELECTION_AUDIT_REPORT.md | 6f502c9eb94591115fdd4063440970049535a63f119aa86d0c26e2739dcb6230 |
| research_runs/Q8-A002/analysis/Q8_A002_INNER_FOLD_INFLUENCE_REPORT.md | a9b4f60156fbd74e5bf039df8dd4cb1f64c26040c9ead506b5e178b1256ead5d |
| research_runs/Q8-A003/analysis/Q8_A003_RULE_SENSITIVITY_REPORT.md | 9310784216368bea3909e7401b60ac27697d6883070cfd6abc1ebaa7ee0475b6 |
| research_runs/Q8-E001/analysis/Q5_vs_Q8_paired_statistics.json | c6ae12eaf9a606e252afa3274f6b2067ce59d16e914635b453b785e5dddb5b2c |
| research_runs/Q8-E001/analysis/Q8_E001_FINAL_REPORT.md | 8c9eb06e4ef043544f7291ee3ca9070bd04c1b72acd48c3c27e31b1ebd656293 |
| research_runs/Q8-E001/analysis/validation_report.json | 167edce7058fcf958176ac6765c92f5827e2330284fcf9e3dff9709a3a21a5aa |
| research_runs/Q8-E001/code/validate_and_analyze_q8_e001.py | 687a241ba4888e71bad0746787a456690f96f7f9d67b9822e0b06d0f78d5eafd |
| research_runs/Q8-E001/results/config.json | daac05d5dffc36cd1d44dd30927d480c0a1087125828ce95ebb2b383d7d18342 |
| research_runs/Q8-E001/results/predeclared_selection.csv | bd9ea80e9f8379ce888fa45e9da92481a1d24fa0a89dbf2f51641d67488dee8d |
| research_runs/Q8-E001/results/predictions.csv | 1c468c09f80ea96151b666f339ed582ef1f58dbad775b9e2c0e9addd262b8f4d |
| research_runs/Q8-E001/results/selection.csv | a9bd17507e66e876ad54b97130cfb4749ba16eda91b17adfa9940ad9179966fc |
| research_runs/Q8-E001/results/selection_provenance.json | 95c4cd4c3aa95e99feb4dcd5ce77cad1289b8732e27ee5b7130905eaa655d912 |
| research_runs/Q8-E001/results/source_files.json | 0ccef780ed5bfbc2d430b8caf0c108641fb230a2dc27e4189e7e771c999f64a6 |
| research_runs/Q8-E001/results/status.json | 96a6b74ef7a451c077b30d681ce1df10228fed65059260f8068f103b261dce71 |
| research_runs/Q9-E001/PROTOCOL.md | af31aa3677fdb572b23e5820838a6c6b79cb7557a586171f878aa2d7905e12d3 |
| research_runs/Q9-E001/Q9_BATCH_MATRIX.json | cdfa48b9c837704c1f1e6003cebb2bba77d552a9fbc21eb4d89413f9f33febe8 |
| results/Q10-A001/config.json | 62348494583a91bb967227c471539df1080d1f49cf937acf5a7b697d9b063b33 |
| results/Q10-A001/predictions.csv | 838260b8662a714f24a99f7e44ce7cefa797b031fe38ee2dc299857230227797 |
| results/Q10-A001/status.json | 5092c161cbac2629459416fd2766a3efd7a4b6b25d61402f2b4d3c1914eb04ec |
| results/Q10-A001/validation_report.json | e01868cc06bf9e0bb7f03bf3cf62b2625180d41eb2f1c33145f06012020badd2 |
| results/Q10-E001/analysis/paired_contrasts.json | cf35fda8b4d73bb5b9faba8b74b7cbff1d0db51848a1152915ef83440f2b8f78 |
| results/Q10-E001/validation_report.json | b7168c12160c684b7ea5b328e80c160075f0826be9a1387b259329395f04d546 |
| results/Q10-V001/audit_report.json | 9de753324c7caa63a26a9ad154825a781185add77da80fe6ba03f112414dd692 |
| results/Q11-E001/analysis/paired_contrasts.json | 31d5dc60d82007c04e610bbf4f1a5e05d6ea01d67e4a7a71879d3c5c9d6d1695 |
| results/Q11-E001/validation_report.json | 2891172c4f55c8637381266edc9878d9c1dd6da0901fc5ae6ec20268a937a9ac |
| results/Q5-E001/config.json | 8caa3589d3ca2d8e21f2ed9d9f8de33d30e942a2159f2df236ad3923b509862c |
| results/Q5-E001/predictions.csv | 438364a8dee3b7d605bede33ab58278b1dfa9b82aaf4969d7815789d12876a33 |
| results/Q5-E001/selection.csv | 1b71fc50c58ea70284ba4f4cd1967b7c9b21d5b5d12d8469ddb07129a441491a |
| results/Q5-E001/source_files.json | 0ccef780ed5bfbc2d430b8caf0c108641fb230a2dc27e4189e7e771c999f64a6 |
| results/Q5-E001/status.json | 145fc9d6b12d7608a803f2731bdf8bba746ec3ad729bdb391c7b840074e8f747 |
| results/Q5-E001/validation_report.json | 237b846d2d9c851aeb7d0db5aded0dbf87676ff2f4ea18bfa5c5df650a7e519f |
| results/Q9-A001/config.json | 862bac10d959b386825796a15408c1c767125faf96faef6b028367bcfb1dbbaa |
| results/Q9-A001/predictions.csv | c045a17aab8bbd284206b0e93b29bd32fea6892c5fdfc1d1eb6d63a1993af747 |
| results/Q9-A001/status.json | 8835432a531a4d2ccd9e0035ac867dcde217788f480f171bc4dd4aa388825881 |
| results/Q9-BATCH/validation_report.json | 85fd34163ac72a9ff91d1b4ae965e5da2beb0a7a8260bb138adfe3ad26562d21 |
