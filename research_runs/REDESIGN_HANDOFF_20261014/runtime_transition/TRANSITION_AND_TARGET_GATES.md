# Paper1: accounting transition and target recovery remain separate gates

This preparation does not start a worker, extend a budget, create an execution
registration, read raw EEG, contact R2, import Torch, or request Pod shutdown.
Only dot operates the running Pod. A successful diagnostic or source acceptance
cannot substitute for the accounting, backup, runtime, or target gates below.

## Preserve the historical execution identity

The failed job is `20261014T071918Z-exploratory-89b0c07d`, revision
`05e683e91e2bb39b977970d04402221761e575d2`. Its published failure recorded zero
source fits, zero optimizer updates, and no target predictions. This historical
record does not prove that a new host has the same complete local accounting
state. Inaccessibility is **not** a newly verified zero counter or absent
checkpoint. Preserve the native `array_hashes` failure and all prior evidence.

The original clock starts `2026-10-14T07:07:45.290107+00:00` and expires
`2026-10-14T15:07:45.290107+00:00`. Source code still enforces this eight-hour
clock; retries, checkout changes, or a new directory cannot reset it. Existing
scope is at most 26 source fits and 34440 optimizer updates; target fitting and
optional grouping remain disabled. Broad/shared, fixed20/mean-loss/mean-rank,
the 19 channels, source groups, seeds, and target exposure classification remain
unchanged.

Existing `--resume` requires the old revision, original hostname/GPU UUID,
runtime lock, and unexpired machine budget. Neither a CPU acceptance nor this
metadata utility supplies a cross-machine/cross-revision resume path. Do not
run the old launcher against a blank work root to obtain a fresh clock. Do not
delete a registration or issue a second core experiment.

Before a separately reviewed execution transition, the reviewer needs:

1. Immutable old registration, budget origin, launch/runtime/code identity,
   status and ledger, if recoverable; their hashes and explicit missingness.
2. A reconciled checkpoint inventory and any `update_intent.json` / remote
   PENDING state. If nonzero counters or unresolved intents are found, no
   zero-fit transition is permitted. Checkpoints/optimizer/RNG are private;
   this utility does not read their binaries or assert absence.
3. A verified private recovery review copy where available. Existing
   `private_recovery.py restore` accepts only COMMITTED HEAD, a byte-matching
   manifest, all blobs fully read back, and unchanged HEAD after restore.
   Its `VERIFIED_REVIEW_COPY_NOT_RESUME_AUTHORIZATION` receipt is evidence for
   human/code review, not permission to resume. Unknown/missing backup remains
   unknown; do not fabricate a no-checkpoint assertion.
4. Actual training-runtime input acceptance, bound to the numerical policy,
   consumer imports and the audited full diagnostic package SHA256
   `2871f422755bf5d0b939d0db59fc41547b192d6c939db1a6a13b97a91ba49ae9`.
5. A **separate explicit machine/budget amendment** recording current runtime,
   provider price, new execution scope, author authorization source/date,
   deadlines, retained old counters, and backup ownership. This document
   neither issues that amendment nor silently changes the original ledger.
   The research fit/update ceilings do not disappear with a funding amendment.
6. A tested, reviewed transition implementation before any command capable of
   fitting; no such launch command is supplied by this metadata tool.

`transition_plan.template.json` records all unresolved gates as UNKNOWN, with
null evidence references. Its schema disallows PASS and budget authorization.
It is a plan, not `budget_authorization.json`, `execution_registration.json`,
or `numerical_execution_review.json`. Add observed evidence references in a
separate copy; never fill unknowns from expectation or replace old records.

## Dreyer restoration and mapping

The frozen target is the NEMAR `nm000250` v1.0.5 acquisition EDF mirror:
174 EDF files, **2515343396 bytes**, initially 87 participants. The frozen
provider technical exclusions A17/A41 leave 85 participants and 6800 events.
Only 170 of the 174 files contribute retained events; excluded-provider files
remain in the full acquisition manifest and the official 192-file importer
inventory. Do not shrink the download/audit inventory to 170 by outcome or
without a separate protocol change. The target is not authenticated original
Zenodo GDF bytes. Prior exposure remains unknown, so external evaluation is
exploratory, not independent confirmatory evidence.

Frozen byte references:

| Record | SHA256 |
|---|---|
| 174-file acquisition manifest | `2cfdf35aa7990df880826d1b84d1230e0bda3c9393c17d3ec6e27b7b311d2bf2` |
| 85-person/6800-event raw-only roster | `f578c8d0ee4a2500532f473c06f561390f698072f353c479accef639707df4a1` |
| Source whole-input receipt | `66c5aa472809cf29fe68b7b56401c4f0aa4b4f577156425a1f4e1fc20d45d8dd` |
| Source trial fingerprints | `e142e927228d9c46afb872fa649335cc6e9ec286b1d291b94ac0e43a6d59e4cf` |

The currently committed `source_r2_mapping.json` maps the 18 BNCI files only.
It lacks **all 174 actual Dreyer R2 object keys**. No metadata review can infer
these keys from filenames, provider URLs, or hashes. Supply authentic existing
upload receipts or an explicitly authorized metadata object inventory, then
bind a complete mapping SHA256. This step performs no listing, HEAD, GET, or
credential discovery. Historical source backup receipts do not prove current
access to any object.

The existing `r2_only.validate_mapping` requires exactly 192 paths (18 source
plus 174 target), unique safe object keys, integer sizes and frozen SHA256
matches. Once authorized to restore, its importer verifies existing local
files and downloads only missing files; validates size/full SHA256; never
overwrites a valid cache or falls back to the official provider. Complete
local mapping metadata does **not** mean remote objects are accessible or
that raw bytes/tensors are verified.

After separately authorized restoration, the frozen raw-only audit must
reconfirm channels/order, sampling, labels, event IDs, context and all frozen
trial/band input hashes, with the formal 512 Hz numerical path. The mapping
review does not run that audit or read target EEG. Target duration selection,
parameter/normalization fitting, and BatchNorm updates remain prohibited.

## Storage: known lower bounds, not a launch guarantee

The latest supplied remote free-space observation is 20443377664 bytes; this
document did not query the Pod. Source raw files already verified total
779873919 bytes. Missing Dreyer raw bytes total 2515343396 (2.343 GiB).
`r2_only` requires missing raw bytes plus **6 GiB reserve** before import:

- if only Dreyer is missing: 8957794340 bytes free is the import minimum;
- if all 192 raw files are absent: 9737668259 bytes free is the import minimum.

These bounds exclude new runtime storage, model/checkpoint/log growth, existing
paper2 disk growth and tensor/working temporaries. Three target float32 tensors
need at least 496128000 bytes; three source tensors need 189112320 bytes.
Recheck measured free space after isolated runtime preparation and before
restoration. A reusable exact CUDA donor can reduce environment duplication,
but must be inventoried and verified independently; this utility neither
installs CUDA nor modifies the paper2 runtime.

## Minimal read-only metadata command for dot

Run the following in the reviewed fixed checkout named by the parent handoff.
It is not a source reconstruction, acceptance rerun, restore, or fit. It only
prints JSON to stdout; redirect to a **new** evidence file if desired. The
expected exit is **3** because unresolved gates deliberately remain blocked.

```bash
python3 research_runs/REDESIGN_HANDOFF_20261014/runtime_transition/transition_target_gate.py \
  --repo "$PWD" \
  --old-work-root /workspace/mi-eeg-cloud \
  --r2-mapping research_runs/REDESIGN_HANDOFF_20261014/source_r2_mapping.json \
  --r2-mapping-sha256 7d5ec2e9ddec16d2be5cb3778037c96dabb6559b8c208ad4cca9923c67407663 \
  --plan research_runs/REDESIGN_HANDOFF_20261014/runtime_transition/transition_plan.template.json
```

Unknown local old records remain null; the utility does not conclude historical
zero fits from a missing directory. Replace the mapping argument only with an
actual reviewed mapping and its exact SHA256, not a fabricated completed list.
Even if that mapping becomes complete, output remains TRAINING_BLOCKED and
neither the scientific runtime nor budget/target gates are cleared.
