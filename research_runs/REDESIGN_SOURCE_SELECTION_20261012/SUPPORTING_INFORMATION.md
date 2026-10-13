# Supporting Information: source-only selection reliability research work package

Prepared 13 October 2026. This document separates **preserved historical findings**, a **new completed retrospective traditional-source diagnostic**, and a **planned neural validation that has not been executed**. It is not a completed new-target Results section or a submission-ready supplement. Primary historical results and their original testing rules are retained; descriptive replay quantities do not replace them.

## S1. Historical participant-level development evidence

The historical development endpoint is four-class balanced accuracy (BA), with each person and the recorded final seeds weighted equally. Binary external scores below represent a different endpoint and acquisition protocol; they are not pooled with these values. Mean-loss and mean-rank refer to their historical duration-selection conditions. Fixed20 and the matched-runtime replay form a separate follow-up; effective runtime identity of the earlier mean-rank run is not fully authenticated. Thus cross-run differences are exploratory evidence motivating the new locked study, not a randomized or independently confirmed selection-rule effect.

Table S1. Historical development scores and paired differences. BA columns are percentages; differences are percentage points (pp). CSV values retain their stored precision.

| Person | Mean-loss BA | Mean-rank BA | Fixed20 BA | Matched-loss BA | Rank−loss pp | Fixed−matched-loss pp | Fixed−historical-rank pp |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | 57.002 | 57.002 | 55.150 | 57.523 | 0.000 | -2.373 | -1.852 |
| S2 | 24.479 | 27.836 | 30.671 | 24.421 | 3.356 | 6.250 | 2.836 |
| S3 | 26.100 | 60.880 | 68.461 | 26.100 | 34.780 | 42.361 | 7.581 |
| S4 | 36.921 | 36.921 | 35.012 | 36.458 | 0.000 | -1.447 | -1.910 |
| S5 | 24.132 | 25.058 | 24.363 | 24.537 | 0.926 | -0.174 | -0.694 |
| S6 | 28.356 | 28.530 | 28.356 | 28.530 | 0.174 | -0.174 | -0.174 |
| S7 | 28.472 | 30.324 | 29.282 | 29.630 | 1.852 | -0.347 | -1.042 |
| S8 | 29.688 | 65.451 | 64.988 | 29.630 | 35.764 | 35.359 | -0.463 |
| S9 | 48.322 | 52.025 | 59.606 | 48.495 | 3.704 | 11.111 | 7.581 |

Table S2. Historical participant-paired summaries. Each has nine people. Intervals replay the corresponding saved percentile-bootstrap computation. Exhaustive sign-flip p values were computed retrospectively from the archived participant-difference vectors; they are sensitivity descriptions, not replacements for historical testing conventions or the future paired-t primary test. Improved/worsened/tied counts refer to the first method minus the second.

| Contrast | Mean pp | Median pp | Better/worse/tie | Retrospective exhaustive sign-flip p | Saved percentile 95% CI pp |
| --- | --- | --- | --- | --- | --- |
| Mean-rank−mean-loss | 8.951 | 1.852 | 7/0/2 | 0.015625 | [1.048, 19.959] |
| Fixed20−matched-loss | 10.063 | -0.174 | 4/5/0 | 0.125000 | [0.675, 21.528] |
| Fixed20−historical-rank | 1.318 | -0.463 | 3/6/0 | 0.390625 | Not added |

For the developmental rank contrast, the frozen nine-person binomial sensitivity includes two ties and remains p=0.179688. The conventional sign test excluding ties uses seven nonzero differences and gives p=0.015625, as does the retrospective exhaustive sign-flip calculation. Both conventions are retained; the smaller value does not replace the frozen report or confer independent confirmation.

The developmental mean-rank contrast increases mean BA from 33.72% to 42.67%, but S3/S8 contribute 87.57% of the signed aggregate gain and the median difference is only 1.852 pp. Fixed20−matched-loss has a positive 10.063-pp mean while five of nine people worsen and its median is −0.174 pp. Its percentile bootstrap interval and sign-flip p=0.125 arise from different procedures; selecting the more favorable output would be misleading. None establishes a typical-person benefit, an optimum fixed duration, or independent confirmation. No corrected robustness gain is established in the retained robustness experiments.

Complete replay tables: `results/historical_internal_paired.csv`, `results/historical_participant_metrics.csv` (681 participant/method rows), `results/historical_participant_seed_cells.csv`, and `results/historical_source_schedule_replay.csv`. Historical source selection replay matches all selected loss/rank epochs across nine outer folds and 1,440 stored curve rows. Exact source manifests and hashes remain in the historical experiment paths listed in `evidence/historical_reaggregation.json`.

## S2. Preserved external complete-pipeline findings

Table S3. Historical binary external results. BA is equally participant weighted; mean differences are shared minus broad. The PhysioNet evaluation and the later Cho2017/Lee2019 evaluation have separate frozen contracts and testing rules. The p values below preserve those primary rules, not newly substituted sign tests.

| Cohort | People | Trials | Broad BA % | Shared BA % | Mean difference pp | 95% CI pp | Frozen primary p |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PhysioNet | 109 | 4918 | 61.815 | 62.388 | 0.573 | [-0.097, 1.242] | 0.064464 |
| Cho2017 | 52 | 10520 | 59.824 | 58.310 | -1.513 | [-2.249, -0.804] | 0.000050 |
| Lee2019_MI | 54 | 10800 | 65.512 | 65.716 | 0.204 | [-0.515, 0.969] | 0.603670 |

Cho2017/Lee2019 Holm-adjusted p values remain 0.000099995 and 0.603670, respectively. The retained PhysioNet exact-zero rule gives 63 positive, 43 negative and three exact ties, p=0.064464. One stored −1.11×10⁻¹⁶ difference accounts for the difference from a new count-based tolerance description (63/42/4, sign p=0.050442). Both records are retained and distinguished; the exploratory tolerance replay does not replace the frozen inferential result.

Cho2017 is an adverse shared-minus-broad result. PhysioNet superiority is not established; Lee2019 is uncertain and does not establish equivalence. Selected source durations were broad/shared 18/17 epochs for the earlier evaluation and 14/19 for the later evaluation. Views, filtering, BatchNorm exposure and compute also differ. These are complete-pipeline comparisons, not a single-factor causal effect of spectral sharing. The primary estimates retain zero target fitting.

Historical CSP BA remains 51.990% on Cho2017 and 52.769% on Lee2019. Trial-pooled left-prediction shares are 92.072% and 83.213%; the corresponding pooled median left probabilities are 0.669354 and 0.632939. Cho's equal-person left share is 92.112%, so it must not be described as identical to the pooled percentage. The binary-label complement is an arithmetic post-outcome diagnostic, not a new inference or accepted label correction; equal-person complement BA is 48.010%/47.231%. No new target centering, threshold selection or target inference was performed.

## S3. Completed new retrospective source CSP diagnostic

Run `cpu-csp-20261013T004218Z-2828deb4` was executed after the public preanalysis commit `f35fb97a28d7ddeea6b87f92b4d0975a4a0ebece`. Ten real traditional model fits were completed: nine leave-one-source-person-out folds plus one all-source fit evaluated by resubstitution. Each LOSO fold fits eight people/2,304 trials and scores one held-out source person/288 trials; the all-source fit trains and scores 2,592 trials. All 18 original BNCI MATLAB file hashes, native labels, 108-run identities and recorded fit-input array hashes were checked. Artifact flags are retained rather than excluded according to decoder performance.

The diagnostic uses the frozen 21-channel source preprocessing (excluding FCz), CAR and a fixed 21→20 orthonormal basis, 8–30-Hz input, per-real-trial context filtering, 160 Hz and the 0.5–2.5-s half-open decoder crop (320 samples). Preprocessing output is float32; the actual estimator input is float64 and has its own hash. CSP has four components, no regularization, concatenated covariance, log average power, `norm_trace=False`, `rank='full'`, mutual-information ordering; the scaler and SVD LDA are fitted only on each source training partition. This is a new 21-channel source diagnostic, not a trained instance of the planned 19-channel neural study.

Fresh mean participant BA is **61.651235% LOSO** and **63.040123% training resubstitution**. The latter is not held-out validation. Numerical agreement with the earlier unarchived report does not recover that report's run provenance. The original frozen historical model was not deserialized or replayed (`original_model_replay_receipt.json`: SKIP). Thus these results belong to the new run and cannot be called a replayed score of the old model.

Table S4. Held-out source LOSO: complete class-confusion counts. Each person has 144 left and 144 right true trials.

| Person | True left→left | True left→right | True right→left | True right→right |
| --- | --- | --- | --- | --- |
| S1 | 137 | 7 | 126 | 18 |
| S2 | 112 | 32 | 113 | 31 |
| S3 | 143 | 1 | 95 | 49 |
| S4 | 87 | 57 | 64 | 80 |
| S5 | 122 | 22 | 124 | 20 |
| S6 | 18 | 126 | 4 | 140 |
| S7 | 135 | 9 | 111 | 33 |
| S8 | 141 | 3 | 13 | 131 |
| S9 | 104 | 40 | 47 | 97 |

Table S5. Held-out source LOSO: class-specific performance and decision bias. Recalls and left-prediction share are percentages; median probability is descriptive.

| Person | BA % | Left recall % | Right recall % | Predicted left % | Median P(left) |
| --- | --- | --- | --- | --- | --- |
| S1 | 53.819 | 95.139 | 12.500 | 91.319 | 0.673404 |
| S2 | 49.653 | 77.778 | 21.528 | 78.125 | 0.573373 |
| S3 | 66.667 | 99.306 | 34.028 | 82.639 | 0.793927 |
| S4 | 57.986 | 60.417 | 55.556 | 52.431 | 0.503170 |
| S5 | 49.306 | 84.722 | 13.889 | 85.417 | 0.604558 |
| S6 | 54.861 | 12.500 | 97.222 | 7.639 | 0.224782 |
| S7 | 58.333 | 93.750 | 22.917 | 85.417 | 0.600893 |
| S8 | 94.444 | 97.917 | 90.972 | 53.472 | 0.584025 |
| S9 | 69.792 | 72.222 | 67.361 | 52.431 | 0.517431 |


Table S6. All-source training resubstitution: complete class-confusion counts. Each person has 144 left and 144 right true trials.

| Person | True left→left | True left→right | True right→left | True right→right |
| --- | --- | --- | --- | --- |
| S1 | 132 | 12 | 106 | 38 |
| S2 | 110 | 34 | 104 | 40 |
| S3 | 140 | 4 | 86 | 58 |
| S4 | 84 | 60 | 54 | 90 |
| S5 | 114 | 30 | 122 | 22 |
| S6 | 30 | 114 | 14 | 130 |
| S7 | 131 | 13 | 103 | 41 |
| S8 | 70 | 74 | 5 | 139 |
| S9 | 124 | 20 | 3 | 141 |

Table S7. All-source training resubstitution: class-specific performance and decision bias. Recalls and left-prediction share are percentages; median probability is descriptive.

| Person | BA % | Left recall % | Right recall % | Predicted left % | Median P(left) |
| --- | --- | --- | --- | --- | --- |
| S1 | 59.028 | 91.667 | 26.389 | 82.639 | 0.608594 |
| S2 | 52.083 | 76.389 | 27.778 | 74.306 | 0.558299 |
| S3 | 68.750 | 97.222 | 40.278 | 78.472 | 0.638290 |
| S4 | 60.417 | 58.333 | 62.500 | 47.917 | 0.497850 |
| S5 | 47.222 | 79.167 | 15.278 | 81.944 | 0.583361 |
| S6 | 55.556 | 20.833 | 90.278 | 15.278 | 0.317570 |
| S7 | 59.722 | 90.972 | 28.472 | 81.250 | 0.590697 |
| S8 | 72.569 | 48.611 | 96.528 | 26.042 | 0.320645 |
| S9 | 92.014 | 86.111 | 97.917 | 44.097 | 0.349659 |

The distributions include strong class asymmetry and substantial person-to-person variation. Mean source BA exceeds 50% descriptively on these nine already observed people and supports an operational source pipeline; it neither proves all label/channel/preprocessing errors absent nor identifies the reason for cross-dataset collapse. The completed independent validator reloaded native source labels and replayed numeric inputs using the same frozen preprocessing helper without fitting or model inference. A separate review reconstructed confusion counts, split identities and artifact hashes from stored files. Neither is an independently reimplemented alternate EEG transformation or external scientific replication.

Audit artifacts: `results/cpu-csp-20261013T004218Z-2828deb4/independent_validation.json`, `independent_validation_receipt.json`, `participant_confusion_and_metrics.csv`, `folds/*/{partition.json,fit_receipt.json,predictions.csv}`, and `evidence/cpu_csp_execution_independent_review.json`. The ten model artifacts are available under `models/cpu-csp-20261013T004218Z-2828deb4/`; no raw EEG is included in the repository.

## S4. Historical physiological description: no new physiology experiment

The retained physiological analysis is BNCI-only, sensor-level and post-decoder-outcome. Nine source people supply the same frozen baseline-relative power summaries and six descriptive Spearman associations. Re-aggregation of 228,096 saved power rows reproduces `10 log10(Ptask/Pbaseline)` with maximum absolute arithmetic error 5.33×10⁻¹⁵ dB; no raw spectral experiment was rerun. Mean signed laterality is −0.249685 dB for μ and −0.167875 dB for β.

Table S8. Saved laterality–decoder BA rank associations, n=9 for every row. No p values were computed or added.

| Historical model | Band | Spearman ρ | p value |
| --- | --- | --- | --- |
| BROAD_EEGNET | beta | 0.600000 | Not computed |
| BROAD_EEGNET | mu | -0.150000 | Not computed |
| CSP4_LDA | beta | 0.316667 | Not computed |
| CSP4_LDA | mu | 0.066667 | Not computed |
| MU_BETA_SHARED | beta | 0.483333 | Not computed |
| MU_BETA_SHARED | mu | -0.083333 | Not computed |

These associations were measured after outcomes were known and had no decoder feedback. A β association of ρ=0.6 is not confirmatory mechanism evidence. The baseline has one Welch segment and the task window three overlapping segments; these baseline-relative ratios are not claimed unbiased absolute ERD/ERS estimates. The physiology window differs from the decoder window. Negative signed laterality is not equivalent to absolute contralateral ERD, scalp topography is not cortical localization, and association does not establish a learned decoder mechanism. No external physiology replication, clinical utility, causal biological claim or online validation is supported.

## S5. Planned core validation — NOT EXECUTED

The locked scientific question is the reliability of source-only duration decisions, not a new state-of-the-art algorithm. Source models will be newly fitted on the actual 19-channel BNCI–Dreyer intersection with CAR over those 19 channels. Old 21-channel models must not be truncated, padded or relabelled as this new pipeline. The input contract retains six-second real-trial contexts, 0.5–2.5-s crop, 160 Hz and 320 samples.

Dreyer2023 is a conditional first-use candidate from one 87-person acquisition programme. A17/A41 are excluded for provider-reported unrecoverable electrode order, making the current primary ceiling 85 people/6,800 nominal acquisition trials. A04/A09/A29/B78/B79 remain primary quality flags pending locked signal-only QC. Two sham-feedback acquisition runs are planned; the feedback starts at cue+1.25 s within the scoring crop, so the study cannot claim pure MI signal or feedback-free cortical generalization. The A/B/C administrative strata are not three independent replications.

The bounded access preflight verifies three checksum-addressed signal files and seven metadata blobs, including representative cue conversion and a pre-cue physical scale roundtrip. It does not authenticate the full original GDF/Zenodo archive or the entire eligible cohort. The 174-file acquisition manifest contains 2,515,343,396 declared bytes, not 174 successfully QC-cleared files. The provider's published historical online-performance text was encountered during technical/QC review after conditional nomination; it was not used to rank candidates, choose decoder settings or exclude participants by performance. This is not a claim that all dataset-level performance literature remained unseen. Full signal-only QC, original/conversion provenance, participant-identity uncertainty and author prior-exposure confirmation are unresolved. No new-target neural predictions or scores have been produced.

Table S9. Planned neural grid and inference. All rows are design specifications, not observed outcomes.

| Item | Locked design / unresolved boundary |
| --- | --- |
| Architectures | Broad EEGNet and fixed shared μ/β pipeline |
| Rules | Fixed20, mean-loss, mean-rank; candidate epochs 1–40 |
| Source grouping | G0: S1–S2/S3–S4/S5–S6/S7–S9; equal fold weights |
| Source selection seed | 20261012; single trajectory seed per architecture/fold |
| Final seeds | 20261013/14/15; equal mean within participant |
| Nominal core fitting | 8 inner trajectories + 18 final condition/seed fits = 26; none executed |
| Optional grouping fits | 40 additional source-only inner trajectories; disabled |
| Single primary H1 | Broad mean-rank−mean-loss participant BA; paired t, two-sided α=.05 |
| Secondary confirmation | Fixed−loss, fixed−rank, shared-fixed−broad-fixed; Holm-three only after H1 rejection |
| Intervals | Primary 95% t; secondary unadjusted 95% plus conservative 98.333% simultaneous intervals |
| Bootstrap sensitivity | 20,000 participant resamples; seed20261016 |
| Target information | Event/class metadata eligibility/mapping and scoring only; no target fitting/selection |
| Noninferiority/equivalence | Not planned; no posthoc margin |
| Current confirmation gate | Closed: raw/provenance/identity/prior-use and executable neural audits pending |

The analysis CSV uses explicit aliases `BROAD_EEGNET`→`broad`, `MU_BETA_SHARED`→`shared`, `fixed20`→`fixed`; the checkpoint audit must bind `fixed` to exactly 20 epochs. Each eligible person requires at least 20 locked trials in each true class. Repeated seeds, sessions and EEG windows are not independent people. Primary analysis is conditional on the frozen source cohort/models. A significant software-fixture p value does not open actual confirmation gates.

Table S10. Two-sided paired-t minimum detectable effects at 80% power and α=.05. These are assumed Gaussian independent-participant scenarios, not observed target effects or retrospective power.

| Independent people | Assumed paired SD5 pp | SD10 pp | SD15 pp |
| --- | --- | --- | --- |
| 10 | 4.980 | 9.960 | 14.940 |
| 21 | 3.214 | 6.428 | 9.641 |
| 60 | 1.839 | 3.677 | 5.516 |
| 85: current upper bound | 1.537 | 3.074 | 4.611 |
| 87: sensitivity only | 1.519 | 3.038 | 4.557 |

At the current n≤85 ceiling, assumed paired SD10 pp gives a 3.074-pp primary MDE and a conservative three-test boundary MDE of 3.571 pp; further QC exclusions lower precision. With SD10 pp, 80%-power sample sizes for 2/3/5-pp effects are 199/90/34. The study cannot claim precision for a two-point benefit solely from a large trial count. The 72 power scenarios are unchanged; 79 numerical checks include an independent normal/chi-square mixture calculation at five points. Current invented-input software acceptance has 37 tests, with zero EEG reads, fits or target predictions.

## S6. Reproduction and evidence roles

Saved-result numerical replay: `scripts/historical_reaggregate.py`. Source diagnostic execution and independent validation: `scripts/cpu_csp_source_audit.py` and `scripts/validate_cpu_csp_source_audit.py`, governed by `CPU_CSP_PREANALYSIS.md` and its public protocol commit. Do not treat rerunning a model-fit script as a manuscript-formatting step. Statistical planning: `scripts/power_and_sensitivity.py`; grouping registry: `scripts/register_source_groupings.py` (1,260 unique partitions registered, not 1,260 trained). Future score analysis: `scripts/analyze_redesign_scores.py`; software fixtures: `tests/test_redesign_statistics.py`.

The frozen submitted v1.1 package and all historical result/model files retain their original provenance. New prospective specifications and retrospective diagnostics live solely in this redesign directory. Hashes and receipts allow inspection of what was executed; a hash match cannot prove every scientific implementation choice correct. The companion `SCIENTIFIC_VALIDATION_REPORT.md` lists unresolved gates. Final publication/readiness remains blocked until the missing independent neural work and full evidence chain are completed; this work package must not be submitted as if those results already existed.
