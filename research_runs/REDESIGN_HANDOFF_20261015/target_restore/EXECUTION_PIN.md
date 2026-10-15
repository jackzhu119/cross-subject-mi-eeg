# Standalone174 EDF recovery pin — execute without waiting for production routing

**Raw execution commit:** `5e58526918169a15080cc79e3c44d8024e24f911`.
Branch: `research/paper1-handoff-20261014`.

This immutable delivery contains the completed raw-restoration entry and its
dependencies only. Production routing is separate work and is not a
prerequisite for this already authorized byte-only operation.

| Item | SHA256 |
|---|---|
| `target_restore_once.py` | `65507374bc7640d4c6b2b7d9b609d86b809a11d61a1aa55d61e6527ced4e5190` |
| Ten-file `EXECUTION_BUNDLE_SHA256SUMS.txt` | `95fb6dc01b61da863441d16b1d559ce5f9cfa07f87e65df42029b46272439063` |
| `FETCH_OFFICIAL_PREPARATION_CODE.sh` | `15ddb572fa3570ded83e6ef826f58d97d6bb5e4761c8abee62dd235ac781bda8` |
| Frozen174 EDF manifest | `2cfdf35aa7990df880826d1b84d1230e0bda3c9393c17d3ec6e27b7b311d2bf2` |

The ten-file operational bundle is269469 bytes. It contains no raw EEG,
checkpoint, credential, CUDA package, environment or production adapter.
Actual target payload is174 files /2515343396 bytes under CC-BY-4.0.
Eight focused tests passed, including a complete synthetic174-object run.
All19 newly committed files/dependencies were publicly fetched at this commit
and compared byte-for-byte successfully. No Pod or actual target transfer was
performed here.

## Fetch only the small fixed code bundle

Dot may fetch this reviewed code through the existing HTTPS terminal path:

```bash
(
set -eu
P1_TARGET_REVISION=5e58526918169a15080cc79e3c44d8024e24f911
curl --fail --silent --show-error --proto '=https' --tlsv1.2 --retry 0 \
  --connect-timeout 10 --max-time 30 \
  "https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/$P1_TARGET_REVISION/research_runs/REDESIGN_HANDOFF_20261015/target_restore/FETCH_OFFICIAL_PREPARATION_CODE.sh" \
  -o /tmp/paper1-fetch-target-code.sh
printf '%s  %s\n' \
  15ddb572fa3570ded83e6ef826f58d97d6bb5e4761c8abee62dd235ac781bda8 /tmp/paper1-fetch-target-code.sh \
  | sha256sum -c -
bash /tmp/paper1-fetch-target-code.sh \
  --revision "$P1_TARGET_REVISION" \
  --manifest-sha256 95fb6dc01b61da863441d16b1d559ce5f9cfa07f87e65df42029b46272439063
)
```

Destination is the new small code directory
`/workspace/paper1-official-transition-code-run01`. It refuses an existing
directory and never modifies the accepted checkout,97-package runtime or
18 source files. A fetch failure preserves its partial code directory; no
automatic retry or environment work is included.

## Exact single restoration command

After genuine parent review and dot's **fresh `target_raw_restore` slot**,
set `P1_TARGET_REVIEW` and `P1_TARGET_SLOT` to their actual new JSON paths.
Use the raw-only templates in the fetched bundle; neither template is a grant.
Fees and production routing are not prerequisites. The original scientific,
time, disk, Paper2 noninterference, strict byte/hash and single-claim gates
remain unchanged.

```bash
timeout --signal=TERM --kill-after=5s 1200s /usr/bin/python3 -I -B \
  /workspace/paper1-official-transition-code-run01/research_runs/REDESIGN_HANDOFF_20261015/target_restore/target_restore_once.py \
  --delivery-revision 5e58526918169a15080cc79e3c44d8024e24f911 \
  --source-restore-root /workspace/paper1-source-recovery-run01 \
  --source-acceptance-root /workspace/paper1-repaired-source-acceptance-run01 \
  --continuity-report /workspace/paper1-continuity-review-run01/continuity_review_run01.json \
  --review-record "${P1_TARGET_REVIEW:?actual approved raw-operation review JSON}" \
  --priority-receipt "${P1_TARGET_SLOT:?actual fresh target_raw_restore slot JSON}"
```

Dot should use [the same single command with actual exit/log capture](DOT_RAW_RESTORE_ONCE.md)
to retain the observed outer receipt for later routing. Lower the outer
timeout if the real parent review specifies a lower cap. No detached second
worker, restart, retry, training, environment repair or diagnostic is included.

Expected raw success is an actual exit0 plus mutually bound
`target_restore_run01.json` and `target_bytes_receipt.json`, all174 files
verified. An existing claim, unknown partial/member, byte/TLS failure or
uncertain exit stops and preserves evidence. A success-looking summary alone
is not final process success. Unknown original fit/backup state stays unknown;
the raw operation never initializes a ledger or authorizes a fit.
