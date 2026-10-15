# Separate production supplement — never delay or modify the raw recovery pin

**Production code commit:** `ebd024aee8eca2f5655c8ddcd9d51cbc94c5b693`.
**Raw recovery remains:** `5e58526918169a15080cc79e3c44d8024e24f911`.

Dot can execute the independently delivered raw restoration immediately after
its real raw review/slot. This later supplement is neither its prerequisite
nor permission to restart it. It only supplies the completed cache-routing
adapter, unchanged frozen metadata and unissued preparation templates.

| Item | SHA256 |
|---|---|
| `prepare_official.py` | `c75a025b9e632d9b06400ef71e85b77efd8b33508decad1400c1566d7fa34cc4` |
| Frozen23-dependency list | `5d193bfc68cc775435301630122b4a5ac1c4ff0f910e6a14356e64eb1cda26d7` |
| Fourteen-file supplement manifest | `1e3f2867101f54c2141fe7bb65db2dab9dd606accf133fe108bfdfd8432816ff` |

The supplement is153761 bytes in14 source/metadata files, disjoint from the
ten immutable raw bundle paths. No environment, CUDA library, EEG, checkpoint
or credential is included. Eight production-specific tests passed; the
separate raw entry has eight tests. Independent review verified the original
scientific preparation suffix has identical AST and all23 existing scientific
dependencies match frozen1efe bytes. Original scientific files are unchanged.

## Append only the verified missing supplement files

The following code fetch performs no scientific operation and issues no grant.
It preserves every existing raw file and refuses any mismatched existing
supplement. It can be scheduled independently while dot manages raw recovery,
provided dot confirms no impact on the active operation or Paper2.

```bash
(
set -eu
P1_PRODUCTION_REVISION=ebd024aee8eca2f5655c8ddcd9d51cbc94c5b693
P1_PROD_CODE=/workspace/paper1-official-transition-code-run01
test -d "$P1_PROD_CODE"
test ! -L "$P1_PROD_CODE"
printf '%s  %s\n' \
  95fb6dc01b61da863441d16b1d559ce5f9cfa07f87e65df42029b46272439063 \
  "$P1_PROD_CODE/EXECUTION_BUNDLE_SHA256SUMS.txt" | sha256sum -c -
(cd "$P1_PROD_CODE" && sha256sum -c EXECUTION_BUNDLE_SHA256SUMS.txt)
P1_PROD_MANIFEST="$P1_PROD_CODE/PRODUCTION_SUPPLEMENT_SHA256SUMS.txt"
test ! -e "$P1_PROD_MANIFEST"
test ! -L "$P1_PROD_MANIFEST"
curl --fail --silent --show-error --proto '=https' --tlsv1.2 --retry 0 \
  --connect-timeout 10 --max-time 30 --max-filesize 16384 \
  "https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/$P1_PRODUCTION_REVISION/research_runs/REDESIGN_HANDOFF_20261015/official_production/PRODUCTION_SUPPLEMENT_SHA256SUMS.txt" \
  -o "$P1_PROD_MANIFEST"
printf '%s  %s\n' \
  1e3f2867101f54c2141fe7bb65db2dab9dd606accf133fe108bfdfd8432816ff "$P1_PROD_MANIFEST" \
  | sha256sum -c -
while read -r P1_PROD_SHA P1_PROD_REL P1_PROD_EXTRA; do
  test -z "$P1_PROD_EXTRA"
  [[ "$P1_PROD_SHA" =~ ^[0-9a-f]{64}$ ]]
  [[ "$P1_PROD_REL" =~ ^research_runs/[a-zA-Z0-9_./-]+$ ]]
  case "/$P1_PROD_REL/" in *'/../'*|*'/./'*|*'//'*) exit 3 ;; esac
  P1_PROD_DEST="$P1_PROD_CODE/$P1_PROD_REL"
  P1_PROD_PARENT="$P1_PROD_DEST"
  while [ "$P1_PROD_PARENT" != / ]; do
    test ! -L "$P1_PROD_PARENT"
    P1_PROD_PARENT=$(dirname -- "$P1_PROD_PARENT")
  done
  if [ ! -e "$P1_PROD_DEST" ]; then
    mkdir -p -- "$(dirname -- "$P1_PROD_DEST")"
    curl --fail --silent --show-error --proto '=https' --tlsv1.2 --retry 0 \
      --connect-timeout 10 --max-time 30 --max-filesize 2097152 \
      "https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/$P1_PRODUCTION_REVISION/$P1_PROD_REL" \
      -o "$P1_PROD_DEST"
  fi
  test -f "$P1_PROD_DEST"
  printf '%s  %s\n' "$P1_PROD_SHA" "$P1_PROD_DEST" | sha256sum -c -
done < "$P1_PROD_MANIFEST"
(cd "$P1_PROD_CODE" && sha256sum -c PRODUCTION_SUPPLEMENT_SHA256SUMS.txt)
printf '%s\n' 'PRODUCTION_CODE_SUPPLEMENT_VERIFIED_NO_DATA_PROCESSING_NO_FITS'
)
```

This is a code fetch only. The actual CPU preparation command, authentic
three-file prerequisites, route/target-outer binding and new review/slot are
in [DOT_TARGET_NEXT.md](../target_restore/DOT_TARGET_NEXT.md), steps2–3. Set
`P1_PRODUCTION_REVISION` to the production commit above; the earlier raw
command continues using its original `P1_TARGET_REVISION`5e585269.

Production execution needs the actual successful174-byte receipt, raw summary
and independently observed final raw exit0. It uses only the existing
`/workspace/paper1-training-runtime-cp312-run01` and original1efe checkout,
with separate source/raw/tensor paths and a new preparation review copy.
It does not create an execution registration, initialize fit counters or
install its output into the original job. A successful preparation remains
`TRAINING_STILL_BLOCKED` until authentic old fit/checkpoint/backup continuity
and future scheduling authority are resolved. Financial conditions stay
superseded; no cost query or new credential is required.
