# Q12 source-only domain generalization: pre-execution protocol

Status: prepared, **not executed**. This packet adds Q12-E001 (source-only whitening and group-risk control) and Q12-E002 (train-only perturbations). It does not alter frozen Q5–Q14 artifacts. BNCI2014_001 is already explored, so all Q12 findings are **exploratory**, not an independent confirmation.

## Question and estimand

Does a source-only transformation or robust optimization improve zero-calibration performance on unseen BNCI2014_001 people beyond Q8-E001 broadband EEGNet? The estimand is the equal-subject mean of each held-out person's three paired-seed balanced accuracies. The target person is withheld across both sessions. Report all nine person-level contrasts, class recall, collapse, seed variability and session strata; never select a condition, seed or epoch using target results.

## Frozen common protocol

- Four-class left/right/feet/tongue; subjects 1–9; 22 EEG channels at 250 Hz; Q8 run-local zero-phase Butterworth 4–40 Hz; trial-start `[2.5,5.5)` seconds; all 5,184 trials including flags; µV input. Identical target trial IDs to Q8 are required.
- Outer LOSO: eight source subjects train, one target subject tests. Inner validation: four consecutive pairs of sorted eight source subjects; the other six train. Every learned transform is fit anew on the exact six or eight source-training subjects and then fixed on validation/target.
- Selection seed 20260923: 40-epoch inner trajectories, earliest epoch minimizing the equal-inner-fold mean of within-fold validation-cross-entropy ranks. Final seeds 20260924/25/26. Q8 architecture, Adam, batch size, learning rate and weight decay are inherited without target-driven changes. No early stop by target.
- Save fit-manifest trial identities, source MAT hashes, code/config hashes, checkpoint, full probability vectors, learning curves and completion receipt per fit. No target-derived scaler, covariance, alignment, class prior, weight or BatchNorm adaptation. A deterministic transformation of a *single* target trial is allowed; pooling target trials to learn a statistic is prohibited.

## Q12-E001: source-only whitening and risk weighting

1. `SOURCE_POOLED_WHITEN`: For each fit, center each training trial over time, compute channel covariance, average covariances **equally by source subject**, regularize with a prespecified 5% mean-eigenvalue ridge, and construct `W = sqrt(mean_eigenvalue) (C + ridge I)^(-1/2)`. The factor preserves the overall µV scale. Apply the same frozen W to training, validation and target trials. No target sample enters the covariance. Record source sample-ID hash, covariance eigenspectrum and W in a receipt.
2. `SOURCE_BALANCED_ERM`: Match GroupDRO's source-balanced batch construction, optimizer steps and random sampling, but average the source-subject losses equally. This is a mandatory control: GroupDRO cannot be credited for benefits caused simply by balanced batching.
3. `SOURCE_GROUP_DRO`: Use the same balanced batches; update non-gradient source-subject weights `q_g ∝ q_g exp(0.05 L_g)` after each step, with persistent normalized q across epochs. Optimize the weighted group loss. Report group weights and per-source losses. No target group/statistic enters the update.

The 5% ridge and DRO step 0.05 are fixed *before* target inference, not selected from a target-driven grid. Whitened-vs-Q8 is a pipeline comparison; GroupDRO-vs-balanced ERM isolates robust weighting. GroupDRO-vs-Q8 alone would conflate batching and risk weighting.

## Q12-E002: training-only perturbations

1. `CHANNEL_DROPOUT`: independently zero each source-training example/channel at probability 0.10; scale survivors by 1/0.90.
2. `GAIN_PERTURB`: independently multiply each source-training example/channel by a uniform random gain in `[0.8,1.2]`.
3. `CHANNEL_AND_GAIN`: apply the exact gain then dropout operators above; no new hyperparameters.

Validation and target trials are never augmented. Test both each mechanism and their interaction, including detrimental outcomes and class collapse.

## Comparison and inference

Q8-E001 is the frozen pooled-ERM reference; its checkpoints/results are reused without retraining. Q12-E001 has three new conditions × (36 inner + 27 final) = **189 deep fits**. Q12-E002 also has three × 63 = **189**. Total **378** new deep fits. The source-only DG family contains predeclared subject-paired contrasts `WHITEN−Q8`, `BALANCED_ERM−Q8`, `GROUP_DRO−BALANCED_ERM`; augmentation family contains each arm against Q8. Within each family report Holm-adjusted exploratory p-values if shown. Bootstrap resamples **subjects**, not trial or seed rows. Nine overlapping LOSO training sets and previously explored BNCI scores limit confirmatory interpretation.

## Activation gate

This packet is not permission to launch on the paid host. **The batch CLI defaults to plan-only**; paid work requires `--execute`. Before *any* GPU job, the batch checks that Q12 code/protocol are committed and unchanged, that Q8's independent validation receipt passed without target-training leakage, that a CUDA device works, and that the data directory exists. Before target prediction, all 216 source-only inner fits across six conditions finish and freeze their selections. Verify source split/whitener/augmentation invariants on synthetic data and review the exact Git commit before activation. The older Q9 batch receipt is orchestration-only; do not promote Q9 as independently scientifically validated without a separate audit.

The cloud environment needs matching CUDA-enabled `torch` and `torchaudio`, `braindecode`, `mne`, `moabb`, `numpy`, `pandas`, `scikit-learn`, `threadpoolctl` and this repository's pinned requirements. The `--data-dir` must point to locally cached **raw BNCI2014_001 MAT data**; raw EEG remains outside GitHub. `--output-root` must be the repository's `results` directory for the existing safe publisher. Linux example, after checkout of the reviewed commit and environment setup:

```bash
python scripts/q12_batch.py --data-dir /workspace/bnci2014_001 --output-root ./results --plan-only
python scripts/q12_batch.py --data-dir /workspace/bnci2014_001 --output-root ./results --execute --publish
```

The first command never starts training. The second runs one GPU job at a time, resumes only intact hashed fits, independently replays checkpoint predictions from raw EEG, checks all 216 inner and 162 final fits, and publishes results/logs to GitHub after validation. On failure it stops, preserves the failed-attempt evidence and attempts to publish partial/failure records without calling them validated. Automatic GitHub publishing additionally requires a noninteractive, write-authorized SSH deploy key and a clean `main`; a failed push leaves the local cloud files and a publish receipt for retry. A code or protocol revision after first target prediction requires a new amendment ID; do not overwrite existing results.
