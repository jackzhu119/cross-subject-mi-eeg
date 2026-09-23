# Q8-E001

## Experiment

**Mean-Rank Source-Only Epoch Selection**

Parent comparator:

`Q5-E001`

## Single experimental factor

Q5:

- raw EEG
- EEGNet
- source-only LOSO
- earliest epoch minimizing mean validation CE

Q8-E001:

- raw EEG
- same EEGNet
- same source-only LOSO
- earliest epoch minimizing mean within-fold validation-CE rank

Everything else is frozen to Q5.

## Inner-model reuse

The original 36 Q5 inner fits were NOT retrained.

Q8-E001 reuses the frozen Q5 40-epoch inner validation trajectories.

Mean-rank selected epochs were frozen before Q8 final-model evaluation.

## Final training

- 9 held-out subjects
- 3 final seeds per subject
- 27 new final fits

## No target fitting

Held-out target subjects do not contribute to:

- training
- epoch ranking
- model selection
- normalization
- hyperparameter tuning

## Important limitation

The mean-rank method was motivated by earlier exploratory analysis
on BNCI2014_001.

Therefore Q8-E001 is not independent external confirmation.

Read:

- `analysis/Q8_E001_FINAL_REPORT.md`
- `analysis/validation_report.json`
- `results/predeclared_selection.csv`

before designing the next experiment.
