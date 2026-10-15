# One offline repair of the retained failed runtime — run01

This is a separate operational repair, not another execution of the failed
preparation. Dot alone operates the Pod. Paper 2's independent work keeps
priority. This delivery did not operate the Pod, install a package, fetch a
wheel, read EEG, repeat a diagnostic, or start a fit.

## Independent evidence review

The original 423996-byte archive, SHA256
`7c83bcb991857dd99b7cda2b4bd8f9fe467d87217fb3a73c408b7b1474f4b3a0`,
contains 26 regular payloads plus its manifest. Every member length/SHA and the
complete 79-entry resolution/recorded cache inventory agree. The resolution is
1399863 bytes, SHA256
`a0ed2680c8e057a60aec9cde0d736c9869f3ea9e747f5a6216d79766d07f9b5a`.
All 13 direct scientific pins remain those at 1efe9d1; the 79 recorded wheels
contain no new Torch, torchaudio, Triton or NVIDIA distribution.

The archived run actually failed between 03:54:00.757256 and 03:54:43.978652 UTC
on 15 October 2026: outer exit 3, inner exit 1, before scientific wheel
installation. This is a real preserved failure, not a successful preparation.
The original 1efe helper and b078 controller are unchanged. See
[the audit](FAILED_PREPARATION_INDEPENDENT_AUDIT.json) and
[the frozen cache index](frozen_wheel_cache_index.json).

The archive has no wheel binaries or complete installed-site inventory. Thus
this review authenticates the recorded observations, not current cache bytes,
current free space, or the current partial. Those must pass the controller's
fresh read-only checks immediately before any repair installation. No live
Pod preflight is claimed here.

## Exact exception, without modifying or omitting wheel members

Only these whole-wheel identities can carry the following extra destinations:

| Wheel | Whole-wheel SHA256 | Approved document member | Bytes | Member SHA256 |
|---|---|---|---:|---|
| fonttools 4.67.0 | `eb3c98cac93aac4b9f6e3ce2008325340b234cc9b0338ca6b513f31962a1e278` | `fonttools-4.67.0.data/data/share/man/man1/ttx.1` | 5377 | `70b6e6fe938e8f50bbe93d905ef0f1cf00e3f6093e193779473b6f4ccb28b85c` |
| sympy 1.14.0 | `e091cc3e99d2141a0ba2847328f5479b05d94a6635cb96148ccb3f34671bd8f5` | `sympy-1.14.0.data/data/share/man/man1/isympy.1` | 6659 | `f4365d48e2102e292b0131e56e4743674e0b0508a0643504d3fa025c10ef741b` |

The only additional ZIP entries approved are fonttools' three zero-byte
directories `fonttools-4.67.0.data/data/share/`, `.../share/man/` and
`.../share/man/man1/`, each SHA256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Member type, exact path, bytes, SHA and complete five-entry exception set are
checked, as are every wheel's unchanged ordinary ZIP/startup/protected-GPU
guards. Other data/headers destinations remain blocked.

The actual child `sysconfig` data path must equal the existing venv prefix.
The documents install to that child's `share/man/man1/`, with both files read
back against exact member SHA afterward. Existing symlink ancestors, special
files, path traversal, duplicate members and protected-component writes block
the repair. There is no wheel rewriting or file omission.

## Parent review and a new slot are mandatory

1. Parent reviews the fixed three-file repair bundle, this evidence and the
   narrow exception. Copy `repair_parent_review.PLAN_ONLY.json` to a new
   review file outside the bundle, supply the immutable revision and all three
   hashes from `REPAIR_PIN.md`, actual review/expiry UTC and review notes.
   Set its six reviewed conditions true only after review, status to
   `DOT_PARENT_SINGLE_OFFLINE_REPAIR_APPROVED`; leave every prohibited
   authority false. The template as committed cannot authorize execution.
2. Dot checks actual Paper 2 noninterference, partial/cache preservation and
   current free space, then issues a NEW `runtime_preparation` slot after
   that review. It must bind Pod `52ivinpjwv947i` / container `a7d3f0e408a4`,
   use the existing exact slot schema in
   `../runtime/paper2_priority_slot.PLAN_ONLY.json`, and carry its actual
   Paper 2 reserve (at least 5 GiB). Do not reuse or extend any prior slot.
   Its expiry must not exceed review expiry or 2026-10-16 09:54:00 UTC.
   This repair's wall cap is at most 1200 seconds, also bounded by the slot.
3. Keep the retained `/workspace/paper1-training-runtime-cp312-run01` and its
   79 wheels, old logs and 1efe checkout untouched. The controller requires the
   exact original five partial configuration files and four failure logs. It
   verifies every cached wheel's name/size/SHA against the original resolution,
   then checks all ZIP members before installation. Any mismatch blocks;
   do not delete or rename paths to bypass it.

The fresh uninstalled-site gate requires only the original 24 approved GPU
component links plus seed pip and its one dist-info directory. Extra science
packages, startup hooks, foreign entries or altered interpreter links block.
Seed pip's fresh METADATA/RECORD hashes are recorded; this does not invent a
historical seed-pip version absent from the archive. A stdlib-only child
sysconfig probe follows those static checks. No Torch/CUDA import is performed.
The full 22450-byte donor report SHA must remain
`3a83a9cf93cca3e9813056645bc73f26a9429ee6f1f7bc06f2ae78a1c36471b1`.

## Dot invocation, once the two gates above actually pass

Use the small verified bundle from `REPAIR_PIN.md`, not another repository
clone or another venv. The reported old controller path below is not presumed
to exist: it must still be the original 22347-byte file, SHA256
`7a1fbc9b364c8dd42faf6894450ae065a49d59a977d4c5470a3c2daffff50cc3`.
If missing, retain that fact and obtain only those exact authenticated source
bytes from the original evidence or fixed b078 commit; never rerun its main.
The original failed archive must already be available at its genuine local
path. These variables contain paths and a public commit, not secrets.

```bash
(
set -eu
: "${P1_REPAIR_DIR:?small verified three-file repair bundle from REPAIR_PIN.md}"
: "${P1_REPAIR_REVISION:?fixed 40-character repair code commit in REPAIR_PIN.md}"
: "${P1_PRIOR_CONTROLLER:?original b078 controller file verified by SHA}"
: "${P1_FAILURE_ARCHIVE:?actual original 423996-byte failed-preparation tar.gz}"
: "${P1_REPAIR_REVIEW:?new actual dot_parent single-repair review record}"
: "${P1_REPAIR_SLOT:?NEW dot runtime_preparation slot issued after review}"
/usr/bin/python3 -I -B "$P1_REPAIR_DIR/repair_preparation_once.py" \
  --repair-revision "$P1_REPAIR_REVISION" \
  --prior-controller "$P1_PRIOR_CONTROLLER" \
  --code-dir /workspace/paper1-metadata-code-1efe9d1 \
  --failure-archive "$P1_FAILURE_ARCHIVE" \
  --donor-report /workspace/paper1-cp312-metadata-20261015-run01/gpu_donor_inventory.json \
  --review-record "$P1_REPAIR_REVIEW" --priority-receipt "$P1_REPAIR_SLOT" \
  --log /workspace/paper1-repair-run01.log
)
```

The command validates first, then exclusively creates the child's
`repair_run01.journal.jsonl` before its first pip command. That consumes this
single attempt. A changed/expired/revoked review or slot, cancellation,
installation failure or changed inputs retains the journal and all evidence.
There is no automatic retry; do not remove the journal or rerun the command.
Before this journal exists, a failed preflight is still a block to investigate,
not permission to keep trying installation.

The only installer commands are child `pip install --no-deps --no-index
--no-cache-dir --disable-pip-version-check` on all 79 original local wheel
paths, then child `pip check`, under the unchanged helper's clean environment.
No resolver, wheel download, apt/global pip, whole-site inheritance, cp311
reuse, numerical-thread change or CUDA reinstallation is introduced.

## Storage, accounting and return evidence

The failed partial's archived allocation was 165703680 bytes; archived sampled
owned peak was 168755200 bytes. The 79 retained wheels total 148288134 compressed
bytes. Fresh accounting includes the entire existing child/cache, old owned
failure logs, repair journal/receipt and new repair log. Its total remains
`min(3 GiB, slot.max_new_bytes)`, including existing allocation; it is not a new
3 GiB allowance. Free space must remain at least `max(10 GiB,
slot.min_free_bytes) + slot.paper2_reserve_bytes`. Preinstall free space must
also cover `2 * measured_wheel_expanded_bytes + 256 MiB` above that floor.
The controller reserves evidence space and samples owned allocations/free
space while monitoring only its own installer; this is not a kernel quota or
continuous GPU observation. Cancellation targets only its own process tree.

Return the original failed archive identity, new review and slot, exact command
and actual UTC start/end/exit, `/workspace/paper1-repair-run01.log`, child
`repair_run01.journal.jsonl` and, if successful, child
`runtime_repair_run01.json`, plus path/size/SHA evidence. Keep old failure
outputs unchanged. No wheel binary, EEG or secret goes to GitHub.

Expected repair-only status:
`REPAIRED_PREPARED_IMPORT_SOURCE_REVIEW_PENDING`. The original absent
`runtime_preparation.json` is not fabricated. This distinct repair receipt
requires a separately reviewed acceptance adapter before the later actual
training-runtime imports and strict source acceptance; it cannot impersonate
the failed original transaction. Private source-package binding, old task/
budget/checkpoint/backup reconciliation, target recovery/mapping and execution
authorization remain blocked. No source diagnostic is repeated here.

Old attributed costs/GPU hours are unknown, not zero. The $10 total, $2 reserve,
8 cumulative GPU-hour, fit/update ceilings and deadline-only extension to
2026-10-16 09:54 UTC remain unchanged. Repair evidence is not a new budget,
renewal, platform-balance observation, or training permission.
