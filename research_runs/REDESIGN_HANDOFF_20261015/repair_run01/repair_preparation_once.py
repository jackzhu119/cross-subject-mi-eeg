"""One reviewed, offline continuation of the retained failed child, never a fit.

This does not call the old prepare(), resolver, downloader, controller run(), or
venv creator. The original failed transaction remains immutable evidence. A new
O_EXCL journal consumes this single repair attempt before the first pip command.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.parser import BytesParser
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import time
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).absolute().parent
BASE_REVISION = '1efe9d1ba2ab8671ad1bf76c360e067fb63fd7ac'
HELPER_REL = 'research_runs/REDESIGN_HANDOFF_20261014/runtime_transition/isolated_training_runtime.py'
CONTROLLER_REL = 'research_runs/REDESIGN_HANDOFF_20261015/runtime_preparation/prepare_runtime_only.py'
CONTROLLER_SHA = '7a1fbc9b364c8dd42faf6894450ae065a49d59a977d4c5470a3c2daffff50cc3'
HELPER_SHA = 'cdd8c2d47fb6e1653e8b5c2eb48de6483d4dd57a0af392f2c1495669e3c0cd9e'
ARCHIVE_SHA = '7c83bcb991857dd99b7cda2b4bd8f9fe467d87217fb3a73c408b7b1474f4b3a0'
RESOLUTION_SHA = 'a0ed2680c8e057a60aec9cde0d736c9869f3ea9e747f5a6216d79766d07f9b5a'
DONOR_SHA = '3a83a9cf93cca3e9813056645bc73f26a9429ee6f1f7bc06f2ae78a1c36471b1'
FAILED_ENDED = datetime(2026, 10, 15, 3, 54, 43, 978652, tzinfo=timezone.utc)
DEADLINE = datetime(2026, 10, 16, 9, 54, tzinfo=timezone.utc)
ENVIRONMENT = Path('/workspace/paper1-training-runtime-cp312-run01')
JOURNAL_NAME = 'repair_run01.journal.jsonl'
RECEIPT_NAME = 'runtime_repair_run01.json'
GIB = 1024 ** 3
REVIEW_TRUE = ('failure_archive_independently_reviewed', 'all79_original_wheels_reviewed',
    'exact_manpage_exception_reviewed', 'paper2_absolute_priority',
    'retained_partial_reuse_only', 'unknown_old_accounting_retained')
REVIEW_FALSE = ('training_authorization', 'budget_reset_authorized',
    'budget_expansion_authorized', 'gpu_import_authorized', 'source_acceptance_authorized',
    'target_EEG_read_authorized', 'automatic_retry_authorized')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def no_symlink(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('regular_path_without_symlink_ancestors_required')
    return path


def fixed_module(name, path, digest):
    path = no_symlink(path)
    if not path.is_file() or sha(path) != digest:
        raise ValueError('fixed_source_sha_mismatch:' + name)
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def verify_checkout(root, revision, paths):
    no_symlink(root)
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('fixed_revision_required')
    if subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip() != revision:
        raise ValueError('fixed_checkout_head_mismatch')
    if subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain'], text=True):
        raise ValueError('fixed_checkout_must_be_clean_do_not_reset')
    values = {}
    for rel in paths:
        path = no_symlink(root / rel)
        committed = subprocess.check_output(['git', '-C', str(root), 'show', revision + ':' + rel])
        if path.read_bytes() != committed:
            raise ValueError('uncommitted_repair_source')
        values[rel] = hashlib.sha256(committed).hexdigest()
    return values


def validate_review(value, ctrl, repair_sha, policy_sha, index_sha, current, repair_revision):
    bindings = {'schema_version': 1, 'status': 'DOT_PARENT_SINGLE_OFFLINE_REPAIR_APPROVED',
        'issuer': 'dot_parent', 'failure_archive_sha256': ARCHIVE_SHA,
        'wheel_resolution_sha256': RESOLUTION_SHA, 'donor_report_sha256': DONOR_SHA,
        'base_revision': BASE_REVISION, 'repair_controller_sha256': repair_sha,
        'repair_revision': repair_revision,
        'manpage_policy_sha256': policy_sha, 'wheel_cache_index_sha256': index_sha,
        'environment': str(ENVIRONMENT)}
    allowed = set(bindings) | set(REVIEW_TRUE) | set(REVIEW_FALSE) | {
        'reviewed_at_utc', 'expires_at_utc', 'maximum_wall_seconds', 'review_notes'}
    if not isinstance(value, dict) or set(value) != allowed:
        raise ValueError('exact_repair_parent_review_schema_required')
    if type(value['schema_version']) is not int or any(value[k] != v for k, v in bindings.items()):
        raise ValueError('repair_parent_review_binding_mismatch')
    if any(value[k] is not True for k in REVIEW_TRUE) or any(value[k] is not False for k in REVIEW_FALSE):
        raise ValueError('repair_only_review_cannot_grant_training_or_budget')
    reviewed, end = (ctrl.timestamp(value[k]) for k in ('reviewed_at_utc', 'expires_at_utc'))
    if not FAILED_ENDED < reviewed <= current < end <= DEADLINE:
        raise ValueError('fresh_repair_review_after_failure_and_before_deadline_required')
    seconds = value['maximum_wall_seconds']
    if type(seconds) is not int or not 1 <= seconds <= 1200:
        raise ValueError('repair_wall_cap_1_to1200_seconds')
    if not isinstance(value['review_notes'], str) or not value['review_notes'].strip():
        raise ValueError('actual_repair_review_notes_required')
    return reviewed, end, seconds


def failed_archive(path):
    path = no_symlink(path)
    if path.stat().st_size != 423996 or sha(path) != ARCHIVE_SHA:
        raise ValueError('exact_failed_archive_required')
    with tarfile.open(path, 'r:gz') as archive:
        members = archive.getmembers()
        if len(members) != 27 or len({m.name for m in members}) != 27:
            raise ValueError('failure_archive_exact27_members_required')
        result = {}
        for item in members:
            p = Path(item.name)
            if not item.isfile() or p.is_absolute() or '..' in p.parts or item.size > 2 * 1024**2:
                raise ValueError('bounded_regular_failure_payload_required')
            result[item.name] = archive.extractfile(item).read()
    return result


def bound_partial_files(archive, donor):
    """No diagnostic re-run: compare the retained failed transaction's bytes."""
    for name in ('pyvenv.cfg', 'gpu-donor-constraints.txt', 'runtime_plan.json',
                 'wheel-resolution.json', 'resolved-lightweight-wheels.txt'):
        path = no_symlink(ENVIRONMENT / name)
        if not path.is_file() or path.read_bytes() != archive['partial-environment/' + name]:
            raise ValueError('retained_partial_changed:' + name)
    if sha(ENVIRONMENT / 'wheel-resolution.json') != RESOLUTION_SHA:
        raise ValueError('failed_resolution_not_exact')
    cfg = (ENVIRONMENT / 'pyvenv.cfg').read_text()
    if 'include-system-site-packages = false' not in cfg or 'version = 3.12.3' not in cfg:
        raise ValueError('retained_cp312_isolation_not_verified')
    for name in ('runtime_preparation.json', RECEIPT_NAME, JOURNAL_NAME):
        if (ENVIRONMENT / name).exists() or (ENVIRONMENT / name).is_symlink():
            raise ValueError('already_prepared_or_repair_attempt_consumed:' + name)
    old_files = ('paper1-runtime-prepare-run01.stdout.json', 'paper1-runtime-prepare-run01.stderr.log',
                 'paper1-runtime-prepare-run01.install.log', 'paper1-runtime-prepare-run01.stdout.json.dispatch.json')
    for name in old_files:
        path = no_symlink(ENVIRONMENT.parent / name)
        if not path.is_file() or path.read_bytes() != archive['controller/' + name]:
            raise ValueError('original_failed_evidence_changed_or_missing:' + name)
    failure = json.loads(archive['controller/paper1-runtime-prepare-run01.stdout.json.dispatch.json'])
    if (failure.get('status') != 'PREPARATION_FAILED_OR_BLOCKED_RETAIN_OWN_EVIDENCE_NO_RETRY'
            or failure.get('child_exit_code') != 1 or failure.get('controller_sha256') != CONTROLLER_SHA
            or failure.get('training_authorization') is not False):
        raise ValueError('original_failure_identity_not_verified')
    return [ENVIRONMENT.parent / name for name in old_files]


def validate_seed_site(site, donor):
    """Fresh metadata check: the archive did NOT inventory this child site."""
    no_symlink(site)
    links = {x['name']: x['path'] for x in donor['components']}
    for name, target in links.items():
        p = site / name
        if not p.is_symlink() or p.resolve() != Path(target).resolve():
            raise ValueError('retained_gpu_component_mapping_changed')
    extra = {p.name for p in site.iterdir()} - set(links)
    pip_meta = [n for n in extra if re.fullmatch(r'pip-[0-9A-Za-z_.+!-]+\.dist-info', n)]
    if len(pip_meta) != 1 or extra != {'pip', pip_meta[0]}:
        raise ValueError('uninstalled_partial_requires_only_seed_pip_and_gpu_links')
    for folder in (site / 'pip', site / pip_meta[0]):
        no_symlink(folder)
        if not folder.is_dir():
            raise ValueError('regular_seed_pip_required')
        if any(p.is_symlink() or (not p.is_dir() and not p.is_file()) for p in folder.rglob('*')):
            raise ValueError('seed_pip_symlink_or_special_file_forbidden')
    meta_path, record_path = site / pip_meta[0] / 'METADATA', site / pip_meta[0] / 'RECORD'
    meta = BytesParser().parsebytes(meta_path.read_bytes())
    if meta.get('Name') != 'pip' or not meta.get('Version') or not record_path.is_file():
        raise ValueError('seed_pip_metadata_required')
    return {'name': 'pip', 'version': meta['Version'], 'METADATA_sha256': sha(meta_path),
        'RECORD_sha256': sha(record_path), 'site_entries': sorted(p.name for p in site.iterdir()),
        'historical_site_inventory_available': False, 'freshly_observed_only': True}


def validate_child_layout(donor):
    no_symlink(ENVIRONMENT)
    if not ENVIRONMENT.is_dir():
        raise ValueError('retained_partial_environment_required_no_second_venv')
    expected_top = {'bin', 'bounded-temp', 'gpu-donor-constraints.txt', 'include', 'lib',
        'lib64', 'pyvenv.cfg', 'resolved-lightweight-wheels.txt', 'reviewed-wheels',
        'runtime_plan.json', 'wheel-resolution.json'}
    if {p.name for p in ENVIRONMENT.iterdir()} != expected_top:
        raise ValueError('retained_partial_top_level_differs_from_failure_inventory')
    site = ENVIRONMENT / 'lib/python3.12/site-packages'
    seed = validate_seed_site(site, donor)
    expected = {'bin/python': '/usr/bin/python3', 'bin/python3': 'python',
        'bin/python3.12': 'python', 'lib64': 'lib'}
    # Ubuntu venv may use python -> /usr/bin/python3 and aliases -> python;
    # compare the terminal identity, retaining its exact observed link spelling.
    observed = {}
    for rel in expected:
        p = ENVIRONMENT / rel
        if not p.is_symlink():
            raise ValueError('expected_venv_interpreter_or_lib_alias_required')
        terminal = Path('/usr/bin/python3').resolve() if rel != 'lib64' else (ENVIRONMENT / 'lib').resolve()
        if p.resolve() != terminal:
            raise ValueError('child_interpreter_or_lib_alias_escape')
        observed[rel] = os.readlink(p)
    allowed = {site / n for n in (x['name'] for x in donor['components'])} | {ENVIRONMENT / n for n in expected}
    for p in ENVIRONMENT.rglob('*'):
        if p.is_symlink() and p not in allowed:
            raise ValueError('unexpected_partial_symlink')
        if not p.is_symlink() and not p.is_file() and not p.is_dir():
            raise ValueError('special_partial_member_forbidden')
    share = ENVIRONMENT / 'share'
    if share.exists() or share.is_symlink():
        raise ValueError('manpage_destination_must_not_preexist_in_uninstalled_child')
    return site, seed, observed


def validate_cached_index(items, index, wheels):
    rows = index['wheels']
    if len(items) != 79 or len(rows) != 79:
        raise ValueError('exact_original79_wheel_closure_required')
    expected = {row['file']: row for row in rows}
    if len(expected) != 79 or {p.name for p in wheels.iterdir()} != set(expected):
        raise ValueError('exact_original_wheel_cache_filenames_required')
    bysha = {x['download_info']['archive_info']['hashes']['sha256']: x for x in items}
    if len(bysha) != 79:
        raise ValueError('unique79_resolution_hashes_required')
    paths = []
    for filename, row in sorted(expected.items()):
        path = no_symlink(wheels / filename)
        if not path.is_file() or path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError('cached_original_wheel_bytes_changed:' + filename)
        item = bysha.get(row['sha256'])
        if item is None or item['download_info']['url'] != row['official_url']:
            raise ValueError('original_resolution_url_or_hash_binding_changed')
        parsed = urlsplit(row['official_url'])
        if (parsed.scheme != 'https' or parsed.hostname != 'files.pythonhosted.org' or parsed.username
                or parsed.password or parsed.query or parsed.fragment or unquote(Path(parsed.path).name) != filename):
            raise ValueError('exact_official_wheel_url_required_no_fetch')
        if item['metadata']['name'] != row['name'] or item['metadata']['version'] != row['version']:
            raise ValueError('original_wheel_name_or_version_changed')
        paths.append(path)
    return paths


def offline_commands(paths):
    py = str(ENVIRONMENT / 'bin/python')
    return [[py, '-I', '-B', '-m', 'pip', 'install', '--no-deps', '--no-index',
             '--no-cache-dir', '--disable-pip-version-check', *map(str, paths)],
            [py, '-I', '-B', '-m', 'pip', 'check']]


class Journal:
    def __init__(self, path, initial):
        self.path = no_symlink(path)
        self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        self.append('REPAIR_ATTEMPT_CONSUMED_BEFORE_INSTALL', initial)

    def append(self, stage, value):
        raw = json.dumps({'stage': stage, 'at_utc': datetime.now(timezone.utc).isoformat(), **value}, sort_keys=True).encode() + b'\n'
        os.write(self.fd, raw); os.fsync(self.fd)

    def close(self):
        os.close(self.fd)


def resource_check(ctrl, paths, permit):
    permit.assert_active()
    if permit.paper2_reserve_bytes < 5 * GIB or permit.max_new_bytes <= 0:
        raise ValueError('at_least5GiB_paper2_reserve_and_nonzero_totalcap_required')
    used = sum(ctrl.allocated(p) for p in (ENVIRONMENT, *paths))
    if used + 65536 > min(3 * GIB, permit.max_new_bytes):
        raise ValueError('original_partial_plus_repair_evidence_exceeds_total3GiB_cap')
    if shutil.disk_usage(ENVIRONMENT.parent).free < max(10 * GIB, permit.min_free_bytes) + permit.paper2_reserve_bytes:
        raise ValueError('10GiB_plus_actual_paper2_reserve_floor_reached')
    for p in paths:
        if p.exists() and (p.is_symlink() or not p.is_file() or p.stat().st_size > 8 * 1024**2):
            raise ValueError('regular_bounded_repair_evidence_required')
    return used


def run_owned(command, log, ctrl, runtime, checkpoint):
    env = runtime.clean_env()
    # Retain the helper's existing per-child temporary path, never global temp.
    temp = ENVIRONMENT / 'bounded-temp'
    no_symlink(temp)
    if not temp.is_dir():
        raise ValueError('original_bounded_temp_directory_required')
    env['TMPDIR'] = str(temp)
    checkpoint()
    fd = os.open(log, os.O_WRONLY | os.O_APPEND | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'ab') as stream:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('regular_own_repair_log_required')
        stream.write(json.dumps(command).encode() + b'\n'); stream.flush()
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
            env=env, start_new_session=True)
        known = {}
        try:
            while process.poll() is None:
                ctrl.remember_descendants(process.pid, known, ctrl.process_table())
                checkpoint()
                try:
                    process.wait(timeout=0.25)
                except subprocess.TimeoutExpired:
                    pass
            checkpoint()
            if process.returncode:
                raise ValueError('offline_child_nonzero_inspect_retained_repair_log')
        except BaseException:
            ctrl.stop_owned(process, known)
            raise


def installed_metadata(site, donor, items):
    expected = {re.sub('[-_.]+', '-', x['metadata']['name']).lower(): x['metadata']['version'] for x in items}
    expected.update({re.sub('[-_.]+', '-', n).lower(): v['version'] for n, v in donor['distributions'].items()})
    found = {}
    for p in site.glob('*.dist-info'):
        if p.is_symlink() and p.name not in {x['name'] for x in donor['components']}:
            raise ValueError('unexpected_installed_metadata_link')
        meta = BytesParser().parsebytes((p / 'METADATA').read_bytes())
        name = re.sub('[-_.]+', '-', meta.get('Name', '')).lower()
        if name in found:
            raise ValueError('duplicate_installed_distribution_metadata')
        found[name] = meta.get('Version')
    actual = {k: v for k, v in found.items() if k != 'pip'}
    if actual != expected:
        raise ValueError('installed_complete79_closure_or_gpu_versions_changed')
    return found


def run(args):
    code = no_symlink(args.code_dir)
    if not re.fullmatch('[0-9a-f]{40}', args.repair_revision):
        raise ValueError('fixed_repair_revision_required')
    # Three small externally pinned files suffice; no second repository/venv.
    # The parent's actual review binds their bytes and public delivery revision.
    policy_sha, index_sha = (sha(no_symlink(HERE / name)) for name in
                            ('manpage_policy.py', 'frozen_wheel_cache_index.json'))
    ctrl = fixed_module('paper1_original_controller_utilities', args.prior_controller, CONTROLLER_SHA)
    verify_checkout(code, BASE_REVISION, (HELPER_REL, ctrl.GATE_REL, ctrl.REQ_REL))
    runtime = fixed_module('paper1_original_runtime_for_offline_repair', code / HELPER_REL, HELPER_SHA)
    runtime.fixed_checkout(BASE_REVISION)
    archive = failed_archive(args.failure_archive)
    donor, _, _ = ctrl.regular_json(args.donor_report, 22450, 22450, DONOR_SHA)
    review, review_sha, review_identity = ctrl.regular_json(args.review_record, 16384)
    current = datetime.now(timezone.utc)
    reviewed, review_end, seconds = validate_review(review, ctrl, sha(__file__),
        policy_sha, index_sha, current, args.repair_revision)
    policy = fixed_module('paper1_exact_manpage_exception', HERE / 'manpage_policy.py', policy_sha)
    permit = runtime.arm_priority(args.priority_receipt, 'runtime_preparation')
    old_slot = json.loads(archive['controller/paper1-runtime-prepare-run01.stdout.json.dispatch.json'])['slot_sha256']
    if (permit.receipt_sha256 == old_slot or ctrl.timestamp(permit.receipt['issued_at_utc']) < reviewed
            or ctrl.timestamp(permit.receipt['expires_at_utc']) > review_end):
        raise ValueError('new_repair_slot_after_parent_review_required')
    original_evidence = bound_partial_files(archive, donor)
    site, seed, interpreter_links = validate_child_layout(donor)
    # stdlib sysconfig only, after site-startup entries and executable links are checked.
    layout = json.loads(subprocess.check_output([str(ENVIRONMENT / 'bin/python'), '-I', '-B', '-c',
        'import sys,sysconfig,json; print(json.dumps({"version":".".join(map(str,sys.version_info[:3])),"SOABI":sysconfig.get_config_var("SOABI"),"purelib":sysconfig.get_path("purelib"),"platlib":sysconfig.get_path("platlib"),"scripts":sysconfig.get_path("scripts"),"data":sysconfig.get_path("data")}))'],
        env=runtime.clean_env(), timeout=30))
    if layout != {'version': '3.12.3', 'SOABI': donor['SOABI'], 'purelib': str(site),
            'platlib': str(site), 'scripts': str(ENVIRONMENT / 'bin'), 'data': str(ENVIRONMENT)}:
        raise ValueError('actual_cp312_child_and_data_scheme_required')
    before = runtime.donor_observation('/usr/bin/python3')
    if runtime.identity(before) != runtime.identity(donor):
        raise ValueError('donor_metadata_changed_since_original_inventory')
    resolution = json.loads(archive['partial-environment/wheel-resolution.json'])
    items = runtime.validate_plan(resolution, donor['distributions'])
    index, _, _ = ctrl.regular_json(HERE / 'frozen_wheel_cache_index.json', 2 * 1024**2,
                                  expected_sha=index_sha)
    paths = validate_cached_index(items, index, no_symlink(ENVIRONMENT / 'reviewed-wheels'))
    budget = policy.validate_cached_wheels(ENVIRONMENT / 'reviewed-wheels', items,
        {x['name'] for x in donor['components']}, runtime=runtime, environment=ENVIRONMENT)
    log = no_symlink(args.log)
    if log.parent != ENVIRONMENT.parent or log.exists() or log.is_symlink():
        raise ValueError('new_direct_workspace_repair_log_required')
    protected = (HERE, code, args.prior_controller, args.failure_archive, args.donor_report, args.review_record, args.priority_receipt)
    if any(log == Path(p).absolute() or log.is_relative_to(Path(p).absolute()) for p in protected):
        raise ValueError('repair_log_overlaps_protected_input')
    owned = [log, *original_evidence]
    used_before = resource_check(ctrl, owned, permit)
    floor = max(10 * GIB, permit.min_free_bytes) + permit.paper2_reserve_bytes
    if shutil.disk_usage(ENVIRONMENT.parent).free < floor + 2 * budget['wheel_expanded_bytes'] + 256 * 1024**2:
        raise ValueError('installation_peak_and_paper2_free_reservation_required')
    clock, peak = time.monotonic(), used_before
    journal = Journal(ENVIRONMENT / JOURNAL_NAME, {'repair_controller_sha256': sha(__file__),
        'repair_revision': args.repair_revision, 'fixed_base_revision': BASE_REVISION,
        'failure_archive_sha256': ARCHIVE_SHA, 'wheel_resolution_sha256': RESOLUTION_SHA,
        'review_sha256': review_sha, 'slot_sha256': permit.receipt_sha256,
        'seed_pip_fresh_metadata': seed, 'observed_existing_owned_bytes': used_before,
        'historical_partial_du_bytes': 165703680, 'original_total_storage_cap_bytes': 3 * GIB,
        'actual_total_storage_cap_bytes': min(3 * GIB, permit.max_new_bytes),
        'actual_reserved_free_floor_bytes': floor, 'disk_budget': budget,
        'training_authorization': False, 'old_accounting_unknown': True,
        'budget_reset': False, 'budget_expanded': False})

    def checkpoint():
        nonlocal peak
        fresh, digest, identity = ctrl.regular_json(args.review_record, 16384)
        if digest != review_sha or identity != review_identity:
            raise ValueError('repair_parent_review_revoked_replaced_or_changed')
        if sha(HERE / 'manpage_policy.py') != policy_sha or sha(HERE / 'frozen_wheel_cache_index.json') != index_sha:
            raise ValueError('repair_policy_or_index_bytes_changed')
        validate_review(fresh, ctrl, sha(__file__), policy_sha, index_sha, datetime.now(timezone.utc), args.repair_revision)
        peak = max(peak, resource_check(ctrl, owned, permit))
        if time.monotonic() - clock >= seconds:
            raise ValueError('single_repair_wall_timeout')

    try:
        fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        os.close(fd)
        for command in offline_commands(paths):
            journal.append('OWNED_OFFLINE_CHILD_START', {'command': command})
            run_owned(command, log, ctrl, runtime, checkpoint)
            journal.append('OWNED_OFFLINE_CHILD_EXIT0', {'command': command})
        versions = installed_metadata(site, donor, items)
        validate_cached_index(items, index, ENVIRONMENT / 'reviewed-wheels')
        policy.verify_installed_manpages(ENVIRONMENT, budget['approved_manpage_members'])
        after = runtime.donor_observation('/usr/bin/python3')
        if runtime.identity(before) != runtime.identity(after):
            raise ValueError('donor_metadata_changed_during_repair')
        for name, target in ((x['name'], x['path']) for x in donor['components']):
            if not (site / name).is_symlink() or (site / name).resolve() != Path(target).resolve():
                raise ValueError('gpu_donor_link_changed_during_repair')
        checkpoint()
        result = {'status': 'REPAIRED_PREPARED_IMPORT_SOURCE_REVIEW_PENDING',
            'repair_revision': args.repair_revision, 'repair_controller_sha256': sha(__file__),
            'original_base_revision': BASE_REVISION, 'environment': str(ENVIRONMENT),
            'failure_archive_sha256': ARCHIVE_SHA, 'wheel_resolution_sha256': RESOLUTION_SHA,
            'donor_report_sha256': DONOR_SHA, 'review_sha256': review_sha,
            'slot_sha256': permit.receipt_sha256, 'disk_budget': budget,
            'installed_versions_metadata_only': versions, 'interpreter_links': interpreter_links,
            'actual_total_owned_bytes': resource_check(ctrl, owned, permit),
            'observed_peak_owned_bytes': peak, 'donor_metadata_unchanged': True,
            'no_resolver_or_download_executed': True, 'no_second_environment_created': True,
            'runtime_import_acceptance_passed': False, 'source_acceptance_passed': False,
            'old_accounting_reconciled': False, 'old_cost_known': False,
            'target_EEG_read': False, 'new_fits': 0, 'budget_reset': False,
            'budget_expanded': False, 'training_authorization': False,
            'future_acceptance_adapter_review_required': True}
        # A distinct receipt never impersonates the original failed transaction.
        runtime.emit(ENVIRONMENT / RECEIPT_NAME, result)
        journal.append('REPAIR_PREPARATION_COMPLETE_ACCEPTANCE_STILL_BLOCKED',
            {'repair_receipt_sha256': sha(ENVIRONMENT / RECEIPT_NAME)})
        print(json.dumps(result, indent=2)); return 0
    except BaseException as exc:
        journal.append('REPAIR_FAILED_OR_CANCELLED_NO_AUTOMATIC_RETRY', {'error': type(exc).__name__ + ':' + str(exc)})
        raise
    finally:
        journal.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('prior-controller', 'code-dir', 'failure-archive', 'donor-report',
                 'review-record', 'priority-receipt', 'log'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--repair-revision', required=True)
    try:
        raise SystemExit(run(p.parse_args()))
    except Exception as exc:
        print(json.dumps({'status': 'REPAIR_BLOCKED_OR_FAILED_RETAIN_ALL_EVIDENCE',
            'error': type(exc).__name__ + ':' + str(exc), 'training_authorization': False,
            'new_fits': 0, 'automatic_retry': False}), file=sys.stderr)
        raise SystemExit(3)


if __name__ == '__main__':
    main()
