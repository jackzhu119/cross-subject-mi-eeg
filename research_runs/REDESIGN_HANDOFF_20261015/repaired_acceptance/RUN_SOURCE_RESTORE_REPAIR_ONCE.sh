#!/usr/bin/env bash
# Dot only: record the actual controller exit without changing its claim/results.
set -eu
P1_REPAIR_BUNDLE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
P1_REPAIR_CACHE=/workspace/paper1-source-recovery-run01
P1_REPAIR_EXIT_RECORD="$P1_REPAIR_CACHE/source_restore_repair_run01.outer_exit.json"
if [ -e "$P1_REPAIR_EXIT_RECORD" ] || [ -L "$P1_REPAIR_EXIT_RECORD" ]; then
  echo 'Repair outer-exit record already exists; no retry.' >&2
  exit 3
fi
set +e
/usr/bin/python3 -I -B "$P1_REPAIR_BUNDLE/restore_source_after_failure_once.py" "$@"
P1_REPAIR_EXIT_CODE=$?
set -e
/usr/bin/python3 -I -B - "$P1_REPAIR_CACHE" "$P1_REPAIR_EXIT_CODE" "$0" <<'PY'
import hashlib,json,os,stat,sys
from datetime import datetime,timezone
from pathlib import Path
root=Path(sys.argv[1]); code=int(sys.argv[2]); wrapper=Path(sys.argv[3]).absolute()
if any(p.is_symlink() for p in (root,*root.parents,wrapper)):
    raise SystemExit('Outer evidence path must not be a symlink.')
value={'status':'OBSERVED_SOURCE_REPAIR_PROCESS_EXIT','exit_code':code,
       'observed_at_utc':datetime.now(timezone.utc).isoformat(),'source_root':str(root),
       'wrapper_sha256':hashlib.sha256(wrapper.read_bytes()).hexdigest(),
       'prior_source_restore_failure_archive_sha256':'89f8b8b05dc2b94a97038e6800fb94238081e63657e2b1492361da2aa4d7c536',
       'training_authorization':False,'new_fits':0}
for name,key in [('source_restore_repair_run01.json','receipt_sha256'),
                 ('source_restore_repair_run01.completion.json','controller_completion_sha256')]:
    path=root/name
    if path.is_symlink():raise SystemExit('Outer evidence member symlink forbidden.')
    if path.exists():
        info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size>131072:raise SystemExit('Bounded regular metadata required.')
        value[key]=hashlib.sha256(path.read_bytes()).hexdigest()
    else:value[key]=None
path=root/'source_restore_repair_run01.outer_exit.json'
with path.open('x') as stream:
    json.dump(value,stream,sort_keys=True);stream.write('\n');stream.flush();os.fsync(stream.fileno())
PY
exit "$P1_REPAIR_EXIT_CODE"
