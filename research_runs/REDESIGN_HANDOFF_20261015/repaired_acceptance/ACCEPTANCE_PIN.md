# Fixed repaired-runtime recovery code

**Historical30-minute delivery.** The author has since approved48-hour CPU
recovery availability. Use [AUTHOR48_PIN.md](AUTHOR48_PIN.md) and its new
gate/author-record bundle for the current operation. Keep this old immutable
pin as evidence; do not mix its gate SHA with the new author window or ask
for the same time approval again.

Execution code commit:
**`8766036b1b5b8f76d07f5bb015d653f242cafc11`**.
Branch: `research/paper1-handoff-20261014`.
All 22 files in that code commit passed immutable public byte readback;
[the actual record](PUBLIC_CODE_READBACK.json) preserves bytes and SHA values.
The final documentation commit does not change this execution pin.

| Execution file | SHA256 |
|---|---|
| `acceptance_gate.py` | `e17e366adc496e95e8620b4e4121107651b4f98eeebc4de147a17d818449a6c2` |
| `restore_source_once.py` | `2ee6355f51b29bbeedd30f8422c078af76615c26873e16826156ebc015d7f220` |
| `accept_repaired_runtime_source.py` | `83c30546f693511c7eee80d4520eb0cab70a945530e0321db575b7c75d25a7ca` |

The parent can review all pinned files off-host now. Any subsequent Pod command,
including placing this small source bundle, needs dot's new actual review/slot.
Do not execute the block below merely because it is public. No old slot is
renewed, no secret is required, and no author CPU-hour exception is inferred.
Follow the [accounting decision and two operation gates](DOT_NEXT.md) first.

## Small public code bundle, after the deployment/scope check

Dot may obtain these seven small source/invalid-template files within its
explicitly reviewed delivery/source-restoration operation window. The same
absolute author-approved CPU window covers delivery, restoration, review
handoff and acceptance; downloading code does not start a fresh allowance.
Dot's existing outside-Pod supervisor must bound this delivery to that window;
the new Python gate cannot govern a curl before it has been delivered.

The new folder must be absent. Do not replace, delete or rename an existing
folder to retry. No repository clone, environment, wheel or EEG is downloaded
by this block. All URLs are immutable public GitHub source/JSON URLs.

```bash
(
set -eu
P1_ACCEPT_DIR=/workspace/paper1-acceptance-code-8766036b
P1_ACCEPT_REVISION=8766036b1b5b8f76d07f5bb015d653f242cafc11
mkdir -m 700 "$P1_ACCEPT_DIR"
P1_ACCEPT_BASE="https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/$P1_ACCEPT_REVISION/research_runs/REDESIGN_HANDOFF_20261015/repaired_acceptance"
for P1_ACCEPT_FILE in acceptance_gate.py restore_source_once.py accept_repaired_runtime_source.py source_restore_review.PLAN_ONLY.json source_restore_slot.PLAN_ONLY.json source_acceptance_review.PLAN_ONLY.json source_acceptance_slot.PLAN_ONLY.json; do
  curl -fSsL --proto '=https' --tlsv1.2 --max-time 30 \
    "$P1_ACCEPT_BASE/$P1_ACCEPT_FILE" -o "$P1_ACCEPT_DIR/$P1_ACCEPT_FILE"
done
cd "$P1_ACCEPT_DIR"
sha256sum -c <<'SHA256'
e17e366adc496e95e8620b4e4121107651b4f98eeebc4de147a17d818449a6c2  acceptance_gate.py
2ee6355f51b29bbeedd30f8422c078af76615c26873e16826156ebc015d7f220  restore_source_once.py
83c30546f693511c7eee80d4520eb0cab70a945530e0321db575b7c75d25a7ca  accept_repaired_runtime_source.py
4d7b8480dc1752a64aaa84d9358a411b5efaf62c1c178993b11758b3cc9a8637  source_restore_review.PLAN_ONLY.json
752fd1b9f6f03903d930e5355423072af1364c1cd4c8f719988633d8f9c1a18e  source_restore_slot.PLAN_ONLY.json
83936c23108d2c73f15fffc17639a8ad86d9d56f4db658646da0cc561f89ff5b  source_acceptance_review.PLAN_ONLY.json
28c76079196b6575cd07dd14c2272a4753b2f1cca28e3176ac5a1418edfd3830  source_acceptance_slot.PLAN_ONLY.json
SHA256
)
```

The committed templates are deliberately invalid. Parent-supplied approved
records must be separate files. Parent reviews actual scope, real author
exception provenance, complete refreshed dollar bound, Paper 2 noninterference,
resource envelope and the exact code SHA; it must not auto-flip the booleans.

## Exact values for both subsequent operation commands

After delivery validation, these non-secret variables select this one pin:

```bash
export P1_ACCEPT_DIR=/workspace/paper1-acceptance-code-8766036b
export P1_ACCEPT_REVISION=8766036b1b5b8f76d07f5bb015d653f242cafc11
```

Use [DOT_NEXT.md Step A](DOT_NEXT.md#step-a--restore-the-18-source-originals-with-a-new-source-only-slot)
for the exact source-restoration command. Its parent review binds
`operation=source_raw_restore`, `operation_script_sha256=2ee6355f…`, this
`delivery_revision`, the gate SHA above, the actual CPU exception SHA/window,
and `source_restore_receipt_sha256=null`. Dot's slot must have the same exact
operation. A metadata/runtime_preparation/old source slot is rejected.

After successful source restoration, the parent reviews that complete result
and its actual receipt SHA before issuing Step B's review. Use
[DOT_NEXT.md Step B](DOT_NEXT.md#step-b--one-actual-repaired-runtime-cpu-source-acceptance)
for the full invocation including the original evidence paths, mandatory
source-restoration receipt, noclobber log and process-group timeout300s.
The review binds `operation=source_cpu_acceptance`,
`operation_script_sha256=83c30546…`, this same delivery/gate identity, the same
grant/window and the full actual source-restoration receipt SHA. Its
`maximum_wall_seconds` must be exactly300; at least310 seconds of slot/review
headroom must remain before imports. No second half-hour is granted.

Both actual records must use complete 64-character SHA values, not the
abbreviations in the prose above. They must be active UTC records after the
real repair, within the same <=30-minute approved absolute window and no later
than2026-10-16 09:54UTC. A narrower approved window stays narrower. The source
raw stage has a maximum1200 seconds; the actual slot/window can be tighter.

## Evidence and boundaries for parent review

- [Independent full repair archive review](INDEPENDENT_REPAIR_AUDIT.json).
- [Targeted validation and protected scientific hashes](VALIDATION.json):
  167 local CPU synthetic tests, no failures/errors/skips. This is software
  verification, not an actual Pod runtime or source acceptance.
- [Concrete billing proposal](ACCOUNTING_REVIEW_0449UTC.md), with two conditional
  dollar scenarios, a smaller finite alternative and the necessary explicit
  allocation-hour exception. The original fit validator is not passed or edited.
- [Detailed no-repair-repeat/source/acceptance handoff](DOT_NEXT.md).

Expected future raw status:
`SOURCE18_EXACT_BYTES_RESTORED_NUMERICAL_ACCEPTANCE_PENDING`.
Expected future accepted-runtime/source status:
`REPAIRED_ACTUAL_TRAINING_RUNTIME_SOURCE_MATCH_OTHER_GATES_PENDING`.
Neither is observed in this delivery. Original failed preparation and new
repair retain their identities. GPU computation, old task/cost/checkpoint/
backup transition, target restoration/mapping and fit authorization stay
separate; target data or extra experiments are never used to open these gates.
