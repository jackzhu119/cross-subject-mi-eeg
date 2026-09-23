# Q7-E001

## Purpose

Mechanistic reconstruction of the S3 Q5→Q6 improvement.

Four-cell design:

| Cell | SourceNorm | Epochs |
|---|---|---:|
| A | OFF | 2 |
| B | ON | 2 |
| C | OFF | 16 |
| D | ON | 16 |

A is reused from Q5-E001.

D is reused from Q6-E001.

Only B and C were newly trained.

## Research question

Does S3 recover from class collapse because of:

1. source normalization itself,
2. longer training duration,
3. an interaction between normalization and duration?

## Important boundary

Q7 is a mechanistic single-subject ablation.

It must not be interpreted as population-level proof.

Read:

`analysis/Q7_MECHANISTIC_REPORT.md`

and:

`analysis/validation_report.json`

before designing Q8.
