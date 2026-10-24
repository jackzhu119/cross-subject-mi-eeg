#!/usr/bin/env bash
# Update only the login-side submitter; reuse the installed environment and data.
set -euo pipefail
CODE_ROOT="${PAPER1_CODE_ROOT:-/public/home/zhuziyuan/projects/PAPER1_HPC_20261023}"
PROJECT="${PAPER1_PROJECT:-/public/home/zhuziyuan/projects/paper1-risk-v1}"
PYTHON_BIN="${PAPER1_PYTHON:-/public/home/zhuziyuan/.venvs/paper3-hpc-cu121-offline/bin/python}"
MODULE_SHA="1061f9a6ee1cfb9f9808c71989456d62f323f5b2978ee23195ad453ecc235115"
MODULE_BLOB="055acd83b28418c89199db48a66dc7f4dde2bebe"
TARGET="$CODE_ROOT/hpcmi/submit_single.py"
CACHE="$PROJECT/state/submission-code-repair"
mkdir -p "$CACHE"
exec 9>"$CACHE/update.lock"
if ! flock -n 9; then
  printf 'Another submission-code update is active; no duplicate update started.\n'
  exit 0
fi
if [ ! -f "$TARGET" ] || [ ! -f "$CODE_ROOT/LAUNCH.sh" ] || [ ! -x "$PYTHON_BIN" ]; then
  printf 'The existing school runtime or installed submission entry was not found.\n' >&2
  exit 2
fi
OBSERVED="$(sha256sum "$TARGET")"
if [ "${OBSERVED%% *}" != "$MODULE_SHA" ]; then
  PAYLOAD="$CACHE/$MODULE_SHA.py"
  if [ ! -f "$PAYLOAD" ]; then
    curl -4 -f --connect-timeout 8 --max-time 60 --speed-time 30 --speed-limit 128 --retry 1 \
      -H 'Accept: application/vnd.github.raw+json' \
      "https://api.github.com/repos/jackzhu119/cross-subject-mi-eeg/git/blobs/$MODULE_BLOB" -o "$PAYLOAD.part"
    RECEIVED="$(sha256sum "$PAYLOAD.part")"
    if [ "${RECEIVED%% *}" != "$MODULE_SHA" ]; then
      printf 'Downloaded submitter checksum differs; existing code retained.\n' >&2
      exit 2
    fi
    mv "$PAYLOAD.part" "$PAYLOAD"
  fi
  "$PYTHON_BIN" - "$PAYLOAD" "$TARGET" "$CACHE" "$MODULE_SHA" <<'UPDATE_MODULE'
import hashlib,os,sys,tempfile
from pathlib import Path
source,target,cache=map(Path,sys.argv[1:4]); expected=sys.argv[4]
payload=source.read_bytes()
assert hashlib.sha256(payload).hexdigest()==expected,'Submission update SHA mismatch'
compile(payload,str(target),'exec')
before=target.read_bytes()
backup=cache/('before-'+hashlib.sha256(before).hexdigest()+'.py')
if not backup.exists():
    backup.write_bytes(before)
fd,temporary=tempfile.mkstemp(prefix=target.name+'.',suffix='.tmp',dir=target.parent)
try:
    with os.fdopen(fd,'wb') as stream:
        stream.write(payload);stream.flush();os.fsync(stream.fileno())
    os.chmod(temporary,0o644)
    os.replace(temporary,target)
finally:
    if os.path.exists(temporary):os.unlink(temporary)
print('Submission-only update ready. Existing environment, data, checkpoints and failure ledger retained.',flush=True)
UPDATE_MODULE
fi
# Release this short update lock before any token prompt or environment reuse.
flock -u 9
exec 9>&-
# This enters the existing submitter and its independent scheduler deduplication.
exec bash "$CODE_ROOT/LAUNCH.sh" --project "$PROJECT" "$@"
