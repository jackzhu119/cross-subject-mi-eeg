# Immutable repair code and exact dot handoff

Repair code commit:
**`461d079eca6e91addcfb59de944b966e51e1b30b`** on
`research/paper1-handoff-20261014`.
All 14 files changed in that commit passed immutable public byte readback.
See [the readback record](PUBLIC_REPAIR_CODE_READBACK.json).
The later documentation commit does not change this execution pin.

| Small code bundle file | SHA256 |
|---|---|
| `repair_preparation_once.py` | `a6d6b30bdbda3594bf459cbc98031b82f3f2e7fe76fc26a29d15b687303375fc` |
| `manpage_policy.py` | `701cf5e37461307776ef8f476655366cb4cb49619fc63ee7600e6ec1cb62a9b5` |
| `frozen_wheel_cache_index.json` | `8a973c03b28297a5c533b8f86ea62a83da82b246197a99dd929a2d21494d51bf` |

The invalid parent-review template SHA is
`5982154ff4acd6552e3bee9ba8df34127230dfd2ef89bdb123ba97b39c65526f`.
The parent must review the three files and supply an actual new record; merely
downloading or editing the template does not establish that review.

## Obtain only the small code/metadata bundle

This command is for dot's delivery/review stage. It fetches public source and
the invalid review template, no wheel, EEG or environment. It does not invoke
the repair or request a slot. The directory must be absent; do not delete an
existing directory to force another attempt.

```bash
(
set -eu
P1_REPAIR_DIR=/workspace/paper1-repair-code-461d079e
P1_REPAIR_REVISION=461d079eca6e91addcfb59de944b966e51e1b30b
mkdir -m 700 "$P1_REPAIR_DIR"
P1_REPAIR_BASE="https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/$P1_REPAIR_REVISION/research_runs/REDESIGN_HANDOFF_20261015/repair_run01"
for P1_REPAIR_FILE in repair_preparation_once.py manpage_policy.py frozen_wheel_cache_index.json repair_parent_review.PLAN_ONLY.json; do
  curl -fSsL --proto '=https' --tlsv1.2 --max-time 60 \
    "$P1_REPAIR_BASE/$P1_REPAIR_FILE" -o "$P1_REPAIR_DIR/$P1_REPAIR_FILE"
done
cd "$P1_REPAIR_DIR"
sha256sum -c <<'SHA256'
a6d6b30bdbda3594bf459cbc98031b82f3f2e7fe76fc26a29d15b687303375fc  repair_preparation_once.py
701cf5e37461307776ef8f476655366cb4cb49619fc63ee7600e6ec1cb62a9b5  manpage_policy.py
8a973c03b28297a5c533b8f86ea62a83da82b246197a99dd929a2d21494d51bf  frozen_wheel_cache_index.json
5982154ff4acd6552e3bee9ba8df34127230dfd2ef89bdb123ba97b39c65526f  repair_parent_review.PLAN_ONLY.json
SHA256
)
```

## Single invocation after actual parent review and a new slot

Parent binds `repair_revision` to the code commit above, the three SHA values,
original archive/resolution/donor identities, actual review times/notes and all
review conditions in [DOT_REPAIR_NEXT.md](DOT_REPAIR_NEXT.md). Dot then checks
Paper 2 noninterference and supplies a new, active `runtime_preparation` slot.
No old slot may be extended or reused. Both clocks end by
2026-10-16 09:54:00 UTC; wall cap is 1200 seconds or less.

`P1_PRIOR_CONTROLLER` is the original fixed b078 source file, not its log.
The reported path `/tmp/paper1-prepare-runtime-b07892c3.py` must be checked,
not assumed. Its SHA is
`7a1fbc9b364c8dd42faf6894450ae065a49d59a977d4c5470a3c2daffff50cc3`.
The exact public fallback source, if genuinely missing, is
[the original b078 controller](https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/b07892c320e25e3465c50ea3a31d1a21bf722df3/research_runs/REDESIGN_HANDOFF_20261015/runtime_preparation/prepare_runtime_only.py);
retrieving its source is not permission to rerun its preparation main.

```bash
(
set -eu
: "${P1_PRIOR_CONTROLLER:?actual original b078 controller path}"
: "${P1_FAILURE_ARCHIVE:?actual original 423996-byte failure tar.gz path}"
: "${P1_REPAIR_REVIEW:?new independently completed dot_parent repair-review file}"
: "${P1_REPAIR_SLOT:?NEW active dot runtime_preparation slot AFTER that review}"
/usr/bin/python3 -I -B /workspace/paper1-repair-code-461d079e/repair_preparation_once.py \
  --repair-revision 461d079eca6e91addcfb59de944b966e51e1b30b \
  --prior-controller "$P1_PRIOR_CONTROLLER" \
  --code-dir /workspace/paper1-metadata-code-1efe9d1 \
  --failure-archive "$P1_FAILURE_ARCHIVE" \
  --donor-report /workspace/paper1-cp312-metadata-20261015-run01/gpu_donor_inventory.json \
  --review-record "$P1_REPAIR_REVIEW" --priority-receipt "$P1_REPAIR_SLOT" \
  --log /workspace/paper1-repair-run01.log
)
```

All 79 cached wheel bytes and the actual pip-only partial are checked before
the exclusive single-use journal. Successful repair writes only the distinct
`runtime_repair_run01.json`, status
`REPAIRED_PREPARED_IMPORT_SOURCE_REVIEW_PENDING`. It never writes the missing
original preparation receipt. Any consumed/failed repair requires a new
independent decision, not another invocation, path removal or renamed partial.

The 89 focused local CPU tests passed; their JUnit and scope are preserved in
[VALIDATION.json](VALIDATION.json). They are not a claim of actual Pod repair,
real training-runtime imports, strict source acceptance or training authority.
No scientific pin/hash, original $10/8 cumulative GPU-hour budget, old ledger,
fit/update counter or deadline was reset. Unknown costs remain unknown.
