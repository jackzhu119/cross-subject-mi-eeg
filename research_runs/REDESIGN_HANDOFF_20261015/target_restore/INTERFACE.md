# One official EDF byte-only restoration

`target_restore_once.py` restores the 174 frozen NEMAR nm000250/v1.0.5
acquisition EDF objects (2,515,343,396 bytes) to
`/workspace/paper1-target-recovery-run01/dreyer_acquisition/`. It reuses the
unchanged exact-URL/TLS/no-redirect/full-SHA transport primitive. No R2 key,
package installation, target header/event processing, normalization, inference,
model fitting, or Pod control is exposed. CC-BY-4.0 attribution remains in the
original frozen transport plan/provider metadata. Old continuity unknowns stay
unknown; source/runtime acceptance is reused through its five exact JSONs.

The script and its unchanged dependencies retain their repository-relative
layout. Required dependencies are `official_edf_transport/official_edf_transport.py`,
`continuity_resume/continuity_review.py`, `runtime/priority_gate.py` and the three
frozen catalogue/provenance/README files referenced by the original transport
helper. Their complete identities are checked; no full runtime or CUDA copy is
needed. `continuity_report` must have SHA256
`ec86526fb6af6c01a19e4d86b0fb69532098175181d2e7175c1e6668038aa6cc`.

## New operation slot and review

Dot issues a fresh slot with the unchanged priority gate's exact schema, except
`operation` is explicitly `target_raw_restore`. All no-GPU/no-fit flags remain
false and Paper2 priority/noninterference flags true. It expires within 30
minutes and no later than 2026-10-16 09:54 UTC. It supplies a separate target
allocation of at most 3 GiB, at least 10 GiB free floor, and actual Paper2
reserve of at least 5 GiB. This separate allocation does not reset the retained
source/runtime allocation or any old ledger. Financial prerequisites remain
`superseded-by-user`; old costs/counters are not changed or asserted to be zero.

The real dot-parent review is an exact JSON object whose fixed fields are
enumerated in `parent_review()`. Dot must bind the fixed code revision/SHA,
unchanged helpers, frozen manifest, five actual source/runtime JSON hashes and
the actual continuity report hash. Required additional fields are actual UTC
`reviewed_at_utc`, `expires_at_utc` and integer `maximum_wall_seconds <= 1200`.
The fresh slot must follow this real review. A template is not authorization.

The reusable `validate_slot(path, current=None, *, expected_operation=...)`
accepts only `target_raw_restore` or a separately issued
`target_input_preparation` operation. It returns `(path, raw, inode_identity,
slot_dict)`. Consumers must compare the original raw/identity and revalidate
freshness; it never mutates or relabels the protected original priority gate.

## Exact invocation interface

After the parent has pinned the final commit/SHA and dot has issued its new
valid raw-restore slot, dot substitutes those **actual** paths/revision:

```bash
timeout --signal=TERM --kill-after=5s 1200s /usr/bin/python3 -I -B \
  "$P1_TARGET_CODE/research_runs/REDESIGN_HANDOFF_20261015/target_restore/target_restore_once.py" \
  --source-restore-root /workspace/paper1-source-recovery-run01 \
  --source-acceptance-root /workspace/paper1-repaired-source-acceptance-run01 \
  --continuity-report /workspace/paper1-continuity-review-run01/continuity_review_run01.json \
  --review-record "$P1_TARGET_REVIEW" --priority-receipt "$P1_TARGET_SLOT" \
  --delivery-revision "$P1_TARGET_REVISION"
```

The outer timeout must match the reviewed actual wall cap if lower than1200s.
The default fixed target root is mandatory. Existing files are completely
size/SHA checked before the first GET, and only missing objects are requested.
Unknown members, old claims, any partial, or mismatched objects stop unchanged.
The exclusive claim is consumed once; failure/uncertain exit prohibits a retry.

The single process performs resource scans synchronously between its own
writes/publications. It has no asynchronous rglob/lstat sampler. Missing members
and symlinks fail, with no ENOENT suppression or zero accounting fallback.
Remaining target writes, total target-owned allocation and actual free space
are checked during every bounded transfer step; the Paper2 reserve remains.

`target_bytes_receipt.json` is exactly the original helper's byte-only receipt
schema accepted by `transport_receipt_union.py`. `target_restore_run01.json`,
the immutable claim, journal and log retain separate operational identity.
Only a final 174/174 exact receipt can enter the later independent scientific
preparation gate. It cannot establish target QC/input hashes, old checkpoint
continuity, an accepted backup, a GPU slot, or training authorization.
