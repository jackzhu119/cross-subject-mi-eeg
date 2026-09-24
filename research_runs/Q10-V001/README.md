# Q10-V001 — independent artifact-level audit of Q5–Q9

Status: **passed with caveats**, 2026-09-24. This is an exploratory audit of
the same nine-person BNCI2014_001 development cohort, not new target inference
or independent external confirmation. The executable source of truth is
`scripts/q10_scientific_audit.py`; all derived tables and its machine-readable
receipt are in `results/Q10-V001/`. `scripts/q10_scientific_figures.py` makes
the four inspectable figures in `results/Q10-V001/figures/` and records every
input hash. Q5–Q9 files were read, never rewritten.

## Question, population, and estimand

Does the previously reported EEGNet and spatial-spectral improvement survive
prediction-level reconstruction, paired subject analysis, class-collapse
inspection, selection-curve checks, and source-manifest inspection? The primary
unit is the **held-out subject**: balanced accuracy is averaged over three
fixed seeds within each person and then equally across nine people. The Q4
shallow pipelines have one fit per person. The four-class chance reference is
0.25, not an inferential threshold. Q5/Q6/Q8 and each completed Q9 deep
condition have 27 fold-seed predictions and 15,552 prediction rows (the same
5,184 distinct target trials repeated for three seeds). Q4 and Q9-A001 each
have 5,184 predictions per condition.

| Frozen condition | Mean subject BA | SD across subjects | Fold-seeds with ≥1 zero-recall class |
| --- | ---: | ---: | ---: |
| Q4 BroadCSP+LDA | 0.3904 | 0.1418 | 3/9 fits |
| Q5 broadband EEGNet | 0.3372 | 0.1158 | 9/27 |
| Q6 duration control | 0.3793 | 0.1568 | 9/27 |
| Q8 mean-rank broadband EEGNet | 0.4267 | 0.1604 | 3/27 |
| Q9 8–30 Hz EEGNet | 0.4455 | 0.1717 | 5/27 |
| Q9 shared mu/beta EEGNet | 0.4219 | 0.1410 | 3/27 |
| Q9 beta-only EEGNet | 0.3153 | 0.1005 | 15/27 |

The Q8–Q5 descriptive difference is +0.0895 BA, but S3 and S8 explain most
of it; without those two subjects it is about +0.0143. Q8 versus Q4 BroadCSP
is +0.0363 BA on average, with five of nine subjects improving and four
worsening. Four Q8 subjects (S2/S5/S6/S7) remain around 0.25–0.30 BA.
Thus the evidence supports meaningful **heterogeneity and class collapse**,
not uniform deep-learning superiority.

For the predeclared Q9 shared-mu/beta versus Q8 contrast, paired subject mean
ΔBA is **−0.0048**, subject-bootstrap 95% interval **[−0.0321, +0.0141]**,
exact nine-sign-flip sensitivity **p=0.9141**. Q9 8–30 Hz has the largest
observed mean (+0.0188 over Q8), but its bootstrap interval
**[−0.0136, +0.0504]** crosses zero and the gain disappears when S3 and S9
are omitted. These are post-Q9 exploratory intervals and p-values, not
confirmatory claims; overlapping LOSO training sets and multiple viewed
conditions limit inference. Beta-only worsens Q8 by −0.1114 BA on average
and shows 15/27 collapsed fold-seeds. Fixed-Q8-epoch and source-clean/source-
norm controls do not establish a robust positive spatial-spectral effect.

Q7's dramatic two-to-sixteen-epoch change is an S3-only mechanism probe; it
cannot be generalized to all people. Q9-A001 PSD44+LDA/SVM produce means of
0.3628/0.3578; they do not settle whether covariance geometry or a different
spatial representation transfers better. Q10-A001 and Q10-E001 address that
gap under new IDs rather than silently filling unrun Q9 conditions.

## What was independently checked

- Saved probabilities, `argmax`, confusion matrices, BA, seed and subject
  coverage, class recall, prediction dominance, session and artifact-flag
  strata, and exact target-trial identity were recomputed from CSVs.
- Q9 inner selection was recomputed for 81 fold-condition rows from its four
  source-only validation curves; source/validation/target role status was
  inspected. Q5/Q6/Q8/Q9 raw-source file manifests agree on 18 MAT file
  basenames, sizes and SHA256 values. The Q9 cloud logs preserve launch
  failures (missing module, incompatible TorchAudio CUDA, initially incorrect
  MAT count) and their later resolution.
- Q9 actually completed ten selected conditions: eight deep conditions plus
  two shallow methods, **432 deep fits** (216 inner + 216 final) and **18
  shallow outer fits**. The two Q9-E003 CSP8/PCA8 conditions in the original
  matrix were **not run**. The Q9 batch validator explicitly reports
  `passed_orchestration_only`; this independent audit is stronger at the
  prediction/artifact level but does **not** replay original checkpoints or
  prove that every training operation was leak-free.
- Q9's protocol, matrix and runner were not present in its recorded runtime
  Git commit. Runtime code hashes/timestamps exist, but it cannot be called
  Git-pre-registered. This is why a new committed Q10 protocol/ID is required.

## What is *not* supported

No present result proves that spectral decomposition, source artifact
exclusion, or normalization improves the average unseen person. No EEG
artifact-removal effectiveness was measured. The data do not justify choosing
the best seed, the best nine-person condition, or a post-hoc subject subset as
a confirmatory paper result. Session-specific target scores are descriptive
strata of LOSO inference, not an independent train-session-to-test-session
experiment. Q5–Q9 all use the same development cohort; their differences do
not establish cross-dataset generalization. Zero-phase filtering is offline
and acausal, so online real-time decoding is not demonstrated.

## Forward decision gate

Run and retain all predeclared Q10 conditions, including failures and negative
results. The paper's BNCI cohort is a **method-development cohort**. Before
looking at independent-cohort classification scores, lock a task-harmonized
binary left/right source protocol, exact channels/reference/window, eligibility
rule, methods, seeds, metrics and primary contrast. Source-only train/selection
on BNCI precedes a single zero-shot PhysioNet transfer. PhysioNet can confirm
or falsify the binary transfer hypothesis, **not** four-class tongue decoding;
its chance BA is 0.50. Any adaptation tuned on PhysioNet becomes a separately
labeled exploratory experiment, not the frozen external validation.

Recreate this audit from the repository root with:

```bash
python scripts/q10_scientific_audit.py
python scripts/q10_scientific_figures.py
```

The receipt `results/Q10-V001/audit_report.json` defines the precise check
scope and caveats. The figure receipt records source hashes so changes to
derived images can be traced back to data or code.
