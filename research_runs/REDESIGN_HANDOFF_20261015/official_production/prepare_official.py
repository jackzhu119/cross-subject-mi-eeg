#!/usr/bin/env python3
"""Separately gated CPU preparation of exact official source/target cache bytes.

Default is a static plan. Execute neither downloads nor fits; it consumes genuine
five-record routing, a fresh parent review and one dot target_input_preparation
slot. The frozen prepare_data suffix is copied statically and checked by AST;
the historical R2-only producer and every scientific file remain unchanged.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import shutil
import socket
import stat
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OLD_JOB = '20261014T071918Z-exploratory-89b0c07d'
OLD_REVISION = '05e683e91e2bb39b977970d04402221761e575d2'
SCIENCE_REVISION = '1efe9d1ba2ab8671ad1bf76c360e067fb63fd7ac'
SCIENCE_ROOT = Path('/workspace/paper1-metadata-code-1efe9d1')
RUNTIME = Path('/workspace/paper1-training-runtime-cp312-run01')
SOURCE_ROOT = Path('/workspace/paper1-source-recovery-run01')
TARGET_ROOT = Path('/workspace/paper1-target-recovery-run01')
OUTPUT_ROOT = Path('/workspace/paper1-official-preparation-run01')
ORIGINAL_PREPARE = 'research_runs/REDESIGN_CLOUD_20261013/scripts/prepare_data.py'
ORIGINAL_PREPARE_SHA = '426252640951bdbcfd1cafebc5b103b2846bac2f363d1bbbc6cb8586afe8e3db'
LAUNCH_SHA = 'edb2b3e4790d383878106144eddc3ee8ffc9dc65c6ae4128ec92330757fca49e'
FORMAL_SHA = '9f6980404ccd2ceb8f96aa300d497919caa185b02bbff0cc441451ae0a8a59e9'
RUNTIME_BOUND_SHA = '8e5ae3890240b130c875180a18e455dcd3158eab53926dcabb95c2f40768a39b'
SOURCE_RESTORE_SHA = 'acdaa915e5f5c0dd66e1b0178fa8602791a70146f46734fd023e2c455acb196c'
CONTINUITY_SHA = 'ec86526fb6af6c01a19e4d86b0fb69532098175181d2e7175c1e6668038aa6cc'
OLD_RUNTIME_LOCK_SHA = 'a18529ba66d7e73f47438981eafe1b2f7761d6b028998871d621a7656c7e1fa6'
CPU_ACCEPTANCE_ARCHIVE_SHA = '2c943a5f70608d10cb1f0720be5874ce53c01e3bed6d5bf2cbcafbc636ff312d'
UNION_REL = 'research_runs/REDESIGN_HANDOFF_20261015/transport_union/transport_receipt_union.py'
UNION_SHA = 'c4638ec15c1b2a2e4b87940df55b0006ac05cd553818eb458648a77785f13ace'
TARGET_GATE_REL = 'research_runs/REDESIGN_HANDOFF_20261015/target_restore/target_restore_once.py'
TARGET_GATE_SHA = '65507374bc7640d4c6b2b7d9b609d86b809a11d61a1aa55d61e6527ced4e5190'
DEPENDENCIES_SHA = '5d193bfc68cc775435301630122b4a5ac1c4ff0f910e6a14356e64eb1cda26d7'
MAX_JSON = 2 * 1024**2
GIB = 1024**3
CLAIM = 'official_preparation_run01.claim.json'
INITIAL_FILES = {'launch_record.json', 'formal_source_acceptance.json', 'numerical_execution_review.json'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def no_symlink(path):
    path = Path(path).absolute()
    require('..' not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)), 'symlink_or_noncanonical_path')
    return path


def metadata(path, expected=None):
    path = no_symlink(path)
    require(path.suffix == '.json', 'explicit_JSON_required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= MAX_JSON, 'bounded_regular_JSON_required')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(MAX_JSON + 1)
        after = os.fstat(fd)
        require(all(getattr(before, k) == getattr(after, k) for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))
                and len(data) == before.st_size, 'JSON_changed_during_read')
    finally:
        os.close(fd)
    require(expected is None or sha(data) == expected, 'JSON_SHA_changed:' + path.name)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate_JSON_key')
            result[key] = value
        return result
    result = json.loads(data, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_JSON')))
    require(isinstance(result, dict), 'JSON_object_required')
    return result, sha(data)


def fixed_module(name, path, expected):
    path = no_symlink(path)
    require(path.is_file() and path.stat().st_size <= 256 * 1024
            and sha(path.read_bytes()) == expected, 'fixed_module_changed:' + path.name)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def suffix_statements(text, name):
    tree = ast.parse(text)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    marker = next(i for i, node in enumerate(function.body) if isinstance(node, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'records' for t in node.targets))
    return ast.dump(ast.Module(body=function.body[marker:], type_ignores=[]), include_attributes=False)


def check_science(code):
    pins, _ = metadata(HERE / 'frozen_preparation_dependencies.json', DEPENDENCIES_SHA)
    require(pins['original_prepare_sha256'] == ORIGINAL_PREPARE_SHA, 'protected_prepare_pin_changed')
    for relative, expected in pins['files'].items():
        path = no_symlink(code / relative)
        require(path.is_file() and path.stat().st_size <= 16 * 1024**2
                and sha(path.read_bytes()) == expected, 'frozen_preparation_dependency_changed:' + relative)
    original = (code / ORIGINAL_PREPARE).read_text()
    require(suffix_statements(original, 'prepare') == suffix_statements(Path(__file__).read_text(), '_frozen_prepare_suffix'),
            'frozen_scientific_suffix_AST_changed')
    return pins


def route(args):
    union = fixed_module('_paper1_official_192_union', REPO / UNION_REL, UNION_SHA)
    mapping, mapping_sha = metadata(args.route_records, args.route_records_sha256)
    require(set(mapping) == set(union.RECORDS), 'five_named_route_records_required')
    records = {}; hashes = {}
    for name in union.RECORDS:
        item = mapping[name]
        require(isinstance(item, dict) and set(item) == {'path', 'sha256'}, 'route_record_path_and_SHA_only')
        records[name] = union.read_json(item['path'], item['sha256'])
        hashes[name] = item['sha256']
    require(hashes['source_restore'] == SOURCE_RESTORE_SHA and hashes['formal_source'] == FORMAL_SHA
            and hashes['runtime_bound'] == RUNTIME_BOUND_SHA, 'existing_source_CPU_acceptance_must_be_reused')
    result = union.bound_candidate(union.frozen_catalogue(), records, hashes)
    require(result['source_root'] == str(SOURCE_ROOT) and result['target_root'] == str(TARGET_ROOT), 'fixed_separate_cache_roots_required')
    return result, mapping_sha


def target_exit(args, routed):
    summary, summary_sha = metadata(args.target_restore_summary, args.target_restore_summary_sha256)
    outer, outer_sha = metadata(args.target_restore_outer, args.target_restore_outer_sha256)
    require(summary.get('status') == 'TARGET174_OFFICIAL_BYTES_RESTORED_SCIENTIFIC_GATES_PENDING'
            and summary.get('old_task') == OLD_JOB and type(summary.get('files_verified')) is int
            and summary['files_verified'] == 174 and type(summary.get('verified_bytes')) is int
            and summary['verified_bytes'] == 2515343396
            and summary.get('target_bytes_receipt_sha256') == routed['receipt_sha256']['target_bytes']
            and summary.get('script_sha256') == TARGET_GATE_SHA
            and summary.get('training_authorization') is False
            and type(summary.get('new_source_fits')) is int and summary['new_source_fits'] == 0
            and type(summary.get('target_fits')) is int and summary['target_fits'] == 0
            and type(summary.get('target_predictions')) is int and summary['target_predictions'] == 0
            and summary.get('target_scientific_processing') is False, 'complete_actual_target_restore_summary_required')
    require(outer == {'schema_version': 1, 'status': 'OBSERVED_TARGET_RAW_RESTORE_PROCESS_EXIT',
            'exit_code': 0, 'target_restore_summary_sha256': summary_sha,
            'script_sha256': TARGET_GATE_SHA, 'training_authorization': False}
            and type(outer['schema_version']) is int and type(outer['exit_code']) is int,
            'actual_target_outer_exit_zero_required')
    return summary_sha, outer_sha


def claim(path, obj):
    path = no_symlink(path)
    data = (json.dumps(obj, sort_keys=True, allow_nan=False) + '\n').encode()
    require(len(data) <= MAX_JSON, 'bounded_own_JSON_required')
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def owned_bytes(root):
    total = 0
    stack = [no_symlink(root)]
    while stack:
        path = stack.pop()
        info = no_symlink(path).lstat()
        require(stat.S_ISDIR(info.st_mode), 'own_output_directory_required')
        total += info.st_blocks * 512
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            require((os.fstat(fd).st_dev, os.fstat(fd).st_ino) == (info.st_dev, info.st_ino), 'own_output_directory_changed')
            with os.scandir(fd) as entries:
                for entry in entries:
                    item = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(item.st_mode):
                        stack.append(path / entry.name)
                    else:
                        require(stat.S_ISREG(item.st_mode), 'own_output_symlink_or_special_file')
                        total += item.st_blocks * 512
        finally:
            os.close(fd)
    return total


def current_cgroup():
    result = {}
    for name in ('cpu.max', 'memory.max', 'cpuset.cpus.effective'):
        path = Path('/sys/fs/cgroup') / name
        try:
            with path.open('rb') as stream:
                value = stream.read(2049)
            require(len(value) <= 2048, 'bounded_cgroup_metadata_required')
            result[name] = value.decode().strip()
        except FileNotFoundError:
            result[name] = None
    if result['cpu.max'] is None or result['memory.max'] is None:
        # This Pod previously exposed v1 limits; never substitute host48CPUs.
        for name in ('cpu/cpu.cfs_quota_us', 'cpu/cpu.cfs_period_us', 'cpu,cpuacct/cpu.cfs_quota_us',
                     'cpu,cpuacct/cpu.cfs_period_us', 'memory/memory.limit_in_bytes', 'cpuset/cpuset.cpus'):
            try:
                with (Path('/sys/fs/cgroup') / name).open('rb') as stream:
                    value = stream.read(2049)
                require(len(value) <= 2048, 'bounded_cgroup_metadata_required')
                result[name] = value.decode().strip()
            except FileNotFoundError:
                result[name] = None
    return result


def execute(args):
    require(Path(sys.prefix) == RUNTIME and sys.version_info[:2] == (3, 12), 'existing_repaired_cp312_runtime_required')
    require(re.fullmatch('[0-9a-f]{40}', args.delivery_revision or ''), 'fixed_delivery_revision_required')
    code = no_symlink(args.science_code_dir)
    require(code == SCIENCE_ROOT, 'fixed_existing_scientific_checkout_required')
    revision = subprocess.check_output(['git', '-C', str(code), 'rev-parse', 'HEAD'], text=True).strip()
    require(revision == SCIENCE_REVISION, 'scientific_checkout_revision_changed')
    check_science(code)
    gate_module = fixed_module('_paper1_official_target_operation_gate', REPO / TARGET_GATE_REL, TARGET_GATE_SHA)
    slot = gate_module.validate_slot(args.priority_receipt, expected_operation='target_input_preparation')
    review, review_sha = metadata(args.parent_review, args.parent_review_sha256)
    routed, mapping_sha = route(args)
    target_summary_sha, target_outer_sha = target_exit(args, routed)
    continuity, continuity_sha = metadata(args.continuity_report, CONTINUITY_SHA)
    require(continuity['old_job_id'] == OLD_JOB and continuity['training_authorization'] is False, 'actual_continuity_report_required')
    root = no_symlink(args.output_dir)
    require(root == OUTPUT_ROOT and root.is_dir() and {p.name for p in root.iterdir()} == INITIAL_FILES,
            'new_preparation_review_copy_with_only_three_genuine_prerequisites_required')
    launch, _ = metadata(root / 'launch_record.json', LAUNCH_SHA)
    metadata(root / 'formal_source_acceptance.json', FORMAL_SHA)
    _, numerical_review_sha = metadata(root / 'numerical_execution_review.json')
    require(launch['job_id'] == OLD_JOB and launch['code_revision'] == OLD_REVISION, 'original_launch_identity_required')
    expected = {'status': 'PASS_OFFICIAL_192_DATA_PREPARATION_PARENT_REVIEW', 'operation': 'target_input_preparation',
        'old_job_id': OLD_JOB, 'old_code_revision': OLD_REVISION, 'science_revision': SCIENCE_REVISION,
        'delivery_revision': args.delivery_revision,
        'adapter_sha256': sha(Path(__file__).read_bytes()), 'route_records_sha256': mapping_sha,
        'source_root': str(SOURCE_ROOT), 'target_root': str(TARGET_ROOT), 'output_root': str(root),
        'numerical_execution_review_sha256': numerical_review_sha, 'launch_record_sha256': LAUNCH_SHA,
        'formal_source_acceptance_sha256': FORMAL_SHA, 'continuity_report_sha256': continuity_sha,
        'target_restore_summary_sha256': target_summary_sha, 'target_restore_outer_sha256': target_outer_sha,
        'target_bytes_receipt_sha256': routed['receipt_sha256']['target_bytes'],
        'old_runtime_lock_sha256': OLD_RUNTIME_LOCK_SHA, 'paper2_no_impact_checked_by_dot': True,
        'new_allocation_scope': 'preparation_review_copy_only_excludes_retained_raw_and_runtime',
        'source_runtime_acceptance_reused': True, 'target_predictions_authorized': False,
        'training_authorization': False, 'original_registration_overwrite_authorized': False}
    for key, value in expected.items():
        require(type(review.get(key)) is type(value) and review[key] == value, 'parent_review_identity:' + key)
    cap = review.get('max_new_bytes')
    require(type(cap) is int and 0 < cap <= 3 * GIB and cap <= slot[3]['max_new_bytes'], 'separate_preparation_allocation_cap_required')
    reviewed_at = datetime.fromisoformat(review['reviewed_at_utc'].replace('Z', '+00:00'))
    issued_at = datetime.fromisoformat(slot[3]['issued_at_utc'].replace('Z', '+00:00'))
    require(reviewed_at.tzinfo is not None and reviewed_at <= issued_at
            and (issued_at - reviewed_at).total_seconds() <= 1800, 'fresh_parent_review_before_new_slot_required')
    # Frozen85x80x3x19x320 float32 tensors contain496128000 payload bytes;
    # reserve2GiB upfront for their fixed .npz headers/IDs and bounded audit JSON.
    require(owned_bytes(root) + 2 * GIB <= cap, 'separate_two_GiB_preparation_write_reservation_required')
    require(shutil.disk_usage(root).free >= max(10 * GIB, slot[3]['min_free_bytes'])
            + max(5 * GIB, slot[3]['paper2_reserve_bytes']) + 2 * GIB,
            'full_preparation_write_reservation_above_floor_required')
    start = time.monotonic()
    def time_guard(*_):
        again = gate_module.validate_slot(args.priority_receipt, expected_operation='target_input_preparation')
        require(again[:3] == slot[:3], 'slot_replaced_or_changed')
        _, current_review_sha = metadata(args.parent_review, review_sha)
        require(current_review_sha == review_sha and time.monotonic() - start < 1800, 'review_changed_or_wall_cap_reached')
        require(shutil.disk_usage(root).free >= max(10 * GIB, slot[3]['min_free_bytes'])
                + max(5 * GIB, slot[3]['paper2_reserve_bytes']) + 8 * 1024**2, 'free_floor_Paper2_reserve_and_write_reserve')
    def guard(reservation=8 * 1024**2):
        time_guard()
        require(type(reservation) is int and reservation >= 0, 'explicit_nonnegative_IO_reservation')
        require(owned_bytes(root) + reservation <= cap, 'preparation_allocation_cap_and_write_reserve')
        require(shutil.disk_usage(root).free >= max(10 * GIB, slot[3]['min_free_bytes'])
                + max(5 * GIB, slot[3]['paper2_reserve_bytes']) + reservation,
                'free_floor_Paper2_reserve_and_IO_reservation')
    guard()
    for item in routed['files']:
        prefix = SOURCE_ROOT if item['path'].startswith('bnci/') else TARGET_ROOT
        path = no_symlink(prefix / item['path'])
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_size == item['bytes'], 'actual192_cache_size_or_path_missing')
    claim(root / CLAIM, {'status': 'CLAIMED_ONCE_NO_FIT_AUTHORIZATION', 'at_utc': datetime.now(timezone.utc).isoformat(),
        'old_job_id': OLD_JOB, 'review_sha256': review_sha, 'slot_sha256': sha(slot[1]),
        'route_records_sha256': mapping_sha, 'adapter_sha256': sha(Path(__file__).read_bytes()), 'new_fits': 0})
    transition = {'status': 'NEW_MACHINE_DATA_PREPARATION_TRANSITION_NOT_ORIGINAL_MACHINE_OR_TRAINING',
        'old_job_id': OLD_JOB, 'old_code_revision': OLD_REVISION, 'old_runtime_lock_sha256': OLD_RUNTIME_LOCK_SHA,
        'numerical_code_revision': SCIENCE_REVISION, 'source_runtime_acceptance_archive_sha256': CPU_ACCEPTANCE_ARCHIVE_SHA,
        'delivery_revision': args.delivery_revision, 'adapter_sha256': sha(Path(__file__).read_bytes()),
        'route_records_sha256': mapping_sha,
        'formal_source_acceptance_sha256': FORMAL_SHA, 'runtime_bound_acceptance_sha256': RUNTIME_BOUND_SHA,
        'continuity_report_sha256': CONTINUITY_SHA, 'observed_hostname': socket.gethostname(),
        'python': sys.version, 'python_executable': sys.executable, 'sys_prefix': sys.prefix,
        'effective_cgroup_snapshot': current_cgroup(), 'old_machine_identity_proven': False,
        'original_registration_overwritten': False, 'old_counts': continuity['old_task']['counters'],
        'old_costs': 'UNKNOWN_NOT_ZERO', 'financial_preconditions': 'superseded-by-user',
        'source_runtime_pass_reused': True, 'backup_continuity_verified': False,
        'training_authorization': False, 'new_fits': 0, 'target_predictions_computed': False}
    claim(root / 'new_machine_data_preparation_transition.json', transition)
    scripts = code / 'research_runs/REDESIGN_CLOUD_20261013/scripts'
    sys.path.insert(0, str(scripts))
    pins, _ = metadata(HERE / 'frozen_preparation_dependencies.json', DEPENDENCIES_SHA)
    for name in ('cloud_contract', 'formal_core_inputs', 'numerical_review_gate'):
        require(name not in sys.modules, 'scientific_module_preimport_or_shadowing')
        relative = 'research_runs/REDESIGN_CLOUD_20261013/scripts/' + name + '.py'
        fixed_module(name, code / relative, pins['files'][relative])
    original = fixed_module('_paper1_original_prepare_verified', code / ORIGINAL_PREPARE, ORIGINAL_PREPARE_SHA)
    from numerical_review_gate import verify_review
    verify_review(root)  # Unchanged producer gate; genuine review is never created here.
    tensors = root / 'dreyer_inputs'
    tensors.mkdir()
    old_alarm = signal.signal(signal.SIGALRM, time_guard)
    signal.setitimer(signal.ITIMER_REAL, 1, 1)
    try:
        result = _frozen_prepare_suffix(original, root, TARGET_ROOT, SOURCE_ROOT / 'bnci',
            TARGET_ROOT / 'dreyer_acquisition', tensors, original.now(), guard)
        guard()
        route(args)  # Recheck all five bound JSON identities after actual processing.
        check_science(code)
        require(result['status'] == 'PASS_DATA_PREPARATION_EXPLORATORY' and result['source_file_count'] == 18
                and result['target_file_count'] == 174 and result['retained_participants'] == 85
                and result['retained_events'] == 6800 and result['target_fits'] == 0
                and result['target_predictions_computed'] is False, 'complete_original_scientific_data_gate_required')
        claim(root / 'official_preparation_completion.json', {'status': 'OFFICIAL_192_FROZEN_INPUT_PREPARATION_COMPLETE_TRAINING_STILL_BLOCKED',
            'data_prepare_receipt_sha256': sha((root / 'data_prepare_receipt.json').read_bytes()),
            'route_records_sha256': mapping_sha, 'review_sha256': review_sha, 'slot_sha256': sha(slot[1]),
            'original_prepare_sha256': ORIGINAL_PREPARE_SHA, 'scientific_suffix_AST_identical': True,
            'old_job_id': OLD_JOB, 'new_fits': 0, 'target_fits': 0, 'training_authorization': False,
            'old_accounting_checkpoint_backup_continuity_passed': False})
        return result
    except BaseException as error:
        signal.setitimer(signal.ITIMER_REAL, 0)
        claim(root / 'official_preparation_failure.json', {'status': 'FAILED_OR_BLOCKED_NO_AUTOMATIC_RETRY',
            'error_class': type(error).__name__, 'new_fits': 0, 'training_authorization': False})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_alarm)


def guarded_io(module, guard):
    """Operational local IO guards; producer functions/results are unchanged."""
    def write(path, obj):
        needed = len((json.dumps(obj, indent=2, allow_nan=False) + '\n').encode()) + 65536
        guard(max(8 * 1024**2, needed))
        result = module.write(path, obj)
        guard(0)
        return result
    def verified_tensor(path, arrays, event_ids):
        needed = sum(a.nbytes for a in arrays.values()) + len(event_ids) * max(map(len, event_ids), default=0) * 4 + 65536
        guard(max(8 * 1024**2, needed))
        result = module.verified_tensor(path, arrays, event_ids)
        guard(0)
        return result
    class CopyOnly:
        @staticmethod
        def copyfile(src, dst):
            guard(max(8 * 1024**2, Path(src).stat().st_size + 65536))
            result = module.shutil.copyfile(src, dst)
            guard(0)
            return result
    return write, verified_tensor, CopyOnly


def _frozen_prepare_suffix(module, job_dir, data_dir, src, raw, tensors, started_at, io_guard):
    # Explicit helper bindings only; no producer global is modified or patched.
    ROOT, STUDY, AUDIT = module.ROOT, module.STUDY, module.AUDIT
    read, write, now, sha = module.read, module.write, module.now, module.sha
    source_one, verified_tensor = module.source_one, module.verified_tensor
    source, access, qc, np = module.source, module.access, module.qc, module.np
    ThreadPoolExecutor, json = module.ThreadPoolExecutor, module.json
    write, verified_tensor, shutil = guarded_io(module, io_guard)

    records=read(ROOT/'research_runs/Q8-E001/results/source_files.json')
    # Historical provenance is an array rather than a gate object.
    if len(records)!=18:raise ValueError('source_manifest_incomplete')
    with ThreadPoolExecutor(max_workers=3) as pool:source_files=list(pool.map(lambda r:source_one(r,src,False),records))
    cfg=read(STUDY/'config/experiment.json');_,source_rows,source_audit=source.load_source19(src,cfg)
    del _
    expected_source=read(AUDIT/'evidence/source_exact_input_fingerprints_receipt.json')['source_file_provenance']
    for key in ('array_hashes','source_labels_sha256','source_metadata_sha256','source_sample_ids_sha256'):
     if source_audit[key]!=expected_source[key]:raise ValueError('frozen_source_input_changed:'+key)
    manifest,_=access.verified_plan();access.author_uncertainty_gate();header=access.import_previous('scripts/check_dreyer_metadata.py','cloud_edf_header')
    acquired=[]
    def one(row):return access.run_one(row,raw,data_dir/'pilot_unused',False,header)
    with ThreadPoolExecutor(max_workers=3) as pool:
     for result in pool.map(one,manifest):
      acquired.append(result);print(json.dumps({'stage':'raw_download_verified','completed':len(acquired),'expected':174}),flush=True)
    write(job_dir/'acquisition_receipt.json',{'status':'ALL_174_HASH_HEADER_EVENT_AUDITED_EXPLORATORY_ONLY_FULL_SIGNAL_QC_PENDING','files':acquired,'errors':[],'target_fits':0,'target_predictions':0,'evidence_class':access.CLASS,'independent_confirmation_qualified':False,'all_174_hash_header_event_audited':True})
    frozen_dir=AUDIT/'results/raw-qc-543feb2f';roster=read(frozen_dir/'raw_only_roster.json');rules=qc.verified_rules();modules=qc.pinned_modules();events_by_file={};by_person={};audit_files=[];tensor_files=[]
    for e in roster['events']:
     events_by_file.setdefault(e['source_file'],[]).append(e);by_person.setdefault(e['subject_id'],[]).append(e)
    from collections import Counter
    seen_native=set()
    for person in range(1,88):
     p_name=qc.subject_name(person);buffers={b:[] for b in ['broad','mu','beta']};ids=[]
     for row in sorted((r for r in manifest if int(access.PATH_PATTERN.fullmatch(r['path']).group(1))==person),key=lambda r:r['path']):
      match=access.PATH_PATTERN.fullmatch(row['path']);entry={**row,'subject':person,'run':match.group(2)}
      signal,cues,drops,file_audit=qc.inspect_run(raw/row['path'],entry,rules,modules)
      native=file_audit['native_signal19_sha256']
      if native in seen_native:raise ValueError('duplicate_native_run')
      seen_native.add(native);audit_files.append(file_audit)
      if person in [17,41]:continue
      if drops:raise ValueError('changed_event_context_eligibility')
      expected=events_by_file[row['path']]
      if len(cues)!=len(expected):raise ValueError('frozen_native_event_count_changed')
      for current,frozen in zip(cues,expected):
       for key in ('event_id','cue_sample','ytrue','context_native_start','context_native_stop'):
        if current[key]!=frozen[key]:raise ValueError('frozen_native_event_changed:'+key)
       context=signal[:,current['context_native_start']:current['context_native_stop']]
       if source.array_hash(context)!=frozen['native_context19_sha256']:raise ValueError('native_context_hash_changed')
       arrays=source.transform_context19(signal,512,current['cue_sample'],rules['input_processing'])
       if any(source.array_hash(a)!=frozen['input_sha256'][band] for band,a in arrays.items()):raise ValueError('frozen_target_input_changed')
       for band,a in arrays.items():buffers[band].append(a)
       ids.append(current['event_id'])
     if person not in [17,41]:
      arrays={band:np.stack(v) for band,v in buffers.items()};p=tensors/(p_name+'.npz');digest=verified_tensor(p,arrays,ids)
      tensor_files.append({'subject_id':p_name,'path':str(p),'bytes':p.stat().st_size,'sha256':digest,'n_events':len(ids)})
     print(json.dumps({'stage':'full_signal_input_reconstruction','people_processed':person,'expected':87,'target_fits':0}),flush=True)
    if len(audit_files)!=174 or len(tensor_files)!=85 or sum(x['n_events'] for x in tensor_files)!=6800:raise ValueError('complete_roster_required')
    q=job_dir/'qc';q.mkdir(exist_ok=True);shutil.copyfile(frozen_dir/'raw_only_roster.json',q/'raw_only_roster.json');shutil.copyfile(frozen_dir/'raw_only_event_roster.csv',q/'raw_only_event_roster.csv')
    write(q/'file_signal_audit.json',{'files':audit_files});write(q/'tensor_cache_receipt.json',{'files':tensor_files,'new_model_fits':0,'target_fits':0,'target_predictions_computed':False,'numerical_execution':source.numerical_identity()})
    report={**read(frozen_dir/'full_raw_qc_report.json'),'started_at_utc':started_at,'finished_at_utc':now(),'cloud_exact_reconstruction':True,'source_frozen_qc_report_sha256':sha(frozen_dir/'full_raw_qc_report.json'),'roster_sha256':sha(q/'raw_only_roster.json'),'file_audit_sha256':sha(q/'file_signal_audit.json'),'tensor_cache_receipt_sha256':sha(q/'tensor_cache_receipt.json'),'acquisition_receipt_sha256':sha(job_dir/'acquisition_receipt.json')}
    report['numerical_execution']=source.numerical_identity()
    # Do not mislabel the old audit timestamp/public registration as newly issued.
    report['public_registration']={'code_revision':read(job_dir/'launch_record.json')['code_revision'],'scope':'New pinned cloud reconstruction; original QC registration is preserved in source_frozen_qc_report.'}
    write(q/'full_raw_qc_report.json',report)
    receipt={'status':'PASS_DATA_PREPARATION_EXPLORATORY','checked_at_utc':now(),'source_dir':str(src),'source_data_dir':str(src),'source_raw_files_verified':18,'qualified_independent_confirmation':False,'source_files':source_files,'source_input_audit':source_audit,'raw_dir':str(raw),'tensor_cache':str(tensors),'roster_path':str(q/'raw_only_roster.json'),'roster_sha256':sha(q/'raw_only_roster.json'),'raw_qc_report_path':str(q/'full_raw_qc_report.json'),'tensor_cache_receipt_path':str(q/'tensor_cache_receipt.json'),'independent_confirmation_qualified':False,'author_prior_use':'unknown','target_fits':0,'target_predictions_computed':False,'source_file_count':18,'target_file_count':174,'retained_participants':85,'retained_events':6800,'exact_frozen_input_reconstruction':True,'numerical_execution':source.numerical_identity()}
    write(job_dir/'data_prepare_receipt.json',receipt);return receipt


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--plan', action='store_true')
    mode.add_argument('--execute', action='store_true')
    p.add_argument('--science-code-dir', '--scientific-code', dest='science_code_dir', type=Path, default=SCIENCE_ROOT)
    p.add_argument('--output-dir', type=Path, default=OUTPUT_ROOT)
    p.add_argument('--route-records', type=Path)
    p.add_argument('--route-records-sha256')
    p.add_argument('--parent-review', type=Path)
    p.add_argument('--parent-review-sha256')
    p.add_argument('--priority-receipt', type=Path)
    p.add_argument('--continuity-report', type=Path)
    p.add_argument('--delivery-revision')
    p.add_argument('--target-restore-summary', type=Path)
    p.add_argument('--target-restore-summary-sha256')
    p.add_argument('--target-restore-outer', type=Path)
    p.add_argument('--target-restore-outer-sha256')
    a = p.parse_args(argv)
    if not a.execute:
        check_science(a.science_code_dir)
        print(json.dumps({'status': 'STATIC_OFFICIAL_CACHE_PREPARATION_PLAN_NO_DATA_NO_IMPORTS_NO_FITS',
            'source_root': str(SOURCE_ROOT), 'target_root': str(TARGET_ROOT), 'output_root': str(OUTPUT_ROOT),
            'original_prepare_sha256': ORIGINAL_PREPARE_SHA, 'scientific_suffix_AST_identical': True,
            'target_files': 174, 'target_fits': 0, 'new_fits': 0, 'training_authorization': False}))
        return 0
    if any(getattr(a, n) is None for n in ('delivery_revision', 'route_records', 'route_records_sha256', 'parent_review', 'parent_review_sha256', 'priority_receipt', 'continuity_report',
                                         'target_restore_summary', 'target_restore_summary_sha256', 'target_restore_outer', 'target_restore_outer_sha256')):
        p.error('Execute requires five-record routing bundle/SHA, genuine parent review/SHA, fresh slot and bound continuity JSON.')
    result = execute(a)
    print(json.dumps({'status': result['status'], 'training_authorization': False, 'new_fits': 0}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
