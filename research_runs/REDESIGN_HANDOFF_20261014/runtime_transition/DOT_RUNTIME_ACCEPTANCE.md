# dot fixed recovery handoff — HOLD: protocol delivery only

**Latest instruction: do not touch the Pod or start training.** This file records
conditional future steps, not permission to execute them now. No current Pod
preflight was performed. No old path is presumed to exist after the reported
2026-10-14 14:59:11UTC rebuild.

Fixed code: **`23bbe5e4d4ab0e2f9b39e955a057cc445ddb0d08`**, on
`research/paper1-handoff-20261014`. The 26 changed public files were read back
byte-for-byte; see `PUBLIC_EXECUTION_READBACK.json`. Old scientific code,
source/target manifests, fingerprints, numerical profile, results, main and
publication tags remain unchanged. This release creates no scientific job.

## Verified evidence and outstanding observations

The exact 12299-byte formal CPU receipt archive passed independent integrity and
record-consistency audit: SHA256
`a4c6c3f7beadf6ce0c927c6e4b9d20b6d37ff3bc2c033ad4b4fd836ca38a6b0d`,
16 payloads + manifest, ten execution identities at97f, diagnostic role,
18files/108runs/2592trials, three strict aggregate hashes, expected exit3.
Original wrapper `Extra data` error and the parsing-only correction are retained.
The audit did not reconstruct arrays, execute archived scripts, or rerun source
acceptance. Six GPU PID records include one zombie sample; only five show a
non-zombie paper2 GPU child. No claim of paper2 scientific/backup completion is
made from these snapshots.

The previously audited full source diagnostic archive remains134436bytes, SHA
`2871f422755bf5d0b939d0db59fc41547b192d6c939db1a6a13b97a91ba49ae9`,
12 payloads + manifest. Restoring these two evidence archives means verifying
their exact bytes/manifest, **never repeating their old diagnostics**.

The same Pod ID does not prove container/runtime/data/lock continuity. The author
reports container b5646c12356b→a7d3f0e408a4, `/workspace` only `.cache`, overlay
30→50GiB, cause unknown, no dot Stop/Restart and no fit7. Off-host/R2 backup is
reported for the source/acceptance and paper2 fits1–6; actual current R2 objects,
HEAD, manifests and blob hashes have not been observed here. Do not fabricate
current preflight or infer absence of pending optimizer state from an empty root.

## Complete restoration checklist, preserving the existing tasks

| Required item | Exact condition / evidence boundary |
|---|---|
| Access | Existing HTTPS/browser route only after the HOLD is lifted; no SSH installation, new keys, credentials, security-setting copy or guessed Jupyter endpoint |
| Current container | Actual container/mount/free-space/base-Python/package observations;50GiB is reported capacity, not measured free or persistent space |
| Paper1 code | Fixed23bbe checkout at a new reviewed path; verify committed bytes/checksums; recovering code does not initialize a new experiment |
| Original task | `20261014T071918Z-exploratory-89b0c07d`, original code05e683e9; retain native failure, public zero-fit history, old registration/ledger/intents/checkpoint metadata and missingness |
| Original accounting | Preserve07:07:45.290107→15:07:45.290107UTC eight-hour ledger; no fresh `budget_origin.json`, registration deletion or blank-root launch |
| Existing shared authorization | Absolute end **2026-10-16 09:54UTC**, unchanged; attach actual pre-existing authorization/accounting provenance in a separately reviewed operational transition, no renewed clock |
| Evidence archives | Exact12299/134436byte packages above, manifests/recorded code identities; neither raw EEG nor private packages enter GitHub |
| Source raw bytes | 18 BNCI MAT,779873919bytes; frozen source manifest and all SHA unchanged; restore missing verified bytes only |
| Paper1 runtime | CPython3.12.3; torch/torchaudio2.8.0+cu128;CUDA12.8; NumPy2.3.5/SciPy1.17.0 plus all committed pins |
| Paper2 runtime | CPython3.11.16; distinct numerical site and fixed uv.lock; whole Torch/torchaudio/Triton directories cannot cross ABI |
| Shared storage | Reviewed actual wheel/component plan; measured peaks plus raw/tensors/checkpoints/two-paper growth; no automatic duplication of CUDA |
| Paper1 runtime acceptance | One NEW-runtime CPU acceptance through actual trainer loader plus full private archive binding; no model, CUDA tensor, target EEG or saved substitute arrays |
| Numerical review | Independent review of runtime-bound receipt before any numerical_execution_review or production data_prepare PASS; helper never fabricates these |
| Private recovery | Authentic COMMITTED HEAD, unchanged after restore, manifest/all blobs complete fullSHA readback; unresolved PENDING/intent blocks; restore-review-copy is not resume authorization |
| Dreyer | Authentic174R2keys still missing; complete192file mapping;2515343396target raw bytes; frozen85participants/6800events and512Hz trial-band hashes must later be verified |
| Paper2 results | First5 public acknowledgements retained; fit6 user-reported backup must be independently bound/acknowledged without refit; fit7 prohibited now |
| Execution transition | A tested append-only cross-container/revision/accounting transition preserving original limits/counters/authorization; original launcher cannot supply this by changing work root |

Detailed dependency/storage conditions:
[CONTAINER_REBUILD_DEPENDENCIES.md](CONTAINER_REBUILD_DEPENDENCIES.md).
Detailed backup/identity gates:
[CONTAINER_REBUILD_RECOVERY_GATES.md](CONTAINER_REBUILD_RECOVERY_GATES.md).
Paper2 fixed record inventory:
[PAPER2_REBUILD_POINTERS.md](PAPER2_REBUILD_POINTERS.md).

## Conditional exact helper calls — DO NOT EXECUTE NOW

The variables below deliberately have **no old-path defaults**. They must be
bound to independently observed or reviewed future restored paths. New names
are proposed destinations, not current filesystem observations. Existing files,
failure logs or partial environments must be preserved, not deleted for retry.
Code revision must remain23bbe for these calls; its helpers reject mismatches.
The documentation commit may be newer without changing that execution pin.

### 1. Metadata-only review after fixed code/evidence restoration

The interpreter executing the following first command may be a measured current
stdlib Python. The donor argument must be a freshly measured CPython3.12.3,
not the expired paper2 cp311 runtime. If no such donor exists, this route blocks;
use the separately reviewed fresh-ABI construction plan, which is **not
implemented by the donor-only helper**.

```bash
# RECORD ONLY: this task has not lifted the HOLD on Pod access.
P1_REV=23bbe5e4d4ab0e2f9b39e955a057cc445ddb0d08
test "$(git -C "${P1_CODE:?actual fixed recovered code path}" rev-parse HEAD)" = "$P1_REV"
test -z "$(git -C "$P1_CODE" status --porcelain)"
"${P1_METADATA_PYTHON:?actual current stdlib Python}" -I -B \
  "$P1_CODE/research_runs/REDESIGN_HANDOFF_20261014/runtime_transition/runtime_preflight.py" \
  --code-revision "$P1_REV" \
  --donor-python "${P1_DONOR_PYTHON:?fresh exact CPython3.12.3 GPU metadata candidate}" \
  --output-dir "${P1_PREFLIGHT_OUT:?new direct workspace evidence directory}" \
  --old-work-root "${P1_OLD_REVIEW_ROOT:?authentic historical review root or explicitly unobserved path}" \
  --diagnostic-package "${P1_FULL_ARCHIVE:?exact recovered134436byte archive path}"
```

This records metadata/package/accounting gates and creates no runtime. Return
its small evidence to the parent reviewer before installation. Wrong/missing
versions, missing archives or stale paths block; preserve the error and output.

### 2. Lightweight donor route, only if independently qualified

First run without `--prepare` for a plan. After that exact donor inventory,
wheel/disk plan and permitted installation scope are reviewed, the **same**
invocation may use `--prepare --log "$P1_INSTALL_LOG"`; the log must be a new
direct `/workspace` sibling file. The helper checks exact3.12.3, creates a new
no-inheritance child, reuses only same-ABI GPU components, and caps new peak
allocation at3GiB with10GiB remaining. It never installs Torch/CUDA or calls a
scientific launcher. Source bytes/accounting are untouched.

```bash
# RECORD ONLY; no installation is authorized by this handoff.
"$P1_METADATA_PYTHON" -I -B \
  "$P1_CODE/research_runs/REDESIGN_HANDOFF_20261014/runtime_transition/isolated_training_runtime.py" \
  --code-revision "$P1_REV" --donor-python "$P1_DONOR_PYTHON" \
  --donor-report "$P1_PREFLIGHT_OUT/gpu_donor_inventory.json" \
  --environment "${P1_ENV:?new reviewed paper1-only environment path}"
```

No qualified donor means this helper cannot construct the environment. A full
fresh cp311/cp312 GPU closure needs actual hashed wheel inventory, a bounded
installer and storage review; a provisional20GiB ceiling is not an installation
estimate. Do not invoke the old GPU launcher to trigger its fallback.

### 3. Restore only source bytes after existing bindings/backup scope are cleared

This newly added helper avoids the old reconstruction script that also ran the
native diagnostic. Its default prints a metadata plan. A future authorized
restore adds `--restore --output "$P1_SOURCE_RESTORE_RECEIPT"`. It reads only
already-injected R2 bindings; no prompt, credential cache, new secret, List or
provider fallback. It verifies all18original file sizes/fullSHA and reuses valid
files. No source transform or target EEG access occurs.

```bash
# RECORD ONLY; default is offline metadata plan.
"$P1_ENV/bin/python" -I -B \
  "$P1_CODE/research_runs/REDESIGN_HANDOFF_20261014/runtime_transition/restore_source_cache_only.py" \
  --code-revision "$P1_REV" --data-dir "${P1_RAW_DATA:?new reviewed raw cache path}"
```

No current binding evidence means restoration remains blocked. Missing secrets
must not be recreated or requested under this plan.

### 4. ONE actual-runtime CPU input acceptance, later

Use only the prepared child and authentic full archive after independent review.
Never rerun the old diagnostic or delete the historical formal receipt. The
following acceptance has a different purpose: bind the restored runtime that
would consume training inputs. The output is a separately registered new path.

```bash
# RECORD ONLY; source acceptance has not been authorized on the new container.
timeout --signal=TERM --kill-after=10s 300s \
  "$P1_ENV/bin/python" -I -B \
  "$P1_CODE/research_runs/REDESIGN_HANDOFF_20261014/runtime_transition/accept_training_runtime_source.py" \
  --code-revision "$P1_REV" \
  --runtime-receipt "$P1_ENV/runtime_preparation.json" \
  --data-dir "$P1_RAW_DATA" \
  --output-dir "${P1_TRAINING_ACCEPT_OUT:?new registered runtime-source acceptance output}" \
  --old-work-root "$P1_OLD_REVIEW_ROOT" --diagnostic-package "$P1_FULL_ARCHIVE"
```

Expected complete scope is exit0 with
`SOURCE_NUMERICAL_ACCEPTANCE_MATCH_TRAINING_STILL_BLOCKED` and separate
`runtime_bound_acceptance.json`. All source original/per-trial/aggregate hashes
remain strict. The wrapper checks child isolation, actual package origins and
versions, one actual trainer-loader call and stable donor metadata. It does not
authorize GPU computation, budget transition, target restoration or model fitting.
Failure/pending evidence is returned without automatic retry.

## Do not confuse the plan with a runnable training release

Fresh full-GPU installation, authentic private backup retrieval/fit6 acceptance,
old-task accounting migration and full Dreyer object mapping remain unresolved
or unimplemented. This is stated explicitly, not hidden by successful software
tests. This handoff contains **no fit launcher, queue loop, Stop, Terminate,
Restart, SSH install, new API key or security restoration command**.

Current work stays in the code/evidence repository. Future dot operations use
only the existing HTTPS/browser path after the HOLD is lifted; the absolute
2026-10-16 09:54UTC authorization end is unchanged throughout recovery.
