"""One reviewed repair after the authenticated run01 failure; no old claim retry.

Reuses the same12 exact source originals and downloads only the frozen missing6.
Old metadata is immutable. No installation, diagnostic, target EEG or fitting.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import time
import traceback

sys.dont_write_bytecode = True
HERE = Path(__file__).absolute().parent
FAILURE_SHA = '89f8b8b05dc2b94a97038e6800fb94238081e63657e2b1492361da2aa4d7c536'
FAILURE_BYTES = 26831
OLD_RECEIPT_SHA = '9042616a19d99fb67038749b33bff9d149e84d1dc825bc443f68c4bf07c37d0a'
OLD_JOURNAL_SHA = '67ca560b409de314537d046bf09101349852cdc8f0243ed5be845343798b30b8'
EMPTY_SHA = hashlib.sha256(b'').hexdigest()
BASE_SHA = '2ee6355f51b29bbeedd30f8422c078af76615c26873e16826156ebc015d7f220'
GATE_SHA = '579067cf8eab2d3e6d20a00f54bc303f619796db04df9bd33eee4fdea066f528'
METER_SHA = '96221076dc8d13c5f30dca4c271c971935af671061498486aa018aaf6c553582'
OLD_FILES = {'source_restore_run01.json': OLD_RECEIPT_SHA,
             'source_restore_run01.journal.jsonl': OLD_JOURNAL_SHA,
             'source_restore_run01.log': EMPTY_SHA}
ATTEMPT = 'source-restore-repair-run01'
RECEIPT = 'source_restore_repair_run01.json'
JOURNAL = 'source_restore_repair_run01.journal.jsonl'
LOG = 'source_restore_repair_run01.log'
COMPLETION = 'source_restore_repair_run01.completion.json'
PRESENT = {f'A{i:02d}{s}.mat' for i in range(1, 7) for s in ('E', 'T')}
MISSING = {f'A{i:02d}{s}.mat' for i in range(7, 10) for s in ('E', 'T')}
CONTROLLED_INPUT_LABELS = {}


def load(name, path, expected):
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('source_repair_fixed_dependency_changed')
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


base = load('paper1_preserved_source_run01', HERE / 'restore_source_once.py', BASE_SHA)
meter = load('paper1_source_repair_measurement', HERE / 'source_owned_measurement.py', METER_SHA)


def old_records(root):
    for name, expected in OLD_FILES.items():
        path = base.no_symlink(root / name)
        if not stat.S_ISREG(path.lstat().st_mode) or base.sha(path) != expected:
            raise ValueError('source_repair_prior_failure_record_missing_or_changed')


def failure_package(path):
    path = base.no_symlink(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size != FAILURE_BYTES:
        raise ValueError('source_repair_exact_original_failure_archive_required')
    with path.open('rb') as stream:
        data = stream.read(FAILURE_BYTES + 1)
    if len(data) != FAILURE_BYTES or hashlib.sha256(data).hexdigest() != FAILURE_SHA:
        raise ValueError('source_repair_exact_original_failure_archive_required')
    bodies = {}; expanded = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for member in archive:
            name = member.name; expanded += member.size
            if (not member.isfile() or name in bodies or name.startswith('/') or '\\' in name
                    or any(p in ('', '.', '..') for p in name.split('/'))
                    or str(PurePosixPath(name)) != name or member.size > 262144
                    or expanded > 2 * 1024**2 or len(bodies) >= 28):
                raise ValueError('source_repair_unsafe_failure_archive')
            bodies[name] = archive.extractfile(member).read(member.size + 1)
            if len(bodies[name]) != member.size:
                raise ValueError('source_repair_failure_payload_length')
    manifest = json.loads(bodies['MANIFEST.json']); rows = manifest['payloads']
    if len(rows) != 27 or len(bodies) != 28 or {r['path'] for r in rows} != set(bodies) - {'MANIFEST.json'}:
        raise ValueError('source_repair_complete27_failure_payloads_required')
    for row in rows:
        data = bodies[row['path']]
        if type(row['bytes']) is not int or len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('source_repair_failure_payload_hash')
    if json.loads(bodies['dispatch/completion.json'])['exit_code'] != 3:
        raise ValueError('source_repair_original_outer_failure_required')
    for name, expected in OLD_FILES.items():
        if hashlib.sha256(bodies['source/' + name]).hexdigest() != expected:
            raise ValueError('source_repair_original_failure_bindings_changed')


def append(root, value):
    path = base.no_symlink(root / JOURNAL)
    raw = (json.dumps(dict(value, at_utc=base.now()), sort_keys=True) + '\n').encode()
    if len(raw) > 16384:
        raise ValueError('source_repair_bounded_journal_required')
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode) or os.write(fd, raw) != len(raw):
            raise ValueError('source_repair_journal_write_failed')
        os.fsync(fd)
    finally:
        os.close(fd)


def details(error, stage):
    result = dict(getattr(error, 'controlled_diagnostic', {}))
    result.setdefault('errno', getattr(error, 'errno', None))
    result.setdefault('relative_filename', 'not-recorded-or-outside-controlled-roots')
    if result['relative_filename'] == 'not-recorded-or-outside-controlled-roots':
        value = getattr(error, 'filename', None)
        if isinstance(value, str):
            path = Path(value).absolute()
            if path in CONTROLLED_INPUT_LABELS:
                result['relative_filename'] = CONTROLLED_INPUT_LABELS[path]
            for prefix, root in [('source', base.SOURCE_ROOT), ('runtime', base.ENVIRONMENT), ('delivery', HERE)]:
                if path.is_relative_to(root):
                    result['relative_filename'] = prefix + '/' + path.relative_to(root).as_posix()
                    break
    result.setdefault('stage', stage)
    frames = [f for f in traceback.extract_tb(error.__traceback__) if Path(f.filename).name in
              {Path(__file__).name, 'source_owned_measurement.py', 'restore_source_once.py', 'acceptance_gate.py'}]
    result.setdefault('code_location', (Path(frames[-1].filename).name + ':' + str(frames[-1].lineno)) if frames else 'source_repair_controller')
    result['error_class'] = type(error).__name__
    return result


def cache_preflight(root, rows, helper, worker=False):
    if root != base.SOURCE_ROOT or not root.is_dir():
        raise ValueError('source_repair_same_existing_cache_required')
    old_records(root)
    expected = {'bnci', *OLD_FILES}
    if worker:
        expected |= {JOURNAL, LOG}
    if {p.name for p in root.iterdir()} != expected:
        raise ValueError('source_repair_unreviewed_member_or_consumed_claim')
    directory = base.no_symlink(root / 'bnci')
    if not directory.is_dir() or {p.name for p in directory.iterdir()} != PRESENT:
        raise ValueError('source_repair_exact12_cache_no_unknown_partial_required')
    reused = []
    for row in rows:
        if row['filename'] in PRESENT:
            helper.verify(directory / row['filename'], row)
            reused.append({k: row[k] for k in ('filename', 'bytes', 'sha256')})
    if len(reused) != 12 or sum(r['bytes'] for r in reused) != 513941297:
        raise ValueError('source_repair_complete12_strict_SHA_required_before_GET')
    return reused


def gate_for(args):
    guard = load('paper1_source_repair_gate', HERE / 'acceptance_gate.py', GATE_SHA)
    gate = guard.Gate(args.review_record, args.priority_receipt, 'source_raw_restore',
                      args.delivery_revision, base.sha(Path(__file__)))
    if base.datetime.fromisoformat(gate.review['reviewed_at_utc'].replace('Z', '+00:00')) <= base.datetime.fromisoformat('2026-10-15T06:02:59.928544+00:00'):
        raise ValueError('source_repair_new_technical_review_must_follow_actual_failure')
    original = gate.check
    paths = [(Path(__file__), gate.script_sha), (HERE / 'restore_source_once.py', BASE_SHA),
             (HERE / 'source_owned_measurement.py', METER_SHA),
             (args.code_dir / base.HELPER_REL, base.HELPER_SHA),
             (args.code_dir / base.MANIFEST_REL, base.MANIFEST_SHA)]
    def check():
        original(); old_records(base.SOURCE_ROOT)
        for path, expected in paths:
            if base.sha(base.no_symlink(path)) != expected:
                raise ValueError('source_repair_bound_code_or_manifest_changed')
    gate.check = check
    return gate


def resources(root, gate, rows, *, before_next_write=0, claimed=True):
    gate.check()
    if type(before_next_write) is not int or before_next_write < 0:
        raise ValueError('source_repair_invalid_write_reservation')
    observed = getattr(gate, '_repair_observed_mat_names', set(PRESENT))
    for row in rows:
        if row['filename'] in MISSING and (root / 'bnci' / row['filename']).exists():
            observed.add(row['filename'])
    gate._repair_observed_mat_names = observed
    required = list(OLD_FILES) + ['bnci/' + name for name in sorted(observed)]
    if claimed:
        required += [JOURNAL, LOG]
    total = meter.owned_bytes(root, receipt_name=RECEIPT, attempt=ATTEMPT,
        partial_rows=[r for r in rows if r['filename'] in MISSING], required_paths=required,
        on_event=(lambda event: append(root, dict(event, phase='controlled_allocation_rescan'))) if claimed else None)
    for row in rows:
        if row['filename'] in observed and (root / 'bnci' / row['filename']).lstat().st_size != row['bytes']:
            raise ValueError('source_repair_retained_mat_size_changed')
    cap = min(base.MAX_SOURCE_BYTES, gate.max_new_bytes)
    if total + before_next_write > cap:
        raise ValueError('source_repair_original_source_allocation_cap_reached')
    allocated = base.runtime_allocated(base.ENVIRONMENT)
    retained = max(base.BASE_OWNED, allocated + base.BASE_OWNED - base.HISTORICAL_ENV_DU)
    combined_cap = min(3 * base.GIB, gate.max_new_bytes)
    if retained + total + before_next_write > combined_cap:
        raise ValueError('source_repair_original_combined_allocation_cap_reached')
    floor = max(10 * base.GIB, gate.min_free_bytes) + max(5 * base.GIB, gate.reserve_bytes)
    if shutil.disk_usage(root).free < floor + before_next_write:
        raise ValueError('source_repair_original_free_floor_and_write_reservation_required')
    return dict(owned_bytes=total, retained_runtime_owned_bytes=retained,
                combined_owned_bytes=retained + total, combined_total_allocation_cap_bytes=combined_cap,
                total_allocation_cap_bytes=cap, required_remaining_free_bytes=floor,
                before_next_write_bytes=before_next_write)


def transfer(args, root, rows, helper, gate, claim, reused):
    check = lambda **kw: resources(root, gate, rows, **kw)
    report = dict(claim, status='SOURCE_RESTORE_REPAIR_RUNNING_NOT_NUMERICAL_ACCEPTANCE',
        files=[dict(row, status='REUSED_VERIFIED_CACHE') for row in reused],
        actual_response_routes={}, source_expected_files=18, source_expected_bytes=base.SOURCE_BYTES,
        official_manifest_sha256=base.MANIFEST_SHA, old_task=base.OLD_TASK,
        diagnostic_rerun=False, runtime_imported=False, target_EEG_accessed=False,
        training_authorization=False, new_fits=0, budget_reset=False,
        old_accounting_status='UNKNOWN_NOT_ZERO', original_missing_path_proven=False)
    helper.atomic_json(root / RECEIPT, report)
    try:
        for row in rows:
            if row['filename'] not in MISSING:
                continue
            check(before_next_write=65536)
            append(root, dict(phase='source_file_started', file=row['filename']))
            def route_callback(route):
                report['actual_response_routes'][row['filename']] = route
                helper.atomic_json(root / RECEIPT, report)
            outcome = helper.download_one(row, root / 'bnci', ATTEMPT,
                time.monotonic() + min(base.MAX_WALL_SECONDS, gate.remaining_seconds()),
                opener_factory=lambda item: base.CheckedOpener(helper.official_opener(item), check),
                route_callback=route_callback)
            if outcome['status'] != 'RESTORED_OFFICIAL_EXACT_BYTES':
                raise ValueError('source_repair_missing6_must_have_no_concurrent_destination')
            report['files'].append(outcome); helper.atomic_json(root / RECEIPT, report)
            append(root, dict(phase='source_file_verified', file=row['filename'], bytes=row['bytes'], sha256=row['sha256']))
        for row in rows:
            check(before_next_write=65536); helper.verify(root / 'bnci' / row['filename'], row)
        if len(report['files']) != 18:
            raise ValueError('source_repair_full18_required')
        report.update(status='SOURCE18_EXACT_BYTES_RESTORED_NUMERICAL_ACCEPTANCE_PENDING',
                      final_disk=check(before_next_write=65536), finished_at_utc=base.now())
        helper.atomic_json(root / RECEIPT, report)
        return report
    except BaseException as error:
        report.update(status='SOURCE_RESTORE_REPAIR_FAILED_OR_BLOCKED_NO_RETRY',
                      failure=details(error, 'worker_transfer'), finished_at_utc=base.now())
        helper.atomic_json(root / RECEIPT, report)
        append(root, dict(phase='worker_failed_no_retry', **details(error, 'worker_transfer')))
        raise


def run(args):
    gate = gate_for(args); gate.check()
    failure_package(args.failure_archive)
    root = base.validate_root(args.data_dir)
    helper, rows = base.fixed_helper(args.code_dir)
    reused = cache_preflight(root, rows, helper, args.worker)
    if args.worker:
        claim = json.loads((root / JOURNAL).open().readline())
        if (claim.get('controller_sha256') != gate.script_sha or claim.get('review_sha256') != gate.review_sha256
                or claim.get('slot_sha256') != gate.slot_sha256 or claim.get('parent_pid') != os.getppid()
                or claim.get('prior_source_restore_failure_archive_sha256') != FAILURE_SHA
                or claim.get('attempt') != ATTEMPT or claim.get('source_root') != str(root)):
            raise ValueError('source_repair_matching_new_parent_claim_required')
        return transfer(args, root, rows, helper, gate, claim, reused)
    baseline = resources(root, gate, rows, before_next_write=265932622 + base.CHUNK, claimed=False)
    claim = dict(phase='single_repair_attempt_claimed', attempt=ATTEMPT, at_utc=base.now(),
        source_root=str(root), old_task=base.OLD_TASK, parent_pid=os.getpid(), controller_sha256=gate.script_sha,
        delivery_revision=args.delivery_revision, review_sha256=gate.review_sha256, slot_sha256=gate.slot_sha256,
        prior_source_restore_failure_archive_sha256=FAILURE_SHA,
        prior_source_restore_receipt_sha256=OLD_RECEIPT_SHA, prior_source_restore_journal_sha256=OLD_JOURNAL_SHA,
        prior_outer_exit_code=3, old_failure_receipt_overwritten=False, same_cache_12_verified=reused,
        remaining_frozen_files=sorted(MISSING), remaining_frozen_bytes=265932622,
        baseline_disk=baseline, automatic_retry=False, maximum_seconds=min(1200, gate.max_wall_seconds))
    base.write_json_once(root / JOURNAL, claim)
    child = None
    def interrupted(signum, frame):
        raise InterruptedError('source_repair_supervisor_interrupted')
    prior_term = signal.signal(signal.SIGTERM, interrupted)
    try:
        with base.no_symlink(root / LOG).open('xb') as log:
            command = [sys.executable, '-I', '-B', str(Path(__file__).absolute()), '--worker',
                '--code-dir', str(args.code_dir), '--data-dir', str(root), '--failure-archive', str(args.failure_archive),
                '--review-record', str(args.review_record), '--priority-receipt', str(args.priority_receipt),
                '--delivery-revision', args.delivery_revision]
            child = subprocess.Popen(command, stdout=log, stderr=log, start_new_session=True)
            end = time.monotonic() + min(1200, gate.max_wall_seconds)
            while child.poll() is None:
                resources(root, gate, rows, before_next_write=65536)
                if time.monotonic() >= end:
                    raise TimeoutError('source_repair_wall_cap_reached')
                time.sleep(.2)
            if child.returncode != 0:
                raise RuntimeError('source_repair_worker_failed_no_retry')
        resources(root, gate, rows, before_next_write=65536)
        report = json.loads((root / RECEIPT).read_text())
        if report.get('status') != 'SOURCE18_EXACT_BYTES_RESTORED_NUMERICAL_ACCEPTANCE_PENDING' or len(report.get('files', [])) != 18:
            raise ValueError('source_repair_worker_full18_success_required')
        old_records(root)
        append(root, dict(phase='supervisor_verified_new_repair_no_training', worker_exit_code=0))
        base.write_json_once(root / COMPLETION, dict(status='SOURCE_RESTORE_REPAIR_CONTROLLER_VERIFIED_EXTERNAL_EXIT_REQUIRED',
            worker_exit_code_observed=0, controller_process_exit_observed=False, source_root=str(root),
            receipt_sha256=base.sha(root / RECEIPT), journal_sha256=base.sha(root / JOURNAL),
            controller_sha256=gate.script_sha, prior_source_restore_failure_archive_sha256=FAILURE_SHA,
            finished_at_utc=base.now(), training_authorization=False))
        return report
    except BaseException as error:
        if child is not None:
            base.stop_own_worker(child)
        append(root, dict(phase='supervisor_failed_or_blocked_no_retry',
            worker_exit_code=None if child is None else child.poll(), **details(error, 'supervisor')))
        raise
    finally:
        signal.signal(signal.SIGTERM, prior_term)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-dir', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, default=base.SOURCE_ROOT)
    parser.add_argument('--failure-archive', type=Path, required=True)
    parser.add_argument('--review-record', type=Path, required=True)
    parser.add_argument('--priority-receipt', type=Path, required=True)
    parser.add_argument('--delivery-revision', required=True)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    CONTROLLED_INPUT_LABELS.update({args.review_record.absolute(): 'authorization/review_record',
        args.priority_receipt.absolute(): 'authorization/priority_receipt',
        args.failure_archive.absolute(): 'evidence/source_restore_run01_failure_archive'})
    try:
        report = run(args)
        print(json.dumps(dict(status=report['status'], source_files=18,
                              parent_or_worker='worker' if args.worker else 'supervisor',
                              training_authorization=False, new_fits=0)), flush=True)
    except BaseException as error:
        print(json.dumps(dict(status='SOURCE_REPAIR_FAILED_OR_BLOCKED_NO_RETRY',
            failure=details(error, 'dispatch'), new_fits=0, training_authorization=False)), flush=True)
        raise SystemExit(3) from None


if __name__ == '__main__':
    main()
