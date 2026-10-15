# Fixed original-job metadata continuation entry

Code commit: **`6710cf4e14c6182896668320fe96dfd3efa1e901`** on
`research/paper1-handoff-20261014`.

| Source | SHA256 |
|---|---|
| `continuity_resume/continuity_review.py` | `2d7904b7787c92449dd0ffe7b56c09327ffb803eb942a417fd0e2fabad0fd8d7` |
| unchanged `runtime/priority_gate.py` | `eb88b6c75381a714bd91d9b0bb0acb4fd82edf295b73a25abed4f0236c054fff` |

Six focused synthetic tests pass. All16 changed code-commit files plus the
existing priority gate were fetched at the fixed public commit and compared
byte-for-byte: **17/17 match**. The16 frozen scientific/execution files bound
by the acceptance report remain unchanged. This is local/offline code review
and GitHub readback, not a new Pod observation or training receipt.

## Exact command for dot, after its new metadata slot check

Dot sets `P1_SLOT` to the **actual newly issued metadata-slot JSON path**, not
the consumed CPU acceptance slot or a template. The slot requirements and
optional genuine backup metadata are specified in [DOT_CONTINUITY_NEXT.md](DOT_CONTINUITY_NEXT.md).
No new secret, package environment, full checkout, EEG transfer or GPU query
is involved. This downloads only28904 bytes of fixed Python source; the output
directory must not already exist. Financial prerequisites are superseded.

```bash
(
set -eu
: "${P1_SLOT:?dot must supply its new active noninterfering metadata slot JSON}"
P1_PIN=6710cf4e14c6182896668320fe96dfd3efa1e901
P1_REVIEW_DIR=/workspace/paper1-continuity-review-run01
P1_OLD_REVIEW_ROOT="${P1_OLD_REVIEW_ROOT:-/workspace/mi-eeg-cloud}"
test -f "$P1_SLOT"
test ! -e "$P1_REVIEW_DIR"
test ! -L "$P1_REVIEW_DIR"
mkdir -m 700 -- "$P1_REVIEW_DIR"

curl --fail --silent --show-error --proto '=https' --tlsv1.2 \
  --retry 0 --connect-timeout 10 --max-time 30 --max-filesize 32768 \
  "https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/$P1_PIN/research_runs/REDESIGN_HANDOFF_20261015/continuity_resume/continuity_review.py" \
  -o "$P1_REVIEW_DIR/continuity_review.py"
curl --fail --silent --show-error --proto '=https' --tlsv1.2 \
  --retry 0 --connect-timeout 10 --max-time 30 --max-filesize 32768 \
  "https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/$P1_PIN/research_runs/REDESIGN_HANDOFF_20261015/runtime/priority_gate.py" \
  -o "$P1_REVIEW_DIR/priority_gate.py"
printf '%s  %s\n' \
  2d7904b7787c92449dd0ffe7b56c09327ffb803eb942a417fd0e2fabad0fd8d7 "$P1_REVIEW_DIR/continuity_review.py" \
  eb88b6c75381a714bd91d9b0bb0acb4fd82edf295b73a25abed4f0236c054fff "$P1_REVIEW_DIR/priority_gate.py" \
  | sha256sum -c -

set +e
timeout --signal=TERM --kill-after=5s 60s /usr/bin/python3 -I -B \
  "$P1_REVIEW_DIR/continuity_review.py" \
  --source-restore-root /workspace/paper1-source-recovery-run01 \
  --source-acceptance-root /workspace/paper1-repaired-source-acceptance-run01 \
  --old-work-root "$P1_OLD_REVIEW_ROOT" \
  --priority-gate "$P1_REVIEW_DIR/priority_gate.py" \
  --priority-receipt "$P1_SLOT" \
  --output "$P1_REVIEW_DIR/continuity_review_run01.json" \
  > "$P1_REVIEW_DIR/continuity_review_run01.log" 2>&1
P1_REVIEW_EXIT=$?
set -e
printf '%s\n' "$P1_REVIEW_EXIT" > "$P1_REVIEW_DIR/exit-code.txt"
cat "$P1_REVIEW_DIR/continuity_review_run01.log"
if [ -f "$P1_REVIEW_DIR/continuity_review_run01.json" ]; then
  sha256sum "$P1_REVIEW_DIR/continuity_review_run01.json" \
    > "$P1_REVIEW_DIR/report.sha256"
  cat "$P1_REVIEW_DIR/report.sha256"
fi
exit "$P1_REVIEW_EXIT"
)
```

If an authentic old review root or backup metadata is available, supply it
before this first attempt as described in the handoff. The default old path
is only a request to inspect, not a claim that it exists. Missing records
produce explicit unknowns, not an initialized ledger or training permission.

If the command fails or times out, retain the directory, log and exit code;
do not delete, overwrite or automatically retry it. If it exits0, return the
JSON/log/exit/checksum for continuity review. Do not run the old `--resume`
launcher or fit from this metadata result. Paper2 remains GPU priority.
