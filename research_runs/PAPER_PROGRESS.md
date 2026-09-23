# Manuscript / Research Progress

## Working title

**Cross-Subject Motor Imagery EEG Decoding Using Spatial-Spectral Features and Deep Learning**

中文：

**基于空频特征与深度学习的跨被试运动想象脑电解码**

---

# Current stage

The project is in the mechanistic / methodology-development stage.

The experimental framework is mature, but the final proposed
spatial-spectral method has not yet been frozen.

---

# Completed evidence

## Q4

Traditional cross-subject baselines:

- CSP + LDA
- CSP + SVM

Completed.

## Q5

Source-only EEGNet LOSO baseline.

Completed and independently validated.

Mean balanced accuracy approximately:

0.3372

## Q6

Source-only per-channel normalization.

Completed and independently validated.

Mean balanced accuracy approximately:

0.3793

However:

- median improvement was only about +0.23 pp;
- subject-level tests were not significant;
- aggregate improvement was dominated by S3;
- S8 showed negative transfer.

Therefore SourceNorm is not established as a general improvement.

## Q7

S3 normalization × training-duration mechanistic ablation.

Four-cell result:

- Raw + 2 epochs: BA ≈ 0.2610
- SourceNorm + 2 epochs: BA ≈ 0.2569
- Raw + 16 epochs: BA ≈ 0.6771
- SourceNorm + 16 epochs: BA ≈ 0.6586

Conclusion:

S3 recovery was primarily reproduced by longer training duration,
not by normalization itself.

## Q8-A001

Source-only epoch-selection stability audit.

Important observation:

the four source-validation folds frequently have highly different
individual optimum epochs.

This motivates investigation of source-only model-selection
robustness.

## Q8-A002

Leave-one-inner-fold-out influence audit.

Purpose:

determine whether a specific validation-subject pair can dominate
selected training duration.

## Q8-A003

Source-only aggregation-rule stability analysis.

Purpose:

compare source-only candidate model-selection rules without using
held-out target performance to select a winner.

---

# Current scientific story

Cross-subject EEGNet does not fail only because of static signal
distribution differences.

The project has identified another potential failure mechanism:

**source-subject heterogeneity can make model-selection / training-
duration decisions unstable, and inappropriate duration can produce
severe target-subject class collapse.**

S3 currently provides the strongest causal evidence for the
training-duration mechanism.

Population-level generalization of this mechanism remains unproven.

---

# Manuscript readiness

Approximate status:

- problem formulation: advanced
- dataset/protocol: advanced
- reproducibility framework: advanced
- baseline experiments: complete
- failure-mode characterization: advanced
- mechanism experiments: advanced
- final proposed method: not complete
- spatial-spectral contribution: not complete
- final multi-subject comparison: not complete
- external validation: not complete
- discussion/limitations: partially developed
- final manuscript writing: not complete

The project should not yet be presented as a finished paper.

---

# Required work before final paper

The next methodological decision is how training duration/model
selection should be controlled without target-subject information.

After this is resolved and frozen, the project should proceed to
the predefined spatial-spectral method stage.

A final paper should eventually include:

1. frozen baseline protocol;
2. subject-level LOSO evaluation;
3. failure-mode analysis;
4. source-only model-selection method;
5. spatial-spectral method;
6. ablation studies;
7. statistical uncertainty;
8. negative-transfer cases;
9. external or independent validation where feasible;
10. complete reproducibility artifacts.

---

# Important scientific boundary

Existing Q5-Q8 analyses are exploratory.

Already observed target results must not be used to retrospectively
choose a model-selection rule and then describe that choice as
independent confirmation.

Any future rule should be frozen before new evaluation.
