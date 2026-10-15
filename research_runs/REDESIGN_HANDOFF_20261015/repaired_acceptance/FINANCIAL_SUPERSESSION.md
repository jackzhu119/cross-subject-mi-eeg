# Current narrow amendment: financial preconditions superseded by user

> **Current source correction:** actual source run01 failed. Preserve its RUNNING receipt and old claim; do not execute the old Stage A below. Follow [SOURCE_RESTORE_REPAIR.md](SOURCE_RESTORE_REPAIR.md) for the new one-shot repair. Stage B remains blocked until that repair completes18/18 with observed outer exit0. The financial supersession itself is unchanged.

The author explicitly reports dot's question, “旧累计10美元门是否改为本次30分钟增量独立授权”,
and the immediate author reply, **“别再计算这该死的费用了，把有关费用和钱的都移出去”**.
The new immutable record is `AUTHOR_FINANCIAL_SUPERSESSION_20261015.json`, SHA256
`d3a4e670332a9bf158da98abae0ab84702d092018c6043cbc36bf4f3f5fb7d90`.
The recorded UTC is an assistant tool-clock observation, not the author's message time.

For the existing **source_raw_restore / source_cpu_acceptance** operations:

- The old total-dollar cap, monetary reserve, balance observation and
  `covered_dollar_upper_bound_reviewed` are **superseded-by-user**, not passed.
  Do not wait for complete billing, balance research or another money approval.
- The original48-hour author JSON is retained byte-for-byte, including its
  historical financial wording. This append-only record explicitly supersedes
  its `covered_refreshed_dollar_upper_bound_still_required` field for these two
  operations. No account, unknown or failed record is deleted or filled with zero.
- Actual technical review now binds `financial_preconditions_status` to
  `superseded-by-user` and `financial_supersession_sha256` to the SHA above.
  **Remove** the obsolete `covered_dollar_upper_bound_reviewed` key rather than
  setting it true. The gate checks the new record before and during execution.
- `unknown_accounting_retained=true` means preserving unknown history, not
  resolving costs. The unchanged `budget_reset_authorized=false` and
  `budget_expansion_authorized=false` prohibit resetting records or inferring a
  new purchase authorization; they do not reinstate superseded monetary limits.

Only `acceptance_gate.py`, the review/slot templates and this operational
documentation change. The two execution scripts remain identical to709a213c.
Use the new gate/record together, never overwrite the old delivery directory.
`FINANCIAL_SUPERSESSION_PIN.md` supplies the fixed new commit and SHA download block.
Review templates remain PLAN_ONLY until dot's parent records the actual technical
review; no author/time/financial question needs to be repeated. Dot then issues
fresh operation-specific slots. Existing consumed claims must not be retried.

## Unchanged controls

The CPU availability remains **2026-10-15 05:07:25 to2026-10-17 05:07:25 UTC**;
the original GPU deadline remains **2026-10-16 09:54 UTC**. Single slots remain
at most30minutes for resource scheduling. Source restore remains at most1200s;
CPU acceptance uses the300s watchdog with at least310s slot headroom.
The18 original MAT files total779873919bytes, with their original exact full SHA.
All one-shot claims, failures, runtime/donor checks,3GiB ownership cap,
10GiB disk floor plus actual Paper2 reserve (at least5GiB), and Paper2
noninterference checks remain unchanged. No numerical version, scientific input,
hash, tolerance, environment or experiment changes.

The user reports dot has recovered both historical evidence archives and checked
their frozen SHAs. Use those actual paths, not a new download or replacement:
134436bytes / `2871f422755bf5d0b939d0db59fc41547b192d6c939db1a6a13b97a91ba49ae9`;
12299bytes / `a4c6c3f7beadf6ce0c927c6e4b9d20b6d37ff3bc2c033ad4b4fd836ca38a6b0d`.
The existing repaired97-distribution child is reused, with its independent repair
receipt and original successful442155-byte repair archive. No installation or
old diagnostic is repeated. This statement records dot's supplied recovery
status, not a new live inspection by this assistant.

## Stage A — source-only restoration, once

Set the two public delivery variables using the fixed pin. Dot supplies the
actual newly bound technical review and source_raw_restore slot. The reviewed
old1efe checkout, same repaired runtime and all output/claim paths are unchanged.
If this stage already succeeded, use its original receipt instead of rerunning.

```bash
(
set -eu
: "${P1_ACCEPT_DIR:?verified new small bundle from FINANCIAL_SUPERSESSION_PIN.md}"
: "${P1_ACCEPT_REVISION:?fixed new code commit from the pin}"
: "${P1_SOURCE_RESTORE_REVIEW:?actual parent technical source_raw_restore review}"
: "${P1_SOURCE_RESTORE_SLOT:?fresh dot source_raw_restore slot}"
/usr/bin/python3 -I -B "$P1_ACCEPT_DIR/restore_source_once.py" \
  --delivery-revision "$P1_ACCEPT_REVISION" \
  --code-dir /workspace/paper1-metadata-code-1efe9d1 \
  --data-dir /workspace/paper1-source-recovery-run01 \
  --review-record "$P1_SOURCE_RESTORE_REVIEW" \
  --priority-receipt "$P1_SOURCE_RESTORE_SLOT"
)
```

## Stage B — actual repaired-runtime CPU source acceptance, once

The parent binds the actual successful Stage A receipt SHA and a review time
after that stage's finish. Dot supplies a separate fresh source_cpu_acceptance
slot. Use the already recovered original archives at their actual paths.
The new output, adjacent attempt claim and log must not have been consumed.

```bash
(
set -eu
set -C
: "${P1_ACCEPT_DIR:?verified new small bundle}"
: "${P1_ACCEPT_REVISION:?fixed new code commit}"
: "${P1_REPAIR_ARCHIVE:?actual original442155-byte repair archive}"
: "${P1_FULL_DIAGNOSTIC_ARCHIVE:?actual original134436-byte recovered archive}"
: "${P1_FORMAL_DIAGNOSTIC_ARCHIVE:?actual original12299-byte recovered archive}"
: "${P1_SOURCE_ACCEPT_REVIEW:?actual parent technical source_cpu_acceptance review}"
: "${P1_SOURCE_ACCEPT_SLOT:?fresh dot source_cpu_acceptance slot}"
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

Retain exact commands, UTC start/end, both exits (including watchdog exits),
review/slot/record SHAs, original journals and actual source/runtime acceptance
receipts. A child receipt does not override an outer failure or consumed claim.
Success remains `REPAIRED_ACTUAL_TRAINING_RUNTIME_SOURCE_MATCH_OTHER_GATES_PENDING`.
This amendment establishes neither a historical financial PASS nor a training
PASS. It authorizes no payment, top-up, purchase, new resource, target EEG read,
Pod operation by this assistant or GPU fit. Dot remains the only Pod operator.
