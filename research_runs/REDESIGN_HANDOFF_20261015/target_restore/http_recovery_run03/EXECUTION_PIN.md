# Run03 fixed execution pin

**Execution revision:** `be83d6116fd8c010c91984b56a06364d3d34f234`.
Branch: `research/paper1-handoff-20261014`.

| Item | SHA256 |
|---|---|
| `target_restore_run03.py` | `11e02a4f487a74a46ba99567f82d2642f1785323afc2eb58871ec799a7887947` |
| `RUN_RUN03_ONCE.sh` | `ee3ed081f01c40d09e8ea0d15a273cd9b39991ce5d8c2ea4b7aedfaed74636ec` |
| Unchanged single-hop adapter | `7a717fd63b4c0945e2a232c7560f475b5618c3c992c069cb9f451a569e5d4716` |
| Six-file execution bundle index | `ed0fb3c573bdffca3a865f992462fd9bbb060591beedddf07ef5ac8bd7dc93d3` |

The six-file bundle is51902 bytes. It appends the new controller/wrapper and
unissued templates, and reuses the exact adapter if already present. It
contains no environment, raw EEG or model. Fifteen focused integration/outer
identity tests passed; the31 transport tests and source/scientific acceptance
were not rerun. Independent controller/wrapper review passed.

## 1. Append/reuse only these fixed code and metadata files

This fetch uses the existing small code directory. Existing files must
already match the frozen SHA; mismatches/partials are preserved and stop.
No old code, data, runtime or claim is overwritten.

```bash
(
set -eu
P1_RUN03_REVISION=be83d6116fd8c010c91984b56a06364d3d34f234
P1_RUN03_CODE=/workspace/paper1-official-transition-code-run01
P1_RUN03_ORIGIN="https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/$P1_RUN03_REVISION"
P1_RUN03_INDEX=/tmp/paper1-run03-be83d611-bundle.sha256
test -d "$P1_RUN03_CODE"
test ! -L "$P1_RUN03_CODE"
test ! -L "$P1_RUN03_INDEX"
if [ ! -e "$P1_RUN03_INDEX" ]; then
  curl --fail --silent --show-error --proto '=https' --tlsv1.2 --retry 0 \
    --connect-timeout 10 --max-time 30 --max-filesize 16384 \
    "$P1_RUN03_ORIGIN/research_runs/REDESIGN_HANDOFF_20261015/target_restore/http_recovery_run03/EXECUTION_BUNDLE_SHA256SUMS.txt" \
    -o "$P1_RUN03_INDEX"
fi
printf '%s  %s\n' ed0fb3c573bdffca3a865f992462fd9bbb060591beedddf07ef5ac8bd7dc93d3 "$P1_RUN03_INDEX" | sha256sum -c -
P1_RUN03_COUNT=0
while read -r P1_RUN03_SHA P1_RUN03_REL P1_RUN03_EXTRA; do
  test -z "$P1_RUN03_EXTRA"
  case "$P1_RUN03_REL" in
    research_runs/REDESIGN_HANDOFF_20261015/target_restore/target_restore_run03.py|research_runs/REDESIGN_HANDOFF_20261015/target_restore/RUN_RUN03_ONCE.sh|research_runs/REDESIGN_HANDOFF_20261015/official_edf_transport/nemar_single_hop.py|research_runs/REDESIGN_HANDOFF_20261015/target_restore/http_recovery_run03/parent_run03_review.PLAN_ONLY.json|research_runs/REDESIGN_HANDOFF_20261015/target_restore/http_recovery_run03/run03_slot.PLAN_ONLY.json|research_runs/REDESIGN_HANDOFF_20261015/target_restore/http_recovery_run03/outer_run03.PLAN_ONLY.json) ;;
    *) exit 3 ;;
  esac
  P1_RUN03_DEST="$P1_RUN03_CODE/$P1_RUN03_REL"
  /usr/bin/python3 -I -B - "$P1_RUN03_DEST" <<'PY_PATH'
from pathlib import Path
import sys
p=Path(sys.argv[1])
if any(x.is_symlink() for x in (p,*p.parents)):
    raise SystemExit('Code destination symlink rejected; preserve it.')
PY_PATH
  if [ ! -e "$P1_RUN03_DEST" ]; then
    mkdir -p -- "$(dirname -- "$P1_RUN03_DEST")"
    curl --fail --silent --show-error --proto '=https' --tlsv1.2 --retry 0 \
      --connect-timeout 10 --max-time 30 --max-filesize 65536 \
      "$P1_RUN03_ORIGIN/$P1_RUN03_REL" -o "$P1_RUN03_DEST"
  fi
  printf '%s  %s\n' "$P1_RUN03_SHA" "$P1_RUN03_DEST" | sha256sum -c -
  P1_RUN03_COUNT=$((P1_RUN03_COUNT + 1))
done < "$P1_RUN03_INDEX"
test "$P1_RUN03_COUNT" -eq 6
)
```

## 2. Genuine new parent review and dot slot

Dot prepares `/workspace/paper1-target-dispatch-20261015-run03`, then parent
issues `parent-run03-review.json` from the new parent template and dot issues
`target-raw-slot.json` from the new slot template. The template status/issuer,
null timestamps/revision and false authority fields deliberately cannot pass.
Use this execution revision, exact SHA fields and actual noninterference/free
space observations; do not reuse the consumed run02 review/slot. Preserve the
false fit/scientific/credential/resource-purchase fields and existing deadline.
Review must precede the new slot and cover its full bounded command.

The historical HEAD input path below is taken from the actual run02 argv.
Both old actual outer paths and all six old cache records are bound by exact
SHA. Missing/different old metadata stops; do not synthesize replacement
history or rerun a diagnostic. No cost/balance prerequisite is introduced.

## 3. Exact single dispatch

After those genuine files exist, execute once:

```bash
P1_RUN03_REVISION=be83d6116fd8c010c91984b56a06364d3d34f234 \
P1_RUN03_REVIEW=/workspace/paper1-target-dispatch-20261015-run03/parent-run03-review.json \
P1_RUN03_SLOT=/workspace/paper1-target-dispatch-20261015-run03/target-raw-slot.json \
P1_RUN03_HEAD=/workspace/paper1-target-dispatch-20261015-run01/same-pod-first-object-head-run01.json \
bash /workspace/paper1-official-transition-code-run01/research_runs/REDESIGN_HANDOFF_20261015/target_restore/RUN_RUN03_ONCE.sh
```

The wrapper records actual process exit, including nonzero/timeout, under
the new dispatch's `completion.json` and `observed_outer.json`. It does not
detach a second worker or claim controller startup from a shell launch.
Dot may supervise it through its existing authorized process mechanism.
This command is a single foreground operation; do not issue it a second time.

Progress is the new cache `target_restore_run03.journal.jsonl`; the verified
byte receipt is `target_bytes_receipt_run03.json`, summary
`target_restore_run03.json`. Require real174/174 and actual outer0 before
considering raw recovery complete. Old claims/failures remain intact;
partial/unknown/hash mismatch preserves evidence and stops without retry.
No training or production-preparation command is part of this raw dispatch.
