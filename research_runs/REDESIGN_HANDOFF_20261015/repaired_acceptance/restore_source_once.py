"""One separately reviewed source-MAT transport, not numerical acceptance.

Uses only the frozen official downloader's load_manifest/download_one/verify
functions. It never calls the old diagnostic launcher, resolver, or EEG reader.
The one-attempt marker and any failed partials are retained, never repaired here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).absolute().parent
BASE_REVISION = '1efe9d1ba2ab8671ad1bf76c360e067fb63fd7ac'
HELPER_REL = 'research_runs/REDESIGN_HANDOFF_20261014/official_source_diagnostic/restore_source_official_lampx_v2.py'
MANIFEST_REL = 'research_runs/REDESIGN_HANDOFF_20261014/official_source_diagnostic/source_official_manifest.json'
HELPER_SHA = '48ff089bdc138888b6fd577c0a178490598e3ef5991fb1af90bce3b03c7aae26'
MANIFEST_SHA = 'e553d65cd86e5309e077ccfea21a9bee6020c5d9d5040de12089c2b859770b86'
SOURCE_ROOT = Path('/workspace/paper1-source-recovery-run01')
ENVIRONMENT = Path('/workspace/paper1-training-runtime-cp312-run01')
BASE_OWNED = 869490688
HISTORICAL_ENV_DU = 869425152
SOURCE_BYTES = 779873919
GIB = 1024**3
MAX_SOURCE_BYTES = GIB
MAX_WALL_SECONDS = 1200
JOURNAL = 'source_restore_run01.journal.jsonl'
RECEIPT = 'source_restore_run01.json'
LOG = 'source_restore_run01.log'
CHUNK = 1024**2
OLD_TASK = '20261014T071918Z-exploratory-89b0c07d'


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(CHUNK), b''):
            digest.update(block)
    return digest.hexdigest()


def no_symlink(path):
    path = Path(path).absolute()
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError('source_restore_symlink_path_forbidden')
    return path


def module(name, path, expected=None):
    path = no_symlink(path)
    if not path.is_file() or (expected is not None and sha(path) != expected):
        raise ValueError('source_restore_fixed_module_hash_mismatch')
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def fixed_helper(code_dir):
    code_dir = no_symlink(code_dir)
    head = subprocess.check_output(['git', '-C', str(code_dir), 'rev-parse', 'HEAD'], text=True).strip()
    if head != BASE_REVISION:
        raise ValueError('source_restore_exact_clean_1efe_checkout_required')
    if subprocess.check_output(['git', '-C', str(code_dir), 'status', '--porcelain'], text=True):
        raise ValueError('source_restore_checkout_dirty_do_not_reset')
    for rel, digest in ((HELPER_REL, HELPER_SHA), (MANIFEST_REL, MANIFEST_SHA)):
        path = no_symlink(code_dir / rel)
        committed = subprocess.check_output(['git', '-C', str(code_dir), 'show', BASE_REVISION + ':' + rel])
        if sha(path) != digest or path.read_bytes() != committed:
            raise ValueError('source_restore_fixed_source_bytes_changed')
    helper = module('paper1_original_source_transport', code_dir / HELPER_REL, HELPER_SHA)
    rows = helper.load_manifest(code_dir / MANIFEST_REL)
    return helper, rows


def bind_fixed_inputs(gate, code_dir):
    """Recheck the executing source identities at dispatch, GET/read and end."""
    original_check = gate.check
    paths = ((Path(__file__), gate.script_sha),
             (Path(code_dir) / HELPER_REL, HELPER_SHA),
             (Path(code_dir) / MANIFEST_REL, MANIFEST_SHA))
    def check():
        original_check()
        for path, expected in paths:
            if sha(no_symlink(path)) != expected:
                raise ValueError('source_restore_bound_code_or_manifest_changed')
    gate.check = check
    gate.check()


def validate_root(root):
    root = no_symlink(root)
    if root != SOURCE_ROOT:
        raise ValueError('source_restore_exact_isolated_root_required')
    for item in (root, *root.parents):
        if (item / '.git').exists():
            raise ValueError('source_restore_raw_and_logs_outside_repository_required')
    if root.exists() and not root.is_dir():
        raise ValueError('source_restore_root_directory_required')
    if root.exists():
        for item in root.rglob('*'):
            info = item.lstat()
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise ValueError('source_restore_special_or_symlink_member_forbidden')
    return root


def owned_bytes(root):
    if not root.exists():
        return 0
    total = 0
    for item in (root, *root.rglob('*')):
        info = item.lstat()
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise ValueError('source_restore_special_or_symlink_member_forbidden')
        total += info.st_blocks * 512
    return total


def runtime_allocated(root):
    """Measure child-owned blocks only; GPU/donor symlink targets stay unread.

    This is allocation accounting, never a runtime-integrity acceptance claim.
    Full link, distribution and source verification belongs to the next gate.
    """
    root = no_symlink(root)
    if not root.is_dir():
        raise ValueError('source_restore_retained_runtime_directory_required')
    total = 0
    for item in (root, *root.rglob('*')):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode):
            continue
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise ValueError('source_restore_special_runtime_member_forbidden')
        total += info.st_blocks * 512
    return total


def resource_check(root, gate, *, before_next_write=0):
    gate.check()
    if type(before_next_write) is not int or before_next_write < 0:
        raise ValueError('source_restore_invalid_write_reservation')
    cap = min(MAX_SOURCE_BYTES, gate.max_new_bytes)
    total = owned_bytes(root)
    if total + before_next_write > cap:
        raise ValueError('source_restore_original_total_allocation_cap_reached')
    observed_runtime = runtime_allocated(ENVIRONMENT)
    runtime_owned = max(BASE_OWNED, observed_runtime + BASE_OWNED - HISTORICAL_ENV_DU)
    combined_cap = min(3 * GIB, gate.max_new_bytes)
    if runtime_owned + total + before_next_write > combined_cap:
        raise ValueError('source_restore_combined_retained_runtime_and_source_cap_reached')
    floor = max(10 * GIB, gate.min_free_bytes) + max(5 * GIB, gate.reserve_bytes)
    existing = root if root.exists() else root.parent
    if shutil.disk_usage(existing).free < floor + before_next_write:
        raise ValueError('source_restore_10GiB_plus_actual_paper2_reserve_required')
    return {'owned_bytes': total, 'total_allocation_cap_bytes': cap,
            'observed_runtime_allocated_bytes': observed_runtime,
            'retained_runtime_owned_bytes': runtime_owned,
            'combined_owned_bytes': runtime_owned + total,
            'combined_total_allocation_cap_bytes': combined_cap,
            'runtime_historical_owned_bytes_preserved': BASE_OWNED,
            'required_remaining_free_bytes': floor}


def cache_preflight(root, rows, helper):
    """All existing destinations are checked before even the first GET."""
    if root.exists() and any((root / name).exists() for name in (JOURNAL, RECEIPT, LOG)):
        raise ValueError('source_restore_single_attempt_already_consumed')
    if root.exists() and {item.name for item in root.iterdir()} - {'bnci'}:
        raise ValueError('source_restore_unreviewed_existing_root_members')
    directory = no_symlink(root / 'bnci')
    if directory.exists() and not directory.is_dir():
        raise ValueError('source_restore_bnci_directory_required')
    names = {row['filename'] for row in rows}
    if directory.exists() and {item.name for item in directory.iterdir()} - names:
        raise ValueError('source_restore_unreviewed_existing_cache_or_partial')
    missing = []
    for row in rows:
        path = no_symlink(directory / row['filename'])
        if path.exists():
            helper.verify(path, row)
        else:
            missing.append(row)
    return sum(row['bytes'] for row in missing)


def write_json_once(path, value):
    with no_symlink(path).open('x') as stream:
        stream.write(json.dumps(value, sort_keys=True) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def append_journal(root, value):
    path = no_symlink(root / JOURNAL)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('source_restore_regular_journal_required')
        raw = (json.dumps(dict(value, at_utc=now()), sort_keys=True) + '\n').encode()
        if len(raw) > 16 * 1024:
            raise ValueError('source_restore_bounded_journal_row_required')
        with os.fdopen(fd, 'ab', closefd=False) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)


class CheckedResponse:
    def __init__(self, response, check):
        self.response, self.check = response, check

    def __enter__(self):
        self.response.__enter__()
        return self

    def __exit__(self, *args):
        return self.response.__exit__(*args)

    def __getattr__(self, name):
        return getattr(self.response, name)

    def read(self, size):
        if type(size) is not int or not 0 < size <= CHUNK:
            raise ValueError('source_restore_bounded_response_read_required')
        self.check(before_next_write=size + 65536)
        return self.response.read(size)


class CheckedOpener:
    def __init__(self, opener, check):
        self.opener, self.check = opener, check
        self.source_redirect = opener.source_redirect

    def open(self, request, timeout):
        self.check(before_next_write=65536)
        return CheckedResponse(self.opener.open(request, timeout=timeout), self.check)


def execute_transfer(root, rows, helper, gate, claim):
    """Worker-only transport. Its parent bounds wall time and its process group."""
    check = lambda **kw: resource_check(root, gate, **kw)
    check(before_next_write=65536)
    attempt = claim['attempt']
    report = dict(claim, status='SOURCE_RESTORE_RUNNING_NOT_NUMERICAL_ACCEPTANCE',
        files=[], actual_response_routes={}, source_expected_files=18,
        source_expected_bytes=SOURCE_BYTES, official_manifest_sha256=MANIFEST_SHA,
        diagnostic_rerun=False, runtime_imported=False, target_EEG_accessed=False,
        training_authorization=False, new_fits=0, budget_reset=False,
        old_accounting_status='UNKNOWN_NOT_ZERO', old_task=OLD_TASK)
    helper.atomic_json(root / RECEIPT, report)
    try:
        for row in rows:
            check(before_next_write=65536)
            append_journal(root, {'phase': 'source_file_started', 'file': row['filename']})
            def route_callback(route):
                report['actual_response_routes'][row['filename']] = route
                helper.atomic_json(root / RECEIPT, report)
            def opener_factory(item):
                return CheckedOpener(helper.official_opener(item), check)
            outcome = helper.download_one(row, root / 'bnci', attempt,
                time.monotonic() + min(MAX_WALL_SECONDS, gate.remaining_seconds()), opener_factory=opener_factory,
                route_callback=route_callback)
            report['files'].append(outcome)
            helper.atomic_json(root / RECEIPT, report)
            append_journal(root, {'phase': 'source_file_verified', 'file': row['filename'],
                'bytes': row['bytes'], 'sha256': row['sha256']})
        for row in rows:
            check(before_next_write=65536)
            helper.verify(root / 'bnci' / row['filename'], row)
        report.update(status='SOURCE18_EXACT_BYTES_RESTORED_NUMERICAL_ACCEPTANCE_PENDING',
            final_disk=check(before_next_write=65536), finished_at_utc=now())
        helper.atomic_json(root / RECEIPT, report)
        append_journal(root, {'phase': 'source_restore_verified_not_training'})
    except BaseException as error:
        report.update(status='SOURCE_RESTORE_FAILED_OR_BLOCKED_KEEP_PARTIALS_NO_RETRY',
            error_class=type(error).__name__, finished_at_utc=now())
        helper.atomic_json(root / RECEIPT, report)
        append_journal(root, {'phase': 'failed_or_blocked', 'error_class': type(error).__name__})
        raise
    return report


def gate_for(args):
    guard = module('paper1_repaired_acceptance_gate', HERE / 'acceptance_gate.py')
    return guard.Gate(args.review_record, args.priority_receipt, 'source_raw_restore',
                      args.delivery_revision, sha(Path(__file__)))


def validate_claim(args, root, gate):
    path = no_symlink(root / JOURNAL)
    with path.open('rb') as stream:
        first = stream.readline(16385)
    if not first.endswith(b'\n') or len(first) > 16384:
        raise ValueError('source_restore_bounded_matching_claim_required')
    claim = json.loads(first)
    expected = {'phase': 'single_attempt_claimed', 'delivery_revision': args.delivery_revision,
        'controller_sha256': sha(Path(__file__)), 'review_sha256': gate.review_sha256,
        'slot_sha256': gate.slot_sha256, 'source_root': str(root)}
    if any(claim.get(key) != val for key, val in expected.items()):
        raise ValueError('source_restore_matching_parent_claim_required')
    if claim.get('parent_pid') != os.getppid():
        raise ValueError('source_restore_live_own_parent_required')
    return claim


def stop_own_worker(child):
    if child.poll() is None:
        try:
            os.killpg(child.pid, signal.SIGTERM)
            child.wait(timeout=5)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)


def run(args):
    gate = gate_for(args)
    gate.check()
    root = validate_root(args.data_dir)
    helper, rows = fixed_helper(args.code_dir)
    bind_fixed_inputs(gate, args.code_dir)
    if args.worker:
        claim = validate_claim(args, root, gate)
        return execute_transfer(root, rows, helper, gate, claim)
    missing = cache_preflight(root, rows, helper)
    baseline = resource_check(root, gate, before_next_write=missing + 1024**2)
    # No directory, claim, log, receipt or GET is created until fresh review,
    # slot, fixed source identity, every cache file, and disk preflight all pass.
    gate.check()
    root.mkdir(exist_ok=True)
    no_symlink(root / 'bnci').mkdir(exist_ok=True)
    claim = {'phase': 'single_attempt_claimed', 'attempt': 'source-restore-run01',
        'at_utc': now(), 'delivery_revision': args.delivery_revision,
        'controller_sha256': sha(Path(__file__)), 'review_sha256': gate.review_sha256,
        'slot_sha256': gate.slot_sha256, 'source_root': str(root), 'parent_pid': os.getpid(),
        'maximum_seconds': min(MAX_WALL_SECONDS, gate.max_wall_seconds), 'automatic_retry': False,
        'baseline_disk': baseline, 'new_fits': 0, 'training_authorization': False}
    # O_EXCL consumes this authorization before the first potential GET.
    write_json_once(root / JOURNAL, claim)
    command = [sys.executable, '-I', '-B', str(Path(__file__).absolute()),
        '--worker', '--code-dir', str(args.code_dir), '--data-dir', str(root),
        '--review-record', str(args.review_record), '--priority-receipt', str(args.priority_receipt),
        '--delivery-revision', args.delivery_revision]
    child = None
    def interrupted(signum, frame):
        raise InterruptedError('source_restore_supervisor_interrupted')
    prior_term = signal.signal(signal.SIGTERM, interrupted)
    try:
        resource_check(root, gate, before_next_write=65536)
        with no_symlink(root / LOG).open('xb') as log:
            child = subprocess.Popen(command, stdout=log, stderr=log, start_new_session=True)
            end = time.monotonic() + min(MAX_WALL_SECONDS, gate.max_wall_seconds)
            while child.poll() is None:
                resource_check(root, gate, before_next_write=65536)
                if time.monotonic() >= end:
                    raise TimeoutError('source_restore_wall_cap_reached')
                time.sleep(.2)
            if child.returncode != 0:
                raise RuntimeError('source_restore_worker_failed_no_retry')
        resource_check(root, gate, before_next_write=65536)
        report = json.loads(no_symlink(root / RECEIPT).read_text())
        if report.get('status') != 'SOURCE18_EXACT_BYTES_RESTORED_NUMERICAL_ACCEPTANCE_PENDING':
            raise ValueError('source_restore_verified_worker_receipt_required')
        return report
    except BaseException as error:
        if child is not None:
            stop_own_worker(child)
        append_journal(root, {'phase': 'supervisor_failed_or_blocked_no_retry',
            'error_class': type(error).__name__, 'worker_exit_code': None if child is None else child.poll()})
        raise
    finally:
        signal.signal(signal.SIGTERM, prior_term)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-dir', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, default=SOURCE_ROOT)
    parser.add_argument('--review-record', type=Path, required=True)
    parser.add_argument('--priority-receipt', type=Path, required=True)
    parser.add_argument('--delivery-revision', required=True)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        report = run(args)
        print(json.dumps({'status': report['status'], 'source_files': len(report['files']),
            'source_bytes': SOURCE_BYTES, 'runtime_source_acceptance': False,
            'training_authorization': False, 'new_fits': 0}), flush=True)
    except BaseException as error:
        print(json.dumps({'status': 'SOURCE_RESTORE_FAILED_OR_BLOCKED_NO_RETRY',
                          'error_class': type(error).__name__, 'new_fits': 0,
                          'training_authorization': False}), flush=True)
        raise SystemExit(3) from None


if __name__ == '__main__':
    main()
