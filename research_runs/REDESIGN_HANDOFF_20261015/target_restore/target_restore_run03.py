"""One reviewed run03 using the fixed exact-host single-hop transport adapter.

The protected priority gate remains unchanged. This adapter accepts only a new
target_raw_restore operation with its otherwise identical slot schema.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import sys
import time
import urllib.error

sys.dont_write_bytecode = True
HERE = Path(__file__).absolute().parent
ROOT = Path('/workspace/paper1-target-recovery-run01')
OPERATION = 'target_raw_restore'
GIB = 1024**3
TOTAL_BYTES = 2515343396
MAX_WALL = 1200
CONTINUITY_SHA = 'ec86526fb6af6c01a19e4d86b0fb69532098175181d2e7175c1e6668038aa6cc'
MODULES = {
    'transport': ('official_edf_transport/nemar_single_hop.py', '7a717fd63b4c0945e2a232c7560f475b5618c3c992c069cb9f451a569e5d4716'),
    'original_transport': ('official_edf_transport/official_edf_transport.py', '1aa2da0b710b3ef109d00d19c75a00fda013a79f947e9aebbe3480c8e99b895f'),
    'continuity': ('continuity_resume/continuity_review.py', '2d7904b7787c92449dd0ffe7b56c09327ffb803eb942a417fd0e2fabad0fd8d7'),
    'priority': ('runtime/priority_gate.py', 'eb88b6c75381a714bd91d9b0bb0acb4fd82edf295b73a25abed4f0236c054fff')}
CLAIM, JOURNAL, LOG = ('target_restore_run03.' + x for x in ('claim.json', 'journal.jsonl', 'log'))
BYTE_RECEIPT = 'target_bytes_receipt_run03.json'
SUMMARY = 'target_restore_run03.json'
RECOVERY_ID = 'target_raw_restore_run03_exact_host_single_hop'
ADAPTER_GO_COMMIT = '009a3629bd6b50648f580421ef596b40b271e8a4'
FAILURE_ARCHIVE_SHA = {
    'run01': '599a690184f657da06d2dcf35fd519fd6c8d4999115bc763396bf220d4242e43',
    'run02': '6f9bbb8e6070bf0df1a0ffdcd57b484184e9b6d244c82b08bc3285fa0e1bf176'}
PRIOR_FILES = {
    'target_restore_run01.claim.json': '43ab15e83b921a8be9b3794f3abddc1390bf3157d226ec6c694a8ef2fa397ff7',
    'target_restore_run01.journal.jsonl': 'fb735cbfda52acea32c56c2035039b0c1a93baf9b0cd00064946337f7bf9951f',
    'target_restore_run01.log': 'fb735cbfda52acea32c56c2035039b0c1a93baf9b0cd00064946337f7bf9951f',
    'target_restore_run02.claim.json': '0850d68a286366a4c904cfed04badf6a288958f9629e0426a043616fb700d169',
    'target_restore_run02.journal.jsonl': '8f66687515b35b601cbfc4ed620c5116d43c3b0a0237c03624cc8519c5da640d',
    'target_restore_run02.log': '8f66687515b35b601cbfc4ed620c5116d43c3b0a0237c03624cc8519c5da640d'}
PRIOR_OUTER_SHA = {
    'run01': '04963eb245867ed026a338ddb59471a20e4d92135b765efbefcd22cb3255a823',
    'run02': 'c9e1508e776a3b2dcb80ee473fff991fc3f9fca8916865c8d7221fd645c3d367'}
HEAD_SHA = 'a1d19255b427122f9f961cde33873693f35c0db3773112fdaebaa17ae8629ebe'
ORIGINAL_SCRIPT_SHA = '65507374bc7640d4c6b2b7d9b609d86b809a11d61a1aa55d61e6527ced4e5190'
RUN02_SCRIPT_SHA = '5a5fb300c800c0d9884df9d29f0287f46ee2304ce8b21f815c2f93138eb188db'
ERROR_CODES = frozenset('''
actual_response_url_changed
canonical_http_status_rejected
canonical_request_open_failed
controlled_transport_or_resource_failure_partial_preserved
download_size_or_sha256_mismatch_partial_preserved
exact_frozen_canonical_row_required
existing_object_corrupt_preserved
existing_partial_preserved_manual_review_required
http_body_exceeds_frozen_size_partial_preserved
http_content_encoding_not_identity
http_content_length_not_exact_frozen_size
insufficient_disk_for_object_floor_and_paper2_reserve
integer_resource_limit_required
location_not_exact_derived_frozen_storage_object
paper2_reserved_free_space_before_write_partial_preserved
paper2_reserved_free_space_reached_partial_preserved
storage_http_status_rejected
storage_request_open_failed
target_parent_exact_schema
target_parent_fixed_bindings
target_parent_review_changed
target_parent_review_expired_or_wall_invalid
target_restore_actual_source_runtime_continuity_binding
target_restore_bound_metadata_changed
target_restore_bounded_journal_row
target_restore_bounded_receipt
target_restore_bounded_regular_metadata_required
target_restore_cached_size_sha_mismatch_preserved
target_restore_exact_external_root
target_restore_existing_root_required
target_restore_explicit_total_target_allocation_cap
target_restore_fixed_helper_sha
target_restore_fixed_revision
target_restore_free_floor_plus_remaining_write_bytes
target_restore_frozen174
target_restore_metadata_changed_during_read
target_restore_outer_timeout
target_restore_regular_journal_log
target_restore_root_directory
target_restore_special_member
target_restore_symlink_or_traversal
target_restore_unknown_member_or_consumed_claim_preserved
target_restore_wall_cap
target_run03_both_actual_prior_failures_required
target_run03_partial_preserved_no_resume
target_run03_preserved_exact_run01_run02_metadata_required
target_run03_prior_failure_or_HEAD_binding_changed
target_slot_exact_identity_and_operation
target_slot_exact_schema
target_slot_expired_or_overlong
target_slot_explicit_new_operation
target_slot_must_follow_parent_review
target_slot_paper2_no_fit_boundary
target_slot_rationale
target_slot_replaced_or_revoked
target_slot_separate_allocation_and_floor
transport_disk_or_byte_cap_invalid
'''.split())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe(path):
    path = Path(path).absolute()
    require('..' not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)), 'target_restore_symlink_or_traversal')
    return path


def digest(path):
    path = safe(path)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= 2 * 1024**2, 'target_restore_bounded_regular_metadata_required')
        raw = stream.read(2 * 1024**2 + 1)
        after = os.fstat(stream.fileno())
    identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    require(identity(before) == identity(after) and len(raw) == before.st_size, 'target_restore_metadata_changed_during_read')
    return hashlib.sha256(raw).hexdigest()


def diagnostic(error):
    candidate = getattr(error, 'code', None)
    if candidate is None and type(error) is ValueError and len(error.args) == 1:
        candidate = error.args[0]
    code = candidate if type(candidate) is str and candidate in ERROR_CODES else ''
    name = Path(error.filename).name if isinstance(getattr(error, 'filename', None), str) else ''
    known = {CLAIM, JOURNAL, LOG, BYTE_RECEIPT, SUMMARY, Path(__file__).name,
        'continuity_review_run01.json', 'gpu_donor_inventory.json', 'source_official_manifest.json',
        'source_restore_repair_run01.json', 'source_restore_repair_run01.completion.json',
        'source_restore_repair_run01.compat_outer_exit.json', 'formal_source_acceptance.json',
        'repaired_runtime_bound_acceptance.json'} | {Path(rel).name for rel, _ in MODULES.values()}
    safe_name = name if name in known or re.fullmatch(r'sub-[0-9]{2}_task-R[12]acquisition_eeg\.edf(?:\.partial)?', name) else None
    result = {'error_class': type(error).__name__, 'error_code': code if re.fullmatch(r'[a-z][a-z0-9_]{0,95}', code) else 'target_restore_controlled_operation_failed',
        'errno': error.errno if type(getattr(error, 'errno', None)) is int else None, 'affected_basename': safe_name}
    # Never merge arbitrary exception dictionaries or serialize Location/URLs.
    values = getattr(error, 'safe_metadata', None)
    if isinstance(values, dict):
        for key in ('query_present', 'fragment_present'):
            if type(values.get(key)) is bool:
                result[key] = values[key]
        for key, allowed in (
            ('location_scheme', ('https', 'http', 'other', None)),
            ('location_hostname', ('data.nemar.org', 'nemar.s3.us-east-2.amazonaws.com', 'other', None))):
            value = values.get(key)
            if value is None or (type(value) is str and value in allowed):
                result[key] = value
        status, port = values.get('http_status'), values.get('location_port')
        result['http_status'] = status if type(status) is int and 100 <= status <= 599 else None
        result['location_port'] = port if type(port) is int and 0 <= port <= 65535 else None
    return result


def prior_failure_bindings(args, root):
    """Read exact preserved metadata only; HEAD200 is not a GET diagnosis."""
    bindings = [(root / name, sha) for name, sha in PRIOR_FILES.items()]
    bindings += [(args.prior_run01_outer, PRIOR_OUTER_SHA['run01']),
        (args.prior_run02_outer, PRIOR_OUTER_SHA['run02']), (args.same_pod_head, HEAD_SHA),
        (HERE / 'target_restore_once.py', ORIGINAL_SCRIPT_SHA),
        (HERE / 'target_restore_run02.py', RUN02_SCRIPT_SHA)]
    require(all(digest(path) == sha for path, sha in bindings), 'target_run03_prior_failure_or_HEAD_binding_changed')
    for path, sha in ((args.prior_run01_outer, PRIOR_OUTER_SHA['run01']),
                      (args.prior_run02_outer, PRIOR_OUTER_SHA['run02'])):
        outer, _ = load_module('continuity').load(path, sha)
        require(outer['exit_code'] == 3 and outer['target_restore_summary_sha256'] is None
            and outer['training_authorization'] is False, 'target_run03_both_actual_prior_failures_required')
    return bindings


def load_module(name):
    rel, expected = MODULES[name]
    path = safe(HERE.parent / rel)
    require(path.stat().st_size <= 65536 and digest(path) == expected, 'target_restore_fixed_helper_sha')
    spec = importlib.util.spec_from_file_location('_paper1_target_' + name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_slot(path, current=None, *, expected_operation=OPERATION):
    """Validate only the explicit new operation; do not mutate the old gate."""
    require(expected_operation in ('target_raw_restore', 'target_input_preparation'), 'target_slot_explicit_new_operation')
    gate = load_module('priority')
    path, raw, identity = gate._read(path)
    data = json.loads(raw, object_pairs_hook=gate._unique_object,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('target_slot_nonfinite')))
    require(isinstance(data, dict) and set(data) == gate._KEYS, 'target_slot_exact_schema')
    require(type(data['schema_version']) is int and data['schema_version'] == 1
        and data['status'] == gate.STATUS and data['issuer'] == 'dot'
        and data['pod_id'] == gate.POD_ID and data['container_id'] == gate.CONTAINER_ID
        and data['operation'] == expected_operation, 'target_slot_exact_identity_and_operation')
    require(all(data[k] is True for k in gate._TRUE_FIELDS)
        and all(data[k] is False for k in gate._FALSE_FIELDS), 'target_slot_paper2_no_fit_boundary')
    issued, start, end = (gate._timestamp(data[k]) for k in ('issued_at_utc', 'not_before_utc', 'expires_at_utc'))
    current = gate._clock(current)
    require(issued <= start <= current < end <= gate.AUTHORIZATION_DEADLINE
        and end - issued <= gate.MAX_SLOT and current - issued <= gate.MAX_SLOT, 'target_slot_expired_or_overlong')
    require(all(type(data[k]) is int for k in ('max_new_bytes', 'min_free_bytes', 'paper2_reserve_bytes'))
        and 0 < data['max_new_bytes'] <= 3 * GIB and data['min_free_bytes'] >= 10 * GIB
        and data['paper2_reserve_bytes'] >= 5 * GIB, 'target_slot_separate_allocation_and_floor')
    require(isinstance(data['slot_rationale'], str) and data['slot_rationale'].strip(), 'target_slot_rationale')
    return path, raw, identity, data


def parent_review(path, revision, source, current=None):
    continuity = load_module('continuity')
    review, sha = continuity.load(path)
    expected = {'schema_version': 1, 'status': 'DOT_PARENT_TARGET_RAW_RESTORE_APPROVED',
        'issuer': 'dot_parent', 'operation': OPERATION, 'delivery_revision': revision,
        'operation_script_sha256': digest(__file__), 'frozen_manifest_sha256': load_module('transport').FROZEN_SHA256,
        'transport_helper_sha256': MODULES['transport'][1], 'priority_helper_sha256': MODULES['priority'][1],
        'continuity_helper_sha256': MODULES['continuity'][1], 'continuity_report_sha256': CONTINUITY_SHA,
        'source_runtime_metadata_sha256': source['metadata_sha256'], 'target_raw_byte_transport_authorized': True,
        'paper2_absolute_priority': True, 'paper2_noninterference_reviewed': True,
        'new_target_allocation_separate_from_retained_source_runtime': True,
        'old_task_unknowns_and_failures_retained': True, 'financial_preconditions': 'superseded-by-user',
        'training_authorization': False, 'GPU_fit_authorized': False,
        'target_scientific_processing_authorized': False, 'source_EEG_read_authorized': False,
        'new_resources_or_credentials_authorized': False, 'automatic_retry_authorized': False}
    expected.update(recovery_identity=RECOVERY_ID, prior_failure_archive_sha256=FAILURE_ARCHIVE_SHA,
        prior_cache_records_sha256=PRIOR_FILES, prior_outer_sha256=PRIOR_OUTER_SHA,
        same_pod_head_sha256=HEAD_SHA, one_additional_bounded_attempt_authorized=True,
        single_hop_adapter_GO_commit=ADAPTER_GO_COMMIT, single_hop_adapter_reviewed=True,
        original_transport_helper_sha256=MODULES['original_transport'][1],
        outer_wrapper_sha256=digest(HERE / 'RUN_RUN03_ONCE.sh'))
    require(set(review) == set(expected) | {'reviewed_at_utc', 'expires_at_utc', 'maximum_wall_seconds'}, 'target_parent_exact_schema')
    require(all(type(review[k]) is type(v) and review[k] == v for k, v in expected.items()), 'target_parent_fixed_bindings')
    gate = load_module('priority')
    now = gate._clock(current)
    start, end = (gate._timestamp(review[k]) for k in ('reviewed_at_utc', 'expires_at_utc'))
    require(start <= now < end <= gate.AUTHORIZATION_DEADLINE
        and type(review['maximum_wall_seconds']) is int and 0 < review['maximum_wall_seconds'] <= MAX_WALL,
        'target_parent_review_expired_or_wall_invalid')
    return review, sha


def allocated(root):
    """Synchronous scanner: never samples concurrently with own publications."""
    root = safe(root)
    require(root.is_dir(), 'target_restore_existing_root_required')
    total = root.lstat().st_blocks * 512
    stack = [root]
    while stack:
        with os.scandir(stack.pop()) as entries:
            for entry in entries:
                info = entry.stat(follow_symlinks=False)
                require(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode), 'target_restore_special_member')
                total += info.st_blocks * 512
                if stat.S_ISDIR(info.st_mode):
                    stack.append(Path(entry.path))
    return total


def cache_preflight(root, rows, helper):
    """Verify every cached object before any GET; preserve unknown/partial files."""
    expected = {r['restore_relative_path']: r for r in rows}
    require(root.is_dir() and all(digest(root / name) == sha for name, sha in PRIOR_FILES.items()),
        'target_run03_preserved_exact_run01_run02_metadata_required')
    allowed_dirs = {str(p) for rel in expected for p in Path(rel).parents if str(p) != '.'}
    if root.exists():
        require(root.is_dir(), 'target_restore_root_directory')
        def inaccessible(error):
            raise error
        for base, dirs, files in os.walk(root, followlinks=False, onerror=inaccessible):
            for name in sorted(dirs + files, key=lambda n: not n.endswith('.partial')):
                path = safe(Path(base) / name)
                relative = path.relative_to(root).as_posix()
                require(not relative.endswith('.partial'), 'target_run03_partial_preserved_no_resume')
                require((relative in allowed_dirs and path.is_dir()) or
                    (relative in PRIOR_FILES and path.is_file() and digest(path) == PRIOR_FILES[relative]) or
                    (relative in expected and path.is_file()),
                    'target_restore_unknown_member_or_consumed_claim_preserved')
    missing = []
    for relative, row in expected.items():
        path = helper.safe_path(root, relative)
        if path.exists():
            require(stat.S_ISREG(path.lstat().st_mode) and path.stat().st_size == row['bytes']
                and helper.digest_file(path) == row['sha256'], 'target_restore_cached_size_sha_mismatch_preserved')
        else:
            missing.append(row)
    return missing


def atomic(path, value):
    path = safe(path)
    raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
    require(len(raw) <= 2 * 1024**2, 'target_restore_bounded_receipt')
    temporary = path.with_name(path.name + '.tmp-' + str(time.monotonic_ns()))
    with temporary.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def append(root, value):
    value = dict(value, at_utc=datetime.now(timezone.utc).isoformat())
    raw = (json.dumps(value, sort_keys=True) + '\n').encode()
    require(len(raw) <= 16384, 'target_restore_bounded_journal_row')
    for name in (JOURNAL, LOG):
        fd = os.open(safe(root / name), os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
        with os.fdopen(fd, 'ab') as stream:
            require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'target_restore_regular_journal_log')
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def run(args):
    require(re.fullmatch('[0-9a-f]{40}', args.delivery_revision or ''), 'target_restore_fixed_revision')
    root = safe(args.data_dir)
    require(root == ROOT and not any((p / '.git').exists() for p in (root, *root.parents)), 'target_restore_exact_external_root')
    helper, continuity = load_module('transport'), load_module('continuity')
    source = continuity.source_review(args.source_restore_root, args.source_acceptance_root)
    report, _ = continuity.load(args.continuity_report, CONTINUITY_SHA)
    require(report['status'] == 'SOURCE_RUNTIME_ACCEPTED_ORIGINAL_TASK_CONTINUITY_AND_TARGET_GATES_PENDING'
        and report['source_runtime'] == source and report['training_authorization'] is False,
        'target_restore_actual_source_runtime_continuity_binding')
    review, review_sha = parent_review(args.review_record, args.delivery_revision, source)
    slot_path, slot_raw, slot_identity, slot = validate_slot(args.priority_receipt)
    gate = load_module('priority')
    require(gate._timestamp(review['reviewed_at_utc']) <= gate._timestamp(slot['issued_at_utc'])
        and gate._timestamp(slot['expires_at_utc']) <= gate._timestamp(review['expires_at_utc']), 'target_slot_must_follow_parent_review')
    plan = helper.frozen_plan()
    require(plan['total_bytes'] == TOTAL_BYTES and plan['file_count'] == 174, 'target_restore_frozen174')
    prior_bindings = prior_failure_bindings(args, root)
    started = time.monotonic()
    bound_files = [(Path(__file__), digest(__file__)),
        (HERE / 'RUN_RUN03_ONCE.sh', digest(HERE / 'RUN_RUN03_ONCE.sh')),
        (args.continuity_report, CONTINUITY_SHA)] + prior_bindings
    for key, (name, _, sha) in continuity.BINDINGS.items():
        bound_files.append((Path(args.source_restore_root if key in ('restore', 'completion', 'outer') else args.source_acceptance_root) / name, sha))
    bound_files += [(HERE.parent / rel, sha) for rel, sha in MODULES.values()]
    remaining = 0  # Read-only cache inspection first; reserve exact missing bytes before claim/GET.
    def check():
        _, raw, identity, _ = validate_slot(slot_path)
        require(raw == slot_raw and identity == slot_identity, 'target_slot_replaced_or_revoked')
        _, actual_review_sha = parent_review(args.review_record, args.delivery_revision, source)
        require(actual_review_sha == review_sha, 'target_parent_review_changed')
        require(time.monotonic() - started < review['maximum_wall_seconds'], 'target_restore_wall_cap')
        require(all(digest(path) == sha for path, sha in bound_files), 'target_restore_bound_metadata_changed')
        current = root if root.exists() else root.parent
        floor = slot['min_free_bytes'] + slot['paper2_reserve_bytes']
        require(shutil.disk_usage(current).free >= floor + remaining + 65536, 'target_restore_free_floor_plus_remaining_write_bytes')
        if root.exists():
            require(allocated(root) + min(remaining, helper.CHUNK) + 65536 <= min(3 * GIB, slot['max_new_bytes']), 'target_restore_explicit_total_target_allocation_cap')
    check()
    missing = cache_preflight(root, plan['files'], helper)
    remaining = sum(r['bytes'] for r in missing)
    check()
    root.mkdir(mode=0o700, exist_ok=True)
    claim = {'status': 'ONE_TARGET_RAW_RESTORE_RUN03_CLAIM_CONSUMED', 'operation': OPERATION,
        'recovery_identity': RECOVERY_ID, 'prior_failure_archive_sha256': FAILURE_ARCHIVE_SHA,
        'prior_cache_records_sha256': PRIOR_FILES, 'single_hop_adapter_sha256': MODULES['transport'][1],
        'single_hop_adapter_GO_commit': ADAPTER_GO_COMMIT,
        'outer_wrapper_sha256': digest(HERE / 'RUN_RUN03_ONCE.sh'),
        'prior_outer_sha256': PRIOR_OUTER_SHA, 'same_pod_head_sha256': HEAD_SHA,
        'delivery_revision': args.delivery_revision, 'script_sha256': digest(__file__),
        'review_sha256': review_sha, 'slot_sha256': hashlib.sha256(slot_raw).hexdigest(),
        'continuity_report_sha256': CONTINUITY_SHA, 'old_task': continuity.OLD_JOB,
        'old_continuity_state': report['old_task']['state'], 'old_counters': report['old_task']['counters'],
        'old_cost_or_counters_reset': False, 'automatic_retry': False, 'training_authorization': False}
    with (root / CLAIM).open('x') as stream:
        json.dump(claim, stream, sort_keys=True); stream.flush(); os.fsync(stream.fileno())
    for name in (JOURNAL, LOG):
        (root / name).open('xb').close()
    append(root, dict(claim, phase='claimed_no_fit'))
    outcomes = []
    try:
        for row in plan['files']:
            check()
            outcome = helper.transport_one(row, root, control_check=check,
                min_free_bytes=slot['min_free_bytes'], paper2_reserve_bytes=slot['paper2_reserve_bytes'], max_new_bytes=TOTAL_BYTES)
            outcomes.append(outcome)
            if outcome['status'] == 'new_exact_bytes_atomic_publish':
                remaining -= row['bytes']
            append(root, dict(outcome, phase='frozen_target_object_verified',
                http_status=200 if outcome['status'] == 'new_exact_bytes_atomic_publish' else None,
                automatic_retry=False))
        byte_receipt = helper.verify_cached_manifest(root, control_check=check)
        check()
        atomic(root / BYTE_RECEIPT, byte_receipt)
        summary = dict(claim, status='TARGET174_OFFICIAL_BYTES_RESTORED_SCIENTIFIC_GATES_PENDING',
            files_verified=len(outcomes), verified_bytes=TOTAL_BYTES, target_bytes_receipt_sha256=digest(root / BYTE_RECEIPT),
            finished_at_utc=datetime.now(timezone.utc).isoformat(), new_source_fits=0, target_fits=0,
            target_predictions=0, source_EEG_read=False, target_scientific_processing=False,
            license=plan['license'])
        atomic(root / SUMMARY, summary)
        append(root, {'phase': 'complete_byte_only_not_training', 'target_bytes_receipt_sha256': summary['target_bytes_receipt_sha256']})
        check()
        return summary
    except BaseException as error:
        append(root, dict(diagnostic(error), phase='failed_or_blocked_preserve_no_retry', training_authorization=False))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-restore-root', 'source-acceptance-root', 'continuity-report', 'review-record', 'priority-receipt'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--delivery-revision', required=True)
    parser.add_argument('--data-dir', type=Path, default=ROOT)
    parser.add_argument('--prior-run01-outer', type=Path, default=Path('/workspace/paper1-target-dispatch-20261015-run01/observed_outer.json'))
    parser.add_argument('--prior-run02-outer', type=Path, default=Path('/workspace/paper1-target-dispatch-20261015-run02/observed_outer.json'))
    parser.add_argument('--same-pod-head', type=Path, required=True)
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(TimeoutError('target_restore_outer_timeout')))
    try:
        result = run(args)
        print(json.dumps({'status': result['status'], 'files_verified': result['files_verified'], 'training_authorization': False}))
    except BaseException as error:
        print(json.dumps(dict(diagnostic(error), status='TARGET_RESTORE_FAILED_OR_BLOCKED_NO_RETRY', training_authorization=False)))
        raise SystemExit(3) from None


if __name__ == '__main__':
    main()
