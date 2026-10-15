# Next operation: reviewed, bounded formal runtime preparation

**Metadata and plan-only are complete; do not repeat them. No preparation or
installation has been executed by this assistant.** Dot remains the sole Pod
operator, and Paper 2's environment/files and review work retain priority.
The author reports18/18 Paper 2 fits executed/exported, with accepted still7;
this task does not accept the remaining11 or touch that environment.

Independent metadata audit:8589-byte archive/SHA
`7a652a96eded108155188a366d4cf4d930e6ea404566cf44e9773ba0ce6f69d0`.
Independent actual plan audit:6463-byte archive/SHA
`bca300252a44997e46f102e689c6d1a10f16c91d079f8ed4eb3752acf68ad526`.
The plan used the original direct helper; no later outer controller or
continuous monitoring is retroactively attributed to that execution.
See `../metadata_acceptance/PLAN_RUN01_INDEPENDENT_REVIEW.json`.

## Before dot can execute this preparation

1. Dot's parent independently reviews this controller/policy, the accepted
   plan and cost handling, and saves an explicit review record based on
   `dot_parent_review.PLAN_ONLY.json`. That template is invalid and must not
   be submitted unchanged or automatically turned into an approval. The
   required status is `DOT_PARENT_RUNTIME_PREPARATION_REVIEW_APPROVED`, issuer
   `dot_parent`, with real UTC review/expiry times and actual review notes.
   The record binds the exact plan/donor/helper/child and explicitly reviews
   the bounded binary-wheel resolver policy; it does **not** assert an unseen
   transitive wheel closure has already been reviewed. Unknown past costs stay
   unknown. Cost-handling review does not prove a balance, old ledger or budget
   gate, and cannot expand or reset the original allowance. If the parent cannot
   justify the bounded preparation under existing authorization, it must not
   issue the record. No new resource purchase or budget is requested here.
2. After that review, dot checks actual Paper 2 noninterference and issues a
   NEW `runtime_preparation` slot. It must be issued after the review and actual
   plan completion, with a fresh real reserve. Neither archived slot can be
   extended or reused. The old plan SHA17edfc14... is explicitly rejected; the
   old metadata slot is the wrong operation and too early. The slot/review must
   end by2026-10-16 09:54UTC. The controller creates neither record nor credential.
3. The actual accepted plan and donor files must still match the exact lengths
   and SHA below. Keep the observed1efe checkout clean; no clone/reset/re-init
   or edits inside it. Obtain only the small standalone controller at the
   immutable public pin in `CONTROLLER_PIN.md`, validate its SHA, and keep it
   outside both environments/checkout. The proposed child must remain absent.

## Exact preparation invocation

The following command is for dot **only after** the two reviews above. The
assistant has not run it. These path variables contain no credentials.
`P1_ACCEPTED_PLAN` must be the actual25128-byte stdout from the accepted plan,
not the tarball or a reconstructed JSON. The donor path below was reported in
the03:14 package; the controller checks its continued existence and SHA.

```bash
(
set -eu
: "${P1_PREP_CONTROLLER:?standalone controller verified against CONTROLLER_PIN.md}"
: "${P1_ACCEPTED_PLAN:?actual25128-byte plan.stdout.json from the accepted plan}"
: "${P1_PARENT_REVIEW:?new actual dot_parent preparation-review record}"
: "${P1_NEW_SLOT:?NEW dot runtime_preparation slot issued AFTER that review}"
/usr/bin/python3 -I -B "$P1_PREP_CONTROLLER" \
  --code-dir /workspace/paper1-metadata-code-1efe9d1 \
  --donor-report /workspace/paper1-cp312-metadata-20261015-run01/gpu_donor_inventory.json \
  --accepted-plan "$P1_ACCEPTED_PLAN" \
  --review-record "$P1_PARENT_REVIEW" --priority-receipt "$P1_NEW_SLOT" \
  --output /workspace/paper1-runtime-prepare-run01.stdout.json \
  --log /workspace/paper1-runtime-prepare-run01.stderr.log \
  --install-log /workspace/paper1-runtime-prepare-run01.install.log
)
```

All four evidence paths (including stdout name plus `.dispatch.json`) must be
new direct `/workspace` siblings. The environment is fixed by the accepted plan
to `/workspace/paper1-training-runtime-cp312-run01`; an existing/partial child
is retained and blocks this operation. Do not delete or rename it to force a
retry. The controller verifies `/usr/bin/python3` through the unchanged helper,
exact donor/plan identities, committed requirements and fresh metadata before
creating a new isolated cp312 child. It never borrows Paper 2's cp311 packages.

Bound identities:

| Item | SHA256 |
|---|---|
| Actual25128-byte plan stdout | `e4852d1e2517abc69464c22e69658c2618d8e3950184fa40eb4c8a2af6ce5a0c` |
| Actual22450-byte donor inventory | `3a83a9cf93cca3e9813056645bc73f26a9429ee6f1f7bc06f2ae78a1c36471b1` |
| Fixed1efe inner runtime helper | `cdd8c2d47fb6e1653e8b5c2eb48de6483d4dd57a0af392f2c1495669e3c0cd9e` |
| Unchanged frozen requirements | `7322d4f85f25064ef8c29efa502c67417fc9b8a0d3297692263c1e618804769a` |

## Limits and required return evidence

The child plus outer evidence together are capped at3GiB or the tighter slot
bound. Keep at least10GiB plus the actual dot reserve, no less than the accepted
5GiB reserve. Full-cap initial free space is at least18GiB; archived free space
is not a present guarantee. Checks are periodic rather than an atomic quota.
No apt/global pip, whole-site inheritance, cp311 package reuse, second CUDA
installation, numerical-thread changes, EEG read, model or fit is permitted.

The same parent-review identity and slot are rechecked every0.25seconds and
after the helper. Maximum duration is20minutes or the tighter review/slot bound;
expiry does not extend either clock. Cleanup first interrupts the own helper
so its exception handler cleans its own installer sessions. Any fallback can
signal only cached, matching PID/starttime descendants, never Paper 2 or a
process name. Failed outputs and partial environments are retained.

On success, expect outer status
`ISOLATED_PREPARATION_VERIFIED_IMPORT_SOURCE_STILL_PENDING` and inner status
`ISOLATED_RUNTIME_PREPARED_IMPORT_AND_SOURCE_ACCEPTANCE_PENDING`. Return the
outer stdout/stderr/dispatch, inner install log, child `runtime_preparation.json`,
`runtime_plan.json`, `wheel-resolution.json`, GPU constraints and resolved
wheel hash list, plus actual path/size/SHA evidence for independent review.
Do not send secrets, environment dumps, or wheel/raw-EEG binaries to GitHub.
The13-pin public PyPI metadata index is only an initial source check, not the
actual resolved closure or downloaded-byte verification. The actual resolution
and retained authenticated wheels must be checked from this operation.

Successful preparation proves neither real training imports/GPU arithmetic,
strict source hashes, target inputs, old accounting/checkpoints/backups nor fit
authorization. Those remain separate gates. The old source diagnostic and
diagnostic-runtime acceptance must not be repeated. A later single actual-
runtime source acceptance is scheduled only after review of this output.

The official174 EDF transport amendment is separately proposed and offline-only
today; do not download a target in this preparation. The old $10/cumulative
8GPU-hour/fit/update caps remain, with actual old expenditure unknown. The failed
balance-permission action is stopped; historical$2.51 is not a current balance,
an attributed Paper 1 cost, or permission to retry another route.
