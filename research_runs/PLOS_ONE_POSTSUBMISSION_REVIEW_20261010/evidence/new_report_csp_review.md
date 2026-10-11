# M1 review of the newly supplied CSP diagnostic report

## Provenance and bottom line

The report is now available and has been read in full (SHA256 `ed7d49e6ae6c33590b89646621751dd951d725d951939ac9ee8cece957dc6b27`, 5596 bytes). Its stated date is 10 October 2026. It has no named author, run ID, new script hash, fold manifests or prediction records. The named diagnostic image is not supplied. The previous `m1_csp_audit` report correctly described this attachment as missing at its own earlier audit time; this addendum supersedes that availability status, not its scientific calculations.

The new attachment resolves the missing-report problem, but not the missing-artifact problem. Original saved-output results are independently verifiable; source resubstitution, new nine-fold CSP training and target centering remain report-reported. M1 is partially addressed, not fully cleared. No raw EEG, models or scientific experiment were executed for this review.

## Claim-by-claim matrix

### M1-01 — New raw BNCI download: 18/18 files match frozen Q8 provenance
Status: **report_reported_new_execution_not_independently_verified**

Historical committed Q15 BNCI receipt contains 18 file hashes and byte counts, all identical to Q8 source_files.json. No new 2026-10-10 download manifests, local raw files or replay logs accompany the report.

Required evidence or limit: New download/hash receipt, 18 filenames/hash/byte counts, raw loader and context-transform code hash, run ID/runtime/epoch/sample-ID provenance.

### M1-02 — Source resubstitution BA 63.04%, recalls 0.721/0.539; LDA coefficients/intercept/classes
Status: **report_reported_unverified**

Actual frozen 9365-byte model hash matches the source manifest and external inference freeze; no source prediction CSV/score or coefficients are archived in the original source validation. The model was not deserialized or executed in this editorial audit.

Required evidence or limit: Resubstitution prediction table for 2592 original sample IDs, frozen model hash, source raw/epoch hashes, exact scoring code and runtime receipt. Present this only as in-sample resubstitution, never held-out source efficacy.

### M1-03 — New same-Q15 nine-fold LOSO: mean BA 61.65%, SD14.1, range49.3–94.4; class recalls by four held-out persons
Status: **report_reported_unverified_new_source_fits**

Report describes nine fitted source models. No nine fold manifests/models/predictions/partitions/hash bindings, exact sample exclusions, or runtime/code records supplied. Historical Q14 CSP mean61.5354938272% is not this experiment. Historical P3 all-trial shrinkage-LDA mean61.6512345679% has different SD/range/pipeline and cannot substitute.

Required evidence or limit: All nine held-out trial-level predictions and training/sample partitions, fold-level models or authenticated model hashes, pipeline parameters/versions, raw-to-epoch provenance and independent aggregation/SD convention. Any additions are post-hoc source-only diagnostic fits, not part of primary frozen source fitting count15.

### M1-04 — External CSP balanced accuracy Cho51.99%, Lee52.77%
Status: **independently_verified**

Equal-person means from original frozen predictions: 51.9903846154% and 52.7685185185%; 52 and54 persons, 10520 and10800 trials.

Required evidence or limit: Already available: original predictions/statistics hashes and independent archived-output script.

### M1-05 — Left-prediction proportions92.07%/83.21%; median p_left0.669/0.633
Status: **independently_verified_with_aggregation_caveat**

Trial-pooled left shares92.0722433460%/83.2129629630%; pooled median0.669354232975/0.632938736955. Cho equal-person mean left share92.1121794872%, so label the reported92.07% as trial-pooled. Medians are not probability-calibration evidence.

Required evidence or limit: Already available: per-person confusion CSV and original stored probabilities.

### M1-06 — De-mean/shift-adjusted BA52.39%/54.18%
Status: **report_reported_unverified_target_input_adaptation**

No centering definition or transformed-feature predictions, fitted shifts, group boundaries, unit conventions, exact threshold, model state check, timing or hashes supplied. Text ambiguously says cohort-level or per-person. Even unlabeled target-input centering is target adaptation and cannot replace the primary frozen no-target-adaptation result.

Required evidence or limit: Exact code, whether feature/decision/EEG centering, cohort vs person/session grain, labels used or not, timing relative to outcomes, all estimated shift parameters and input/output hashes; explicitly post-hoc intervention, no primary result replacement.

### M1-07 — Prediction-label flip BA48.02%/47.22%
Status: **partially_verified_arithmetic_with_numerical_discrepancy**

For binary outputs BA_flip=1−BA_original algebraically. Cho pooled48.0228136882% supports48.02 but primary equal-person complement48.0096153846% rounds48.01. Lee complement47.2314814815% rounds47.23, not47.22; report input/aggregation missing. No new flip intervention or inference performed.

Required evidence or limit: Input/model hashes and scoring grain for report47.22 if retained. Do not change frozen primary results; optional SI algebraic audit must state its grain and descriptive nature.

### M1-08 — 10–17% of trials have p_left within0.5±0.05
Status: **independently_verified_descriptive_from_saved_probabilities**

For explicit closed interval[0.45,0.55], Cho1073/10520=10.1996197719%; Lee1803/10800=16.6944444444%. This summarizes frozen probabilities, not calibrated confidence or feature-shift cause.

Required evidence or limit: Read-only calculation recorded in review_new_csp_report.py.

### M1-09 — All labels/channel/preprocessing errors ruled out; actual cross-device CSP vulnerability proven
Status: **overstated_not_established**

Declared label/channel mappings and deterministic frozen transforms are operationally consistent and original independent raw-to-prediction replay passed. Cho physical MAT row order remains a prospectively reviewed diagram-based assumption; raw voltage calibration, original Cho hardware reference and cue hardware latency are unverified. Shared function does not remove native acquisition differences. Neural BA above50% cannot logically exclude every mapping or implementation error or establish a CSP-specific causal mechanism.

Required evidence or limit: Narrow conclusion to observed class-asymmetric near-chance transfer of this pipeline, plausible domain shift, and no mismatch detected in recorded checks; retain outstanding physical/calibration boundaries.

### M1-10 — Primary zero-calibration results remain frozen
Status: **independently_verified_for_archived_originals**

Prior independent audit checked52 source and221 external artifact hashes; no model reload/refit/inference/threshold or primary prediction edits this audit. New report-described source fitting/target centering lacks traceable artifacts and stays outside primary evidence.

Required evidence or limit: Submitted-package preservation and final candidate validation are parent task responsibilities.

## Independently verified confusion and aggregation

Rows are actual left/right; columns are predicted left/right. Canonical labels are left=1/right=2.

* **Cho2017**: 52 persons, 10520 trials. Pooled confusion `[[4947, 313], [4739, 521]]`; participant-mean BA 51.9903846154%; pooled BA 51.9771863118%; pooled predicted-left 92.0722433460%; participant-mean predicted-left 92.1121794872%; median stored p(left) 0.669354232975. Participant-mean left/right recalls 0.941025641026/0.098782051282.

* **Lee2019_MI**: 54 persons, 10800 trials. Pooled confusion `[[4643, 757], [4344, 1056]]`; participant-mean BA 52.7685185185%; pooled BA 52.7685185185%; pooled predicted-left 83.2129629630%; participant-mean predicted-left 83.2129629630%; median stored p(left) 0.632938736955. Participant-mean left/right recalls 0.859814814815/0.195555555556.

All 106 participant-level confusion summaries are saved in `new_report_csp_per_person_confusion.csv`. No participant outcomes or original predictions were changed.

## Source pipeline and comparison boundaries

The report correctly names the declared Q15 estimator chain: FixedCARBasis → MNE CSP4 (reg=None, log=True, cov_est=concat, norm_trace=False, rank=full, component_order=mutual_info) → source-fitted StandardScaler → LDA(svd). Static agreement with these parameters does not authenticate a new run. Uniform context-processing code preserves deterministic operations; different native sampling, reference, voltage calibration and cue latencies remain acquisition differences.

The earlier 62.76% cited by the report is traceable to an expert-clean, early binary QC endpoint (`P2-E001`, 2346 target trials), not to this all-trial Q15 21-channel pipeline. An earlier all-trial P3 shrinkage-LDA mean also rounds to61.65%, but its SD/range and estimator/preprocessing differ from the new claimed run. Neither historical record supplies the missing new nine-fold evidence. Q14 CSP mean61.5354938272% is a third, distinct earlier protocol.

## Interpretation corrections

* Strong left dominance is observed; the entire cohort does not output exactly one class.
* Median probabilities do not establish calibrated confidence or a feature-shift mechanism.
* Neurodecoder scores above chance are not proof that every label/channel/adapter assumption is correct.
* Poor post-centering BA, even if later authenticated, cannot prove no usable discriminative information exists or isolate spatial-filter failure.
* An exact binary-label complement checks arithmetic. It is not a scientific replay of alternative label biology. Selecting such a complement based on target scores would be target-driven tuning.
* Target-input centering is target adaptation even if labels are not used. The report does not specify cohort versus per-person centering or when its rule was chosen.
* New nine-fold source LOSO is nine additional source fits, not zero-new-fitting work. It must be presented as post-hoc diagnostic evidence, outside original primary fit counts.
* Raw/checkpoint replay passing means the declared benchmark is reproducible within documented limitations; it does not prove that every implementation error is absent.

## Recommended manuscript and supplement wording

### methods

After completion of the frozen transfer evaluation, we inspected the archived CSP predictions for class imbalance and probability asymmetry. These descriptive checks used the original stored predictions and their ground-truth labels for scoring only; no model was refitted, no new prediction inference was run, and no target-derived threshold, centering transformation or label mapping replaced the frozen outputs. Balanced accuracy remained the equally weighted mean across participants. Pooled confusion counts, proportions of predicted left-hand trials and median stored left-hand probabilities were reported separately as trial-level summaries.

### results

The frozen CSP comparator yielded participant-mean balanced accuracies of 51.99% on Cho2017 and 52.77% on Lee2019. In a post-hoc audit of the archived outputs, 92.07% of Cho2017 trials and 83.21% of Lee2019 trials were predicted as left hand; the corresponding pooled median stored left-hand probabilities were 0.669 and 0.633. Pooled confusion matrices showed pronounced class asymmetry rather than uniformly one-class output. These trial-level diagnostics use a different aggregation from the participant-level primary endpoint and did not alter any original prediction.

### discussion

The CSP outputs indicate limited transfer and strong class asymmetry under this particular frozen source-trained pipeline. The recorded checks found no disagreement in the declared label mapping, channel selections or deterministic preprocessing implementation, and the original independent audit reproduced the frozen raw-to-prediction results. These checks do not establish the cause of the transfer failure or rule out every acquisition or adapter limitation. Covariance or feature-distribution shifts are plausible explanations, but the present evidence does not isolate them from differences in device, reference, cue timing and preprocessing assumptions. We therefore treat CSP as a contextual comparator and make no general claim of intrinsic CSP inferiority.

### supplement_unverified_diagnostics

The separately supplied 10 October 2026 diagnostic report states a 63.04% source resubstitution score, a 61.65% mean score from nine new source-only leave-one-participant-out fits, and 52.39%/54.18% scores after target centering. Trial-level predictions, fold/transform manifests and execution/hash records for these new evaluations were not supplied with the report. These numbers are not part of the independently verified candidate results and are withheld from the scientific results until their evidence chain is available. Resubstitution would not constitute held-out validation; the reported leave-one-participant-out evaluation would add new source fits, and centering derived from target inputs would constitute target adaptation even without target labels.

### safe_short_conclusion

Archived-output diagnostics document strong class-asymmetric CSP transfer in this frozen benchmark; they do not prove a unique failure mechanism or the absence of all implementation errors.

## Required follow-up without rerunning experiments

Request the already-produced source prediction file, all nine fold prediction/manifests and de-meaning execution/provenance records from the report author. If they cannot be recovered, retain verified frozen-output diagnostics, disclose the limits, and withhold unsupported new numbers. Do not rerun these studies or revise frozen outcomes merely to resolve documentation.
