# Dot: official target bytes → unchanged scientific input preparation

**2026-10-15 run01 update: do not execute step1 again.** The actual first
attempt exited3 with `HTTPError`, zero objects verified and its claim consumed.
Keep that claim, logs and empty cache intact. The subsequently authorized
single HEAD, from the Codex executor rather than the Pod, returned200 without
`Location`; it does not identify the earlier Pod GET error or authorize retry.
See [the failure audit and HEAD observation](http_metadata_run01/README.md).
No redirect-policy or transfer amendment has been issued. The commands below
remain the original reviewed procedure, not a new execution authorization;
step2 still requires a real successful raw restoration and observed exit0.

This is the current executable continuation-preparation handoff. Do not rerun
the completed continuity observation, source restoration, runtime repair,
diagnostic or actual-runtime CPU acceptance. Dot is the sole Pod operator;
this code-delivery task has performed none of those operations.

Use the independently delivered raw commit and small-bundle fetch command in
[EXECUTION_PIN.md](EXECUTION_PIN.md) for step1. Production later adds only the
[separate fixed supplement](../official_production/EXECUTION_PIN.md); it does
not change or delay the raw pin. These fetches retrieve public source and
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

## 2. Bind actual byte receipts to the minimal production route

This step starts only after independent review of the actual successful raw
restoration evidence. No new parent record can be prepared truthfully before
the real target receipt/summary/outer SHAs exist.

Create a new dispatch directory such as
`/workspace/paper1-official-preparation-dispatch-run01`, outside code, runtime
and caches. Prepare real JSON records from the supplied templates:

* `route_binding.PLAN_ONLY.json`: insert the actual target-byte SHA. Its
  `METADATA_ROUTE_BINDING_FOR_INDEPENDENT_REVIEW_NOT_EXECUTION` status is
  intentionally metadata-only, not a scientific or execution PASS.
* `official_production/route_records.PLAN_ONLY.json`: retain the three existing
  source/runtime/formal paths and SHAs; insert the actual target-byte SHA and
  the SHA of the new route binding. Save as `route_records.json`.
* `numerical_review.PLAN_ONLY.json`: parent independently reviews the already
  accepted source/numerical evidence, then issues the original required
  `PASS_FORMAL_SOURCE_NUMERICAL_REVIEW_TARGET_GATES_REQUIRED` record with real
  issuer/time. The formal acceptance and private-package SHA remain unchanged.
  This is a review of existing evidence, not another numerical acceptance run.
* `official_production/parent_review.PLAN_ONLY.json`: insert the fixed delivery
  revision and all actual route/numerical/summary/outer/target-byte SHAs; parent
  sets `PASS_OFFICIAL_192_DATA_PREPARATION_PARENT_REVIEW` only after real
  review. No fit, target prediction or registration overwrite is authorized.
* `input_slot.PLAN_ONLY.json`: dot issues a fresh
  `target_input_preparation` slot following that review. It has the same
  no-GPU/no-fit/Paper2/floor controls, and a separate3GiB preparation allocation.

No tool in this bundle automatically promotes a template to an approval.
Financial conditions remain superseded. New data preparation is allowed while
old fit history remains unknown; model continuation is not.

Before execution, dot creates the new review-copy output with exactly three
genuine prerequisite files. This does not create an execution registration,
ledger, fit counter or original job directory:

```bash
(
set -eu
: "${P1_NUMERICAL_REVIEW:?actual newly issued numerical-review JSON}"
P1_TARGET_CODE=/workspace/paper1-official-transition-code-run01
P1_PREP_OUT=/workspace/paper1-official-preparation-run01
test ! -e "$P1_PREP_OUT"
test ! -L "$P1_PREP_OUT"
mkdir -m 700 -- "$P1_PREP_OUT"
cp --no-clobber \
  "$P1_TARGET_CODE/research_runs/REDESIGN_HANDOFF_20261015/target_restore/evidence/original_launch_record.json" \
  "$P1_PREP_OUT/launch_record.json"
cp --no-clobber /workspace/paper1-repaired-source-acceptance-run01/formal_source_acceptance.json \
  "$P1_PREP_OUT/formal_source_acceptance.json"
cp --no-clobber "$P1_NUMERICAL_REVIEW" "$P1_PREP_OUT/numerical_execution_review.json"
)
```

The launch copy is the authentic399-byte original, retrieved through normal
read-only GitHub at fixed historical commit, SHA
`edb2b3e4790d383878106144eddc3ee8ffc9dc65c6ae4128ec92330757fca49e`.
The original runtime/code identity copies are also supplied for review, not
installed as a new current machine lock. Original registration and latest
private ledger are still missing; public identity recovery does not fill them.

## 3. Execute unchanged scientific preparation in the existing runtime

Set genuine paths and their independently verified SHA values; no credential
or model/data outcome is an input to these variables. The default dispatch
names below can be used if they correspond to the actual records above.

```bash
(
set -euC
: "${P1_PRODUCTION_REVISION:?separate fixed production code commit}"
: "${P1_PREP_REVIEW:?actual parent data-preparation review JSON}"
: "${P1_PREP_REVIEW_SHA:?actual SHA256 of that exact review}"
: "${P1_PREP_SLOT:?new target_input_preparation slot}"
: "${P1_ROUTE_RECORDS:?actual five-record route JSON}"
: "${P1_ROUTE_RECORDS_SHA:?actual SHA256 of the route JSON}"
: "${P1_TARGET_SUMMARY_SHA:?actual SHA256 of target_restore_run01.json}"
: "${P1_TARGET_OUTER:?actual observed raw-restoration outer JSON}"
: "${P1_TARGET_OUTER_SHA:?actual SHA256 of that exact outer record}"
: "${P1_PREP_DISPATCH:?actual preparation dispatch directory}"
P1_TARGET_CODE=/workspace/paper1-official-transition-code-run01
test -d "$P1_PREP_DISPATCH"
test ! -e "$P1_PREP_DISPATCH/prepare.log"
test ! -e "$P1_PREP_DISPATCH/observed_outer.json"
set +e
timeout --signal=TERM --kill-after=5s 1200s \
  /workspace/paper1-training-runtime-cp312-run01/bin/python -I -B \
  "$P1_TARGET_CODE/research_runs/REDESIGN_HANDOFF_20261015/official_production/prepare_official.py" \
  --execute --delivery-revision "$P1_PRODUCTION_REVISION" \
  --scientific-code /workspace/paper1-metadata-code-1efe9d1 \
  --output-dir /workspace/paper1-official-preparation-run01 \
  --route-records "$P1_ROUTE_RECORDS" --route-records-sha256 "$P1_ROUTE_RECORDS_SHA" \
  --parent-review "$P1_PREP_REVIEW" --parent-review-sha256 "$P1_PREP_REVIEW_SHA" \
  --priority-receipt "$P1_PREP_SLOT" \
  --continuity-report /workspace/paper1-continuity-review-run01/continuity_review_run01.json \
  --target-restore-summary /workspace/paper1-target-recovery-run01/target_restore_run01.json \
  --target-restore-summary-sha256 "$P1_TARGET_SUMMARY_SHA" \
  --target-restore-outer "$P1_TARGET_OUTER" --target-restore-outer-sha256 "$P1_TARGET_OUTER_SHA" \
  > "$P1_PREP_DISPATCH/prepare.log" 2>&1
P1_PREP_EXIT=$?
set -e
/usr/bin/python3 -I -B - "$P1_PREP_EXIT" "$P1_PREP_DISPATCH/observed_outer.json" <<'PY_PREP_OUTER'
import hashlib, json, pathlib, sys
completion = pathlib.Path('/workspace/paper1-official-preparation-run01/official_preparation_completion.json')
value = {'schema_version':1, 'status':'OBSERVED_OFFICIAL_INPUT_PREPARATION_PROCESS_EXIT',
    'exit_code':int(sys.argv[1]),
    'completion_sha256':hashlib.sha256(completion.read_bytes()).hexdigest() if completion.is_file() and not completion.is_symlink() else None,
    'script_sha256':'c75a025b9e632d9b06400ef71e85b77efd8b33508decad1400c1566d7fa34cc4',
    'training_authorization':False}
with pathlib.Path(sys.argv[2]).open('x') as stream:
    json.dump(value, stream, indent=2); stream.write('\n')
print(json.dumps(value))
PY_PREP_OUTER
tail -n 30 "$P1_PREP_DISPATCH/prepare.log"
exit "$P1_PREP_EXIT"
)
```

This command reads source/target raw inputs only after its real preparation
review/slot pass. No raw input or scientific code is opened by this delivery.
The existing source strict gate and all original target eligibility/QC/context/
per-trial band hashes remain enforced. No target adaptation, duration selection,
normalization fitting, BN update, prediction or model fit is performed.

Required final preparation evidence is the observed outer exit0, unchanged
scientific `data_prepare_receipt.json`, acquisition/QC/tensor hashes,
`new_machine_data_preparation_transition.json` and
`official_preparation_completion.json`. The latter deliberately reports
`TRAINING_STILL_BLOCKED`. Do not copy these into the old job or treat them as
an original public freeze/registration. Retain failures and partials, never
reset claims or automatically retry. Dot backs up the review evidence through
its existing working off-host channel; this is not a claim that a new backup
was already created or verified here.

## The exact remaining fit-resumption decision

The package recovers three authentic original **public identity** records;
it does not recover the latest private fit/update ledger, consumed model/
checkpoint identities, pending update state or verified HEAD/manifest/blob
continuity. The available thread/Library route limitation is documented in
[the actual observation](HISTORICAL_RECOVERY_ROUTE_OBSERVATION.json).

If a functioning existing backup route or off-host export yields those real
records, use them for the original-job review. Do not rerun an unchanged
metadata check or re-request billing. If they cannot be recovered, a guaranteed
no-repeat continuation cannot be established: it needs an explicit alternative
recovery-execution decision acknowledging possible repeated work and preserving
historical counts as unknown. Such a decision has not been granted; there is
no training bypass or new zero ledger in this bundle. Official target recovery
and deterministic preparation above remain executable meanwhile.
