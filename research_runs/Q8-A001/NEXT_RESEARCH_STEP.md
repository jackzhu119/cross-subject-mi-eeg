# Next Research Step After Q8-A001

Read first:

- `analysis/Q8_SELECTION_AUDIT_REPORT.md`
- `analysis/FINAL_Q8_CONSOLE_SUMMARY.txt`
- `analysis/selection_stability_audit.csv`
- `analysis/critical_subjects_S2_S3_S8.csv`
- `analysis/inner_fold_optimum_epochs.csv`

Do not retrain Q5, Q6 or Q7.

The next action depends on the audit:

## If early epoch selections are clearly unstable

Define a new source-only robust model-selection hypothesis before
training another model.

Do not choose the rule based on target-subject balanced accuracy.

Possible families may later be considered, but must first be defined
using source-validation logic:

- fold-robust epoch aggregation;
- stability-aware source-validation selection;
- plateau-aware selection;
- fixed-duration sensitivity analysis.

These are candidate research directions, not decisions already made.

## If S2/S8 appear fragile

A later S2/S8 duration ablation may be useful for mechanism testing.

Because their target outcomes have already been observed, such an
experiment is exploratory and cannot independently validate a new rule.

## Spatial-spectral stage

Do not begin the main spatial-spectral experiment until the project has
decided how training duration/model selection will be controlled.

Otherwise a future feature-method improvement could be confounded with
different training duration.
