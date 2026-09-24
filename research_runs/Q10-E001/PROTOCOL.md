# Q10-E001 — source-fitted spatial projections, exploratory extension

This is the two-condition CSP8/PCA8 gap in the original Q9 plan, given a **new
experiment ID** because Q9 target results have already been inspected. Q9's
code, protocol and outcomes remain frozen. Q10-E001 is not an independent
confirmatory test or a claim of preregistration. Its matrix and implementation
must be committed before Q10 target prediction files are generated.

## Question and fixed comparison

Does a source-fitted, 8-component projection per mu/beta band help a 16-channel
EEGNet relative to the Q9 two-band shared-weight model? CSP uses source labels;
PCA uses source EEG only. The CSP/PCA pair has the same 16-channel network width,
but neither has identical architecture to Q9's 22-channel shared-logit fusion;
therefore a difference cannot be attributed solely to spatial information.

## Contract

- BNCI2014_001, all nine subjects, both sessions, all four classes and all
  target trials, including artifact-flagged trials. Same Q8/Q9 event identity,
  22 EEG channels, 250 Hz, `[2.5, 5.5)`-second window, 750 samples, no baseline.
- Fixed fourth-order zero-phase run-local 8–13 Hz and 13–30 Hz Butterworth
  filters. The existing Q9 spatial helper accepts the resulting EEG in volts.
  After source-only projection and source-only per-projected-channel scaling,
  model input is dimensionless 16×750; no target normalization is performed.
- Inner: for each held-out outer target, four fixed two-subject validation
  pairs from the sorted eight source subjects; fit CSP/PCA and projected-channel
  moments on the six training subjects only. Final: refit the projector on all
  eight source subjects. Save subject IDs, source sample-ID hash, filter/moment
  parameters and SHA256 in each fit receipt. No target labels, moments, flags,
  aggregate covariance, or performance may affect fitting or selection.
- The four-class MNE CSP uses the frozen Q9 helper's `reg="oas"`,
  `cov_est="concat"`, `norm_trace=False`, `rank="full"`, and eight components
  per band. PCA uses channel covariance on the same source partition with
  deterministic eigenvector signs. Both produce 16 projected channels.
- EEGNet F1=8, D=2, F2=16, temporal kernel=64, dropout=.25, Adam lr=.001,
  batch=64, 40-epoch inner cap; same frozen Q8/Q9 source-only mean-rank epoch
  algorithm, selection seed 20260923 and final seeds 20260924/25/26.
- Primary descriptive output: nine paired subject-level three-seed mean BA
  differences versus frozen Q9 `MU_BETA_SHARED`, with all subjects, classes,
  confusion matrices, seed/session/flag strata and subject-level uncertainty.
  Compare CSP and PCA as a declared pair; report negative results. Do not choose
  the better method for a confirmatory claim from BNCI target results.

The matrix contains 2 × (36 inner + 27 final) = **126 deep fits**. Each fit
is resumable only if its checkpoint, curves, manifest and projector receipt
match the saved hashes. Batch completion does not substitute for an independent
prediction-level scientific validator. Zero-phase filtering is offline and
non-causal; expert artifact flags are not a deployable rejection algorithm.
