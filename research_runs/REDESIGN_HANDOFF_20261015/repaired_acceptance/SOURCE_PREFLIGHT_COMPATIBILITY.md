# Exact old-tmp compatibility; no old failure overwritten

The63678-byte source-repair preflight failure package SHA256 is
`89569e3a18402665d81f74064a420de522c74115458883b9af9eac6d5bfe8dab`.
All31 payloads and the embedded original27-payload package passed independent
integrity review. The actual5c7e controller exited3 at
2026-10-15 06:37:36.134424UTC in `cache_preflight`, before a repair claim,
receipt or missing-file GET. This does not prove the pathname responsible for
the earlier run01 FileNotFoundError.

This is only a compatibility whitelist correction:

- Preserve and require exactly
  `source_restore_run01.json.tmp-a0f96cd0b1ed43c0967091e562c9884a`, a regular
  non-symlink file of0bytes and empty SHA256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
  It remains an ordinary mandatory old record, not a transient-retry allowance.
- Preserve and require the failed `source_restore_repair_run01.outer_exit.json`,
  SHA256 `112aac0310e0dd5d239e81c88414361a501e6b26a4fcb5189521afe9b60329e9`.
- Other unknown members/partials remain rejected. Old receipt/journal/log,
  cache and all five preserved records remain immutable. No deletion, rename,
  zero-fill or failure-to-success relabelling is performed.
- The unconsumed repair claim/journal/receipt names remain unchanged and
  exclusive. A consumed claim still stops. A new technical review must postdate
  this actual preflight failure, with the same original window and resource gates.
- The wrapper now writes only `source_restore_repair_run01.compat_outer_exit.json`;
  the prior failed outer stays in place. Step B validates the new actual exit0,
  new claim's preflight-failure identity, old five record hashes and full18/18.

No environment, installation, scientific input, numerical rule,12/6 scope,
1200/300second limit, disk/Paper2 gate, author window or financial supersession
changes. Current cache metadata contains12 names/sizes consistent with the
previous fullSHA evidence; no raw MAT was read here. The controller rehashes
all12 actual files before GET and fetches only the remaining6.

## Fixed source command for dot

Use `SOURCE_PREFLIGHT_COMPATIBILITY_PIN.md` for the new fixed bundle and hashes.
Keep all old delivery directories and the failed outer. The argument
`P1_SOURCE_RESTORE_FAILURE_ARCHIVE` still names the already-present original
26831-byte package (SHA89f8b8b0...), not the new63678-byte package; the new
package's SHA and preserved actual outer/tmp are explicitly bound by this patch.

Dot supplies a fresh technically reviewed record/slot for the new code identity:

```bash
(
set -eu
: "${P1_SOURCE_REPAIR_DIR:?verified new compatibility bundle}"
: "${P1_SOURCE_REPAIR_REVISION:?fixed new compatibility code commit}"
: "${P1_SOURCE_RESTORE_FAILURE_ARCHIVE:?existing original26831-byte failure archive}"
: "${P1_SOURCE_REPAIR_REVIEW:?actual new technical review after06:37:36.134424UTC}"
: "${P1_SOURCE_REPAIR_SLOT:?fresh dot source_raw_restore slot}"
bash "$P1_SOURCE_REPAIR_DIR/RUN_SOURCE_RESTORE_REPAIR_ONCE.sh" \
  --delivery-revision "$P1_SOURCE_REPAIR_REVISION" \
  --code-dir /workspace/paper1-metadata-code-1efe9d1 \
  --data-dir /workspace/paper1-source-recovery-run01 \
  --failure-archive "$P1_SOURCE_RESTORE_FAILURE_ARCHIVE" \
  --review-record "$P1_SOURCE_REPAIR_REVIEW" \
  --priority-receipt "$P1_SOURCE_REPAIR_SLOT"
)
```

## Acceptance remains conditional on actual complete source recovery

Step B is still blocked now. After actual18/18, successful new journal/controller
completion and the new **compat_outer_exit** record's observed0, the parent binds
the actual source receipt SHA in a post-success review and dot issues the
separate CPU slot. Use the same full CPU command in
`SOURCE_RESTORE_REPAIR.md`, with the two public variables set to this compatibility
bundle/revision. Its updated adapter reads the compat outer, explicitly preserves
the old failed outer/tmp, and still requires the original full source/runtime
acceptance. No failed or RUNNING receipt is promoted by this delivery.

No Pod operation, EEG read, installation, target access or fit was performed here.
