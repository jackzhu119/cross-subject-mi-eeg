# M1 — independent read-only evidence audit of frozen Q15 CSP outputs

Repository: `jackzhu119/cross-subject-mi-eeg`.
Scientific baseline: `d9a11926076bd348696f6e690078955921dac3f8`.
Scope: saved predictions, saved scientific receipts, static frozen code, original model-file hashes. No raw EEG was accessed; no fitting, prediction inference, post-hoc shift, threshold intervention or new statistical test was run. The original repository was not edited.

## Verified original outcomes, with aggregation stated

| Cohort | Persons | CSP trials | Equal-person mean BA (%) | Pooled trial BA (%) | Pooled left-prediction proportion (%) | Equal-person mean left-prediction proportion (%) | Pooled median stored p(left) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Cho2017 | 52 | 10,520 | 51.9903846154 | 51.9771863118 | 92.0722433460 | 92.1121794872 | 0.669354232975 |
| Lee2019_MI | 54 | 10,800 | 52.7685185185 | 52.7685185185 | 83.2129629630 | 83.2129629630 | 0.632938736955 |

The paper's BA estimand is the equal-person mean. The approximately 92.07% Cho left-prediction number instead pools all trials, giving participants with 240 trials more weight than participants with 200 trials. The two grains must not be conflated. Lee has equal retained trial counts per person, so these aggregates coincide.

Every stored participant CSP confusion matrix and BA matches the frozen `statistics.json`. Every saved CSP label exactly matches argmax of its original two probability columns. Probabilities are finite and sum to one. No mapping was changed. Pooled confusion matrices, with rows actual left/right and columns predicted left/right:

* Cho: `[[4947, 313], [4739, 521]]`.
* Lee: `[[4643, 757], [4344, 1056]]`.

Left dominance is strong, but calling the complete cohort an exact one-class collapse would be too strong. Cohort medians of stored p(left) summarize outputs; they are not evidence that probabilities are calibrated.

## Binary-label flip arithmetic is not a new experiment

For an exhaustive two-class endpoint, complementing the predicted class gives `BA_flip = 1 - BA_original`. This audit reports that algebraic identity solely to check claims; no flipped prediction files or new model predictions were created, and no flip was selected.

* Cho complement: **48.0096153846%** under equal-person weighting; **48.0228136882%** under pooled trial weighting. A reported approximately 48.02% flip score is compatible with the latter grain, not with the paper's primary BA grain.
* Lee complement: **47.2314814815%** under either grain; these original frozen files round to **47.23%**, not 47.22%. A different claimed number requires its own recorded inputs and provenance.

This does not test a new adapter, establish that labels are correct biologically, or authorize changing the frozen outcome. An outcome-selected flip is target-label-driven tuning.

## Actual artifacts and audit depth

* All **52** files bound by the original source validation artifact map and all **221** files bound by the original external validation artifact map still match their recorded SHA256 hashes.
* The actual frozen CSP model is present at `results/Q15-E005/source/CSP4_LDA/all_source/model.joblib`, **9,365 bytes**, SHA256 `15ee57321177bca17472bd0fe211f1a42557291203b4e5700caf74a093bdd61f`. An independent public GitHub readback at the baseline commit returned HTTP 200 and identical bytes. This is an actual model artifact, not merely a manifest entry. It was neither deserialized nor executed in this audit.
* The original source validator is explicitly an **artifact/partition validation**. It checks one all-source CSP fit, source membership and identities, the fixed CAR basis, estimator parameters, learned state shapes, priors and model hash. It does **not** establish held-out source efficacy for this Q15 CSP pipeline.
* The original external validator records successful raw-auditor replay, raw-to-epoch replay, frozen checkpoint prediction replay, unchanged model state and independent statistics reconstruction. These positives establish consistency of the declared frozen benchmark and operational adapters. They do not prove a failure mechanism or resolve physical calibration, Cho original reference, electrode row-order assumptions or hardware cue latency.
* The inference completion receipt deliberately retains its earlier `pending_independent_raw_prediction_replay` status. The later independent `validation_report.json` supplies the actual scientific pass. The historical pending receipt must not be mistaken for a current failure or rewritten.

## Code and metadata invariants checked

1. Q15 source preprocessing removes FCz only from the declared 22-channel BNCI sequence. Source and targets use the same frozen 21-channel order; all archived raw metadata file records cover those canonical names.
2. The shared context transform selects channels, applies 21-channel common-average reference, filters each complete retained six-second trial context independently, resamples to 160 Hz and crops the cue-relative half-open `[0.5, 2.5)` window to 320 samples. Cho class-concatenated signals are not filtered across their artificial trial boundaries.
3. Broad input is 8–30 Hz. Fixed Helmert coordinates project the rank-20 CAR subspace from 21 to 20 coordinates without estimating a transform from either dataset. CSP has four components; scaling and LDA are source-fitted. StandardScaler is not refit on targets.
4. Canonical codes are left=1 and right=2. Lee native right=1/left=2 is explicitly remapped; the native numeric/string/one-hot labels are checked by the original raw adapter. Cho left/right arrays use their declared class identities. Archived file records retain these distinctions.
5. Lee channel names derive from actual `EEG_MI_train.chan`. Cho MAT containers lack channel names: the frozen map uses the official paper's numbered montage as a prospectively reviewed row-order assumption. Therefore the original raw audit does not independently prove actual physical Cho electrode order.
6. Source validation declares 14 neural fits and one shallow fit; external validation declares zero target fits and zero additional model fits. The paired broad/shared external contrasts remain the primary tests; CSP is a contextual comparator.

Evidence locations: `scripts/q15_source.py:114`, `:300`, `:390`; `src/mi_eeg/data/q15_context.py:124`, `:135`; `src/mi_eeg/models/q15_csp.py:1`; `scripts/q15_real_metadata.py:131`, `:156`, `:194`; `scripts/q15_validate_source.py:430`; `scripts/q15_external.py:279`, `:292`, `:328`; `scripts/q15_validate_external.py:372`, `:608`.

## Missing new-audit evidence

Neither named report was supplied in the available uploaded task file or found in the checked repository:

* `Q15_CSP崩溃_验证报告.md`.
* `PLOS_ONE_投稿前评审报告 (1)(1).md`.

Current public branch enumeration contains the historical scientific/publication branches and no identified new CSP-audit branch. Consequently these specific claims remain **unverified**, rather than false or independently established:

* Q15 source resubstitution BA **63.04%**. The original Q15 source CSP manifest and source validation do not store source prediction CSVs or that score.
* New Q15 nine-fold source LOSO BA **61.65%**. No corresponding nine held-out prediction files, training partitions, model manifests, raw-to-epoch audit and analysis receipt were found.
* Any post-hoc mean-centering, intercept shift, threshold shift, or external feature-shift result.
* Any new label-flip intervention result beyond the exact complement arithmetic of the original saved scores above.

The existing earlier **Q14** CSP binary LOSO record is available and independently rechecked from all nine stored prediction files and hashes: its equal-person mean BA is **61.5354938272%**. That earlier model uses 22-channel inputs and different preprocessing. It is neither 61.65% nor evidence for a new nine-fold Q15 assessment. Do not relabel it as the missing new audit.

## Safe revision boundary

The existing saved-output evidence supports stating strong class asymmetry and near-chance contextual CSP transfer under the particular frozen pipeline. It does not justify an intrinsic inferiority claim about CSP, a proved data-shift mechanism, a claim that all adapter errors have been excluded, or replacement of the adverse/null primary results. Source training BA, if later supplied, is resubstitution and must be separated from genuine participant-held-out performance. Target-input-based centering/shift estimation is target adaptation even if it uses no labels; choosing a shift, sign or map after inspecting target outcomes is target-driven tuning. Any such follow-up must remain post hoc and separate from the original frozen no-target-fitting benchmark.

Machine-readable evidence and per-person calculations are in `m1_csp_audit.json`; public model readback is in `m1_public_model_readback.json`; the standalone reproducible read-only audit is `audit_archived_csp_outputs.py`.
