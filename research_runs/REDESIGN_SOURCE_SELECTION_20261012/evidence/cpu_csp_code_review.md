# CPU CSP diagnostic: independent pre-freeze code review

Status: **PASS for software and static code review; real EEG execution not validated here.**

The new source-only diagnostic contains nine held-out-person fits and one all-source training resubstitution fit. It remains separate from the original frozen Q15 experiment and cannot supply provenance for a missing historical diagnostic run.

## Checks

### CSP-01 — source-code comparison: PASS
scripts/q14_source.py::_csp_pipeline declares n_components=4, reg=None, log=True, cov_est=concat, norm_trace=False, rank=full, component_order=mutual_info; scripts/q15_source.py::_fit_csp adds constant FixedCARBasis21→20, scaler and SVD LDA. Fresh estimator matches these declared choices. Runtime/new-fit identity differs from original frozen artifact.

### CSP-02 — default execution safety: PASS
Default CLI prints DRY_RUN_NO_DATA_LOADED_NO_FITS; real execution requires --execute, source data path, baseline PASS and public preanalysis commit. Default dry run completed with zero source/target/neural fits.

### CSP-03 — public preanalysis identity: PASS
Verify requires real 40-hex ancestral git commit, correct repository/branch/commit publication identity, unchanged local/git objects, and actual HTTPS readback SHA for nine minimum executable, label-validation, source-provenance and original-contract dependencies. A receipt-only PASS dictionary, missing contracts, changed bytes/public identity fail software tests. Actual live committed freeze remains root execution responsibility.

### CSP-04 — partition identities/no source holdout leakage: PASS
All nine synthetic LOSO checks exclude held-out subject and sample identities from fitting. Both classes required in training/evaluation, sample IDs unique, independent validator compares original native MAT trial labels/artifact flags/order with CSVs and partitions. Training resubstitution explicitly overlaps evaluation and is not validation.

### CSP-05 — actual fit/prediction array hashes: PASS
Executor constructs contiguous float64 train/evaluation arrays once, hashes shape/dtype/values and passes those same objects to Pipeline.fit/predict/predict_proba. Runtime separately binds frozen preprocessing float32 whole epochs. Validator replays float32 frozen transform and the declared float64 conversion for all ten partitions without model loading, fitting or inference.

### CSP-06 — honest counters and artifact coverage: PASS
Started counter increments immediately before each Pipeline.fit; completed increments only after successful fit, prediction export, model export and completed receipt. Validator requires exactly ten ordinals/folds, status/counters, source partition/numerical hashes, 10 nonempty model artifacts with SHA and heldout prediction coverage of all 2592 unique trials. Declaring 10 in a standalone manifest cannot pass.

### CSP-07 — old pickle safety: PASS
Original pickle replay skips when any required numpy/scipy/sklearn/mne/joblib version is unavailable/different, frozen hash/path unavailable or symlinked. Only configured exact frozen-model SHA can become eligible. Validator rechecks original replay policy for REPLAYED; validator itself never deserializes models. Current freeze must not imply a skipped original artifact was replayed.

### CSP-08 — interpretation: PASS
New nine LOSO fits and one all-source resubstitution fit are new retrospective source-only diagnostics, separate from original primary 15 source fits and any unarchived source report run. No target activity is enabled. Agreement with old rounded 63.04/61.65 cannot restore the old report provenance or independently confirm unseen-cohort performance.

### CSP-09 — runtime/implementation dependencies: PASS
Runtime records, and validator checks, executor, independent label-validator, preprocessing module, basis module, original two contracts, config and source provenance hashes plus scientific library versions. This binds reproducibility but cannot prove absence of every implementation error.

## Completed software checks

33 software tests passed, zero failed. Python compilation and the default dry-run CLI passed. The tests use synthetic identities and mathematical arrays; no raw EEG, real estimator fits or model inference were performed.

## Changes before freeze

- Hash and use actual float64 estimator inputs; retain float32 preprocessing hash separately
- Pin both original preprocessing contract files as minimum public/local/git preanalysis dependencies
- Verify actual public immutable source bytes rather than trusting receipt PASS
- Verify runtime implementation, label-validation, contract and library-version records
- Recheck original-model compatibility policy if a replay is reported

## Remaining scientific verification

The actual public protocol publication/readback, ten real source fits and original-label/numerical-input/output verification must be checked after root execution. Source resubstitution is not held-out validation. New source LOSO remains retrospective on previously observed BNCI participants. Do not identify a new rounded numerical match as a reconstruction of the old report.

## Limits
- Software tests are synthetic and are not scientific evidence about real EEG
- Native-label validation and numeric replay reuse selected frozen helper functions; they are not an independently designed preprocessing implementation
- Static source-code agreement does not authenticate original historical runtime or unarchived source fits
- No original raw EEG was accessed by this review agent before root run completion
