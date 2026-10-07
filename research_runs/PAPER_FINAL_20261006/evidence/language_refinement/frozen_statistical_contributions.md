# Frozen-result statistical contribution review

Read-only interpretation of existing frozen outputs; no fitting, inference, p-values, confidence intervals, endpoints or subgroup analyses generated.

## Recommended priority contributions

### 1. priority_1_selection_diagnostics

Source-only model selection deserves an explicit failure-mode audit: in this development benchmark, very short selected schedules and one-class prediction concentration could account for failures that a representation or normalization comparison alone would leave ambiguous.

**Added value:** An empirical diagnostic contribution linking selection schedules to prediction collapse, rather than a new EEGNet variant. The four-cell S3 comparison supports a specific duration explanation without requiring a physiological story.

**Strength:** Moderate empirical/methodological contribution within this research program; algorithmic novelty or priority over the literature is not established.

**Frozen evidence:**

- `research_runs/PAPER_FINAL_20261006/paper_numbers.json`: {"key": "q7_cells", "values": {"S3_raw_2epochs_BA": 0.2609953703703704, "S3_normalized_2epochs_BA": 0.2569444444444444, "S3_raw_16epochs_BA": 0.6770833333333334, "S3_normalized_16epochs_BA": 0.6585648148148148, "raw_2epoch_dominant_prediction_share": 0.941550925925926}}
- `research_runs/PAPER_FINAL_20261006/evidence/paper_internal_numbers.json`: {"key": "q8_verified_review", "values": {"Q5_mean_BA": 0.33719135802469136, "Q8_mean_BA": 0.42669753086419754, "S3_S8_share_of_sum_improvement": 0.8757183908045977}}
- `research_runs/PAPER_FINAL_20261006/tables/internal_subjects.csv`: {"rows": "S3 and S8 selected schedules and individual outcomes"}
- `research_runs/PAPER_FINAL_20261006/manuscript_en.md`: {"section": "3.4–3.5, 4.1, 5.1", "detail": "Mean-rank aggregation changes within-fold loss-scale weighting; no external mean-loss versus mean-rank contrast was performed."}

**Limits:**

- S3 is one diagnostic person and three fixed seeds, not a population factorial experiment.
- The repeated nine-person development program is exploratory; later candidate design was outcome informed.
- Within-fold ranks remove scale information but also discard loss magnitude; no claim that rank aggregation is intrinsically more correct.
- The source grouping and equal-fold weighting are frozen choices, not an optimized or prospectively tested design.
- Do not claim external validation of the internal selection-rule improvement.

### 2. priority_2_mean_vs_typical_person

The paired participant results distinguish aggregate recovery from typical-participant improvement: a large positive cohort mean can coexist with a negative median and a majority of participants worsening.

**Added value:** The same frozen study contains two distinct patterns: a positive mean with seven nonzero improvements under rank selection, and a positive mean with four improvements under fixed duration. Keeping the median, signs and concentration alongside the mean prevents a population-average result from becoming an individual-benefit claim.

**Strength:** Strongest statistically distinctive empirical contribution; the statistical concepts themselves are standard.

**Frozen evidence:**

- `research_runs/PAPER_FINAL_20261006/evidence/paper_internal_numbers.json`: {"key": "q8_verified_review", "values": {"mean_difference_pp": 8.950617283950615, "median_difference_pp": 1.851851851851849, "positive": 7, "negative": 0, "ties": 2, "S3_S8_share_of_sum_improvement": 0.8757183908045977}}
- `research_runs/PAPER_FINAL_20261006/evidence/paper_internal_numbers.json`: {"key": "q13_verified_matched_runtime", "values": {"fixed20_minus_ce_pp": 10.063014403292179, "median_difference_pp": -0.17361111111110494, "positive_subjects": 4, "negative_subjects": 5, "exact_sign_flip_p": 0.125}}
- `research_runs/PAPER_FINAL_20261006/paper_numbers.json`: {"key": "q13_matched_contrast", "values": {"saved_orientation": "historical_CE_minus_fixed20", "mean": -0.1006301440329218, "bootstrap_CI": [-0.21528420781893, -0.0067515432098765]}}
- `research_runs/PAPER_FINAL_20261006/tables/internal_subjects.csv`: {"detail": "All nine Q5/Q8/fixed20/matched-CE paired scores retained."}

**Limits:**

- This is an existing descriptive comparison, not a newly tested mean-versus-median difference.
- Do not call it a new heterogeneity estimator, subgroup discovery or individualized treatment algorithm.
- All internal inference remains exploratory, with overlapping source training partitions and only nine people.
- Fixed20 reuses the historical duration schedule in a matched runtime; it does not freshly reselect mean-loss durations under that runtime.
- Bootstrap CIs and randomization tests use different finite-sample procedures; an interval excluding zero does not override sign-flip p=0.125.

### 3. priority_3_frozen_transfer_failure_boundary

The frozen external results establish a dataset-specific adverse contrast for the evaluated shared-input pipeline and limit claims of a consistent transfer advantage; they do not identify a harmful spectral mechanism.

**Added value:** A retained adverse result is substantive evidence against a consistent advantage of this particular fixed pipeline. It is more informative than a leaderboard selected after target scores. The uncertain Lee result is explicitly distinct from equivalence.

**Strength:** Strong empirical boundary result for a specific frozen pipeline; no novel DG algorithm or literature-wide first claim.

**Frozen evidence:**

- `research_runs/PAPER_FINAL_20261006/paper_numbers.json`: {"key": "q14_primary", "values": {"PhysioNet_n": 109, "mean_delta_pp": 0.5732962069873878, "CI_pp": [-0.09668274012807707, 1.2415551025224094], "positive": 63, "negative": 43, "ties": 3, "p": 0.0644635919894938}}
- `research_runs/PAPER_FINAL_20261006/evidence/q15_numbers.json`: {"key": "cohorts.Cho2017.primary", "values": {"n": 52, "mean_delta": -0.015133547008547011, "CI": [-0.022489583333333365, -0.0080448717948718], "holm_p": 9.99950002499875e-05, "positive": 12, "negative": 37, "ties": 3}}
- `research_runs/PAPER_FINAL_20261006/evidence/q15_numbers.json`: {"key": "cohorts.Lee2019_MI.primary", "values": {"n": 54, "mean_delta": 0.0020370370370370473, "CI": [-0.00515432098765431, 0.009691358024691359], "holm_p": 0.6036698165091745, "positive": 23, "negative": 30, "ties": 1}}
- `research_runs/PAPER_FINAL_20261006/evidence/q15_numbers.json`: {"key": "source_selected_epochs", "values": {"broad": 14, "shared": 19}}
- `research_runs/PAPER_FINAL_20261006/manuscript_en.md`: {"section": "3.1, 3.9, 5.2", "detail": "Q14 broad/shared durations 18/17; Q15 14/19; Q14 and Q15 preprocessing and checkpoints differ."}

**Limits:**

- No cohort-by-pipeline interaction test was declared; do not claim a statistically established interaction merely because signs or p-values differ.
- Q14 and Q15 are separate pipelines; do not claim one frozen decoder was replicated across all three cohorts.
- The estimand is shared complete pipeline minus broad complete pipeline, including duration, two-view computation, BatchNorm exposure and preprocessing.
- Holm adjustment applies to the two Q15 contrasts, not every Q1–Q16 comparison.
- The Cho raw p is a Monte Carlo floor 1/20,001, not an exact probability with arbitrary precision.
- Bootstrap intervals condition on the frozen source models, not another source cohort or adapter.
- No practical reliability, universal calibration-free transfer or state-of-the-art superiority is established.

### 4. priority_4_class_recall_tradeoffs

Class-specific recall reveals opposing response changes that a single balanced-accuracy mean obscures, even in an explicitly balanced scoring rule.

**Added value:** Clarifies how the adverse Cho mean and nearly unchanged Lee mean arise from descriptive class-recall tradeoffs. The fixed CSP context similarly shows why a near-chance BA can conceal a severe class preference.

**Strength:** Useful diagnostic extension of the main external result; a secondary contribution, not a novel classification metric.

**Frozen evidence:**

- `research_runs/PAPER_FINAL_20261006/tables/q15_model_summary.csv`: {"rows": "Cho2017 BROAD_EEGNET and MU_BETA_SHARED", "values": {"broad_left_recall": 0.46788461538461545, "shared_left_recall": 0.3752350427350427, "broad_right_recall": 0.7285897435897436, "shared_right_recall": 0.7909722222222222}}
- `research_runs/PAPER_FINAL_20261006/tables/q15_model_summary.csv`: {"rows": "Lee2019_MI BROAD_EEGNET and MU_BETA_SHARED", "values": {"broad_left_recall": 0.7556172839506172, "shared_left_recall": 0.726851851851852, "broad_right_recall": 0.5546296296296296, "shared_right_recall": 0.5874691358024691}}
- `research_runs/PAPER_FINAL_20261006/tables/q15_model_summary.csv`: {"rows": "CSP4_LDA in both cohorts", "values": {"Cho_left": 0.9410256410256411, "Cho_right": 0.09878205128205128, "Lee_left": 0.8598148148148148, "Lee_right": 0.19555555555555554}}
- `research_runs/PAPER_FINAL_20261006/evidence/q15_numbers.json`: {"key": "class_recall_interpretation", "value": "Equal-person, then equal-seed mean; sessions pooled within person"}

**Limits:**

- These are frozen descriptive outputs, not newly tested class-specific primary endpoints.
- Do not claim causality, threshold miscalibration, hemispheric bias, label-mapping error or a particular acquisition mechanism.
- Do not adjust thresholds, labels, adapters or models in response.
- BA already gives equal weight to classes; this analysis disaggregates that summary rather than correcting an inaccurate BA metric.

### 5. priority_5_separated_validation_and_physiology

The evidence chain separates frozen computational validity, acquisition assumptions and sensor physiology, allowing reproducible decoder comparisons without upgrading numerical agreement into a physiological mechanism.

**Added value:** S2 is a concrete counterexample to treating negative relative laterality as absolute ERD. The positive beta correlation has the opposite reading from a claim that stronger suppression improves decoding. Distinct raw replay, saved-output reaggregation and physical calibration scopes make the evidence inspectable.

**Strength:** Moderate reporting/validation contribution; the signed descriptor and Welch estimator are not claimed as new methods or biomarkers.

**Frozen evidence:**

- `research_runs/PAPER_FINAL_20261006/evidence/q15_numbers.json`: {"keys": ["committed_gate_chronology", "independent_raw_to_prediction_replay", "original_source_fits", "new_source_fits", "target_fits", "calibration_limitations"], "values": {"original_source_fits": 15, "migration_source_fits": 0, "target_fits": 0, "paper_audit_checkpoint_execution": false, "archived_validator_raw_to_prediction_replay": "reported by archived validator; not rerun by this paper audit"}}
- `research_runs/PAPER_FINAL_20261006/evidence/q16_analysis/summary.json`: {"keys": ["laterality_population_summary", "descriptive_associations", "limits"], "values": {"mean_mu_laterality_db": -0.249685033440594, "mean_beta_laterality_db": -0.16787453939998, "broad_mu_rho": -0.15, "broad_beta_rho": 0.6, "n": 9, "p_values": false}}
- `research_runs/PAPER_FINAL_20261006/evidence/q16_analysis/subject_hand_laterality.csv`: {"rows": "subject=2, band=mu", "values": {"contralateral_db": 1.4908942767698035, "ipsilateral_db": 1.6938059453326915, "signed_laterality_db": -0.202911668562888}}
- `research_runs/PAPER_FINAL_20261006/evidence/q16_analysis/independent_validation.json`: {"key": "raw_replay", "values": {"native_files": 18, "event_identities": 5184, "saved_eligibility_rows": 228096, "central_channel_band_pairs_raw_replayed": 31104, "maximum_relative_power_difference": 1.847193004695259e-15, "maximum_absolute_logratio_difference_db": 7.105427357601002e-15}}
- `research_runs/PAPER_FINAL_20261006/evidence/q16_analysis/preprocessing_freeze.json`: {"detail": "Q16 freeze commit 050e01b028aaab8e3d745934b13b2d17e9bb0a7a; post-decoder-outcome; no decoder feedback."}

**Limits:**

- Physiology is BNCI-only, sensor-level, descriptive and specified after decoder outcomes; n=9, six descriptive correlations, no p-values.
- Negative signed laterality is relative contralateral minus ipsilateral change, not necessarily absolute suppression.
- The one-Welch-segment baseline versus three overlapping task segments can bias the log-power difference; no unbiased ERD estimate or correction is established.
- Decoder window [0.5,3.5) differs from physiology [0.5,2.5) for the linked binary LOSO scores.
- Raw spectral algorithm replay covered C3/Cz/C4; all 22-channel rows had identity/eligibility checks and saved aggregation replay, not full raw spectral replay at all sensors.
- Numerical implementation agreement is not independent laboratory replication, cortical localization or evidence of a learned decoder mechanism.
- Acquisition voltage/reference/cue-latency assumptions remain unresolved even after successful computational validation.

## Supporting strengths, not additional standalone inventions

- **source_only_is_not_outcome_blind** — Zero target fitting is an information constraint for each fit, not proof that the repeatedly used development program was outcome blind. Clarifies eligibility/class metadata versus fitting/model-selection information and distinguishes repository freezes from independent preregistration. Supporting evaluation rigor, not a standalone innovation.
- **person_unit_not_pseudoreplication** — Three seeds and two sessions stabilize measurements but do not multiply the number of participants. Makes the primary inference unit and conditional nature of uncertainty clear; avoids 149,240 prediction rows being treated as independent samples. Necessary methodological strength.
- **multiplicity_retains_null_robustness** — Positive point estimates and an unadjusted adverse interval do not supersede the frozen within-family null robustness findings. Retains an adverse exploratory lead without claiming a corrected discovery or general harm from GroupDRO. Evidence integrity; not algorithmic innovation.
- **source_count_cannot_identify_diversity** — The increasing source-count trajectory cannot separate participant diversity from training-data quantity and optimizer-update exposure. Names the causal identification limit instead of presenting a descriptive trajectory as a source-diversity law. Useful interpretation guardrail.
- **gain_invariance_does_not_calibrate** — Within-recording task/baseline power ratios cancel a constant multiplicative gain, but this does not calibrate cross-provider voltage, reference, timing or spatial correspondence. Separates a narrow algebraic invariance from unverified physical measurement equivalence. Supporting measurement clarity.

## Claims to reject

- **A novel SOTA DG algorithm or first calibration-free MI EEG solution**: No new DG algorithm, matched contemporary DG benchmark, or exhaustive priority evidence.
- **Mean-rank selection generalizes better on new external people**: Neither Q14 nor Q15 externally compared rank versus mean-loss selection.
- **Spectral sharing causes poor Cho performance**: Complete pipeline contrast includes duration, view computation, BatchNorm and preprocessing differences.
- **Significant cohort-specific interaction or universal transfer failure**: No declared cohort-by-method interaction; separate Q14/Q15 tensors/checkpoints; finite evaluated cohorts only.
- **Lee models are equivalent or noninferior**: No prespecified equivalence/noninferiority margin or test; CI crossing zero is insufficient.
- **Beta laterality is a biomarker or explains EEGNet decisions**: Post-outcome n=9 descriptive associations, no p-values/external physiology/mechanistic intervention; positive rho does not mean stronger suppression is better.
- **Individualized calibration-free clinical utility**: Offline public nonclinical data; no online or prospective assistive control evidence.
- **New statistical discoveries by reanalyzing subgroups, CIs or p-values**: Current scope forbids new scientific endpoints, subgroup selection, inference reruns or altered frozen results.
- **All-channel independent raw physiology replication and verified physical calibration**: Central channels alone received independent raw spectral replay; full saved tables were reaggregated; hardware calibration unverified.

## Suggested English paragraphs

### introduction_contribution_paragraph

We treat source-only model selection as part of the decoder comparison. In the development benchmark, the duration diagnostics expose a failure that normalization alone does not resolve, while paired participant results distinguish a large mean gain from broad individual benefit. Separate external evaluations retain the frozen pipelines' adverse and uncertain outcomes rather than choosing a favorable cohort. The accompanying native-signal analysis adds sensor-level context without using physiological summaries to explain or modify the decoders.

### discussion_mean_and_median

The two duration comparisons answer different questions about who benefits. Rank selection improved seven participants, but S3 and S8 contributed 87.57% of the summed gain. In the matched-runtime fixed-duration comparison, the mean rose by 10.06 pp even though only four participants improved and the median difference was −0.174 pp. The mean measures the magnitude of the combined recoveries; it does not describe the direction experienced by most participants. These results favor reporting all paired effects and their median alongside the mean, rather than interpreting a cohort-average gain as a typical-person gain.

### discussion_external_estimand

The Cho2017 result is an adverse comparison between two complete source-selected pipelines. Its corrected contrast is not a test of the isolated physiological value of mu or beta activity. Left-hand recall fell from 46.79% to 37.52%, while right-hand recall increased from 72.86% to 79.10%. On Lee2019, opposite class-recall changes accompanied a near-zero mean contrast whose interval still includes effects in either direction. These frozen outputs reveal class-dependent tradeoffs, but they do not identify a threshold, montage, acquisition or physiological cause.

### discussion_uncertainty

The uncertainty statements are conditional on what was actually varied. The external bootstrap resamples participants after their fixed seeds are averaged; it does not resample the source cohort or acquisition adapter. The Lee sessions therefore supply repeated recordings for 54 people, not 108 independent people. Similarly, the unadjusted internal bootstrap intervals and the family-corrected randomization tests are different summaries of a small sample. An interval that excludes zero cannot be used to disregard a null corrected test, and a null Lee contrast cannot be used to claim equivalence.

### discussion_physiological_reading

The physiological descriptor is a relative contrast. S2 illustrates the distinction: its mu laterality was negative even though both contralateral and ipsilateral task/baseline changes were positive. The positive broad-EEGNet beta association likewise means that higher balanced accuracy accompanied a larger, less-negative descriptor, not stronger relative suppression. Together with the unequal baseline/task estimator precision and the different decoder and physiology windows, these observations rule out a simple attribution of decoder performance to the displayed scalp pattern. They remain descriptive observations from the same nine BNCI participants.

### abstract_significance_option

Significance. The study audits source-only model selection and the gap between aggregate and participant-level benefit. The frozen shared-input pipelines showed no consistent external advantage, including a corrected adverse Cho2017 contrast. Sensor-level physiology supplies descriptive context rather than evidence of a decoder mechanism.

### cover_letter_core_contribution

The manuscript contributes an empirical audit of source-only model selection rather than a new domain-generalization algorithm. Its duration diagnostics and paired participant effects expose the limits of aggregate gains, and its frozen external evaluations retain an adverse Cho2017 result and uncertain PhysioNet and Lee2019 contrasts. The reproducibility record separates saved-output verification, raw computational replay and unresolved acquisition assumptions.

## Recommendation

Foreground three empirical contributions (selection diagnostics, participant heterogeneity, retained frozen external adverse/uncertain evidence); use class-recall diagnosis and validation/physiology boundaries as supporting contributions. Do not multiply them into a long nominal innovation list. Consolidate repeated qualifications into the appropriate Methods/Limitations paragraph while keeping the adverse/null results and each claim boundary.
