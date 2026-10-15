# Paper 1 recovery preparation — 15 October 2026

**HOLD: code and acceptance preparation only. No Pod operation, installation,
source/target EEG read or model execution was performed in this update.** Dot
is the sole Pod operator. Paper 2 has absolute priority. Its completed fit7 and
independent/R2 backup are reported by the author in the current instruction;
this task neither re-audits nor re-executes it and does not dispatch fit8.

This is an operational supplement to handoff
`ec7ad35ab7460feb2425055f6117cc556966f22b` and code
`23bbe5e4d4ab0e2f9b39e955a057cc445ddb0d08`. It preserves their scientific
implementation and audited source archives. The new patch is required for the
priority-aware helper interfaces; do not mix a new helper with an old checksum
or pretend the old code already enforced the new scheduling gate.

## What is established, and what remains blocked

| Item | Actual evidence and boundary |
|---|---|
| Current container | Author reports Pod52ivinpjwv947i/container a7d3f0e408a4, A4500/driver580.159.04, 50GiB overlay without a persistent volume. No live observation here; the rebuild and stale-path warnings remain. |
| Paper 2 | Author reports Python3.11.16/91 locked packages at `/workspace/.venvs/paper2-gpu`. That environment and global packages must not be modified. No cp311 Torch/Triton/NumPy/SciPy inheritance into Paper 1. |
| cp312 candidate | All **17 GPU distribution versions** in the supplied transcription are consistent with a Python3.12.3/cu128 candidate. `/usr/local/lib/python3.12/dist-packages` is eligible only under the helper's **measured** interpreter prefixes and same-minor path checks. Its presence does not prove measured prefixes. |
| Original donor JSON | Author reports2390bytes/SHA256 `9a1224dc93b83c476d9012618adb2d9934fefa7478e5ac6aa92842add6ead159`, verified off-host by dot. These original bytes are not attached here. The readable transcription is recorded as such; no recreated JSON is represented as that original. |
| Still-needed donor evidence | Fixed-helper SHA, prefixes/base executable/cache tag, each METADATA/RECORD hash, eligible component paths, required entry-module hashes, existing venv/ensurepip availability and fresh free-space observation. Metadata equality does not prove all native payload bytes or actual training imports. |
| Historical task | Seven exact public job records were recovered at `d612f0cc2bcca045ff1304bc95a87df76bfd4a82` using connected GitHub reads; byte sizes, SHA256 and Git blob identities were checked. Old `array_hashes` failure and zero-fit history are retained. |
| Private accounting | Original external registration, budget origin/ledger, optimizer/RNG/update-intent inventory, committed recovery HEAD and cumulative actual costs/GPU hours are **not recovered**. Historical quote0.34/hour is not today's quote. Zero fits is not zero cost. |
| R2 access | This investigation made one root delimiter LIST and two HEAD requests using existing bindings; all returned401. No object body GET, target read, PUT/DELETE, credential change or retry. This does not establish backup loss. One HEAD was for the protocol-defined recovery key, whose prior existence is not established; one used a genuine source mapping key. |
| Dreyer public inventory | All174 unique frozen EDF paths/sizes/SHA match saved provider provenance:2515343396bytes/87persons,85 retained/6800events. The JSON audit includes every row. CC BY4.0 is supported by saved provider and original dataset metadata. No target EEG was opened. |
| Dreyer private mapping | All174 actual R2 object keys remain unknown (`null`), not inferred from filenames. Full192-object source+target mapping, actual object identities and later512Hz input acceptance remain gates. |
| Source numerical evidence | Reuse the already independently audited134436-byte full diagnostic and12299-byte formal acceptance archives. No old diagnostic or acceptance was rerun. A diagnostic-role pass does not become a training-runtime pass. |

See [CURRENT_CONTEXT.json](CURRENT_CONTEXT.json),
[old-task evidence index](metadata/old_task_accounting_recovery.json),
[complete Dreyer metadata audit](metadata/dreyer_public_metadata_audit.md), and
[donor transcription](runtime/donor_metadata_transcript.json).

## Deadline-only operational amendment

The author's current explicit instruction and supplied transcript are preserved
in [the appended deadline record](deadline_amendment/DEADLINE_ONLY_OPERATION_AMENDMENT.md).
Only the calendar execution deadline becomes **2026-10-16 09:54 UTC**. The old
receipt and start/expiry remain unchanged. The existing ceilings remain **$10
total, $2 non-GPU reserve, 8 cumulative GPU hours, 26 neural fits, 34440 optimizer
updates and $0.75/hour maximum**. Neither unknown prior costs nor rebuilt
directories start a new allowance. Current spending, remaining budget, account
identity and checkpoint ownership are not fabricated.

The production budget validator is deliberately unchanged and still blocks an
expired/mismatched old receipt. This sourced amendment is not a replacement
`budget_authorization.json` or a fit launcher. A later reviewed transition must
actually enforce it against authentic cumulative accounting.

## Minimal isolation and disk rules

The candidate route uses **the measured cp312 donor only**. A fresh, separate
Python3.12.3 venv with `include-system-site-packages = false` may eventually link
only allowlisted same-ABI GPU components and their dist-info. It inherits no
whole site, NumPy/SciPy, generic startup hook, or Paper 2 package. No duplicate
CUDA/Torch download is permitted. Existing `venv` and `ensurepip` must already
be available; missing tooling blocks this route, with no apt/global fallback.

All committed Paper 1 requirements remain unchanged: braindecode1.5.1,
NumPy2.3.5, SciPy1.17.0, pandas2.2.3, mne1.13.2, scikit-learn1.8.0,
skorch1.4.0, einops0.8.2, h5py3.16.0, joblib1.5.3, threadpoolctl3.6.0,
boto3 1.40.61 and pytest9.1.1, with Torch/torchaudio2.8.0+cu128. Resolved
non-GPU transitive wheels must have recorded URL/SHA and bounded compressed and
expanded sizes. This is a reproducible restoration receipt, not proof of
byte-for-byte equality to unobserved historical transitive packages.

For any future permitted runtime preparation, dot must issue a **fresh,
operation-specific slot lasting at most30minutes**, ending no later than the
existing authorization deadline, after checking Paper 2 has spare capacity.
The committed `PLAN_ONLY` template cannot grant a slot. Revocation, replacement,
expiry or changed bytes invalidate the slot. The helper checks before each own
download and while monitoring its own installer; cancellation terminates only
its own installer process group. It never preempts Paper 2 or controls the Pod.

Let `C = min(3GiB, dot.max_new_bytes)` and
`F = max(10GiB, dot.min_free_bytes) + dot.paper2_reserve_bytes`. Before creation,
actual free space on the destination filesystem must be at least `C + F`;
throughout preparation it must remain at least `F`, while new allocation stays
below `C`. Thus the usual cap requires **13GiB plus dot's explicit Paper 2
reserve**, not merely a50GiB capacity label. Failed directories/logs are
preserved, not deleted for retry. Source/target raw files, tensors, checkout,
checkpoints and backup staging need separate space accounting before any later
restoration or fit; this runtime bound does not establish full-job capacity.

The actual-runtime CPU source wrapper uses a separate `source_cpu_acceptance`
slot, exact runtime imports and the audited private full-package binding. It
creates no model/CUDA tensor and reads no target EEG. Its slot is checked before
and after the CPU calculation and immediately before the bound receipt; this
is **not continuous mid-filter cancellation**. Dot must reserve the bounded CPU
window and use the documented outer timeout. The wrapper still cannot authorize
a fit, establish GPU arithmetic, approve old accounting, or restore the target.

## Next action and scientific boundaries

[DOT_NEXT.md](DOT_NEXT.md) gives the fixed, metadata-only next handoff and later
conditional plan/CPU acceptance syntax. **It is not permission to operate the
Pod in this turn, install, restore EEG or launch training.** Return the small
full-helper metadata report for review first. Existing authorised metadata
access may separately recover missing accounting and genuine object mappings;
do not request new secrets or infer remote absence from local loss/401.

All scientific files are unchanged: uniform explicit SOS initialization at250Hz
and512Hz, frozen hashes and strict comparisons, Broad/shared, fixed20/mean-loss/
mean-rank, 19 channels, seeds, source validation groups2/2/2/3, target eval-only
BatchNorm and no target normalization/selection/fitting. Dreyer remains
exploratory because prior exposure is unconfirmed. No native failure, negative
result, Q1–Q16 result, manuscript, main branch or publication tag was altered.

Training remains blocked until actual runtime/source acceptance, independent
review, authentic old task/accounting/checkpoint/backup reconciliation, full
target mapping/restoration and a reviewed execution transition all pass.
