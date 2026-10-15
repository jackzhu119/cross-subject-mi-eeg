# One source restore repair; Step B remains blocked until actual complete success

Original run01 failed. The26831-byte archive has SHA256
`89f8b8b05dc2b94a97038e6800fb94238081e63657e2b1492361da2aa4d7c536`;
all27 payload sizes/SHAs passed independent review. Outer exit3 and the final
`FileNotFoundError` / worker-15 journal override the stale RUNNING11-row receipt.
The missing pathname was not recorded. Receipt replacement and partial
publication are reproducible **race candidates**, not a proven explanation of
that actual failure. See `SOURCE_RESTORE_FAILURE_INDEPENDENT_AUDIT.json`.

Postflight metadata reports12 exact source files (513941297bytes) and6 missing
files (265932622bytes). No MAT bytes are in the archive or read here. Dot's new
operation must independently rehash all12 actual cached files before any GET.
Only A07E/T,A08E/T,A09E/T may be fetched. A wrong hash, unknown member/partial,
symlink, missing retained MAT/runtime/authorization or consumed repair claim
stops and preserves evidence. There is no ordinary-file ENOENT exemption.

## Exact minimal operational change

The preserved `restore_source_once.py` and authorization gate remain byte-identical.
The new `source_owned_measurement.py` retries a **whole allocation scan at most3
times**, solely for the current repair receipt's `.tmp-<32 lowercase hex>` name
or the6 exact current-attempt partial names. A disappeared receipt temporary
requires its regular destination; a disappeared partial requires its paired
regular final MAT of the frozen size. SHA verification remains separate and
strict. It never returns zero because a scan failed. Mandatory paths are checked
before/after the scan, including the12 retained MATs. Missing ordinary files,
runtime or authorization continue to fail. Controlled relative filename,
errno, stage and code location are recorded for retries/failures.

`restore_source_after_failure_once.py` reuses the old verified downloader and
creates ONE new `source_restore_repair_run01.journal.jsonl` claim in the same
`/workspace/paper1-source-recovery-run01` cache. Its technical review must follow
the original06:02:59.928544UTC failure. It binds the actual failure archive,
old receipt/journal/log and new script/slot identities. Old files are never
rewritten or relabelled successful:

- old receipt SHA `9042616a19d99fb67038749b33bff9d149e84d1dc825bc443f68c4bf07c37d0a`;
- old journal SHA `67ca560b409de314537d046bf09101349852cdc8f0243ed5be845343798b30b8`;
- old log is the original0-byte file.

The same checked response reads/write reservations,1GiB source allocation cap,
combined3GiB retained-runtime/source cap,10GiB free floor plus actual Paper2
reserve (at least5GiB),0.2s supervisor sampling,1200s maximum restore and
single-attempt behavior remain. Runtime allocation has no transient exception.
All historical failures and unknown accounting stay intact. Financial
preconditions remain superseded-by-user: no billing or balance study is needed.
No environment, version, scientific SHA,48-hour window or GPU deadline changes.

## Fixed delivery and new source repair command

Use `SOURCE_RESTORE_REPAIR_PIN.md` for the immutable new execution commit,
small-bundle hashes and public exports. Keep the old0603 delivery untouched.
Dot's parent binds the actual technical repair review to this new controller
SHA and unchanged gate SHA, using `source_restore_repair_review.PLAN_ONLY.json`;
dot issues a fresh source_raw_restore slot using the repair slot template.
These templates do not impersonate an actual review/slot.

Dot runs the **wrapper**, not the old restore entry or inner worker directly:

```bash
(
set -eu
: "${P1_SOURCE_REPAIR_DIR:?verified fixed small repair bundle}"
: "${P1_SOURCE_REPAIR_REVISION:?fixed new code commit from the pin}"
: "${P1_SOURCE_RESTORE_FAILURE_ARCHIVE:?actual26831-byte original failure archive}"
: "${P1_SOURCE_REPAIR_REVIEW:?actual new parent technical repair review}"
: "${P1_SOURCE_REPAIR_SLOT:?fresh dot source_raw_restore repair slot}"
bash "$P1_SOURCE_REPAIR_DIR/RUN_SOURCE_RESTORE_REPAIR_ONCE.sh" \
  --delivery-revision "$P1_SOURCE_REPAIR_REVISION" \
  --code-dir /workspace/paper1-metadata-code-1efe9d1 \
  --data-dir /workspace/paper1-source-recovery-run01 \
  --failure-archive "$P1_SOURCE_RESTORE_FAILURE_ARCHIVE" \
  --review-record "$P1_SOURCE_REPAIR_REVIEW" \
  --priority-receipt "$P1_SOURCE_REPAIR_SLOT"
)
```

It fully rehashes/reuses12 and makes at most one exact official request per
missing file, with the unchanged verified-origin/normal-TLS/size/SHA behavior.
It cannot retry run01 or another new repair. No old claim, partial or record is
deleted, renamed or overwritten to make the new operation pass.

Retain the wrapper's actual exit and every new sibling record:

- `source_restore_repair_run01.json`: new18-row success or actual progress/failure;
- `source_restore_repair_run01.journal.jsonl`, `.log`: distinct new attempt;
- `source_restore_repair_run01.completion.json`: controller's observed worker0,
  with exact receipt/journal hashes; it does not claim to observe its own exit;
- `source_restore_repair_run01.outer_exit.json`: wrapper's actual observed
  controller exit, with receipt/controller-completion/wrapper bindings.

No success may be inferred from a child receipt alone. Nonzero outer exit,
missing outer record, interrupted/failed journal or incomplete18 blocks Step B.
The reported06:08 resource snapshot is history; dot rechecks current resources.

## Only after actual successful repair: original CPU acceptance gate

Do not run this command now solely because code/tests pass. The parent first
checks actual18/18 and wrapper exit0, all new/old hashes and the new journal.
The new source_cpu_acceptance review must bind the **new** repair receipt SHA
and postdate the observed outer exit; dot issues its separate fresh slot.
The acceptance adapter permits only the explicitly named repaired receipt and
checks all those provenance/exit bindings before and after the original CPU
acceptance. The original ordinary-success receipt path remains compatible;
the actual old RUNNING receipt still cannot pass.

```bash
(
set -eu
set -C
: "${P1_SOURCE_REPAIR_DIR:?verified fixed repair bundle}"
: "${P1_SOURCE_REPAIR_REVISION:?fixed new code commit}"
: "${P1_REPAIR_ARCHIVE:?actual original442155-byte successful runtime repair archive}"
: "${P1_FULL_DIAGNOSTIC_ARCHIVE:?actual recovered134436-byte historical evidence}"
: "${P1_FORMAL_DIAGNOSTIC_ARCHIVE:?actual recovered12299-byte historical evidence}"
: "${P1_SOURCE_ACCEPT_REVIEW:?actual post-success parent source_cpu_acceptance review}"
: "${P1_SOURCE_ACCEPT_SLOT:?fresh source_cpu_acceptance slot}"
timeout --signal=TERM --kill-after=5s 300s \
  /workspace/paper1-training-runtime-cp312-run01/bin/python -I -B \
  "$P1_SOURCE_REPAIR_DIR/accept_repaired_runtime_source.py" \
  --acceptance-revision "$P1_SOURCE_REPAIR_REVISION" \
  --code-dir /workspace/paper1-metadata-code-1efe9d1 \
  --repair-archive "$P1_REPAIR_ARCHIVE" \
  --runtime-receipt /workspace/paper1-training-runtime-cp312-run01/runtime_repair_run01.json \
  --diagnostic-package "$P1_FULL_DIAGNOSTIC_ARCHIVE" \
  --formal-acceptance-package "$P1_FORMAL_DIAGNOSTIC_ARCHIVE" \
  --source-restore-receipt /workspace/paper1-source-recovery-run01/source_restore_repair_run01.json \
  --data-dir /workspace/paper1-source-recovery-run01 \
  --output-dir /workspace/paper1-repaired-source-acceptance-run01 \
  --review-record "$P1_SOURCE_ACCEPT_REVIEW" \
  --priority-receipt "$P1_SOURCE_ACCEPT_SLOT" \
  --log-file /workspace/paper1-repaired-source-acceptance-run01.log \
  > /workspace/paper1-repaired-source-acceptance-run01.log 2>&1
)
```

The output/attempt/log must remain unconsumed, as in the original acceptance
protocol. Keep300s watchdog/310s slot headroom and all strict source/runtime,
private evidence and Paper2 gates. The code package does not restore or probe
targets, repeat science, initialize CUDA, fit a model, stop/restart the Pod or
change any financial authorization. Dot alone operates the server.
