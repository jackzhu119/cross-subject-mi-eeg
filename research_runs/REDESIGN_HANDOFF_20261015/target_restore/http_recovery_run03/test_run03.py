"""Narrow run03 integration tests; only fixed JSON and tiny synthetic bytes.

No HTTP, EEG decoding, archived-code execution, Pod access, scientific imports,
or tests of the transport adapter's response-body implementation occur here.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).parent
FIXTURES = HERE / 'evidence'
PATH = HERE.parent / 'target_restore_run03.py'
SPEC = importlib.util.spec_from_file_location('paper1_target_run03_integration_subject', PATH)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
NOW = datetime(2026, 10, 15, 9, 30, tzinfo=timezone.utc)
PAYLOAD = b'synthetic'


@pytest.fixture(autouse=True)
def actual_failure_fixtures_are_read_only():
    before = {p.name: p.read_bytes() for p in FIXTURES.iterdir() if p.is_file()}
    assert len(before) == 7
    yield
    assert {p.name: p.read_bytes() for p in FIXTURES.iterdir() if p.is_file()} == before


def copy_prior_cache(root):
    root.mkdir()
    for number in ('01', '02'):
        (root / ('target_restore_run' + number + '.claim.json')).write_bytes(
            (FIXTURES / ('run' + number + '.claim.json')).read_bytes())
        journal = (FIXTURES / ('run' + number + '.journal.jsonl')).read_bytes()
        for suffix in ('journal.jsonl', 'log'):
            (root / ('target_restore_run' + number + '.' + suffix)).write_bytes(journal)
    return root


def prior_args(root):
    return SimpleNamespace(data_dir=root,
        prior_run01_outer=FIXTURES / 'run01.outer.json',
        prior_run02_outer=FIXTURES / 'run02.outer.json',
        same_pod_head=FIXTURES / 'same-pod-first-object-head-run01.json')


def helper():
    return SimpleNamespace(safe_path=lambda root, relative: M.safe(Path(root) / relative),
        digest_file=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest())


def synthetic_row():
    return dict(restore_relative_path='dreyer_acquisition/sourcedata/sub-01/eeg/sub-01_task-R1acquisition_eeg.edf',
        bytes=len(PAYLOAD), sha256=hashlib.sha256(PAYLOAD).hexdigest())


def source_metadata():
    return {'metadata_sha256': {k: v[2] for k, v in M.load_module('continuity').BINDINGS.items()}}


def parent_record(source, revision):
    return dict(schema_version=1, status='DOT_PARENT_TARGET_RAW_RESTORE_APPROVED', issuer='dot_parent',
        operation=M.OPERATION, delivery_revision=revision, operation_script_sha256=M.digest(M.__file__),
        frozen_manifest_sha256=M.load_module('transport').FROZEN_SHA256,
        transport_helper_sha256=M.MODULES['transport'][1], priority_helper_sha256=M.MODULES['priority'][1],
        continuity_helper_sha256=M.MODULES['continuity'][1], continuity_report_sha256=M.CONTINUITY_SHA,
        source_runtime_metadata_sha256=source['metadata_sha256'], target_raw_byte_transport_authorized=True,
        paper2_absolute_priority=True, paper2_noninterference_reviewed=True,
        new_target_allocation_separate_from_retained_source_runtime=True,
        old_task_unknowns_and_failures_retained=True, financial_preconditions='superseded-by-user',
        training_authorization=False, GPU_fit_authorized=False, target_scientific_processing_authorized=False,
        source_EEG_read_authorized=False, new_resources_or_credentials_authorized=False,
        automatic_retry_authorized=False, reviewed_at_utc=(NOW - timedelta(seconds=4)).isoformat(),
        expires_at_utc=(NOW + timedelta(minutes=25)).isoformat(), maximum_wall_seconds=1200,
        recovery_identity=M.RECOVERY_ID, prior_failure_archive_sha256=M.FAILURE_ARCHIVE_SHA,
        prior_cache_records_sha256=M.PRIOR_FILES, prior_outer_sha256=M.PRIOR_OUTER_SHA,
        same_pod_head_sha256=M.HEAD_SHA, one_additional_bounded_attempt_authorized=True,
        single_hop_adapter_GO_commit=M.ADAPTER_GO_COMMIT, single_hop_adapter_reviewed=True,
        original_transport_helper_sha256=M.MODULES['original_transport'][1],
        outer_wrapper_sha256=M.digest(M.HERE / 'RUN_RUN03_ONCE.sh'))


def slot_record():
    gate = M.load_module('priority')
    return dict(schema_version=1, status=gate.STATUS, issuer='dot', pod_id=gate.POD_ID,
        container_id=gate.CONTAINER_ID, operation='target_raw_restore',
        issued_at_utc=(NOW - timedelta(seconds=2)).isoformat(),
        not_before_utc=(NOW - timedelta(seconds=1)).isoformat(),
        expires_at_utc=(NOW + timedelta(minutes=20)).isoformat(), max_new_bytes=3 * M.GIB,
        min_free_bytes=10 * M.GIB, paper2_reserve_bytes=5 * M.GIB,
        slot_rationale='Synthetic single run03 integration test, no HTTP or scientific processing',
        **{k: True for k in gate._TRUE_FIELDS}, **{k: False for k in gate._FALSE_FIELDS})


def snapshot(root):
    return {str(p.relative_to(root)): ('link', os.readlink(p)) if p.is_symlink()
            else ('file', p.read_bytes()) for p in root.rglob('*') if p.is_file() or p.is_symlink()}


def test_exact_both_failure_bindings_and_no_original_record_rewrite(tmp_path):
    root = copy_prior_cache(tmp_path / 'cache')
    args = prior_args(root)
    before = snapshot(root)
    bindings = M.prior_failure_bindings(args, root)
    assert len(bindings) == 11
    assert all(M.digest(path) == digest for path, digest in bindings)
    assert M.digest(args.prior_run01_outer) == M.PRIOR_OUTER_SHA['run01']
    assert M.digest(args.prior_run02_outer) == M.PRIOR_OUTER_SHA['run02']
    assert M.FAILURE_ARCHIVE_SHA == {
        'run01': '599a690184f657da06d2dcf35fd519fd6c8d4999115bc763396bf220d4242e43',
        'run02': '6f9bbb8e6070bf0df1a0ffdcd57b484184e9b6d244c82b08bc3285fa0e1bf176'}
    for attribute in ('prior_run01_outer', 'prior_run02_outer', 'same_pod_head'):
        original = getattr(args, attribute)
        changed = tmp_path / (attribute + '.json')
        changed.write_text('{}')
        setattr(args, attribute, changed)
        with pytest.raises(ValueError, match='prior_failure_or_HEAD_binding_changed'):
            M.prior_failure_bindings(args, root)
        setattr(args, attribute, original)
    assert snapshot(root) == before


def test_parent_requires_new_run03_bindings_and_slot_does_not_mutate_original_gate(tmp_path):
    source, revision = source_metadata(), 'a' * 40
    data = parent_record(source, revision)
    path = tmp_path / 'parent.json'
    path.write_text(json.dumps(data))
    assert M.parent_review(path, revision, source, NOW)[0] == data
    for key, value in [('one_additional_bounded_attempt_authorized', False),
            ('prior_cache_records_sha256', {**M.PRIOR_FILES, 'target_restore_run02.claim.json': '0' * 64}),
            ('prior_outer_sha256', {**M.PRIOR_OUTER_SHA, 'run02': '0' * 64}),
            ('prior_failure_archive_sha256', {**M.FAILURE_ARCHIVE_SHA, 'run02': '0' * 64}),
            ('single_hop_adapter_GO_commit', '0' * 40), ('single_hop_adapter_reviewed', False),
            ('original_transport_helper_sha256', '0' * 64), ('outer_wrapper_sha256', '0' * 64),
            ('same_pod_head_sha256', '0' * 64), ('training_authorization', True)]:
        bad = deepcopy(data); bad[key] = value; path.write_text(json.dumps(bad))
        with pytest.raises(ValueError, match='fixed_bindings'):
            M.parent_review(path, revision, source, NOW)
    bad = deepcopy(data); bad.pop('outer_wrapper_sha256'); path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match='exact_schema'):
        M.parent_review(path, revision, source, NOW)
    gate = M.load_module('priority')
    operations = gate.OPERATIONS
    slot = tmp_path / 'slot.json'; record = slot_record(); slot.write_text(json.dumps(record))
    assert M.validate_slot(slot, NOW)[3] == record
    with pytest.raises(ValueError):
        gate.validate_receipt(slot, 'metadata', NOW)
    record['paper1_fit_authorized'] = True; slot.write_text(json.dumps(record))
    with pytest.raises(ValueError, match='no_fit_boundary'):
        M.validate_slot(slot, NOW)
    assert M.load_module('priority').OPERATIONS == operations


def test_preflight_exact_six_old_records_and_full_SHA_cached_tiny_object_reuse(tmp_path):
    root = copy_prior_cache(tmp_path / 'cache')
    row = synthetic_row()
    before = snapshot(root)
    assert M.cache_preflight(root, [row], helper()) == [row]
    assert snapshot(root) == before
    cached = root / row['restore_relative_path']
    cached.parent.mkdir(parents=True)
    cached.write_bytes(PAYLOAD)
    assert M.cache_preflight(root, [row], helper()) == []
    assert {n: (root / n).read_bytes() for n in M.PRIOR_FILES} == {n: before[n][1] for n in M.PRIOR_FILES}


@pytest.mark.parametrize('case', ['partial', 'unknown', 'hash_mismatch', 'symlink', 'new_claim', 'old_record_changed'])
def test_preflight_bad_member_is_preserved_and_refused(tmp_path, case):
    root = copy_prior_cache(tmp_path / case)
    row = synthetic_row()
    if case == 'partial':
        (root / 'unreviewed.partial').write_bytes(b'synthetic-partial')
    elif case == 'unknown':
        (root / 'unreviewed.json').write_text('{}')
    elif case == 'hash_mismatch':
        p = root / row['restore_relative_path']; p.parent.mkdir(parents=True); p.write_bytes(b'badbytes!')
    elif case == 'symlink':
        outside = tmp_path / 'outside.json'; outside.write_text('{}'); (root / 'unexpected').symlink_to(outside)
    elif case == 'new_claim':
        (root / M.CLAIM).write_text('{"already_claimed":true}')
    else:
        (root / 'target_restore_run02.claim.json').write_text('{"changed":true}')
    before = snapshot(root)
    with pytest.raises(ValueError):
        M.cache_preflight(root, [row], helper())
    assert snapshot(root) == before


def test_diagnostic_forwards_only_typed_whitelisted_safe_metadata():
    secret = 'synthetic-secret-must-not-be-serialized'
    error = ValueError(secret)
    error.safe_metadata = {'http_status': True, 'location_port': True,
        'location_scheme': 'https://' + secret, 'location_hostname': secret,
        'query_present': secret, 'fragment_present': False,
        'Location': 'https://private.invalid/?token=' + secret, 'nested': {'password': secret}}
    result = M.diagnostic(error)
    assert result['error_code'] == 'target_restore_controlled_operation_failed'
    assert result['http_status'] is None and result['location_port'] is None
    assert result['fragment_present'] is False
    assert secret not in json.dumps(result) and 'Location' not in result and 'nested' not in result
    assert M.diagnostic(ValueError('target_parent_fixed_bindings'))['error_code'] == 'target_parent_fixed_bindings'
    plain = RuntimeError(secret); plain.safe_metadata = [secret]
    assert secret not in json.dumps(M.diagnostic(plain))


class ControlledAdapterFailure(Exception):
    def __init__(self, status):
        self.code = 'canonical_http_status_rejected' if status == 302 else 'storage_http_status_rejected'
        self.safe_metadata = {'http_status': status, 'location_scheme': 'https',
            'location_hostname': 'other', 'location_port': None, 'query_present': True,
            'fragment_present': False, 'raw_url': 'https://secret.invalid/?token=synthetic-secret'}
        super().__init__('synthetic-secret must not appear in diagnostics')


def coordinator(tmp_path, monkeypatch, *, cached, status=None):
    real_load = M.load_module
    original, continuity, gate = (real_load(n) for n in ('original_transport', 'continuity', 'priority'))
    monkeypatch.setattr(gate, '_clock', lambda current=None: NOW if current is None else current)
    monkeypatch.setattr(M.shutil, 'disk_usage', lambda _: SimpleNamespace(free=100 * M.GIB))
    rows = [dict(r, bytes=len(PAYLOAD), sha256=hashlib.sha256(PAYLOAD).hexdigest())
        for r in original.frozen_plan()['files']]
    total = sum(r['bytes'] for r in rows)
    monkeypatch.setattr(M, 'TOTAL_BYTES', total)
    restore, acceptance = tmp_path / 'source-json', tmp_path / 'acceptance-json'
    restore.mkdir(); acceptance.mkdir()
    bindings = {k: (v[0], 3, hashlib.sha256(b'{}\n').hexdigest()) for k, v in continuity.BINDINGS.items()}
    for key, (name, _, _) in bindings.items():
        ((restore if key in ('restore', 'completion', 'outer') else acceptance) / name).write_bytes(b'{}\n')
    source = {'metadata_sha256': {key: value[2] for key, value in bindings.items()}}
    current = {'status': 'SOURCE_RUNTIME_ACCEPTED_ORIGINAL_TASK_CONTINUITY_AND_TARGET_GATES_PENDING',
        'source_runtime': source, 'training_authorization': False,
        'old_task': {'state': 'OLD_WORK_ROOT_NOT_OBSERVED', 'counters': None}}
    report = tmp_path / 'continuity_review_run01.json'; report.write_text(json.dumps(current))
    monkeypatch.setattr(M, 'CONTINUITY_SHA', M.digest(report))
    fake_continuity = SimpleNamespace(BINDINGS=bindings, source_review=lambda *_: source,
        load=continuity.load, OLD_JOB=continuity.OLD_JOB)
    calls, missing = [], []
    def transfer(row, root, *, control_check, **_resources):
        control_check(); calls.append(row['restore_relative_path'])
        if status is not None:
            raise ControlledAdapterFailure(status)
        path = original.safe_path(root, row['restore_relative_path'])
        existed = path.exists()
        if not existed:
            missing.append(row['restore_relative_path'])
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + '.partial'); temporary.write_bytes(PAYLOAD)
            os.link(temporary, path); temporary.unlink()
        assert path.read_bytes() == PAYLOAD
        control_check()
        return dict(path=row['restore_relative_path'], bytes=len(PAYLOAD), sha256=row['sha256'],
            status='existing_exact_bytes_reused' if existed else 'new_exact_bytes_atomic_publish',
            network_bytes=0 if existed else len(PAYLOAD))
    def verify(root, *, control_check):
        assert status is None, 'A failed first object cannot publish a complete receipt'
        files = []
        for row in rows:
            control_check(); assert (root / row['restore_relative_path']).read_bytes() == PAYLOAD
            files.append(dict(path=row['restore_relative_path'], bytes=len(PAYLOAD), sha256=row['sha256']))
        return dict(schema_version=1, status='FROZEN_174_LOCAL_EDF_BYTES_VERIFIED_SCIENTIFIC_GATES_PENDING',
            frozen_manifest_sha256=original.FROZEN_SHA256, file_count=174, verified_bytes=total, files=files,
            transport='official_nemar_same_byte_edf_not_r2_key_receipt',
            target_header_event_qc_and_input_hash_acceptance=False, accounting_budget_checkpoint_acceptance=False,
            source_and_actual_training_runtime_acceptance=False, new_source_fits=0, target_fits=0,
            target_predictions=0, training_authorization=False)
    fake_transport = SimpleNamespace(FROZEN_SHA256=original.FROZEN_SHA256, CHUNK=original.CHUNK,
        frozen_plan=lambda: dict(files=rows, file_count=174, total_bytes=total, license={'identifier': 'CC-BY-4.0'}),
        safe_path=original.safe_path, digest_file=original.digest_file, transport_one=transfer,
        verify_cached_manifest=verify)
    modules = {'transport': fake_transport, 'original_transport': original,
        'continuity': fake_continuity, 'priority': gate}
    monkeypatch.setattr(M, 'load_module', lambda name: modules[name])
    revision = 'a' * 40
    review = tmp_path / 'parent.json'; review.write_text(json.dumps(parent_record(source, revision)))
    slot = tmp_path / 'slot.json'; slot.write_text(json.dumps(slot_record()))
    root = copy_prior_cache(tmp_path / 'target')
    monkeypatch.setattr(M, 'ROOT', root)
    if cached:
        first = root / rows[0]['restore_relative_path']; first.parent.mkdir(parents=True); first.write_bytes(PAYLOAD)
    args = prior_args(root)
    args.delivery_revision, args.source_restore_root, args.source_acceptance_root = revision, restore, acceptance
    args.continuity_report, args.review_record, args.priority_receipt = report, review, slot
    return args, calls, missing, total


def test_synthetic174_one_cached173_missing_new_claim_receipt_and_no_second_attempt(tmp_path, monkeypatch):
    args, calls, missing, total = coordinator(tmp_path, monkeypatch, cached=True)
    before = {name: (args.data_dir / name).read_bytes() for name in M.PRIOR_FILES}
    result = M.run(args)
    assert result['files_verified'] == 174 and result['verified_bytes'] == total
    assert len(calls) == len(set(calls)) == 174 and len(missing) == len(set(missing)) == 173
    assert {name: (args.data_dir / name).read_bytes() for name in M.PRIOR_FILES} == before
    claim = json.loads((args.data_dir / M.CLAIM).read_text())
    receipt = json.loads((args.data_dir / M.BYTE_RECEIPT).read_text())
    assert M.CLAIM == 'target_restore_run03.claim.json' and M.BYTE_RECEIPT == 'target_bytes_receipt_run03.json'
    assert M.SUMMARY == 'target_restore_run03.json' and result['training_authorization'] is False
    assert claim['old_counters'] is None and claim['prior_cache_records_sha256'] == M.PRIOR_FILES
    assert receipt['file_count'] == 174 and result['single_hop_adapter_sha256'] == M.MODULES['transport'][1]
    assert 'single_hop_adapter_sha256' not in receipt and 'recovery_identity' not in receipt
    assert receipt['training_authorization'] is False and not list(args.data_dir.rglob('*.partial'))
    snapshot_after = snapshot(args.data_dir)
    with pytest.raises(ValueError, match='unknown_member_or_consumed_claim'):
        M.run(args)
    assert len(calls) == 174 and snapshot(args.data_dir) == snapshot_after


@pytest.mark.parametrize('status', [302, 403])
def test_fake_adapter_error_is_sanitized_one_attempt_and_preserves_both_failures(tmp_path, monkeypatch, status):
    args, calls, missing, _ = coordinator(tmp_path, monkeypatch, cached=False, status=status)
    before = {name: (args.data_dir / name).read_bytes() for name in M.PRIOR_FILES}
    with pytest.raises(ControlledAdapterFailure):
        M.run(args)
    assert len(calls) == 1 and missing == []
    assert {name: (args.data_dir / name).read_bytes() for name in M.PRIOR_FILES} == before
    last = json.loads((args.data_dir / M.JOURNAL).read_text().splitlines()[-1])
    assert last['phase'] == 'failed_or_blocked_preserve_no_retry' and last['http_status'] == status
    assert last['location_hostname'] == 'other' and last['query_present'] is True
    assert 'synthetic-secret' not in (args.data_dir / M.JOURNAL).read_text()
    assert not (args.data_dir / M.BYTE_RECEIPT).exists() and not (args.data_dir / M.SUMMARY).exists()
    assert json.loads((args.data_dir / M.CLAIM).read_text())['automatic_retry'] is False
    with pytest.raises(ValueError, match='unknown_member_or_consumed_claim'):
        M.run(args)
    assert len(calls) == 1
