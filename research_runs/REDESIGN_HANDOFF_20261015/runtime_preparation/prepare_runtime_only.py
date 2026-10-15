"""Bounded preparation controller for the unchanged, accepted fixed helper.

This script is delivered for dot to run later. It does not grant a fit, import
GPU libraries, read EEG, renew a budget, operate a Pod, or run plan-only again.
All writes belong to one new child environment and new /workspace evidence.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import time
from urllib.parse import urlsplit

REVISION = '1efe9d1ba2ab8671ad1bf76c360e067fb63fd7ac'
HELPER_REL = 'research_runs/REDESIGN_HANDOFF_20261014/runtime_transition/isolated_training_runtime.py'
GATE_REL = 'research_runs/REDESIGN_HANDOFF_20261015/runtime/priority_gate.py'
REQ_REL = 'research_runs/REDESIGN_CLOUD_20261013/requirements.txt'
HELPER_SHA = 'cdd8c2d47fb6e1653e8b5c2eb48de6483d4dd57a0af392f2c1495669e3c0cd9e'
GATE_SHA = 'eb88b6c75381a714bd91d9b0bb0acb4fd82edf295b73a25abed4f0236c054fff'
REQ_SHA = '7322d4f85f25064ef8c29efa502c67417fc9b8a0d3297692263c1e618804769a'
DONOR_SHA = '3a83a9cf93cca3e9813056645bc73f26a9429ee6f1f7bc06f2ae78a1c36471b1'
PLAN_SHA = 'e4852d1e2517abc69464c22e69658c2618d8e3950184fa40eb4c8a2af6ce5a0c'
ENVIRONMENT = Path('/workspace/paper1-training-runtime-cp312-run01')
DEADLINE = datetime(2026, 10, 16, 9, 54, tzinfo=timezone.utc)
ACCEPTED_PLAN_ENDED = datetime(2026, 10, 15, 3, 25, 20, 668962, tzinfo=timezone.utc)
GIB = 1024**3
EVIDENCE_CAP = 8 * 1024**2
POLL_SECONDS = 0.25
REVIEW_KEYS = frozenset(('schema_version', 'status', 'issuer', 'code_revision',
    'helper_sha256', 'donor_report_sha256', 'accepted_plan_sha256', 'environment',
    'reviewed_at_utc', 'expires_at_utc', 'maximum_wall_seconds',
    'bounded_binary_wheel_policy_reviewed', 'resolver_closure_not_yet_observed',
    'preparation_cost_handling_reviewed', 'old_accounting_unknown_retained',
    'paper2_absolute_priority', 'budget_reset_authorized',
    'budget_expansion_authorized', 'training_authorization', 'review_notes'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('explicit_utc_timestamp_required')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError('explicit_utc_timestamp_required')
    return result


def unique(pairs):
    data = {}
    for name, value in pairs:
        if name in data:
            raise ValueError('duplicate_json_key')
        data[name] = value
    return data


def regular_json(path, limit, expected_size=None, expected_sha=None):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('regular_input_no_symlink_required')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError('bounded_regular_json_required')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(limit + 1)
        after = os.fstat(fd)
        identity = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        if identity != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('input_changed_during_read')
    finally:
        os.close(fd)
    if len(raw) > limit or (expected_size is not None and len(raw) != expected_size):
        raise ValueError('input_exact_size_mismatch')
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha is not None and digest != expected_sha:
        raise ValueError('input_exact_sha256_mismatch')
    value = json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite_json')))
    if not isinstance(value, dict):
        raise ValueError('json_object_required')
    return value, digest, identity[:2]


def validate_review(value, current):
    if set(value) != REVIEW_KEYS or type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('exact_parent_review_schema_required')
    expected = {'status': 'DOT_PARENT_RUNTIME_PREPARATION_REVIEW_APPROVED',
        'issuer': 'dot_parent', 'code_revision': REVISION, 'helper_sha256': HELPER_SHA,
        'donor_report_sha256': DONOR_SHA, 'accepted_plan_sha256': PLAN_SHA,
        'environment': str(ENVIRONMENT)}
    if any(value[key] != item for key, item in expected.items()):
        raise ValueError('parent_review_binding_or_status_mismatch')
    for key in ('bounded_binary_wheel_policy_reviewed', 'resolver_closure_not_yet_observed',
                'preparation_cost_handling_reviewed', 'old_accounting_unknown_retained',
                'paper2_absolute_priority'):
        if value[key] is not True:
            raise ValueError('parent_policy_review_required:' + key)
    for key in ('budget_reset_authorized', 'budget_expansion_authorized', 'training_authorization'):
        if value[key] is not False:
            raise ValueError('preparation_cannot_grant_budget_or_training:' + key)
    reviewed, end = (timestamp(value[key]) for key in ('reviewed_at_utc', 'expires_at_utc'))
    if not ACCEPTED_PLAN_ENDED <= reviewed <= current < end <= DEADLINE:
        raise ValueError('parent_review_expired_not_yet_valid_or_past_deadline')
    seconds = value['maximum_wall_seconds']
    if type(seconds) is not int or not 1 <= seconds <= 1200:
        raise ValueError('preparation_must_be_bounded_to20minutes')
    if not isinstance(value['review_notes'], str) or not value['review_notes'].strip():
        raise ValueError('actual_parent_review_notes_required')
    return reviewed, end, seconds


def validate_plan(plan):
    if (plan.get('status') != 'ISOLATED_RUNTIME_PLAN_ONLY_REVIEW_REQUIRED'
            or plan.get('code_revision') != REVISION
            or plan.get('environment') != str(ENVIRONMENT)
            or plan.get('donor_report_sha256') != DONOR_SHA
            or type(plan.get('new_fits')) is not int or plan['new_fits'] != 0
            or plan.get('actual_maximum_new_bytes') != 3 * GIB
            or plan.get('paper2_additional_reserved_bytes') != 5 * GIB
            or plan.get('actual_required_free_floor_bytes') != 15 * GIB):
        raise ValueError('accepted_plan_identity_or_resource_binding_mismatch')
    for flag in ('training_authorization', 'source_acceptance_run', 'target_EEG_read',
                 'budget_updated', 'cuda_packages_downloaded', 'donor_modified'):
        if plan.get(flag) is not False:
            raise ValueError('accepted_plan_scope_changed:' + flag)


def safe_outputs(output, log, install_log, protected, workspace=Path('/workspace')):
    paths = tuple(Path(p).absolute() for p in (output, log, install_log))
    dispatch = paths[0].with_name(paths[0].name + '.dispatch.json')
    all_paths = (*paths, dispatch, ENVIRONMENT)
    if len(set(all_paths)) != len(all_paths):
        raise ValueError('distinct_new_evidence_and_environment_required')
    for path in all_paths:
        if path.parent != workspace or path.exists() or path.is_symlink() or any(p.is_symlink() for p in path.parents):
            raise ValueError('fresh_direct_workspace_children_required_no_resume_or_delete')
        for old in (Path(p).absolute() for p in protected):
            if path == old or path.is_relative_to(old) or old.is_relative_to(path):
                raise ValueError('writable_path_overlaps_protected_input')
    return (*paths, dispatch)


def child_command(code, report, slot, install_log):
    return ['/usr/bin/python3', '-I', '-B', str(code / HELPER_REL),
        '--code-revision', REVISION, '--donor-python', '/usr/bin/python3',
        '--donor-report', str(report), '--environment', str(ENVIRONMENT),
        '--priority-receipt', str(slot), '--prepare', '--log', str(install_log)]


def allocated(path):
    path = Path(path)
    if not path.exists() or path.is_symlink():
        return 0
    total = path.lstat().st_blocks * 512
    if path.is_dir():
        for folder, directories, files in os.walk(path, followlinks=False):
            for name in directories + files:
                candidate = Path(folder) / name
                try:
                    info = candidate.lstat()
                except FileNotFoundError:
                    continue
                if not stat.S_ISLNK(info.st_mode):
                    total += info.st_blocks * 512
    return total


def resource_check(paths, permit, disk_parent=Path('/workspace')):
    permit.assert_active()
    used = sum(allocated(p) for p in (*paths, ENVIRONMENT))
    # Reserve the final small dispatch receipt within the same combined cap.
    if used + 65536 > min(3 * GIB, permit.max_new_bytes):
        raise ValueError('owned_environment_plus_evidence_exceeds_new_storage_cap')
    for path in paths:
        if path.exists() and (path.is_symlink() or not path.is_file() or path.stat().st_size > EVIDENCE_CAP):
            raise ValueError('regular_bounded_owned_evidence_required')
    if shutil.disk_usage(disk_parent).free < max(10 * GIB, permit.min_free_bytes) + permit.paper2_reserve_bytes:
        raise ValueError('paper2_reserved_free_floor_reached')
    return used


def process_table(proc=Path('/proc')):
    """Only public stat identity/ancestry; never cmdline, environ or secrets."""
    result = {}
    for folder in proc.iterdir():
        if not folder.name.isdigit():
            continue
        try:
            raw = (folder / 'stat').read_text()
            fields = raw[raw.rindex(')') + 2:].split()
            # fields[0] is stat field3 (state), [19] is field22 (starttime).
            result[int(folder.name)] = (int(fields[1]), int(fields[2]), int(fields[19]))
        except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError, IndexError):
            continue
    return result


def remember_descendants(root_pid, known, table):
    if root_pid not in known:
        if root_pid not in table:
            return
        known[root_pid] = table[root_pid][2]
    parents = {pid for pid, start in known.items() if pid in table and table[pid][2] == start}
    changed = True
    while changed:
        changed = False
        for pid, (ppid, _pgid, start) in table.items():
            if ppid in parents and pid not in parents:
                parents.add(pid); known[pid] = start; changed = True


def stop_owned(process, known, table_fn=process_table, kill=os.kill, pause=time.sleep):
    # A reaped child PID may already have been reused. Never bootstrap ownership
    # from a fresh /proc observation after completion when no identity was seen.
    if process.poll() is not None and not known:
        return
    # First let fixed helper's BaseException path clean its own new sessions.
    table = table_fn(); remember_descendants(process.pid, known, table)
    if process.pid in table and known.get(process.pid) == table[process.pid][2]:
        try:
            kill(process.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    # Fallback touches only PID/starttime identities seen beneath this helper.
    # No pkill, global group name, command-line matching or foreign PID access.
    for sig in (signal.SIGTERM, signal.SIGKILL):
        table = table_fn(); remember_descendants(process.pid, known, table)
        for pid, start in sorted(known.items(), reverse=True):
            if pid in table and table[pid][2] == start:
                try:
                    kill(pid, sig)
                except ProcessLookupError:
                    pass
        pause(0.1)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        raise ValueError('owned_process_did_not_exit_after_bounded_cleanup')


def donor_identity(value):
    return {key: value[key] for key in ('donor_python', 'prefix', 'base_prefix',
        'base_executable', 'python_version', 'SOABI', 'cache_tag', 'platform',
        'site_packages', 'distributions', 'components', 'critical_module_files',
        'torch_gpu_dependency_pins', 'numerical_donor_observation_not_reused',
        'inventory_implementation_sha256', 'isolated_venv_prerequisites')}


def verify_prepared(permit, donor, stdout):
    receipt_path = ENVIRONMENT / 'runtime_preparation.json'
    receipt, receipt_sha, _ = regular_json(receipt_path, 256 * 1024)
    if (receipt.get('status') != 'ISOLATED_RUNTIME_PREPARED_IMPORT_AND_SOURCE_ACCEPTANCE_PENDING'
            or receipt.get('code_revision') != REVISION
            or receipt.get('environment') != str(ENVIRONMENT)
            or receipt.get('donor_report_sha256') != DONOR_SHA
            or receipt.get('requirements_sha256') != REQ_SHA
            or receipt.get('paper2_priority_receipt_sha256') != permit.receipt_sha256
            or receipt.get('donor_metadata_unchanged') is not True
            or type(receipt.get('new_fits')) is not int or receipt['new_fits'] != 0):
        raise ValueError('prepared_receipt_identity_or_scope_mismatch')
    for flag in ('cuda_packages_downloaded', 'donor_modified', 'source_acceptance_run',
                 'target_EEG_read', 'budget_updated', 'training_authorization'):
        if receipt.get(flag) is not False:
            raise ValueError('prepared_receipt_forbidden_scope:' + flag)
    if any(donor_identity(receipt[key]) != donor_identity(donor)
           for key in ('donor_metadata', 'donor_post_metadata')):
        raise ValueError('prepared_donor_before_after_identity_mismatch')
    links = {item['name']: item['path'] for item in donor['components']}
    if receipt.get('linked_gpu_components') != links:
        raise ValueError('prepared_gpu_component_mapping_changed')
    site = ENVIRONMENT / 'lib/python3.12/site-packages'
    if 'include-system-site-packages = false' not in (ENVIRONMENT / 'pyvenv.cfg').read_text().lower():
        raise ValueError('prepared_environment_inherits_global_site')
    for name, target in links.items():
        path = site / name
        if not path.is_symlink() or path.resolve() != Path(target).resolve():
            raise ValueError('prepared_gpu_component_link_mismatch')
    resolution, resolution_sha, _ = regular_json(ENVIRONMENT / 'wheel-resolution.json', 8 * 1024**2)
    if resolution_sha != receipt.get('wheel_resolution_sha256'):
        raise ValueError('resolved_wheel_plan_sha_mismatch')
    items = resolution.get('install')
    if not isinstance(items, list) or not items:
        raise ValueError('nonempty_lightweight_wheel_closure_required')
    hashes = set()
    for item in items:
        url = urlsplit(item['download_info']['url'])
        name = item['metadata']['name'].lower().replace('_', '-')
        digest = item['download_info']['archive_info']['hashes']['sha256']
        if (url.scheme != 'https' or url.hostname != 'files.pythonhosted.org'
                or url.username or url.password or not url.path.endswith('.whl')
                or name in ('torch', 'torchaudio', 'triton') or name.startswith('nvidia-')
                or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest)):
            raise ValueError('prepared_wheel_source_or_gpu_exclusion_mismatch')
        hashes.add(digest)
    wheels = list((ENVIRONMENT / 'reviewed-wheels').glob('*.whl'))
    if len(wheels) != len(items) or {sha(path) for path in wheels} != hashes:
        raise ValueError('prepared_wheel_bytes_differ_from_resolved_closure')
    if (stdout.get('status') != receipt['status']
            or stdout.get('runtime_receipt') != str(receipt_path)
            or type(stdout.get('new_fits')) is not int or stdout['new_fits'] != 0
            or stdout.get('training_authorization') is not False):
        raise ValueError('helper_stdout_does_not_match_prepared_receipt')
    return receipt_sha, resolution_sha


def run(args):
    code, donor_path, plan_path, review_path, slot = (Path(p).absolute() for p in
        (args.code_dir, args.donor_report, args.accepted_plan, args.review_record, args.priority_receipt))
    if any(p.is_symlink() for p in (code, *code.parents)):
        raise ValueError('fixed_checkout_no_symlink_required')
    if subprocess.check_output(['git', '-C', str(code), 'rev-parse', 'HEAD'], text=True).strip() != REVISION:
        raise ValueError('actual_fixed1efe_checkout_required')
    if subprocess.check_output(['git', '-C', str(code), 'status', '--porcelain'], text=True):
        raise ValueError('fixed_checkout_must_be_clean_do_not_reset')
    for name, digest in ((HELPER_REL, HELPER_SHA), (GATE_REL, GATE_SHA), (REQ_REL, REQ_SHA)):
        path = code / name
        committed = subprocess.check_output(['git', '-C', str(code), 'show', REVISION + ':' + name])
        if path.is_symlink() or path.read_bytes() != committed or sha(path) != digest:
            raise ValueError('fixed_helper_gate_or_requirements_changed')
    donor, _, _ = regular_json(donor_path, 22450, 22450, DONOR_SHA)
    plan, _, _ = regular_json(plan_path, 25128, 25128, PLAN_SHA)
    validate_plan(plan)
    review, review_sha, review_identity = regular_json(review_path, 16384)
    current = datetime.now(timezone.utc)
    reviewed, review_end, maximum_seconds = validate_review(review, current)
    spec = importlib.util.spec_from_file_location('paper1_fixed_preparation_slot', code / GATE_REL)
    gate = importlib.util.module_from_spec(spec); sys.modules[spec.name] = gate; spec.loader.exec_module(gate)
    permit = gate.validate_receipt(slot, expected_operation='runtime_preparation')
    if (permit.receipt_sha256 == plan['paper2_priority_receipt_sha256']
            or timestamp(permit.receipt['issued_at_utc']) < reviewed
            or timestamp(permit.receipt['expires_at_utc']) > review_end
            or permit.paper2_reserve_bytes < 5 * GIB or permit.max_new_bytes <= 0):
        raise ValueError('fresh_nonloosening_slot_after_parent_review_required')
    paths = safe_outputs(args.output, args.log, args.install_log,
        (code, donor_path, plan_path, review_path, slot, Path(__file__).absolute(),
         '/workspace/.venvs/paper2-gpu', '/usr', '/opt'))
    output, log, install_log, dispatch = paths
    if shutil.disk_usage(output.parent).free < permit.required_free_bytes + permit.max_new_bytes:
        raise ValueError('new_storage_cap_plus_floor_and_paper2_reserve_required')
    command = child_command(code, donor_path, slot, install_log)
    started, clock = current.isoformat(), time.monotonic()
    error, child_code, receipt_sha, resolution_sha = None, None, None, None
    known, observed_peak = {}, 0

    def checkpoint():
        nonlocal observed_peak
        value, digest, identity = regular_json(review_path, 16384)
        if digest != review_sha or identity != review_identity:
            raise ValueError('parent_review_revoked_replaced_or_changed')
        validate_review(value, datetime.now(timezone.utc))
        observed_peak = max(observed_peak, resource_check(paths, permit))
        if time.monotonic() - clock >= maximum_seconds:
            raise ValueError('bounded_outer_preparation_timeout')

    with output.open('xb') as stdout, log.open('xb') as stderr:
        checkpoint()
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            while process.poll() is None:
                remember_descendants(process.pid, known, process_table())
                checkpoint()
                try:
                    process.wait(timeout=POLL_SECONDS)
                except subprocess.TimeoutExpired:
                    pass
            child_code = process.returncode
            checkpoint()
            if child_code != 0:
                raise ValueError('fixed_preparation_helper_nonzero')
            helper_stdout, _, _ = regular_json(output, EVIDENCE_CAP)
            receipt_sha, resolution_sha = verify_prepared(permit, donor, helper_stdout)
            checkpoint()
        except BaseException as exc:
            stop_owned(process, known)
            child_code = process.returncode
            error = type(exc).__name__ + ':' + str(exc)
    result = {'status': 'ISOLATED_PREPARATION_VERIFIED_IMPORT_SOURCE_STILL_PENDING' if error is None
              else 'PREPARATION_FAILED_OR_BLOCKED_RETAIN_OWN_EVIDENCE_NO_RETRY',
        'fixed_helper_revision': REVISION, 'controller_sha256': sha(__file__),
        'started_at_utc': started, 'ended_at_utc': datetime.now(timezone.utc).isoformat(),
        'command': command, 'child_exit_code': child_code, 'error': error,
        'accepted_plan_sha256': PLAN_SHA, 'donor_report_sha256': DONOR_SHA,
        'parent_review_sha256': review_sha, 'slot_sha256': permit.receipt_sha256,
        'same_slot_periodically_and_after_child_checked': True,
        'periodic_check_seconds': POLL_SECONDS,
        'owned_process_identity_observed': bool(known),
        'observed_peak_owned_allocated_bytes': observed_peak,
        'output_sha256': sha(output), 'log_sha256': sha(log),
        'install_log_sha256': sha(install_log) if install_log.is_file() else None,
        'runtime_preparation_receipt_sha256': receipt_sha,
        'wheel_resolution_sha256': resolution_sha,
        'runtime_import_acceptance_passed': False, 'source_acceptance_passed': False,
        'old_accounting_reconciled': False, 'old_cost_known': False,
        'budget_reset': False, 'budget_expanded': False,
        'training_authorization': False, 'new_fits': 0, 'target_EEG_read': False}
    with dispatch.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if error is None else 3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('code-dir', 'donor-report', 'accepted-plan', 'review-record',
                 'priority-receipt', 'output', 'log', 'install-log'):
        parser.add_argument('--' + name, type=Path, required=True)
    raise SystemExit(run(parser.parse_args()))


if __name__ == '__main__':
    main()
