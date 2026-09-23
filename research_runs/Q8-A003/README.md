# Q8-A003

Source-only epoch-selection rule sensitivity audit.

No model training.

Candidate aggregation rules:

- mean CE
- median CE
- trimmed mean CE
- worst-fold CE
- mean rank
- median rank

The purpose is to evaluate source-validation stability.

Target-subject balanced accuracy is not used to choose among these
rules.

A future experimental rule must be frozen before new target
evaluation.
