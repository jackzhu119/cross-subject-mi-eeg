#!/usr/bin/env bash
# Dot-only single dispatch. This wrapper records the actual outer process exit.
set -eu
P1_RUN03_CODE=/workspace/paper1-official-transition-code-run01/research_runs/REDESIGN_HANDOFF_20261015/target_restore
P1_RUN03_DISPATCH=/workspace/paper1-target-dispatch-20261015-run03
P1_RUN03_CONTROLLER_SHA=11e02a4f487a74a46ba99567f82d2642f1785323afc2eb58871ec799a7887947
P1_RUN03_REVISION=${P1_RUN03_REVISION-}
P1_RUN03_REVIEW=${P1_RUN03_REVIEW-}
P1_RUN03_SLOT=${P1_RUN03_SLOT-}
P1_RUN03_HEAD=${P1_RUN03_HEAD-}

if [ "$#" -ne 0 ]; then
  echo 'Run03 wrapper accepts only the four documented environment fields.' >&2
  exit 3
fi

set +e
/usr/bin/python3 -I -B - "$0" "$P1_RUN03_CODE" "$P1_RUN03_DISPATCH" \
  "$P1_RUN03_CONTROLLER_SHA" "$P1_RUN03_REVISION" "$P1_RUN03_REVIEW" \
  "$P1_RUN03_SLOT" "$P1_RUN03_HEAD" "$$" <<'PY_PREFLIGHT'
from datetime import datetime, timezone
import hashlib, json, os, re, stat, sys
from pathlib import Path

wrapper, code, root = (Path(v).absolute() for v in sys.argv[1:4])
expected, revision, review, slot, head, shell_pid = sys.argv[4:10]
created = False

def safe(path):
    path = Path(path).absolute()
    if '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('noncanonical_or_symlink_path')
    return path

def hashed(path, maximum):
    path = safe(path)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= maximum:
            raise ValueError('bounded_regular_metadata_required')
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    if len(raw) != before.st_size or any(getattr(before, k) != getattr(after, k)
            for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')):
        raise ValueError('metadata_changed_during_read')
    return hashlib.sha256(raw).hexdigest()

def once(name, value):
    path = safe(root / name)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(value, stream, sort_keys=True); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())

try:
    safe(root)
    if not root.is_dir():
        raise ValueError('existing_dot_dispatch_required')
    outputs = ('outer.claim.json', 'observed_outer.json', 'start.json', 'command.json',
               'completion.json', 'controller.stdout', 'controller.stderr')
    if any((root / name).exists() or (root / name).is_symlink() for name in outputs):
        raise ValueError('existing_dispatch_output_no_retry')
    once('outer.claim.json', {'status': 'RUN03_OUTER_ATTEMPT_CLAIMED_NOT_CONTROLLER_SUCCESS',
        'claimed_at_utc': datetime.now(timezone.utc).isoformat(), 'shell_pid': int(shell_pid),
        'delivery_revision': revision if re.fullmatch('[0-9a-f]{40}', revision) else None,
        'expected_controller_sha256': expected if re.fullmatch('[0-9a-f]{64}', expected) else None,
        'training_authorization': False})
    created = True
    if not re.fullmatch('[0-9a-f]{40}', revision) or not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError('fixed_revision_and_controller_hash_required')
    if wrapper != code / 'RUN_RUN03_ONCE.sh':
        raise ValueError('fixed_wrapper_location_required')
    wrapper_sha = hashed(wrapper, 32768)
    controller_sha = hashed(code / 'target_restore_run03.py', 65536)
    if controller_sha != expected:
        raise ValueError('fixed_controller_hash_mismatch')
    inputs = {}
    for name, value, maximum in [('review', review, 16384), ('slot', slot, 16384), ('same_pod_head', head, 16384)]:
        if not value or any(ord(c) < 32 for c in value) or not Path(value).is_absolute() or Path(value).suffix != '.json':
            raise ValueError('explicit_nonsecret_JSON_path_required')
        inputs[name] = {'path': value, 'sha256': hashed(value, maximum)}
    command = ['timeout', '--signal=TERM', '--kill-after=5s', '1200s', '/usr/bin/python3', '-I', '-B',
        str(code / 'target_restore_run03.py'), '--delivery-revision', revision,
        '--source-restore-root', '/workspace/paper1-source-recovery-run01',
        '--source-acceptance-root', '/workspace/paper1-repaired-source-acceptance-run01',
        '--continuity-report', '/workspace/paper1-continuity-review-run01/continuity_review_run01.json',
        '--prior-run01-outer', '/workspace/paper1-target-dispatch-20261015-run01/observed_outer.json',
        '--prior-run02-outer', '/workspace/paper1-target-dispatch-20261015-run02/observed_outer.json',
        '--same-pod-head', head, '--review-record', review, '--priority-receipt', slot]
    once('command.json', {'argv': command, 'delivery_revision': revision, 'input_metadata': inputs,
        'controller_sha256': controller_sha, 'wrapper_sha256': wrapper_sha, 'training_authorization': False})
    once('start.json', {'status': 'OUTER_COMMAND_STARTING_NOT_CONTROLLER_STARTUP_PROOF',
        'started_at_utc': datetime.now(timezone.utc).isoformat(), 'shell_pid': int(shell_pid),
        'controller_sha256': controller_sha, 'wrapper_sha256': wrapper_sha,
        'command_sha256': hashed(root / 'command.json', 32768), 'training_authorization': False})
except Exception:
    print(json.dumps({'status': 'RUN03_WRAPPER_PREFLIGHT_BLOCKED_NO_RETRY',
        'outer_claim_created': created, 'training_authorization': False}))
    raise SystemExit(3 if created else 73) from None
PY_PREFLIGHT
P1_RUN03_PREFLIGHT_RC=$?
set -e

if [ "$P1_RUN03_PREFLIGHT_RC" -eq 73 ]; then
  exit "$P1_RUN03_PREFLIGHT_RC"
fi

P1_RUN03_INVOKED=false
P1_RUN03_EXIT="$P1_RUN03_PREFLIGHT_RC"
if [ "$P1_RUN03_PREFLIGHT_RC" -eq 0 ]; then
  P1_RUN03_INVOKED=true
  set +e
  (
    umask 077
    set -C
    timeout --signal=TERM --kill-after=5s 1200s /usr/bin/python3 -I -B \
      "$P1_RUN03_CODE/target_restore_run03.py" \
      --delivery-revision "$P1_RUN03_REVISION" \
      --source-restore-root /workspace/paper1-source-recovery-run01 \
      --source-acceptance-root /workspace/paper1-repaired-source-acceptance-run01 \
      --continuity-report /workspace/paper1-continuity-review-run01/continuity_review_run01.json \
      --prior-run01-outer /workspace/paper1-target-dispatch-20261015-run01/observed_outer.json \
      --prior-run02-outer /workspace/paper1-target-dispatch-20261015-run02/observed_outer.json \
      --same-pod-head "$P1_RUN03_HEAD" \
      --review-record "$P1_RUN03_REVIEW" \
      --priority-receipt "$P1_RUN03_SLOT" \
      > "$P1_RUN03_DISPATCH/controller.stdout" 2> "$P1_RUN03_DISPATCH/controller.stderr"
  )
  P1_RUN03_EXIT=$?
  set -e
fi

set +e
/usr/bin/python3 -I -B - "$P1_RUN03_DISPATCH" "$P1_RUN03_EXIT" \
  "$P1_RUN03_INVOKED" "$P1_RUN03_CODE" "$P1_RUN03_CONTROLLER_SHA" "$$" <<'PY_COMPLETION'
from datetime import datetime, timezone
import hashlib, json, os, stat, sys
from pathlib import Path

root, actual_exit, invoked, code, expected, shell_pid = sys.argv[1:7]
root, code = Path(root), Path(code)

def safe(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('outer_metadata_symlink_rejected')
    return path

def info(path, maximum, *, include_raw=False):
    path = safe(path)
    if not path.exists():
        return None
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
            raise ValueError('bounded_regular_outer_metadata_required')
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    if len(raw) != before.st_size or any(getattr(before, k) != getattr(after, k)
            for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')):
        raise ValueError('outer_metadata_changed_during_read')
    return raw if include_raw else {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def once(name, value):
    with os.fdopen(os.open(safe(root / name), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(value, stream, sort_keys=True); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())

try:
    safe(root)
    claimed = json.loads(info(root / 'outer.claim.json', 16384, include_raw=True))
    if claimed['shell_pid'] != int(shell_pid):
        raise ValueError('same_outer_claim_owner_required')
    summary = info(Path('/workspace/paper1-target-recovery-run01/target_restore_run03.json'), 2 * 1024**2)
    finished = datetime.now(timezone.utc).isoformat()
    completion = {'status': 'ACTUAL_RUN03_OUTER_EXIT_OBSERVED_NOT_SCIENTIFIC_ACCEPTANCE',
        'finished_at_utc': finished, 'exit_code': int(actual_exit),
        'controller_command_invoked': invoked == 'true', 'expected_controller_sha256': expected,
        'controller_after': info(code / 'target_restore_run03.py', 65536),
        'wrapper_after': info(code / 'RUN_RUN03_ONCE.sh', 32768),
        'start': info(root / 'start.json', 32768), 'command': info(root / 'command.json', 32768),
        'stdout': info(root / 'controller.stdout', 16 * 1024**2),
        'stderr': info(root / 'controller.stderr', 16 * 1024**2),
        'summary': summary, 'training_authorization': False}
    once('completion.json', completion)
    once('observed_outer.json', {'schema_version': 1, 'status': 'OBSERVED_TARGET_RAW_RESTORE_PROCESS_EXIT',
        'exit_code': int(actual_exit), 'target_restore_summary_sha256': None if summary is None else summary['sha256'],
        'script_sha256': expected, 'training_authorization': False})
    print(json.dumps({'status': completion['status'], 'exit_code': int(actual_exit), 'training_authorization': False}))
except Exception:
    print(json.dumps({'status': 'RUN03_OUTER_EVIDENCE_WRITE_BLOCKED_PRESERVE_NO_RETRY',
        'actual_command_exit_code': int(actual_exit), 'training_authorization': False}))
    raise SystemExit(3) from None
PY_COMPLETION
P1_RUN03_EVIDENCE_RC=$?
set -e
if [ "$P1_RUN03_EVIDENCE_RC" -ne 0 ]; then
  echo 'Run03 actual command exit is retained; outer evidence is incomplete and cannot authorize continuation.' >&2
  exit 3
fi
exit "$P1_RUN03_EXIT"
