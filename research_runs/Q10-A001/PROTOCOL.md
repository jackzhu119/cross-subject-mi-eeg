# Q10-A001 — Source-only covariance geometry comparator

Q10-A001 is a **predeclared, exploratory** classical comparator. Q5–Q9 target outcomes on BNCI2014_001 were already inspected, so even a large positive result here will **not** be independent confirmation. All four conditions, including negative outcomes, are reported. They are not a target-BA-driven model-selection grid.

## Scientific question and fixed design

Can covariance geometry capture transferable spatial-spectral structure that fixed CSP or EEGNet may miss? We separate (i) nearest-mean geometry versus a linear discriminative model on the **same 4–40 Hz** log-covariance representation and (ii) broadband versus a **fixed** 8–13 Hz mu / 13–30 Hz beta log-covariance representation. The latter comparison changes both band decomposition and classifier; it is exploratory, **not** a clean causal band ablation. A later orthogonal design must address that.

| Condition | Representation | Classifier |
| --- | --- | --- |
| `BROAD_LOGE_MDM` | 4–40 Hz log covariance | Log-Euclidean nearest source class mean |
| `BROAD_LOGE_LOGREG` | 4–40 Hz source-centered log covariance | Source-scaled L2 logistic regression |
| `MUBETA_LOGE_LDA` | 8–13 and 13–30 Hz source-centered log covariance | Source-scaled shrinkage LDA |
| `MUBETA_LOGE_SVM` | Same two bands | Source-scaled linear SVC, with source-only internal probability calibration |

All use the frozen Q8 four-class trial identity, 22 EEG channels, native 250 Hz, 2.5–5.5 s exclusive window, artifact include-all policy, run-local zero-phase fourth-order Butterworth filtering and both target sessions held out. Each of nine outer folds fits on all 4,608 trials from the other eight subjects and predicts 576 target trials. There is no target normalization, adaptation, early stopping, seed search or hyperparameter choice. The classifier and all reference/scaler statistics are fitted **only** from the eight source subjects. This gives **36 outer source fits**; no external inner model-selection fits. SVC's library-internal five-fold probability calibration also uses source trials only and should not be misread as five target-validation folds. The output records its exact package version.

## Geometry and interpretation

For each 22×750 trial, subtract each channel's temporal mean, compute the unbiased 22×22 covariance, then apply fixed 1% shrinkage toward `trace(C)/22 × I`. Symmetric eigendecomposition produces `log(C)`. Upper-triangular vectorization multiplies off-diagonal entries by `sqrt(2)`, so Euclidean vector distance equals the symmetric-matrix Frobenius distance. The source-only mean `log(C)` is subtracted as the reference for tangent-like linear features. `BROAD_LOGE_MDM` uses per-class source means directly in log space and a source-only within-class distance scale for normalized similarity scores.

This is an **in-house log-Euclidean** representation. It is **not** pyRiemann's affine-invariant tangent space or affine-invariant MDM. We deliberately avoid silently conflating the geometries. Distances/probabilities from MDM are normalized similarity scores, **not calibrated event probabilities**. SVC probability calibration is source-trial-based; cross-subject probability calibration remains unproven. Primary comparisons use balanced accuracy, plus subject-level class recall/confusion and probability diagnostics.

## Integrity, resumability and publication

The runner hashes the 18 raw MAT files and compares them with Q8 `source_files.json`; it also requires exact Q8 trial metadata rows and a pinned metadata SHA256 before fitting. An atomic completed-attempt receipt is written last for each condition×fold. A failed attempt is retained and a resumed run creates a new attempt; it never erases failure evidence. On full completion, an independent read-only validation pass checks 36 receipts, source/target roles, model hashes, 20,736 prediction rows, per-fold metrics and probability identities. Aggregated outputs live under `results/Q10-A001/` and carry the config and package-version provenance. The validator is a structural/artifact check, not independent proof of all runtime behavior.

Run from the repository root after installing the existing project dependencies (`numpy>=2,<3`, `scipy>=1.13,<2`, `pandas>=2.2,<4`, `scikit-learn>=1.6,<2`, `mne>=1.10,<2`, `moabb>=1.4,<2`; `pytest>=8,<10` for tests). **No pyRiemann or PyTorch is needed for this experiment.** The GPU is not used by these classical models; the cloud machine's CPU and RAM execute them.

```bash
python scripts/q10_geometry.py run --data-dir /root/autodl-tmp/data/raw --output-dir results/Q10-A001 --resume
python scripts/q10_geometry.py validate --output-dir results/Q10-A001
```

Use the actual directory containing `MNE-bnci-data` as `--data-dir`. Passing a different raw dataset, modified Q8 trial metadata or edited matrix fails closed. A full run and any comparison with Q5–Q9 should be done **after** source-only tests pass and the exact code/config commit is recorded. Compare all four predeclared conditions against frozen Q4/Q8/Q9 at the **nine-subject** unit of analysis; do not count target trials or technical fit repetitions as independent subjects. A later independent external dataset, harmonized before looking at results, is required for confirmatory generalization.
