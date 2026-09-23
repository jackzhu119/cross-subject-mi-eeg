# Q6-E001 — Source-side Per-channel Z-score Normalization

## Experiment role

Q6-E001 is a post-Q5 exploratory ablation for cross-subject motor-imagery EEG decoding with EEGNet.

The intervention is source-side per-channel z-score normalization. Normalization statistics are fitted only on declared source-training trials and are then applied to the relevant data partitions.

## Dataset and evaluation design

- Dataset: BNCI2014_001 / BCI Competition IV 2a
- Subjects: 9
- Motor-imagery classes: 4
- Evaluation: leave-one-subject-out (LOSO)
- Seeds per held-out subject: 3
- Subject is the unit for subject-level inference; seed fits are not independent people.

## Completion status

- status: `complete`
- completed LOSO folds: 9
- completed inner fits: 36
- completed final fits: 27
- q6_complete: `True`

## Independent validation

- status: `passed`
- experiment_id: `Q6-E001`
- n_subjects: `9`
- n_trials: `5184`
- n_inner_fits: `36`
- n_final_fits: `27`
- n_predictions: `15552`
- n_source_only_scalers: `45`
- n_scaler_scalar_or_checkpoint_checks: `2043`
- n_metric_scalar_checks: `486`
- n_confusion_cell_checks: `1296`
- n_raw_mat_hashes: `18`
- n_snapshot_source_hashes: `56`

Interpretation boundary recorded by the validator:

> Q6 is a post-Q5 exploratory ablation. Nine people, not 27 seed fits, are the units for subject-level inference. Receipts and raw scaler recomputation do not prove unlogged GPU behavior or external generalization.

## Q5 vs Q6 — seed-level balanced accuracy

| Seed | Q5 BA | Q6 BA | Delta (pp) |
|---:|---:|---:|---:|
| 20260924 | 0.331597 | 0.372106 | +4.05 |
| 20260925 | 0.336227 | 0.370949 | +3.47 |
| 20260926 | 0.343750 | 0.394869 | +5.11 |

## Q5 vs Q6 — subject-level balanced accuracy

| Subject | Q5 BA | Q6 BA | Delta (pp) |
|---:|---:|---:|---:|
| S1 | 0.5700 | 0.5689 | -0.12 |
| S2 | 0.2448 | 0.2471 | +0.23 |
| S3 | 0.2610 | 0.6586 | +39.76 |
| S4 | 0.3692 | 0.3738 | +0.46 |
| S5 | 0.2413 | 0.2465 | +0.52 |
| S6 | 0.2836 | 0.2830 | -0.06 |
| S7 | 0.2847 | 0.2865 | +0.17 |
| S8 | 0.2969 | 0.2529 | -4.40 |
| S9 | 0.4832 | 0.4965 | +1.33 |

## Subject-level summary

- Q5 mean BA: **0.3372**
- Q6 mean BA: **0.3793**
- Mean Q6-Q5 change: **+4.21 pp**
- Median Q6-Q5 change: **+0.23 pp**
- Improved subjects: **6/9**
- Worsened subjects: **3/9**

## Paired subject-level statistics

- Wilcoxon signed-rank: statistic = 11.0000, p = **0.203125**
- Paired t-test: t = 0.9409, p = **0.374301**

These tests do not provide evidence, at the conventional 0.05 level, for a consistent subject-level improvement across the nine subjects.

## Important heterogeneity

The mean improvement is strongly influenced by S3 rather than being uniform across subjects.

- S3: 0.2610 -> 0.6586 (+39.76 pp)
- S8: 0.2969 -> 0.2529 (-4.40 pp)

S3 improves strongly across all three seeds, while S8 worsens across all three seeds. Confusion-matrix analysis indicates subject-specific changes in class-collapse behaviour.

## Interpretation

Q6 should not currently be interpreted as demonstrating a universal benefit of source normalization. It provides evidence of a strong subject-specific normalization effect: source normalization can correct prediction collapse for some held-out subjects while producing negative transfer or stronger collapse for others.

The next scientific question is therefore mechanistic: why do S3 and S8 respond so differently to the same source-only normalization procedure?

## Reproducibility artifacts

- `code/` — Q6-specific source, config, validator and Q5→Q6 diff
- `results/` — CSV/JSON scientific outputs and validation report
- `analysis/` — derived Q5/Q6 comparison tables
- `logs/` — saved Q6 execution logs
- `environment/` — Python packages, GPU and system snapshot
- `SHA256SUMS.txt` — hashes for archived files

## Data policy

Raw EEG files and trained model checkpoint binaries are intentionally not archived in this Git repository. Raw-data provenance and hashes are preserved by the experiment's source/provenance records.
