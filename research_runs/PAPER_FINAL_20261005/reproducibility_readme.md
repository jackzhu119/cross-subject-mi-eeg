# Reproducibility guide

This manuscript package is derived from committed research artifacts. Rechecking its numbers does not require training a decoder, a GPU, RunPod access, R2 credentials, or raw EEG redistribution.

## Immutable inputs

| Role | Snapshot / artifact |
|---|---|
| Inspected final Q15 results | `7af1a137e2676a018e1e880ab076de6cae4ce30b`, branch `q15/run-20261005T050511Z-migration-from-r2-b82ad79b` |
| Verified scientific-results publication | `bc48b257eb44f412ad069f50d0f1a72a33c3c520`, bound by the migration job's `publication_evidence.json` |
| Frozen scientific code | `271af288a2f3863430ab80e3145c2dee9bd5571d` |
| Source artifact and continuation base | `782d2d0070a50c37d13c8e9f1cab3b3b81bac4fc` |
| Historical paper delivery | `ac75a339c8db2861ff8e7d072e50690c79c602c4`; underlying research inputs are separately hash-bound in its `evidence/source_snapshot.json` |
| Q15 pre-fit freeze commit | `fc0e7d54006076bec7701064e1045034c02d06a4`, before source fitting |
| Q15 inference/statistics freeze commit | `2ad479f5bccb4f92cd6c77bc78a8ba9b620604c1`, before target predictions |
| Q15 source validation | `results/Q15-E005/source_validation.json` |
| Q15 final validation | `results/Q15-EXTERNAL/validation_report.json` |
| Current job / backup record | `research_runs/Q15-MIGRATION-20261004/jobs/20261005T050511Z-migration-from-r2-b82ad79b/` |

The final validation report has `passed=true`, `scientific_validation_passed=true`, and `status=completed_with_calibration_limitations`. The current job verifies original_source_fits=15, new_source_fits=0, target_fits=0, predictions_computed=true, and github_results_backup_verified=true. It operates in manual-stop mode. No statement of physical shutdown follows from these scientific artifacts.

## Number audit without fitting

1. Obtain the repository and check out the inspected results snapshot in a separate working directory.
2. Inspect the committed prediction tables `results/Q15-EXTERNAL/Q15-E006/predictions.csv` and `results/Q15-EXTERNAL/Q15-E007/predictions.csv` together with the corresponding statistics and final validation report.
3. Run the manuscript companion `audit_q15_numbers.py` from its supplied directory, passing `--repo` for the inspected results checkout and `--output` for an audit directory. It reconstructs paper quantities from saved prediction rows and compares them with the freeze and validation outputs. It contains no decoder-fitting step.
4. Check equal-person aggregation and seed/session handling explicitly. Trial counts are 10,520 and 10,800; prediction-row counts are 73,640 and 75,600. Confirm class recall, within-person three-seed averages, paired effects, bootstrap intervals, sign-flip p values, and Holm correction.
5. Compare the manuscript tables/figures with the audit output and retain the generated report with the submitted version. A number audit on saved predictions verifies published arithmetic; it is narrower than a fresh raw-to-checkpoint scientific replay.

An illustrative checkout uses only public repository reads:

```bash
git clone https://github.com/jackzhu119/cross-subject-mi-eeg.git q15-paper-audit
cd q15-paper-audit
git checkout 7af1a137e2676a018e1e880ab076de6cae4ce30b
```

The manuscript companion may be committed after the results snapshot. Keep its own delivered revision with this snapshot rather than assuming that the old results commit contains newly written paper scripts.

With the delivered companion available separately, the arithmetic check is:

```bash
python /path/to/delivered/PAPER_FINAL_20261005/audit_q15_numbers.py \
  --repo /path/to/q15-paper-audit \
  --output /path/to/q15-number-audit
```

Replace these illustrative locations with real local paths. The script uses NumPy for the frozen randomization calculations and pandas for saved-table processing; its dependency/import requirements should be read before creating an isolated audit environment. Raw EEG, training packages, and cloud credentials are unnecessary for this arithmetic check.

## Replaying the science from original EEG

Raw replay is a separate, more expensive verification. Acquire originals from the official providers under their terms: BNCI/BCI Competition IV dataset 2a, PhysioNet EEG Motor Movement/Imagery v1.0.0, [Cho2017](https://doi.org/10.5524/100295), and [Lee2019/OpenBMI](https://doi.org/10.5524/100542). The archived provider manifests identify exact files, sizes, MD5/SHA-256 bindings where available, channel metadata, and dataset scope. R2 copies used by the cloud run are private transport copies, not the canonical public acquisition resource. No access key belongs in a repository, supplement, log, or manuscript.

Use `requirements-q15-runtime.txt` and the frozen scientific revision to reproduce the recorded Q15 environment; inspect platform/CUDA details in `results/Q15-E005/source/run_config.json`. The relevant modules are `scripts/q15_real_metadata.py`, `scripts/q15_metadata_audit.py`, `src/mi_eeg/data/q15_context.py`, `scripts/q15_preprocess_external.py`, `scripts/q15_validate_source.py`, `scripts/q15_external.py`, and `scripts/q15_validate_external.py`. Default and gate behavior should be inspected before invocation. The paper audit does not authorize additional fits, target adaptation, or a new cloud job.

Reconstruct the complete six-second trial contexts, fixed common 21-channel CAR, native-rate zero-phase filters, polyphase resampling, 320-sample crops, and per-person epoch manifests. Verify the original six neural final checkpoints and shallow model. Then reproduce frozen model probabilities and statistics under the committed inference freeze. The final validator's tolerance is atol=10⁻⁷, rtol=10⁻⁶ for probability replay and exact argmax equality. Preserve raw/file, epoch, checkpoint, code, and model-state hashes; comparing only one status Boolean is insufficient.

Do not silently substitute Q14's 22×480 preprocessing, Q14's selected epochs, Lee's `EEG_MI_test` or `smt`, target-fitted normalization, different class mappings, or continuous filtering across Cho's class-concatenated chunks. Such changes define a different analysis.

## Provenance and limitations

The migration job reused 15 historical BNCI-only source fits and performed no new source fits or target fits. Its public restoration receipt covers 160 external originals and 106 epoch-person artifacts. The broader transport inventory has 178 files including the 18 BNCI originals. These are distinct accounting scopes.

The final validator establishes the executed numerical pipeline and frozen-model replay. It explicitly leaves physical export voltage calibration, original Cho hardware reference, and hardware cue latency unverified. Computational agreement does not resolve those acquisition uncertainties. Historical four-class/Q14 analyses have their own runtime, sampling amendments, and validation scope; preserve those records when checking the integrated paper.

## Data/software availability and archive preparation

Prediction CSVs, condition inventories, contracts, manifests, scripts, and validation receipts are inspectable in the public repository. Review its LICENSE before assigning a software reuse license in a submission or third-party archive. The archived Q15 provider manifests record CC0-1.0 for the GigaDB datasets, but each official provider's current terms and required citations should still be checked. Do not infer that a common license applies to BNCI, PhysioNet, and all derived artifacts.

For a durable manuscript deposit, include the final main manuscript, editable sources, supplements, figure sources/exports, number-audit script and output, references, the exact source snapshots, and a package checksum manifest. A GitHub URL provides inspectability; a DOI-bearing archive can be added after author/metadata/license review. No journal submission or persistent third-party archive is claimed by this guide.
