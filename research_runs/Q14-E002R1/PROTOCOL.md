# Q14-E002R1: custody-preserving continuation of frozen external validation

Status: **code prepared; no Q14-E002R1 external result is claimed here.** This is
an administrative continuation ID, not a new experiment selected using external
outcomes. Q14-E002's source fits, source-only epoch selections, checkpoint
bytes, method comparison, zero-shot target policy, 109-subject cohort, runs
4/8/12, and primary contrast remain unchanged. Prediction CSV rows retain
`experiment_id=Q14-E002`; `Q14-E002R1` identifies only the resumed run and its
new result custody. The original `results/Q14-E002/` is never edited.

## Reason for the revision

The original Q14-E002 target run completed S001–S055, then stopped when a new
AutoDL container changed `platform.platform()` from
`Linux-5.15.0-78-generic-x86_64-with-glibc2.35` to
`Linux-5.15.0-25-generic-x86_64-with-glibc2.35`. The frozen runner refuses to
resume when its `run_config.json` runtime differs. Q14-E002's frozen target
producer also omits `official_checksum_manifest_sha256` from its final
`completion_receipt.json`, although its independent validator requires that
field. Neither frozen producer nor validator is changed. R1 emits a new
completion receipt with that provenance field and uses a new validator.

## Pre-outcome gates

Before reading any target prediction values or inferring S056, the R1 runner:

1. Calls the original source-freeze verification, including code/config,
   source-report, checkpoint, and selected-epoch hashes.
2. Requires the original external `run_config.json` to match current frozen
   code/config, data path, device, subjects, runs, and official checksum
   manifest. Every runtime field must be identical except the one explicitly
   documented kernel string above.
3. Requires **exactly** S001–S055 completed original subject receipts. Each
   receipt, prediction file, and all 165 referenced EDFs are hash-checked;
   EDF bytes must agree with PhysioNet's versioned SHA256SUMS. This phase does
   not parse probabilities, calculate target accuracy, or select a model.
4. Writes `results/Q14-E002R1/external/migration_receipt.json` documenting
   all 55 original receipt/prediction hashes, freeze hash, official manifest,
   old/new runtime, and the original completion-schema gap. Existing receipt
   content must match on every resume.

The original 55 receipt and prediction files are copied byte-for-byte into
new per-subject directories with atomic directory rename. Source model files
are loaded from the frozen original Q14-E002 source directory. S056–S109 use
the original Q14 external loader, filtering, epoch, and inference primitives.
No target fitting, target-based normalization, epoch choice, model/seed
selection, threshold change, rejection, or subject exclusion is permitted.
Each new subject is written atomically and skipped on resume only when its
receipt/prediction hashes and freeze identities verify. Any incomplete visible
subject directory fails closed. Temporary staging directories may remain after
interruption and are retained for forensic inspection; they are not subjects.

## Validation and inference unit

The independent R1 validator hashes the byte-identical original 55 copies,
all 109 subject prediction/receipt pairs and all 327 EDFs, re-reads EDF event
identities, checks all seven model/seed predictions for every trial and
reconstructs the aggregate table. It writes a passing top-level
`results/Q14-E002R1/validation_report.json` only after all 109 subjects pass.
The predeclared primary estimate is `MU_BETA_SHARED - BROAD_EEGNET` balanced
accuracy per PhysioNet subject after averaging the three fixed seeds. A
subject-level 20,000-resample bootstrap CI and exact sign test accompany the
full per-subject and confusion tables. Negative outcomes must be retained.
The binary external endpoint cannot be directly compared to four-class Q5–Q9.

## Commands and publication

After this protocol and scripts are committed, invoke the server-side R1
supervisor/launcher documented in its script, using the preserved external
data directory. Direct phase commands, for debugging only, are:

```bash
python scripts/q14_r1_migration.py --data-dir /root/autodl-tmp/physionet --device cuda
python scripts/q14_r1_validate.py --data-dir /root/autodl-tmp/physionet
```

The supervisor must not claim publication until GitHub push has succeeded and
the remote commit is verified. A server/SSH disconnect cannot be used as
evidence that computation, validation, or publication succeeded.
