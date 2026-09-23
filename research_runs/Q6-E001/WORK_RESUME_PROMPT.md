# Prompt for Resuming Research in ChatGPT Work

Continue the cross-subject motor-imagery EEG research repository from the existing validated Q5/Q6 state.

Repository:

`jackzhu119/cross-subject-mi-eeg`

Before making changes, read:

1. `research_runs/Q6-E001/CONTINUATION_PLAN.md`
2. `research_runs/Q6-E001/Q7_MECHANISTIC_ABLATION_PLAN.md`
3. `research_runs/Q6-E001/RESEARCH_NOTES_Q6.md`
4. `research_runs/Q6-E001/posthoc_analysis/FULL_POSTHOC_ANALYSIS.md`
5. `research_runs/Q6-E001/posthoc_analysis/FINAL_CONSOLE_SUMMARY.txt`
6. `research_runs/Q6-E001/results/validation_report.json`
7. `research_runs/Q6-E001/results/normalization_receipts.json`
8. Q5 and Q6 `selection.csv`
9. Q5 and Q6 per-subject metrics and confusion matrices

Important existing facts:

- Q5 EEGNet subject mean BA ≈ 0.3372.
- Q6 SourceNorm subject mean BA ≈ 0.3793.
- Raw mean increase = +4.21 percentage points.
- Median increase = +0.23 pp.
- 6/9 subjects improved.
- Wilcoxon p = 0.203125.
- Paired t p = 0.374301.
- Sign-test p = 0.507812.
- Bootstrap mean-difference 95% CI crosses zero.
- Q6 does not establish a general population-level improvement.
- S3 drives the aggregate improvement:
  - Q5 ≈ 0.2610
  - Q6 ≈ 0.6586
  - +39.76 pp
- S3 improved in all three seeds.
- Q5 S3 had severe class collapse.
- Q6 largely removed that collapse.
- S8 worsened:
  - 0.2969 → 0.2529
  - -4.40 pp
  - all three seeds worsened.
- S8 class collapse became stronger under Q6.
- Simple target/source channel mean/std mismatch does not explain the result.
- S3 combined distribution mismatch ≈ 0.0512.
- S8 combined mismatch ≈ 0.2459.
- Q5/Q6 selected epochs are identical for nearly every subject except:
  - S3: 2 → 16
  - S5: 13 → 12
- The main mechanistic hypothesis is that SourceNorm changed optimization/source-validation training dynamics for S3.

Q5 and Q6 are frozen.

DO NOT:

- rerun Q5 unnecessarily;
- rerun Q6 unnecessarily;
- modify Q5/Q6 result files;
- use target-subject data for fitting/tuning;
- treat seeds as independent people;
- claim Q6 is statistically established as generally superior;
- exclude S8 to manufacture significance.

Next experiment:

**Q7-E001 — Normalization × Training-Duration Mechanistic Ablation**

Primary S3 factorial:

A. raw + 2 epochs — reuse Q5  
B. SourceNorm + 2 epochs — NEW  
C. raw + 16 epochs — NEW  
D. SourceNorm + 16 epochs — reuse Q6

Use the same three final seeds:

- 20260924
- 20260925
- 20260926

Keep all other Q5/Q6 settings identical.

Primary mechanistic outcomes:

- balanced accuracy
- macro-F1
- Cohen kappa
- class recall
- prediction distribution
- normalized prediction entropy
- dominant prediction share
- learning/training curves

The objective is to determine whether S3 recovery is caused by:

1. normalization directly;
2. longer training;
3. normalization × training-duration interaction.

Create a new independent Q7 directory and experiment ID.

Implement a Q7 validator before interpreting results.

After Q7 is complete and frozen, design Q8 around a predefined source-only spatial-spectral representation.

Do not proceed directly to a larger or more complex deep network without first resolving the Q6 mechanism.
