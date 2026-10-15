# Dot: fixed174 EDF restoration only — ready for one execution

This is the current executable continuation-preparation handoff. Do not rerun
the completed continuity observation, source restoration, runtime repair,
diagnostic or actual-runtime CPU acceptance. Dot is the sole Pod operator;
this code-delivery task has performed none of those operations.

Use the raw-restoration-only fixed commit, source hashes and small-bundle fetch command in
[EXECUTION_PIN.md](EXECUTION_PIN.md). The fetch retrieves public source and
metadata only; it does not clone a project, install packages or run EEG work.
Keep `/workspace/paper1-metadata-code-1efe9d1` and its exact97-package runtime
unchanged. The new code directory is a small operational delivery, not a new
scientific project or job registration.

## 1. Actual174-object restoration, independently of missing old fit history

Parent reviews the fixed code and actual resources, then issues a real record
from `parent_raw_review.PLAN_ONLY.json`. Dot issues a **new**
`target_raw_restore` slot from `raw_slot.PLAN_ONLY.json`. The templates are
unissued and cannot pass. Do not reuse the consumed08:09 metadata slot. Set
actual UTC times, reviewed commit, genuine issuer/status and only those
noninterference/resource assertions actually checked. The exact approved
parent status is `DOT_PARENT_TARGET_RAW_RESTORE_APPROVED`; issuer is
`dot_parent`. The real slot status is `DOT_OPERATION_SLOT_GRANTED`, issuer
`dot`, operation `target_raw_restore`. Required affirmative fields are
enumerated in `parent_review()` and `validate_slot()`; all fit/GPU/new-resource/
credential/automatic-retry flags remain false.

The new target allocation is3GiB, independent of retained source/runtime
allocation. Retain10GiB free plus actual Paper2 reserve>=5GiB and enough room
for all missing target bytes. Parent wall cap<=1200seconds; the new slot must
follow review, cover the full bounded command and expire within30minutes and
before the unchanged deadline. The user reports the36-item Paper2 queue
finished; dot must still check actual audit/backup/CPU/storage impact. No
GPU-idle or current free-space assertion is manufactured by this handoff.
No cost, balance or billing review is required.

After the actual review and slot are issued, dot sets these nonsecret paths:

```text
P1_TARGET_REVISION = fixed code commit in EXECUTION_PIN.md
P1_TARGET_CODE = /workspace/paper1-official-transition-code-run01
P1_TARGET_REVIEW = actual new parent-approval JSON
P1_TARGET_SLOT = actual new target_raw_restore slot JSON
P1_TARGET_DISPATCH = existing NEW dispatch directory for this operation
```

Then run exactly once (the outer record is written from the **actual** process
exit, including failure; it is not an approval or synthetic success):

```bash
(
set -euC
: "${P1_TARGET_REVISION:?fixed code commit from EXECUTION_PIN.md}"
: "${P1_TARGET_REVIEW:?genuine new parent raw-restoration approval}"
: "${P1_TARGET_SLOT:?genuine new target_raw_restore slot}"
: "${P1_TARGET_DISPATCH:?actual dispatch directory outside runtime and raw cache}"
P1_TARGET_CODE=/workspace/paper1-official-transition-code-run01
test -d "$P1_TARGET_DISPATCH"
test ! -e "$P1_TARGET_DISPATCH/restore.log"
test ! -e "$P1_TARGET_DISPATCH/observed_outer.json"
set +e
timeout --signal=TERM --kill-after=5s 1200s /usr/bin/python3 -I -B \
  "$P1_TARGET_CODE/research_runs/REDESIGN_HANDOFF_20261015/target_restore/target_restore_once.py" \
  --delivery-revision "$P1_TARGET_REVISION" \
  --source-restore-root /workspace/paper1-source-recovery-run01 \
  --source-acceptance-root /workspace/paper1-repaired-source-acceptance-run01 \
  --continuity-report /workspace/paper1-continuity-review-run01/continuity_review_run01.json \
  --review-record "$P1_TARGET_REVIEW" --priority-receipt "$P1_TARGET_SLOT" \
  > "$P1_TARGET_DISPATCH/restore.log" 2>&1
P1_RAW_EXIT=$?
set -e
/usr/bin/python3 -I -B - "$P1_RAW_EXIT" "$P1_TARGET_DISPATCH/observed_outer.json" <<'PY_OUTER'
import hashlib, json, pathlib, sys
summary = pathlib.Path('/workspace/paper1-target-recovery-run01/target_restore_run01.json')
value = {'schema_version':1, 'status':'OBSERVED_TARGET_RAW_RESTORE_PROCESS_EXIT',
    'exit_code':int(sys.argv[1]),
    'target_restore_summary_sha256':hashlib.sha256(summary.read_bytes()).hexdigest() if summary.is_file() and not summary.is_symlink() else None,
    'script_sha256':'65507374bc7640d4c6b2b7d9b609d86b809a11d61a1aa55d61e6527ced4e5190',
    'training_authorization':False}
with pathlib.Path(sys.argv[2]).open('x') as stream:
    json.dump(value, stream, indent=2); stream.write('\n')
print(json.dumps(value))
PY_OUTER
cat "$P1_TARGET_DISPATCH/restore.log"
exit "$P1_RAW_EXIT"
)
```

If parent chooses a lower wall cap, lower the outer timeout to that exact cap.
All174 existing files are verified before the first GET; only missing objects
are requested. All redirects, alternate formats, partials, unknown cache
members, hash failures and consumed claims stop. Preserve every failed or
uncertain attempt; do not delete the claim, overwrite the cache or retry it.

Required success evidence is the actual outer exit0 **and**
`target_restore_run01.json` **and** `target_bytes_receipt.json`, with exact
mutual SHA bindings,174 files and2515343396 bytes. A success-looking summary
or byte receipt without the observed final exit0 is insufficient. The tests
cover a late slot revocation after summary publication.


Production routing and original-fit continuity remain separate ongoing work. They are not prerequisites for this already authorized byte-only recovery, and this raw pin does not contain or authorize production processing or training.
