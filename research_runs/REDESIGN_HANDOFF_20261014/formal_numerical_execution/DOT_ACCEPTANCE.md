# dot: one acceptance, no training, no server lifecycle action

Read OPERATION_AMENDMENT.md first. The delivery is a fixed numerical execution
implementation and fail-closed review gate, not a resumed scientific job.

## Existing paths and unique ownership

Use the already restored `/workspace/paper1-readonly-probe/data/bnci` originals.
Do not re-download/copy them. Keep `/workspace/paper1-source-diagnostic-c802`,
all earlier outputs, old failure/registration/accounting and paper2 intact. Use
the existing `/workspace/paper1-diagnostic-runtime` for the first CPU acceptance.
No credentials are requested, no packages are installed, and no GPU/model/target
calculation or network data request is performed by the acceptance script.

The pinned command below will fetch only Git code into the existing object store
and add a separate immutable REVIEW worktree. This is not a new scientific job,
cloned repository, recreated raw cache or replaced budget origin. A dirty old
checkout or an existing review/output directory must be reported, never reset or
deleted. The final command is added after code commit and public byte readback.

## Fixed source-only acceptance command

Execution code commit: `261f27757cad974a5c956e122766b9d8efa5d82b`.
All 23 changed files have been publicly read back byte-for-byte. dot alone runs
this command on the existing server, once. It performs CPU source acceptance
only and intentionally keeps the private-package/training-runtime gates pending.

```bash
set -euo pipefail
PAPER1_NUMERICS_REV=261f27757cad974a5c956e122766b9d8efa5d82b
PAPER1_OLD_CODE=/workspace/paper1-source-diagnostic-c802
PAPER1_REVIEW_CODE=/workspace/paper1-formal-numerics-review-261f2775
PAPER1_ACCEPT_OUT=/workspace/paper1-readonly-probe/formal-source-numerics-acceptance-run01
test -z "$(git -C "$PAPER1_OLD_CODE" status --porcelain)"
test ! -e "$PAPER1_REVIEW_CODE"
test ! -e "$PAPER1_ACCEPT_OUT"
test ! -e "$PAPER1_ACCEPT_OUT.worker.log"
test ! -e "$PAPER1_ACCEPT_OUT.exit-code"
git -C "$PAPER1_OLD_CODE" fetch origin "$PAPER1_NUMERICS_REV"
git -C "$PAPER1_OLD_CODE" worktree add --detach "$PAPER1_REVIEW_CODE" "$PAPER1_NUMERICS_REV"
set +e
timeout --signal=TERM --kill-after=10s 300s \
  /workspace/paper1-diagnostic-runtime/bin/python \
  "$PAPER1_REVIEW_CODE/research_runs/REDESIGN_HANDOFF_20261014/formal_numerical_execution/accept_source_numerics.py" \
  --code-revision "$PAPER1_NUMERICS_REV" \
  --data-dir /workspace/paper1-readonly-probe/data \
  --output-dir "$PAPER1_ACCEPT_OUT" \
  --old-work-root /workspace/mi-eeg-cloud \
  --runtime-role diagnostic > "$PAPER1_ACCEPT_OUT.worker.log" 2>&1
PAPER1_ACCEPT_EXIT=$?
set -e
printf '%s\n' "$PAPER1_ACCEPT_EXIT" > "$PAPER1_ACCEPT_OUT.exit-code"
cat "$PAPER1_ACCEPT_OUT.exit-code"
if test -f "$PAPER1_ACCEPT_OUT/formal_source_acceptance.json"; then
  cat "$PAPER1_ACCEPT_OUT/formal_source_acceptance.json"
else
  tail -n 40 "$PAPER1_ACCEPT_OUT.worker.log"
fi
```

Preserve the output directory, worker log and outer exit-code file, compute their
SHA manifest and return the complete small evidence to the parent task for
independent readback. Do not delete a pending/failing directory and rerun. The
private archive and actual training-runtime acceptance remain separate work,
using their reviewed existing paths rather than guessed paths or new credentials.

## Expected receipts

- Diagnostic runtime, no private archive: exit 3,
  `SOURCE_NUMERICS_MATCH_PRIVATE_PACKAGE_OR_TRAINING_RUNTIME_PENDING`, complete
  exact source hashes but unaccepted training runtime/private package.
- Verified private archive plus the existing exact cu128 training runtime:
  `--runtime-role training` only imports the actual trainer/validator loader and
  runs that loader on CPU. Exit 0,
  `SOURCE_NUMERICAL_ACCEPTANCE_MATCH_TRAINING_STILL_BLOCKED`.
- Any source/file/runtime/policy/accounting mismatch is a failure; preserve output
  and stderr. Do not retry with new states, tolerances, arrays or directories.

Both successful scopes keep training_authorization=false. An exit 3 here is an
intentional pending gate, not evidence of a failed source hash check.

## Private archive

The complete 134436-byte archive is not accessible to this Codex task from its
Library ID. Provide its already retrieved private file path to
`--diagnostic-package`; never upload it into GitHub. The strict auditor checks
the named package SHA, 12 safe members, file inventories, frozen implementation,
native audit, 2592 unique ordered CSV identities, exact mu trial/aggregate hashes,
retained native anomalies, stage-anchor declarations and actual zero exit. The
software does not claim independent signal recomputation from archived hashes.
Archive layout must be checked against the real file; a legitimate unexpected
layout still blocks until reviewed. No payload or scripts are extracted/executed.

## Training runtime and old records

After the first diagnostic receipt, use the existing confirmed training Python
only when its path/runtime has been reviewed; do not guess a path or install a
second environment. Change runtime_role to training and supply the named archive,
with a separately registered acceptance output directory. A repeated acceptance
is review of the actual runtime, not a scientific fit or target adaptation.

`--old-work-root /workspace/mi-eeg-cloud` observes old non-secret accounting when
available. Wrong job/invalid revision/symlink changes fail; an inaccessible old
registration is reported as unobserved, never reconstructed. Present records are
hashed before and after and must remain identical. This does not prove that the
new Pod is the old machine or authorize resumption.

## Still required after source acceptance

Do not invoke LAUNCH_ON_GPU.sh, cloud_supervisor or model fitting. Source acceptance
cannot create numerical_execution_review.json, data_prepare PASS, a public freeze
or a recovery transition. Actual archive audit and training-runtime source
acceptance need review before the separate source review record is issued.

Target mapping/restoration and 174 raw SHA/85 people/6800 event×band exact hashes
remain pending. Old machine/registration/checkpoint/budget transition, current
GPU/runtime and verified private/public backups remain independent gates. The
existing launcher still rejects a different revision/machine; no implicit
cross-revision resume or budget reset is implemented. dot must keep the shared
Pod running for the two tasks and issue no Stop/Terminate under this handoff.
