# Repaired runtime: separate source restoration and actual CPU acceptance

This is a code/protocol delivery. No Pod operation, installation, wheel fetch,
EEG access, diagnostic, model or fit was performed here. Dot is the sole Pod
operator. The author's latest instruction reports Paper 2 accepted 18/18;
that independent task continues and is not re-audited or modified here.
Keep the Pod running; neither script stops, terminates or restarts it.

## What this independent audit establishes

The 442155-byte repair archive SHA256 is
`7ebd6080181ec3bb5d2c9faf74d754af68c0ea4eea48978467df713e8465f8a1`.
All 30 payloads plus the manifest passed safe-path, complete length/SHA and
cross-record review. The recorded unique repair at 04:25:38.127630–04:26:22.935336
UTC on 15 October 2026 exited 0. Its fixed 461d079e code, real review/slot,
single journal, offline 79-wheel install and pip check agree. Recorded 97
distributions partition into 79 resolved wheels, 17 GPU donor distributions
and seed pip. Both included manpages match their exact frozen member bytes.

The distinct 6554-byte repair receipt SHA is
`0e487c7c8dcc83006681c8bdb066254da4184d49ab9f6ce96a07ad53d7cf092b`;
the 22896-byte journal SHA is
`db82e716e22ce7bcf48e6d7908f279b4b8a5ae9ececbd67714ec083d6aa89b0d`.
The original preparation receipt remains absent. No old preparation success
was fabricated. See [the independent audit](INDEPENDENT_REPAIR_AUDIT.json).

The package contains no wheel binaries, installed scientific payload inventory
or live Pod state. Cached-wheel checks are authenticated controller observations,
not independent offline rehashes of unavailable binaries. New postflight
hash records agree with the old failure logs; those old log bodies are not
repeated in this new archive. The earlier original failure archive was also
verified offline. These boundaries do not invalidate the successful repair;
they prevent metadata success from being misreported as runtime acceptance.

## A real accounting decision now precedes any next CPU operation

The new official-console transcription shows 19h29m current Pod uptime.
CPU-only work on a paid GPU allocation still consumes allocation hours. The
original eight-hour cap cannot be certified from that observation or bypassed
with a claim of zero fits. Read
[the concrete conservative accounting proposal](ACCOUNTING_REVIEW_0449UTC.md).

Before either future command below, the parent needs:

1. A complete, refreshed dollar upper bound covering the relevant account/time
   scope, uncertainty and the proposed increment, with the original $10 total
   and $2 reserve intact. The 04:51 examples are conditional arithmetic, not
   observed Paper 1 expense or remaining funds. Do not query another route,
   assume a top-up, or fill historical costs/checkpoints with zero.
2. A real author-approved **single, finite CPU recovery exception** to the
   possibly exhausted allocation-hour limit: at most 30 minutes in total,
   or a smaller explicitly approved affordable window. This preserves unknown
   historical hours and the old cap/breach record; it grants no fit hours.
   Without it, the committed templates fail closed. The current keep-running
   instruction is not silently converted to this new approval.
3. A parent review for each exact operation, followed by its own fresh dot slot.
   Both stages must share the same actual grant SHA and absolute recovery
   window, no longer than 30 minutes. A second slot is not a second allowance.

The required fields `bounded_cpu_recovery_exception_authorized` and
`covered_dollar_upper_bound_reviewed` remain false in both templates. The
parent supplies the real author approval provenance as `cpu_recovery_grant_sha256`
and real window start/end only after review. A syntactically valid hash does
not prove author approval or account completeness. Both reviews and slots
must end inside that window and by 2026-10-16 09:54:00 UTC.

The original GPU-fit budget validator is unchanged and is **not passed by this
adapter**. Its old identity/accounting/checkpoint/fit/update/backup gates remain
independent. There is no budget reset, new purchase or automatic retry.

## Small fixed delivery, same existing code and runtime

Use the public commit and SHA identities in `ACCEPTANCE_PIN.md`. Obtain only
the three small execution files plus invalid review/slot templates; do not
clone another full repository or create/install an environment. The existing
checkout must still be clean at
`1efe9d1ba2ab8671ad1bf76c360e067fb63fd7ac`:
`/workspace/paper1-metadata-code-1efe9d1`. Its existence is checked, not assumed.
Do not reset it or alter original frozen files.

The same repaired child is
`/workspace/paper1-training-runtime-cp312-run01`. The adapter authenticates its
actual new receipt, journal, five configuration files and two manpages against
the original repair package, checks actual 97 distributions and GPU link
mapping, and re-observes donor metadata. No installation, resolver, CUDA test
or second environment is introduced. Paper 2's cp311 environment/global packages
and numerical threads remain untouched.

## Step A — restore the 18 source originals, with a new source-only slot

The current container has **not** been observed to contain the old 18 MAT files.
The source manifest is unchanged: 18 files, **779873919 bytes**, SHA256
`e553d65cd86e5309e077ccfea21a9bee6020c5d9d5040de12089c2b859770b86`.
Its full per-file official URLs, sizes and SHA values are in the clean fixed
checkout under `official_source_diagnostic/source_official_manifest.json`.

This appended operational amendment permits reuse of those exact source bytes
for actual-runtime acceptance. The manifest's old diagnostic-purpose label
is retained as history; it is not an authorization by itself. New code reuses
only the unchanged downloader/manifest/verifier primitives, not the old
diagnostic main or its old-container partial/failure prerequisites. It makes
no R2 request, key guess, credential or R2-success claim.

Parent review uses `source_restore_review.PLAN_ONLY.json`, operation
`source_raw_restore`, followed by a **new source_raw_restore slot** based on
`source_restore_slot.PLAN_ONLY.json`. This new operation exists only in the
local appended gate; old metadata/preparation/source slots cannot authorize it.
Normal TLS and exact direct origin or the previously frozen single actual
origin Location to `lampx.tugraz.at` are required. No mirror substitution,
unverified redirect, size/SHA tolerance or repeated download is allowed.

After those actual gates, dot runs once (fixed delivery revision supplied by
`ACCEPTANCE_PIN.md`; these variables contain public identities/pathnames):

```bash
(
set -eu
: "${P1_ACCEPT_DIR:?verified small execution bundle from ACCEPTANCE_PIN.md}"
: "${P1_ACCEPT_REVISION:?fixed delivery code commit from ACCEPTANCE_PIN.md}"
: "${P1_SOURCE_RESTORE_REVIEW:?actual new parent source_raw_restore review}"
: "${P1_SOURCE_RESTORE_SLOT:?new dot source_raw_restore slot after review}"
/usr/bin/python3 -I -B "$P1_ACCEPT_DIR/restore_source_once.py" \
  --delivery-revision "$P1_ACCEPT_REVISION" \
  --code-dir /workspace/paper1-metadata-code-1efe9d1 \
  --data-dir /workspace/paper1-source-recovery-run01 \
  --review-record "$P1_SOURCE_RESTORE_REVIEW" \
  --priority-receipt "$P1_SOURCE_RESTORE_SLOT"
)
```

All present files are checked before the first GET. Missing files alone are
downloaded; a wrong hash, unknown file/partial, symlink or previous attempt
blocks and is preserved. A one-shot exclusive source journal precedes transfer.
The own supervisor checks slot/resource/code identities every 0.2 seconds;
network reads check at most 1 MiB at a time. Timeout/revocation terminates only
its own newly started worker group and leaves the Pod running. There is no
automatic retry or removal/renaming of partial evidence.

Source-owned allocation is at most 1 GiB, and retained runtime ownership plus
source/next-write reservation jointly remain below the original tighter
3 GiB/slot cap. Original runtime ownership is carried from 869490688 bytes,
increased by any actual child growth over historical environment du 869425152;
donor symlink targets are not counted as duplicate local CUDA storage. Free
space remains at least 10 GiB plus the actual dot reserve, at least 5 GiB.
These are sampled controls, not a kernel quota or real-time GPU monitoring.
The code does not promise full-job disk capacity or free paid hours.

Success is only `SOURCE18_EXACT_BYTES_RESTORED_NUMERICAL_ACCEPTANCE_PENDING`.
Keep `source_restore_run01.json`, `source_restore_run01.journal.jsonl` and
`source_restore_run01.log` under `/workspace/paper1-source-recovery-run01`,
with the 18 raw originals in `bnci/`. Return command/start/end/exit and small
metadata/hashes for parent review; no MAT/wheel binary goes to GitHub. A
supervisor failure/timeout or failed journal phase overrides a partial child
receipt. Do not rerun a consumed source restore.

## Step B — one actual repaired-runtime CPU source acceptance

Parent independently reviews Step A's complete successful record and actual
receipt SHA, then completes `source_acceptance_review.PLAN_ONLY.json` using
that SHA as `source_restore_receipt_sha256`. Its real review time must follow
source restoration completion. Dot issues a **new source_cpu_acceptance slot**
within the **same author-approved recovery window**, not an extended one.

The two historical original evidence archives must already be available at
genuine local paths (no guessed R2 key or old local path assumption):

| Archive | Bytes | SHA256 |
|---|---:|---|
| Full fixed-zi diagnostic evidence | 134436 | `2871f422755bf5d0b939d0db59fc41547b192d6c939db1a6a13b97a91ba49ae9` |
| Formal diagnostic-runtime acceptance evidence | 12299 | `a4c6c3f7beadf6ce0c927c6e4b9d20b6d37ff3bc2c033ad4b4fd836ca38a6b0d` |

These original bytes may be restored through the already authorized existing
HTTPS/browser/off-host route and verified; no new secret or security setup is
needed. Missing originals block this acceptance rather than creating a new
diagnostic. The former diagnostic reports are historical provenance; the old
formal report intentionally had training/private-package gates pending. It
does not become a new-runtime PASS. The full evidence is audited as metadata
by the existing frozen source acceptor; no archived script is executed.

Use this **outer process-group timeout**; the synchronous frozen filter has
pre/post checks, not continuous in-filter cancellation. The adapter also
requires at least its reviewed wall limit plus ten seconds before slot expiry.
This fixed adapter requires `maximum_wall_seconds=300` and at least 310 seconds
before slot expiry; it rejects a tighter review rather than silently using a
longer watchdog. Retain the outer exit, including 124/137 on timeout. `noclobber` protects
the new direct-workspace log. The command does not consult the unobserved old
work root or invent it as accessible.

```bash
(
set -eu
set -C
: "${P1_ACCEPT_DIR:?verified small execution bundle}"
: "${P1_ACCEPT_REVISION:?fixed delivery code commit}"
: "${P1_REPAIR_ARCHIVE:?actual original 442155-byte successful repair archive}"
: "${P1_FULL_DIAGNOSTIC_ARCHIVE:?actual original 134436-byte full evidence archive}"
: "${P1_FORMAL_DIAGNOSTIC_ARCHIVE:?actual original 12299-byte formal evidence archive}"
: "${P1_SOURCE_ACCEPT_REVIEW:?new actual parent source_cpu_acceptance review}"
: "${P1_SOURCE_ACCEPT_SLOT:?new dot source_cpu_acceptance slot after review}"
timeout --signal=TERM --kill-after=5s 300s \
  /workspace/paper1-training-runtime-cp312-run01/bin/python -I -B \
  "$P1_ACCEPT_DIR/accept_repaired_runtime_source.py" \
  --acceptance-revision "$P1_ACCEPT_REVISION" \
  --code-dir /workspace/paper1-metadata-code-1efe9d1 \
  --repair-archive "$P1_REPAIR_ARCHIVE" \
  --runtime-receipt /workspace/paper1-training-runtime-cp312-run01/runtime_repair_run01.json \
  --diagnostic-package "$P1_FULL_DIAGNOSTIC_ARCHIVE" \
  --formal-acceptance-package "$P1_FORMAL_DIAGNOSTIC_ARCHIVE" \
  --source-restore-receipt /workspace/paper1-source-recovery-run01/source_restore_run01.json \
  --data-dir /workspace/paper1-source-recovery-run01 \
  --output-dir /workspace/paper1-repaired-source-acceptance-run01 \
  --review-record "$P1_SOURCE_ACCEPT_REVIEW" \
  --priority-receipt "$P1_SOURCE_ACCEPT_SLOT" \
  --log-file /workspace/paper1-repaired-source-acceptance-run01.log \
  > /workspace/paper1-repaired-source-acceptance-run01.log 2>&1
)
```

The output and adjacent `.attempt.json` must be absent, and the log new. After
all static/byte gates, the exclusive attempt claim precedes scientific imports.
The adapter checks all 18 actual files before imports, then calls only the
old import checker using an explicitly named, transient in-memory binding
view from the authenticated repair/donor. It does **not** call the old
preparation wrapper or write `runtime_preparation.json`. It next calls the
original formal acceptor once with `runtime_role=training`, which uses the
same loader actually imported by training/validation consumers on CPU.

The frozen strict gate remains 18 files/108 runs/2592 trials, including all
trial identities and all three complete array hashes, with no element edits
or tolerance. NumPy 2.3.5 / SciPy 1.17.0, the uniform fixed SOS-state policy,
19 channels, seeds, Broad/shared and duration-selection rules are unchanged.
The adapter creates no model, CUDA tensor, serialized EEG arrays or prediction.
Donor/repair/source/code identities are rechecked before the final bound receipt.
Runtime plus all source recovery evidence, new output/log, original archives
and carried baseline remain subject to the original 3 GiB/slot bound and free
floor. Periodic source-restore checks and synchronous acceptance boundaries
must not be confused with continuous monitoring of every native computation.

Expected files are `formal_source_acceptance.json` and
`repaired_runtime_bound_acceptance.json` in the new output, plus the adjacent
attempt claim and log. Expected final status is
`REPAIRED_ACTUAL_TRAINING_RUNTIME_SOURCE_MATCH_OTHER_GATES_PENDING`.
Return their complete bytes/hashes, real command/start/end/exit, original
repair/old-failure preservation and fresh resource snapshots for review.

## What success still does not grant

Even successful runtime imports and strict source equality do not authorize a
GPU fit. Actual CUDA arithmetic, historical registration/account identity,
allocation-cost/fit-ledger/checkpoint transitions, authentic backup ownership
and readback, target transport/mapping/header/event/QC/input hashes and the
reviewed execution amendment remain independent. Unknown checkpoint/counter
state is not zero; an inaccessible old path is not proof no remote backup exists.

The existing complete [174-object official EDF proposal](../official_edf_transport/README.md)
and [accounting proposal](ACCOUNTING_REVIEW_0449UTC.md) remain available for
review. The target transport is not invoked by either new script or slot;
it must retain frozen same-byte EDF/CC BY 4.0 identities and separate licensed
transport/192-input routing gates, never pretend to be the R2-only importer.
No target data, outcome, fitting, BatchNorm update or new experiment is used
here. Dreyer remains exploratory; original failures/negative results and
Q1–Q16/old submissions/publication history remain untouched.
