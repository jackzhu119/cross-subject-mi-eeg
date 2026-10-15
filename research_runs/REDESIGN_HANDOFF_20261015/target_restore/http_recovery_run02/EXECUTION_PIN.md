# Fixed run02 raw recovery: dot executes once

**Execution commit:** `790adc6eed78c8d5792b4e9d5ba3682c88594e69`.
Branch: `research/paper1-handoff-20261014`.

| Item | SHA256 |
|---|---|
| New `target_restore_run02.py`,20653 bytes | `5a5fb300c800c0d9884df9d29f0287f46ee2304ce8b21f815c2f93138eb188db` |
| Original controller, retained unchanged | `65507374bc7640d4c6b2b7d9b609d86b809a11d61a1aa55d61e6527ced4e5190` |
| Same-Pod historical HEAD,564 bytes | `a1d19255b427122f9f961cde33873693f35c0db3773112fdaebaa17ae8629ebe` |
| Unissued new parent-review template,2431 bytes | `12fc2a6825c7084aefc7430c9a7b055f03d9e041624801ddc9c41090874c8c20` |
| Independent static review | `151523c1d48f05038c0e199c2452a7039c237fa700b43f95fba51d767b16506f` |

This pin authorizes no execution by Codex. Parent has approved the scope of
one additional attempt; dot must issue actual review and fresh resource slot
before dispatch. This does not reuse any prior review/slot or extend deadlines.
Only the new20KB entry needs appending to the existing small code delivery.
No environment, package, scientific checkout, source data or old code is replaced.
These four fixed code/metadata files were publicly read back and compared
byte-for-byte successfully. Sixteen targeted synthetic cases passed; no
provider request, Pod operation, installation or EEG/model work was performed
in this delivery.

## Fetch only the new fixed entry

```bash
(
set -eu
P1_RUN02_CODE=/workspace/paper1-official-transition-code-run01/research_runs/REDESIGN_HANDOFF_20261015/target_restore
test -d "$P1_RUN02_CODE"
printf '%s  %s\n' \
  65507374bc7640d4c6b2b7d9b609d86b809a11d61a1aa55d61e6527ced4e5190 \
  "$P1_RUN02_CODE/target_restore_once.py" | sha256sum -c -
test ! -e "$P1_RUN02_CODE/target_restore_run02.py"
test ! -L "$P1_RUN02_CODE/target_restore_run02.py"
curl --fail --silent --show-error --proto '=https' --tlsv1.2 --retry 0 \
  --connect-timeout 10 --max-time 30 --max-filesize 32768 \
  https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/790adc6eed78c8d5792b4e9d5ba3682c88594e69/research_runs/REDESIGN_HANDOFF_20261015/target_restore/target_restore_run02.py \
  -o "$P1_RUN02_CODE/target_restore_run02.py"
printf '%s  %s\n' \
  5a5fb300c800c0d9884df9d29f0287f46ee2304ce8b21f815c2f93138eb188db \
  "$P1_RUN02_CODE/target_restore_run02.py" | sha256sum -c -
)
```

An existing new entry or failed code fetch stops; preserve it. Do not refetch
the original bundle, reinstall or clear any claim. Parent can obtain the
new review schema from this commit's
`target_restore/http_recovery_run02/parent_run02_review.PLAN_ONLY.json`.
Its null/false/NOT_ISSUED values are not grants: set the actual review time,
expiry, reviewed commit, genuine issuer/status, scope/resource attestations,
raw-byte authority and `one_additional_bounded_attempt_authorized=true` only
after review. Preserve every fixed hash and false fit/processing/credential
field. Use the unchanged `target_restore/raw_slot.PLAN_ONLY.json` schema
for a genuinely new dot `target_raw_restore` slot following that review.

## Exact single process command

Set these three nonsecret paths to the actual issued records and the existing
same-Pod HEAD attachment. Do not run another HEAD:

```text
P1_RUN02_REVIEW = genuine new run02 parent-review JSON
P1_RUN02_SLOT   = genuine fresh dot target_raw_restore slot JSON
P1_RUN02_HEAD   = actual supplied same-pod-first-object-head-run01.json
```

For a lost local HEAD path only, the same564 historical bytes are archived
at this fixed commit under
`target_restore/http_recovery_run02/evidence/same-pod-first-object-head-run01.json`.
Restoring those metadata bytes is not a new network observation; compare the
exact SHA above. The old actual outer path below is taken from the failed
run01 dispatch. A missing/different old record stops; do not synthesize it.

Dot's existing supervisor should record a fresh run02 dispatch and run this
command exactly once, retaining actual argv/start/end, code/review/slot/HEAD
hashes, stdout/stderr and real process exit. Use an outer timeout no greater
than the genuine parent review; the code separately enforces its wall cap:

```bash
timeout --signal=TERM --kill-after=5s 1200s /usr/bin/python3 -I -B \
  /workspace/paper1-official-transition-code-run01/research_runs/REDESIGN_HANDOFF_20261015/target_restore/target_restore_run02.py \
  --delivery-revision 790adc6eed78c8d5792b4e9d5ba3682c88594e69 \
  --source-restore-root /workspace/paper1-source-recovery-run01 \
  --source-acceptance-root /workspace/paper1-repaired-source-acceptance-run01 \
  --continuity-report /workspace/paper1-continuity-review-run01/continuity_review_run01.json \
  --prior-outer /workspace/paper1-target-dispatch-20261015-run01/observed_outer.json \
  --same-pod-head "${P1_RUN02_HEAD:?actual supplied historical HEAD JSON}" \
  --review-record "${P1_RUN02_REVIEW:?actual new approved run02 review JSON}" \
  --priority-receipt "${P1_RUN02_SLOT:?actual fresh target_raw_restore slot JSON}"
```

The cache remains `/workspace/paper1-target-recovery-run01`. This command has
no automatic retry and cannot reuse a run02 claim. Keep all run01 files and
the original failed outer receipt unchanged. New outputs are the four
`target_restore_run02.*` files listed in `OPERATION.md` plus, on complete
success only, `target_bytes_receipt.json`.

The new **observed**, not predeclared, outer receipt must retain schema1,
status `OBSERVED_TARGET_RAW_RESTORE_PROCESS_EXIT`, actual integer
`exit_code`, actual SHA of `target_restore_run02.json` or null if absent,
`script_sha256=5a5fb300c800c0d9884df9d29f0287f46ee2304ce8b21f815c2f93138eb188db`,
and `training_authorization=false`. Do not write a synthetic zero. A current
HTTPError stops with recorded status/controlled Location; keep all evidence.

No production preparation or training command is included. The old production
receipt-SHA gate remains closed for this new entry pending genuine174/174
verification and an independently observed outer0, followed by its separate
minimal receipt-binding review.
