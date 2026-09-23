# Q8-A001 — Source-only Epoch-Selection Stability Audit

## Type

Analysis-only audit.

No EEGNet model was trained.

## Motivation

Q7-E001 showed that S3's recovery from approximately chance-level
classification was primarily reproduced by increasing training duration
from 2 to 16 epochs, even without SourceNorm.

Q8-A001 therefore analyzes the already-saved Q5/Q6 source-validation
learning curves to determine how stable the source-only epoch-selection
procedure is.

## Main inputs

- Q5-E001 learning curves
- Q5-E001 selected epochs
- Q6-E001 learning curves
- Q6-E001 selected epochs
- Q5/Q6 subject metrics
- Q7-E001 four-cell mechanistic result

## Main questions

1. Why was S3 selected at epoch 2 in Q5 and epoch 16 in Q6?
2. Do the four inner source-validation folds disagree strongly?
3. Is the mean validation minimum narrow or nearly flat?
4. Are S2 and S8 epoch-1 selections potentially fragile?
5. Does normalization substantially change the validation trajectory?
6. Should source-only training-duration selection be studied before
   spatial-spectral model development?

## Important boundary

This is post-hoc analysis.

It must not be used to retroactively claim a new confirmatory
epoch-selection rule.

Any rule proposed from this analysis requires later independent
validation.
