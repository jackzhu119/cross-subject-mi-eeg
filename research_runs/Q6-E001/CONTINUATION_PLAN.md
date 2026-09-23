# Q6-E001 Final Scientific Conclusion and Continuation Plan

## 1. Project

**Main research topic**

> Cross-Subject Motor Imagery EEG Decoding Using Spatial-Spectral Features and Deep Learning

中文：

> 基于空频特征与深度学习的跨被试运动想象脑电解码

The long-term objective is not merely to obtain a high EEGNet score. The research objective is to understand and reduce **cross-subject distribution shift and subject-specific failure modes** in motor-imagery EEG decoding, then construct a reproducible method that generalizes to unseen subjects.

---

# 2. Current project status

Completed stages:

- Q4: traditional machine-learning baselines
  - CSP + LDA
  - CSP + SVM
- Q5: source-only EEGNet LOSO baseline
- Q5 independent validation
- Q6: source-only per-channel z-score normalization + EEGNet
- Q6 independent validation
- Q5 vs Q6 subject-level statistical comparison
- class-confusion / prediction-collapse analysis
- target/source distribution mismatch analysis
- epoch-selection analysis
- leave-one-subject-out sensitivity analysis
- reproducibility archive
- post-hoc mechanism analysis

Q6 is now considered **closed/frozen**.

Do not tune Q6 further using the observed test results.

Any new experiment must receive a new experiment ID.

---

# 3. Dataset and protocol

Dataset:

- BNCI2014_001 / BCI Competition IV 2a
- 9 subjects
- 4 motor-imagery classes:
  1. left hand
  2. right hand
  3. feet
  4. tongue

Q5/Q6 common preprocessing:

- native sampling rate: 250 Hz
- EEG channels: 22
- bandpass: 4–40 Hz
- Butterworth order: 4
- zero-phase filtering
- epoch window: 2.5 s to 5.5 s
- 750 time samples per trial
- artifact policy: include all
- no baseline correction
- 5184 total trials

Evaluation:

- leave-one-subject-out (LOSO)
- both sessions of the held-out subject are test data
- no target-subject fitting
- no target-derived normalization
- no target-based early stopping
- no target-based seed selection
- no target-based hyperparameter selection

The independent statistical unit is the **subject (n=9)**.

The 27 final seed fits are not 27 independent people.

---

# 4. Q5 baseline

Q5 is the frozen EEGNet baseline without source normalization.

Three seed-level mean balanced accuracies:

- seed 20260924: 0.331597
- seed 20260925: 0.336227
- seed 20260926: 0.343750

Equal-subject / three-seed mean:

**Q5 BA ≈ 0.3372**

Q5 demonstrated substantial cross-subject heterogeneity.

Examples:

- S1: relatively strong
- S9: moderately strong
- several subjects near four-class chance level (0.25)

This established the main problem:

> EEGNet trained on other subjects does not generalize uniformly to unseen subjects.

---

# 5. Q6 intervention

Q6 introduced one principal intervention:

**source-train-only per-channel z-score normalization**

For each channel:

x' = (x - source_mean) / source_std

Statistics were fitted over:

- source training trials
- time samples

Statistics were not fitted using target-subject data.

Configuration:

- statistics dtype: float64
- application dtype: float32
- variance ddof: 0
- zero-variance protection enabled

The independent validator recomputed the scalers from their declared source-training trial IDs.

Validation result:

- status: passed
- subjects: 9
- trials: 5184
- inner fits: 36
- final fits: 27
- predictions: 15552
- source-only scalers: 45
- scaler/checkpoint checks: 2043
- metric scalar checks: 486
- confusion-matrix cell checks: 1296
- raw MAT hashes: 18
- snapshot source hashes: 56

Therefore Q6 is considered technically validated.

---

# 6. Primary Q5 vs Q6 result

Subject-level mean balanced accuracy:

- Q5: **0.3372**
- Q6: **0.3793**

Raw mean difference:

**+4.21 percentage points**

However this number is not sufficient by itself.

Additional subject-level statistics:

- median improvement: **+0.23 pp**
- subjects improved: **6/9**
- subjects worsened: **3/9**

Paired inference:

- Wilcoxon signed-rank p = **0.203125**
- paired t-test p = **0.374301**
- two-sided sign-test p = **0.507812**
- paired Cohen dz = **0.3136**
- bootstrap 95% CI for mean difference:
  **[-1.12, +13.49] pp**

Therefore:

> Q6 does NOT currently establish a reliable population-level improvement from source normalization.

The observed mean improvement is highly heterogeneous across subjects.

---

# 7. Per-subject Q5 → Q6 changes

| Subject | Q5 BA | Q6 BA | Delta |
|---|---:|---:|---:|
| S1 | 0.5700 | 0.5689 | -0.12 pp |
| S2 | 0.2448 | 0.2471 | +0.23 pp |
| S3 | 0.2610 | 0.6586 | **+39.76 pp** |
| S4 | 0.3692 | 0.3738 | +0.46 pp |
| S5 | 0.2413 | 0.2465 | +0.52 pp |
| S6 | 0.2836 | 0.2830 | -0.06 pp |
| S7 | 0.2847 | 0.2865 | +0.17 pp |
| S8 | 0.2969 | 0.2529 | **-4.40 pp** |
| S9 | 0.4832 | 0.4965 | +1.33 pp |

The central fact is:

> The apparent +4.21 pp overall improvement is dominated by S3.

When S3 is omitted:

**mean Q6-Q5 difference ≈ -0.23 pp**

Therefore the aggregate improvement must not be presented as a general normalization benefit.

---

# 8. S3: major positive effect

S3:

- Q5 BA: 0.2610
- Q6 BA: 0.6586
- improvement: **+39.76 pp**

All three seeds improved:

- Q5 20260924: 0.2517
- Q6 20260924: 0.6441

- Q5 20260925: 0.2517
- Q6 20260925: 0.5694

- Q5 20260926: 0.2795
- Q6 20260926: 0.7622

Therefore the effect is not explained by a single lucky random seed.

## Prediction collapse

Q5 S3:

- dominant predicted-class share: **0.9416**
- normalized prediction entropy: **0.1304**

Q5 had an extreme class-collapse failure mode: it predicted one class for nearly all trials.

Q6 S3:

- dominant predicted-class share: **0.4387**
- normalized prediction entropy: **0.9037**

Source normalization therefore coincided with a major recovery from class collapse.

This is substantially more informative than saying only that BA increased.

---

# 9. S8: negative-transfer case

S8:

- Q5 BA: 0.2969
- Q6 BA: 0.2529
- difference: **-4.40 pp**

All three seeds worsened.

Prediction behavior:

Q5 S8:

- dominant predicted-class share: 0.5978
- normalized prediction entropy: 0.6480

Q6 S8:

- dominant predicted-class share: **0.8646**
- normalized prediction entropy: **0.2627**

Thus normalization coincided with a stronger prediction collapse on S8.

S8 is therefore an important negative-transfer example.

---

# 10. Distribution-mismatch analysis

A post-hoc analysis used the exact Q6 preprocessing pipeline and compared each unseen target subject with the corresponding source-derived channel statistics.

Important:

These target statistics were calculated **only after the experiment for diagnosis**.

They were NOT used by Q6 training or model selection.

## S3

- source channel std mean: 7.8649 µV
- target channel std mean: 8.0281 µV
- target/source std mean ratio: 1.0209
- combined mismatch: **0.0512**
- channels with std ratio < 0.8: 0
- channels with std ratio > 1.25: 0

S3 was actually very well matched to the source amplitude scale.

## S8

- source channel std mean: 7.6223 µV
- target channel std mean: 9.7209 µV
- target/source std mean ratio: 1.2749
- combined mismatch: **0.2459**
- channels with std ratio > 1.25: 15/22

S8 showed substantially more amplitude-scale mismatch.

However, across all nine subjects:

combined mismatch vs Q6-Q5 improvement:

- Pearson r = -0.5325, p = 0.1399
- Spearman rho = 0.1333, p = 0.7324

Sensitivity analyses also did not establish a stable monotonic relation.

Therefore:

> Simple target/source channel mean or variance mismatch does not explain the Q6 effects.

In particular, the large S3 gain cannot be explained by correcting an unusually large amplitude mismatch.

---

# 11. Critical discovery: epoch-selection dynamics

Q5 versus Q6 source-selected epochs:

| Subject | Q5 | Q6 | Difference |
|---|---:|---:|---:|
| S1 | 27 | 27 | 0 |
| S2 | 1 | 1 | 0 |
| S3 | **2** | **16** | **+14** |
| S4 | 10 | 10 | 0 |
| S5 | 13 | 12 | -1 |
| S6 | 7 | 7 | 0 |
| S7 | 6 | 6 | 0 |
| S8 | 1 | 1 | 0 |
| S9 | 7 | 7 | 0 |

This is one of the most important Q6 findings.

S3 is almost the only subject for which normalization strongly changed source-validation-based epoch selection.

The S3 performance transition:

- Q5: 2 epochs → severe class collapse → BA 0.261
- Q6: 16 epochs → balanced multi-class predictions → BA 0.659

This motivates the main mechanistic hypothesis:

> Source normalization may affect EEGNet primarily through optimization and source-validation training dynamics, rather than merely through static source-target amplitude alignment.

This is a hypothesis, not yet a proven causal explanation.

---

# 12. Leave-one-subject sensitivity

Mean Q6-Q5 difference after omitting each subject:

- omit S1: +4.75 pp
- omit S2: +4.71 pp
- omit S3: **-0.23 pp**
- omit S4: +4.68 pp
- omit S5: +4.67 pp
- omit S6: +4.75 pp
- omit S7: +4.72 pp
- omit S8: +5.29 pp
- omit S9: +4.57 pp

Omitting S8 produces Wilcoxon p=0.0391.

This must NOT be reported as a confirmatory significant result because S8 was identified after inspecting outcomes.

Correct interpretation:

> S8 is an influential negative-transfer subject in post-hoc sensitivity analysis.

Do not claim:

> “Q6 is significant after excluding S8.”

---

# 13. Final Q6 scientific conclusion

The strongest defensible conclusion is:

> Source-only per-channel normalization produced strongly heterogeneous effects across held-out subjects. Although mean balanced accuracy increased from approximately 33.72% to 37.93%, subject-level inference did not establish a consistent population-level improvement. The aggregate increase was dominated by S3, where normalization coincided with recovery from severe prediction collapse and a large change in source-selected training duration from 2 to 16 epochs. Conversely, S8 experienced negative transfer and stronger prediction collapse. Simple source-target channel amplitude mismatch did not explain these effects. The evidence therefore motivates a mechanistic investigation of normalization × training-dynamics interactions rather than treating source normalization as an established universal improvement.

---

# 14. Claims that are currently supported

It is reasonable to state:

1. Cross-subject EEGNet performance is highly heterogeneous.
2. Q5 can exhibit severe subject-specific prediction collapse.
3. Source-only normalization can dramatically change outcomes for particular held-out subjects.
4. S3 improved consistently across all three seeds.
5. S8 worsened consistently across all three seeds.
6. Q6 changed S3's source-only epoch selection from 2 to 16 epochs.
7. Simple channel-level amplitude mismatch does not adequately explain the subject-specific effects.
8. Q6 motivates studying optimization/training dynamics and negative transfer.

---

# 15. Claims that must NOT currently be made

Do NOT claim:

- source normalization is generally superior to Q5;
- Q6 produced a statistically established population-level improvement;
- 27 trained models constitute 27 independent samples;
- excluding S8 proves statistical significance;
- S3 proves the method generalizes;
- amplitude mismatch has been proven to cause S3/S8 behavior;
- epoch selection has already been proven to cause S3 improvement;
- Q6 establishes external-dataset generalization;
- the present results are confirmatory preregistered evidence.

Q6 is explicitly an exploratory post-Q5 ablation.

---

# 16. Q6 status

Q6-E001 is now:

- training complete;
- independently validated;
- statistically analyzed;
- mechanism-analyzed;
- archived in GitHub;
- frozen.

Do not rerun or modify Q6 unless performing a clearly documented reproducibility check.

Any new hypothesis test must use a new experiment ID.

---

# 17. Next experiment

The next experiment should be:

**Q7 — Normalization × Training-Duration Mechanistic Ablation**

Primary question:

> Is S3's improvement caused directly by source normalization, indirectly by normalization changing epoch selection/training duration, or by an interaction between the two?

Detailed design is stored in:

`Q7_MECHANISTIC_ABLATION_PLAN.md`

---

# 18. Longer-term research roadmap

Current roadmap:

Q4  
Traditional ML baseline  
✅ completed

Q5  
EEGNet source-only LOSO baseline  
✅ completed and validated

Q6  
Source-only channel normalization  
✅ completed, validated, analyzed and frozen

Q7  
Normalization × training-duration mechanistic ablation  
⬜ next

Q8  
Spatial-spectral representation experiment  
⬜ after Q7

Q9  
Integration of justified components  
⬜ later

Final evaluation  
- stronger statistical evaluation
- robustness checks
- independent/external dataset if protocol compatibility permits

Paper stage  
- methods
- reproducibility
- subject-level heterogeneity
- negative transfer
- mechanism evidence
- limitations

---

# 19. Principle for future experiments

Every new experiment should preserve:

- source-only fitting;
- strict LOSO;
- target subject completely held out;
- fixed subject-level statistical unit;
- multiple training seeds;
- configuration snapshot;
- exact source-code snapshot;
- raw-data hashes;
- predictions;
- confusion matrices;
- learning curves;
- selection records;
- independent validator;
- explicit interpretation boundaries.

Do not optimize experiments based on held-out target outcomes.

---

# 20. Repository continuation point

When research resumes, start from:

`research_runs/Q6-E001/CONTINUATION_PLAN.md`

Then read:

- `RESEARCH_NOTES_Q6.md`
- `posthoc_analysis/FULL_POSTHOC_ANALYSIS.md`
- `posthoc_analysis/FINAL_CONSOLE_SUMMARY.txt`
- `results/validation_report.json`
- `results/normalization_receipts.json`
- `analysis/q5_vs_q6_subject_comparison.csv`
- `posthoc_analysis/q5_q6_subject_level_metrics.csv`
- `posthoc_analysis/q5_q6_selected_epochs.csv`
- `Q7_MECHANISTIC_ABLATION_PLAN.md`

Do not restart from raw exploratory reasoning.

The immediate research continuation is Q7.
