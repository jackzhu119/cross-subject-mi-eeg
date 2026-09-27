# Current evidence and release gates (2026-09-27)

This is a new status snapshot, not an edit to the frozen 2026-09-26 planning
packet or to any Q5--Q14 result. It is based on GitHub `main` at
`e70a07690646561135aa4b22d0bd9335a44c7412` and the local checks listed
below. The cloud instance is off. No new training, external prediction, cloud
deployment, or Git publication is authorized by this file.

| Stage | Present evidence | Release decision |
| --- | --- | --- |
| Q12-E001/E002 | `results/Q12-BATCH/batch_status.json` is `complete_validated`: 12/12 jobs, 216 inner and 162 final fits. `scientific_validation.json` passed checkpoint reconstruction and source-only transform checks. | Complete; retain all six conditions, including negative results. Do not rerun merely because the older paper queue failed. |
| Q14-E002R2V1 | `results/Q14-R2PORT/batch_status.json` is `complete_validated`; `results/Q14-E002R2V1/validation_report.json` passed the independent 327-EDF, 109-subject, 4,918-trial, 34,426-row check with zero new fits and zero new inference rows. | Validated external binary transfer, subject to the published R2 post-partial-execution amendment and cross-host validation-portability amendment. Preserve the original failed validator receipt. |
| Q13-E001/E004/E005 | Frozen matrix and runner exist. Local dry run and unit tests pass, but no `results/Q13-*` scientific result exists in this checkout. | Pending cloud execution and full checkpoint replay. Do not resume the obsolete Q12 paper queue: its frozen manifest no longer matches the current code. |
| Q13-E006 matched-runtime selection control | Q5 historical broad/raw-CE final models were trained with PyTorch 2.14.0+cu132, whereas the latest Q12 environment used PyTorch 2.8.0/cu128. Q13's future runtime remains unknown. The new additive E006 runner, matrix, amendment and 27-checkpoint validator are locally prepared; no E006 fit exists. | Run only after the original 837-fit Q13 batch passes and only under the *same recorded runtime/data identity* as Q13 broad/fixed-20. Compare the historical source-only epoch schedule with fixed 20, not a re-run of the full selection procedure. Never change the frozen Q13 matrix silently. |
| Q15 Lee/Cho | New `Q15_AMENDMENT.md` and `Q15_CONTRACT.json` predeclare a conditional 21-channel common-cohort branch. A metadata-auditor scaffold and guarded Q15-E005 source runner now exist and pass synthetic/structural tests, but **no real Lee/Cho raw metadata receipt, source model, target prediction, or independent validation exists**. The MOABB v1.7.2 Lee MI sensor list omits FCz, which the frozen Q14 22-channel model requires. | Fail closed on the old 22-channel Lee arms unless actual pinned-loader/raw metadata resolves the mismatch. Current auditor deliberately blocks real MAT files until a reviewed adapter and authenticated provider inventory exist. Q15-E005 and zero-shot E006/E007 remain blocked; a source validator and external inference/validator are not yet implemented. |

## Minimum next release sequence (only after explicit user authorization)

1. Commit and review new Q13/Q15 amendments and tests locally, then decide the
   exact cloud queue. Keep historical protocols/results byte-for-byte intact.
2. Before paid computation, verify the destination host's CUDA, Python/science
   package versions, writable storage, Git noninteractive publication, 18
   unique BNCI MAT files and their recorded hashes, and the exact frozen
   code/config commit. A prior host's successful preflight does not certify
   this host.
3. Run Q13's frozen 837-fit batch and its independent 837-checkpoint replay.
   Then run the additive Q13-E006 27-fit matched-runtime control and its
   separate 27-checkpoint replay in the same environment; the combined
   planned new deep fit count is **864**, not 837. Hold all Q13 inferences
   at the target-subject grain; seeds and
   source subsets are repeated measurements. Publish failed as well as passed
   receipts without deleting earlier records.
4. Audit Lee and Cho **metadata only**: provider release, file hashes, every
   subject/session/run, exact channel names/order/reference/units, labeled
   events and cue origin, enough in-task samples for the frozen window,
   missing/corrupt files and licensing. Do not read model scores while making
   eligibility or harmonization decisions. Freeze a versioned contract and
   source checkpoint hashes in Git before external prediction.
5. Only compatible, predeclared Q15 arms may proceed to source fitting and
   then zero-shot inference. The new 21-channel branch has a fail-closed
   metadata-auditor scaffold and source-runner implementation, **not** a
   real-data execution release: real provider adapters/inventory, an
   independent source validator, and external inference/validation remain
   outstanding. Its conditional source-fit count is
   **14 deep + 1 shallow**, with zero external target fits. The Q13 plus
   conditional Q15 total would be **878 deep + 1 shallow** new fits, not a
   presently runnable single queue. For any activated external arm,
   require zero target fits, all eligible people, complete trial-level
   predictions, independent raw-file reconstruction and subject-level
   statistics. A metadata pass alone cannot be called external validation.

## Interpretation boundary

Q12 is nine-person, four-class, repeatedly explored BNCI2014_001 evidence.
Q14 is an independent 109-person **binary** PhysioNet cohort with different
acquisition/reference conditions. Their balanced-accuracy values must not be
pooled or compared as if they were the same task. Q12 has no corrected
improvement claim; Q14's predeclared shared-μ/β minus broad point estimate is
positive but its subject-level 95% CI includes zero. Details and exact input
paths are in `Q12_Q14_EVIDENCE.md`.

## Verification still unavailable while the cloud is off

Local source/test checks cannot establish successful Q13 GPU fits, cross-host
reproducibility, live detached execution, Git publication, Lee/Cho raw-channel
eligibility, external zero-target-fit status, or any Q15 score. These stay
explicitly pending rather than being inferred from planning documents.
Offline checks in this preparation checkout include **190 passing repository
tests** (including 76 focused Q13/Q15 checks) covering Q13/E006 planning
and post-run statistics, Q15 contract/metadata/source preflight, both Q13
no-training dry runs, Q15's contract-only validator, a Q15 source dry run
that correctly stops with zero fits, and a visually inspected Q12 descriptive
heatmap. These synthetic/structural tests do not substitute for raw-cohort
auditing or any Q15 scientific validation.
