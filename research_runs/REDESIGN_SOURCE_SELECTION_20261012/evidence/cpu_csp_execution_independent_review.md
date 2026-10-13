# Independent review of the completed source CSP diagnostic

Status: **PASS for stored-output, provenance and declared-scope review.**
Run: `cpu-csp-20261013T004218Z-2828deb4`.
Public preanalysis commit: `f35fb97a28d7ddeea6b87f92b4d0975a4a0ebece`.

The new nine-fit held-out-source mean balanced accuracy is **61.65123457%** (sample SD 14.12037037 percentage points; range 49.30555556–94.44444444%). The new all-source training resubstitution mean is **63.04012346%**. Ten source fits completed; target fits and new neural fits are zero.

These are new retrospective source diagnostics in a recorded new runtime. The original frozen pickle was skipped and never loaded. Rounding agreement with 63.04%/61.65% does not reconstruct or authenticate the old unarchived diagnostic run.

## Review scope

This reviewer independently recalculated participant balanced accuracy from saved integer decisions, checked all ten partition/sample/hash/model-file records and read the completed original-label/numerical-input validation receipt. No raw EEG reload, model deserialization, fitting or inference was done by this reviewer.

## Checks

- REVIEW-01: PASS — Actual independent validator summary and validator hashes bind its PASS receipt; receipt states zero fitting, inference and deserialization.

- REVIEW-02: PASS — Summary correctly limits new source diagnostics, rather than retroactively authenticating report or claiming independent-cohort confirmation.

- REVIEW-03: PASS — Exactly ten completed new source fits and no declared target fitting/predictions; actual fold artifacts checked below.

- REVIEW-04: PASS — Execution git HEAD equals publicly verified source preanalysis freeze.

- REVIEW-05: PASS — Executor records 18 raw hash/byte matches, 108 runs and 2592 binary trials; native raw labels and actual numeric replay separately checked by completed validator. This reviewer does not independently reload the EEG.

- REVIEW-06: PASS — Saved source metadata has exactly 2592 unique samples.

- FOLD-01-RECEIPT: PASS — loso_s01: completed source fit, explicit actual float64 estimator input and float32 preprocessing output.

- FOLD-01-SPLIT: PASS — Eight source people train; one source person held out, with no sample/participant overlap.

- FOLD-01-IDENTITY: PASS — Prediction sample order and complete evaluation identity agree with partition.

- FOLD-01-HASH: PASS — Nonempty new model file, stored predictions and partition SHA are verified without loading pickle/model.

- FOLD-02-RECEIPT: PASS — loso_s02: completed source fit, explicit actual float64 estimator input and float32 preprocessing output.

- FOLD-02-SPLIT: PASS — Eight source people train; one source person held out, with no sample/participant overlap.

- FOLD-02-IDENTITY: PASS — Prediction sample order and complete evaluation identity agree with partition.

- FOLD-02-HASH: PASS — Nonempty new model file, stored predictions and partition SHA are verified without loading pickle/model.

- FOLD-03-RECEIPT: PASS — loso_s03: completed source fit, explicit actual float64 estimator input and float32 preprocessing output.

- FOLD-03-SPLIT: PASS — Eight source people train; one source person held out, with no sample/participant overlap.

- FOLD-03-IDENTITY: PASS — Prediction sample order and complete evaluation identity agree with partition.

- FOLD-03-HASH: PASS — Nonempty new model file, stored predictions and partition SHA are verified without loading pickle/model.

- FOLD-04-RECEIPT: PASS — loso_s04: completed source fit, explicit actual float64 estimator input and float32 preprocessing output.

- FOLD-04-SPLIT: PASS — Eight source people train; one source person held out, with no sample/participant overlap.

- FOLD-04-IDENTITY: PASS — Prediction sample order and complete evaluation identity agree with partition.

- FOLD-04-HASH: PASS — Nonempty new model file, stored predictions and partition SHA are verified without loading pickle/model.

- FOLD-05-RECEIPT: PASS — loso_s05: completed source fit, explicit actual float64 estimator input and float32 preprocessing output.

- FOLD-05-SPLIT: PASS — Eight source people train; one source person held out, with no sample/participant overlap.

- FOLD-05-IDENTITY: PASS — Prediction sample order and complete evaluation identity agree with partition.

- FOLD-05-HASH: PASS — Nonempty new model file, stored predictions and partition SHA are verified without loading pickle/model.

- FOLD-06-RECEIPT: PASS — loso_s06: completed source fit, explicit actual float64 estimator input and float32 preprocessing output.

- FOLD-06-SPLIT: PASS — Eight source people train; one source person held out, with no sample/participant overlap.

- FOLD-06-IDENTITY: PASS — Prediction sample order and complete evaluation identity agree with partition.

- FOLD-06-HASH: PASS — Nonempty new model file, stored predictions and partition SHA are verified without loading pickle/model.

- FOLD-07-RECEIPT: PASS — loso_s07: completed source fit, explicit actual float64 estimator input and float32 preprocessing output.

- FOLD-07-SPLIT: PASS — Eight source people train; one source person held out, with no sample/participant overlap.

- FOLD-07-IDENTITY: PASS — Prediction sample order and complete evaluation identity agree with partition.

- FOLD-07-HASH: PASS — Nonempty new model file, stored predictions and partition SHA are verified without loading pickle/model.

- FOLD-08-RECEIPT: PASS — loso_s08: completed source fit, explicit actual float64 estimator input and float32 preprocessing output.

- FOLD-08-SPLIT: PASS — Eight source people train; one source person held out, with no sample/participant overlap.

- FOLD-08-IDENTITY: PASS — Prediction sample order and complete evaluation identity agree with partition.

- FOLD-08-HASH: PASS — Nonempty new model file, stored predictions and partition SHA are verified without loading pickle/model.

- FOLD-09-RECEIPT: PASS — loso_s09: completed source fit, explicit actual float64 estimator input and float32 preprocessing output.

- FOLD-09-SPLIT: PASS — Eight source people train; one source person held out, with no sample/participant overlap.

- FOLD-09-IDENTITY: PASS — Prediction sample order and complete evaluation identity agree with partition.

- FOLD-09-HASH: PASS — Nonempty new model file, stored predictions and partition SHA are verified without loading pickle/model.

- FOLD-10-RECEIPT: PASS — all_source_resubstitution: completed source fit, explicit actual float64 estimator input and float32 preprocessing output.

- FOLD-10-SPLIT: PASS — All-source fit evaluated on its own 2592 training samples; resubstitution explicitly is not held-out validation.

- FOLD-10-IDENTITY: PASS — Prediction sample order and complete evaluation identity agree with partition.

- FOLD-10-HASH: PASS — Nonempty new model file, stored predictions and partition SHA are verified without loading pickle/model.

- REVIEW-07: PASS — Across nine heldout files every source binary trial appears exactly once.

- REVIEW-08: PASS — Separate standard-library integer-confusion/person-level score computation agrees with saved independent validation.

- REVIEW-09: PASS — Historical frozen pickle not loaded or inferred; no original-model source score was produced.

- REVIEW-10: PASS — Completed validator declares original MATLAB label and ten input-array hash replay, without fitting or model inference. Its code and actual invocation scope were reviewed; replay uses the same frozen transform helper.

## Limits
- Both cohorts here are the already-observed BNCI source participants, not unknown targets.
- Nine new heldout-source fits provide retrospective source generalization context; all-source score is in-sample resubstitution.
- The newly computed means round to the old report claims, but no old run provenance is authenticated by numerical agreement.
- The original frozen pickle was not loaded; the fresh all-source model is a new model and score.
- No target feature-centering/adaptation, target inference or new neural model fit occurred.
- Raw/input validation reuses the frozen preprocessing implementation; SHA/score agreement does not prove absence of every possible implementation error.
