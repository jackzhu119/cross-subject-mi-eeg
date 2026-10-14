# Container rebuild: recover evidence before execution

## Observed boundary and current authority

The operator reports that Pod `52ivinpjwv947i` was rebuilt at
`2026-10-14 14:59:11 UTC`, changing container `b5646c12356b` to
`a7d3f0e408a4`. The new `/workspace` contains only `.cache`, and the reported
overlay capacity changed from 30 GiB to 50 GiB. This document did not inspect
the Pod, contact R2, SSH to it, fetch data, install an environment, or alter
security/credentials. Treat these details as operator-reported rebuilding
evidence until supplied observations are independently checked.

The same Pod ID does **not** prove persistence of the prior container's
filesystem, process, runtime, or GPU identity. All former code/raw/runtime/
review-output paths are stale references, including
`/workspace/paper1-formal-numerics-review-97f1f42a`,
`/workspace/paper1-diagnostic-runtime`, and `/workspace/mi-eeg-cloud`.
Do not invoke previously supplied acceptance or launcher commands against
those paths. Do not recreate an apparently empty work root and let a launcher
generate a new registration or clock. `.cache` is not a verified raw cache,
checkpoint inventory, runtime, or restoration receipt.

dot remains the sole server operator. Keep the Pod running as instructed.
This handoff supplies no Stop/Terminate, restart, SSH/security change,
credential copying, fit-7, or other fitting command.

## Deadlines and counters remain explicit

The user-authorized 48-hour deadline remains
**`2026-10-16T09:54:00+00:00`**. Rebuilding, recovery, downloads, and reinstalling
do not extend it. Preserve this existing authorization in an append-only
execution amendment; do not ask for or infer a new 48-hour window.

The historical paper1 job is
`20261014T071918Z-exploratory-89b0c07d`, with original revision
`05e683e91e2bb39b977970d04402221761e575d2`. Its original eight-hour budget starts
`2026-10-14T07:07:45.290107+00:00` and ends
`2026-10-14T15:07:45.290107+00:00`. That historical receipt must remain unchanged.
The current code still enforces this old clock and the original machine lock;
the 48-hour user instruction is not automatically implemented by restoring or
rerunning the old launcher. A separate, reviewed operation amendment must
encode the already-given authorization, retained accounting history, current
runtime/machine identity, and absolute deadline before any eligible execution.
No silent change to `budget_origin.json`, no registration deletion, and no
implicit cross-revision/machine resume are permitted.

Published old failure evidence records zero paper1 fits and zero optimizer
updates. The destroyed container's latest local ledger/checkpoint state is
currently **not observed**. Historical zero-fit evidence must be retained,
but it does not justify silently declaring every missing current record zero.
Unknown checkpoint or remote update-intent state is not an absent checkpoint
or completed backup. Preserve ceilings of 26 core source fits and 34440
optimizer updates unless an independently frozen research revision actually
changes the design; a funding/window amendment alone does not do so. Target
fitting and optional grouping remain disabled.

The operator reports paper2's first six fits were backed up to R2. This is a
backup claim to verify, not a verified restoration or permission to start fit
7. Preserve paper2's separate job, ledger, source/model/code freezes, runtime
and deadline references. Never infer their object keys, receipts, fit counts,
or checkpoint completeness from paper1 evidence.

## Recovery sequence: evidence and metadata first

Each stage has its own receipt and must preserve missingness. No stage below
is currently marked PASS, and this document makes no R2-access claim.

| Gate | Required immutable evidence | Current state |
|---|---|---|
| Rebuild identity | Supplied timestamp, container IDs, storage/mount/free-byte observation, before/after continuity scope | Operator report; no independent current Pod observation |
| Git execution source | Fixed commit SHA, clean new review checkout, exact protocol/code byte checks, retained historical commits | Git source can be recovered; no checkout recreated on Pod here |
| Old paper1 accounting | Original registration, budget origin, launch/code/runtime identity, status and ledger, hashes and recorded missingness | Latest container copy inaccessible/not observed |
| Private recovery state | Actual per-job HEAD, manifest hash, full payload readback, consistent counters/checkpoints and unresolved intents | Not read from R2 this round |
| Original full diagnostic archive | Exact 134436-byte package identity and independent archive audit | Historical supplied archive available; not source raw data or a runtime |
| Formal CPU source-acceptance archive | Exact 12299-byte package identity, payload hashes, command/code/exit-3 scope | Historical supplied archive available; training-runtime gate still false |
| Source raw restore | Actual existing R2 mapping/receipts and all 18 byte/hash-verified raw MAT files | Old local files lost; current remote access/content not observed |
| Actual training runtime | Separate exact environment and consumer import/ABI check, space measurement and source acceptance | Prior paths stale; new runtime not prepared |
| Dreyer mapping | Authentic full 174-object target mapping joined to frozen identities, plus 18 source entries | All 174 target object keys still missing |
| Target raw/tensor identity | Full raw-only technical audit and frozen context/trial/band hashes after authorized restore | Not restored or read here |
| Reviewed execution transition | Explicit machine/runtime/budget/backup ownership amendment with preserved histories | Pending; no training authorization issued |

1. **Bind the offline evidence already supplied.** The original full archive is
   134436 bytes, SHA256
   `2871f422755bf5d0b939d0db59fc41547b192d6c939db1a6a13b97a91ba49ae9`,
   containing 12 manifest-listed payloads plus its manifest. The formal
   acceptance archive is 12299 bytes, SHA256
   `a4c6c3f7beadf6ce0c927c6e4b9d20b6d37ff3bc2c033ad4b4fd836ca38a6b0d`,
   containing 16 manifest-listed payloads plus its manifest. Do not execute
   archived scripts, repeat diagnostics/CPU acceptance merely because the
   container was replaced, or interpret old report paths as surviving files.
   Neither archive contains the raw EEG or establishes a new training runtime.

2. **Use a fixed Git source in a new review directory only when dot is asked
   to perform recovery.** Preserve branch
   `research/paper1-handoff-20261014`, scientific branch
   `research/source-selection-redesign-20261012`, main, Q1–Q16, old submissions
   and `plos-one-submission-v1.1`. Historical acceptance source is fixed commit
   `97f1f42a712c4feb1a0be7eca25ac04b06c9c946`; the instruction version was
   `e276cf6bf2595260487a69fb40ea17cbcd770839`. The parent handoff must supply the
   new reviewed delivery SHA explicitly. A moving branch tip is not a runtime
   lock. This document neither clones nor resets a checkout.

3. **Inventory actual non-secret recovery references before requesting raw
   EEG or resuming work.** Use existing private backup receipts or already
   supplied manifests to identify authentic per-job HEAD/manifest/blob keys.
   Do not guess a prefix or perform object discovery here. A later authorized
   recovery requires COMMITTED HEAD, a byte-matching manifest, every referenced
   artifact fully read back and hashed, unchanged HEAD after restore, and
   explicit rejection of PENDING/uncertain writes or unresolved update intents.
   ETag is a concurrency token, not content verification. Restore to a new
   review directory, leaving old evidence immutable. A verified review copy
   still does not authorize resumption. If no old backup is found, record
   NOT_OBSERVED and reconcile against the published failure evidence; do not
   issue a fresh zero ledger or assert complete checkpoint loss.

4. **Recover source raw identity separately from source numerical acceptance.**
   The 18 BNCI MAT files total **779873919 bytes**. Existing committed source
   mapping SHA256 is
   `7d5ec2e9ddec16d2be5cb3778037c96dabb6559b8c208ad4cca9923c67407663`.
   It is a historical mapping, not evidence of current readability. After a
   separately instructed restore, every raw file must match the frozen name,
   size and full SHA256; existing valid files must be reused rather than
   redownloaded. The whole-input receipt SHA256 remains
   `66c5aa472809cf29fe68b7b56401c4f0aa4b4f577156425a1f4e1fc20d45d8dd`;
   trial fingerprint SHA256 remains
   `e142e927228d9c46afb872fa649335cc6e9ec286b1d291b94ac0e43a6d59e4cf`.
   No tolerance, manual three-element patch, replacement frozen hashes,
   or deletion of native failure evidence is permissible.

5. **Reinventory runtime and disk before installing anything.** No previous
   Torch/CUDA donor path can now be assumed to exist. A reported 50 GiB overlay
   is capacity, not measured free storage or persistence. Obtain supplied
   non-secret current inventory and actual free bytes before proposing any
   new environment. Do not recreate or modify the paper2 runtime. If an exact
   valid CUDA donor is absent, the previous lightweight reuse plan is blocked;
   a separate isolated installation/space plan is required. Paper1 requires
   NumPy 2.3.5/SciPy 1.17.0 and its committed training imports; historical
   paper2 NumPy 2.2.6/SciPy 1.15.3 is not equivalent. Old diagnostic acceptance
   did not verify training consumer imports or private-package binding.

6. **Resolve target mapping before any target restore.** The frozen Dreyer
   inventory has 174 acquisition EDFs, **2515343396 bytes**, NEMAR nm000250
   v1.0.5; 85 retained participants and 6800 events after provider exclusions
   A17/A41. All 174 target object keys remain missing from the current source
   mapping. The importer requires exactly 192 entries: 18 source plus 174
   target, safe unique real keys, exact size/SHA256. Do not invent keys or
   silently fall back to official downloads. The target acquisition manifest
   SHA256 is
   `2cfdf35aa7990df880826d1b84d1230e0bda3c9393c17d3ec6e27b7b311d2bf2`;
   raw-only roster SHA256 is
   `f578c8d0ee4a2500532f473c06f561390f698072f353c479accef639707df4a1`.
   Prior exposure remains unknown: exploratory external evaluation only.

7. **Check space against all recovery needs before restore/install.** With
   all 192 raw files lost, raw data require **3295217315 bytes**; the existing
   importer's missing-data-plus-6-GiB reserve minimum is **9737668259 bytes**.
   This excludes Python/CUDA, restored checkpoints, Git, active paper2 growth,
   logs and preparation temporaries. Source/target three-band float32 tensors
   additionally need at least **189112320 / 496128000 bytes** respectively.
   No previous free-byte observation survives the rebuild as current evidence.

8. **Only then prepare a reviewed execution transition.** Actual training
   runtime acceptance, backup reconciliation, old/new identity/accounting,
   absolute deadline implementation and full target restoration gates must
   all be resolved explicitly before a fitting command. The current recovery
   plan changes no scientific schedule, preprocessing rule, trial population,
   source-only selection rule, model or seed. Target labels/EEG cannot choose
   durations, fit normalization/parameters or update BatchNorm.

The immediate task is offline recovery preparation and evidence reconciliation,
not another numerical diagnostic, target audit, scientific inference, or new
fit. Return actual missing record references to the parent handoff instead of
substituting a fresh registration or assumed checkpoint count.
