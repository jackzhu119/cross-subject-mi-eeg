"""Focused synthetic metadata/cache tests; no provider request or EEG contents."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = Path(__file__).with_name('target_restore_once.py')
SPEC = importlib.util.spec_from_file_location('target_restore_tests_subject', PATH)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
NOW = datetime(2026, 10, 15, 8, 0, tzinfo=timezone.utc)


def slot():
    gate = M.load_module('priority')
    return dict(schema_version=1, status=gate.STATUS, issuer='dot', pod_id=gate.POD_ID,
        container_id=gate.CONTAINER_ID, operation='target_raw_restore',
        issued_at_utc=(NOW - timedelta(seconds=2)).isoformat(),
        not_before_utc=(NOW - timedelta(seconds=1)).isoformat(),
        expires_at_utc=(NOW + timedelta(minutes=20)).isoformat(),
        max_new_bytes=3 * M.GIB, min_free_bytes=10 * M.GIB,
        paper2_reserve_bytes=5 * M.GIB, slot_rationale='Synthetic explicit target operation',
        **{k: True for k in gate._TRUE_FIELDS}, **{k: False for k in gate._FALSE_FIELDS})


def test_slot_extends_only_explicit_target_operations_without_mutating_original(tmp_path):
    gate = M.load_module('priority')
    original_operations = gate.OPERATIONS
    path = tmp_path / 'slot.json'
    data = slot()
    path.write_text(json.dumps(data))
    result = M.validate_slot(path, NOW)
    assert result[3]['operation'] == 'target_raw_restore'
    with pytest.raises(ValueError):
        gate.validate_receipt(path, 'metadata', NOW)
    data['operation'] = 'target_input_preparation'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        M.validate_slot(path, NOW)
    assert M.validate_slot(path, NOW, expected_operation='target_input_preparation')[3] == data
    assert M.load_module('priority').OPERATIONS == original_operations


def test_slot_rejects_wrong_identity_bool_reserve_expiry_and_gpu_authority(tmp_path):
    path = tmp_path / 'slot.json'
    for key, value in [('operation', 'metadata'), ('container_id', 'old-container'),
            ('max_new_bytes', True), ('paper2_reserve_bytes', 5 * M.GIB - 1),
            ('expires_at_utc', NOW.isoformat()), ('paper1_fit_authorized', True),
            ('paper2_no_impact_checked_by_dot', False)]:
        data = slot(); data[key] = value; path.write_text(json.dumps(data))
        with pytest.raises(ValueError):
            M.validate_slot(path, NOW)
    path.unlink(); path.symlink_to(tmp_path / 'missing.json')
    with pytest.raises(ValueError):
        M.validate_slot(path, NOW)


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
        expires_at_utc=(NOW + timedelta(minutes=25)).isoformat(), maximum_wall_seconds=1200)


def test_parent_review_binds_real_source_continuity_manifest_and_no_science_scope(tmp_path):
    source = {'metadata_sha256': {k: v[2] for k, v in M.load_module('continuity').BINDINGS.items()}}
    revision = 'a' * 40
    data = parent_record(source, revision)
    path = tmp_path / 'parent.json'; path.write_text(json.dumps(data))
    assert M.parent_review(path, revision, source, NOW)[0] == data
    for key, value in [('continuity_report_sha256', 'b' * 64), ('frozen_manifest_sha256', 'c' * 64),
            ('training_authorization', True), ('source_EEG_read_authorized', True), ('maximum_wall_seconds', 1201)]:
        bad = dict(data); bad[key] = value; path.write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            M.parent_review(path, revision, source, NOW)


def helper():
    return SimpleNamespace(safe_path=lambda root, relative: M.safe(Path(root) / relative),
        digest_file=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest())


def rows():
    return [{'restore_relative_path': 'dreyer_acquisition/sourcedata/sub-01/eeg/sub-01_task-R1acquisition_eeg.edf',
        'bytes': 9, 'sha256': hashlib.sha256(b'synthetic').hexdigest()}]


def test_cache_preflight_reuses_only_full_exact_bytes_and_preserves_unknown_partial(tmp_path, monkeypatch):
    root = tmp_path / 'target'; row = rows()[0]
    path = root / row['restore_relative_path']
    path.parent.mkdir(parents=True); path.write_bytes(b'synthetic')
    assert M.cache_preflight(root, [row], helper()) == []
    path.with_suffix('.edf.partial').write_bytes(b'partial')
    with pytest.raises(ValueError, match='unknown_member'):
        M.cache_preflight(root, [row], helper())
    assert path.with_suffix('.edf.partial').read_bytes() == b'partial'
    path.with_suffix('.edf.partial').unlink(); path.write_bytes(b'bad')
    with pytest.raises(ValueError, match='size_sha_mismatch'):
        M.cache_preflight(root, [row], helper())
    assert path.read_bytes() == b'bad'
    def unreadable(*args, **kwargs):
        kwargs['onerror'](PermissionError(13, 'synthetic unreadable directory', str(root)))
    monkeypatch.setattr(M.os, 'walk', unreadable)
    with pytest.raises(PermissionError):
        M.cache_preflight(root, [row], helper())


def test_claim_is_not_reusable_and_symlink_or_missing_root_is_not_zero(tmp_path):
    root = tmp_path / 'target'; root.mkdir()
    (root / M.CLAIM).write_text('{}')
    with pytest.raises(ValueError, match='unknown_member_or_consumed_claim'):
        M.cache_preflight(root, rows(), helper())
    (root / 'link').symlink_to(tmp_path / 'outside')
    with pytest.raises(ValueError, match='special_member'):
        M.allocated(root)
    with pytest.raises(ValueError, match='existing_root'):
        M.allocated(tmp_path / 'absent')
    fifo = tmp_path / 'fifo.json'; os.mkfifo(fifo)
    with pytest.raises(ValueError, match='bounded_regular_metadata'):
        M.digest(fifo)
    oversized = tmp_path / 'oversized.json'; oversized.write_bytes(b'x' * (2 * 1024**2 + 1))
    with pytest.raises(ValueError, match='bounded_regular_metadata'):
        M.digest(oversized)
    assert M.diagnostic(ValueError('target_restore_cached_size_sha_mismatch_preserved'))['error_code'] == 'target_restore_cached_size_sha_mismatch_preserved'
    error = FileNotFoundError(2, 'arbitrary message must not be copied', '/private/sub-01_task-R1acquisition_eeg.edf')
    assert M.diagnostic(error)['affected_basename'] == 'sub-01_task-R1acquisition_eeg.edf'
    assert 'private' not in json.dumps(M.diagnostic(error))


def test_atomic_publication_finishes_before_synchronous_counter(tmp_path):
    root = tmp_path / 'target'; root.mkdir()
    M.atomic(root / M.SUMMARY, {'status': 'synthetic'})
    assert json.loads((root / M.SUMMARY).read_text()) == {'status': 'synthetic'}
    assert not list(root.glob('*.tmp-*'))
    assert M.allocated(root) == sum(p.lstat().st_blocks * 512 for p in (root, *root.rglob('*')))


def test_frozen_public_catalogue_metadata_retains174_edf_license_and_exact_bytes():
    transport = M.load_module('transport')
    plan = transport.frozen_plan()  # Reads frozen repository JSON/text only.
    assert plan['file_count'] == 174 and plan['total_bytes'] == M.TOTAL_BYTES
    assert plan['license']['identifier'] == 'CC-BY-4.0'
    assert plan['transport_policy']['automatic_retries'] == 0
    assert plan['frozen_manifest_sha256'] == '2cfdf35aa7990df880826d1b84d1230e0bda3c9393c17d3ec6e27b7b311d2bf2'
    assert all(r['url'].startswith('https://data.nemar.org/nm000250/v1.0.5/sourcedata/') for r in plan['files'])


def test_full_coordinator_synthetic174_reuse_missing_claim_receipt_and_late_revocation(tmp_path, monkeypatch):
    """Tiny synthetic objects only; transport is a local stub with no HTTP path."""
    real_load = M.load_module
    transport, continuity, gate = (real_load(n) for n in ('transport', 'continuity', 'priority'))
    monkeypatch.setattr(gate, '_clock', lambda current=None: NOW if current is None else current)
    monkeypatch.setattr(M.shutil, 'disk_usage', lambda _: SimpleNamespace(free=100 * M.GIB))
    payload = b'synthetic'; sha = hashlib.sha256(payload).hexdigest()
    tiny_rows = [dict(r, bytes=len(payload), sha256=sha) for r in transport.frozen_plan()['files']]
    total = len(tiny_rows) * len(payload)
    monkeypatch.setattr(M, 'TOTAL_BYTES', total)
    restore, acceptance = tmp_path / 'source-json', tmp_path / 'acceptance-json'
    restore.mkdir(); acceptance.mkdir()
    bindings = {k: (v[0], 3, hashlib.sha256(b'{}\n').hexdigest()) for k, v in continuity.BINDINGS.items()}
    for key, (name, _, _) in bindings.items():
        ((restore if key in ('restore', 'completion', 'outer') else acceptance) / name).write_bytes(b'{}\n')
    source = {'metadata_sha256': {k: v[2] for k, v in bindings.items()}}
    current = {'status': 'SOURCE_RUNTIME_ACCEPTED_ORIGINAL_TASK_CONTINUITY_AND_TARGET_GATES_PENDING',
        'source_runtime': source, 'training_authorization': False,
        'old_task': {'state': 'OLD_WORK_ROOT_NOT_OBSERVED', 'counters': None}}
    continuity_path = tmp_path / 'continuity_review_run01.json'
    continuity_path.write_text(json.dumps(current)); monkeypatch.setattr(M, 'CONTINUITY_SHA', M.digest(continuity_path))
    fake_continuity = SimpleNamespace(BINDINGS=bindings, source_review=lambda *a: source,
        load=continuity.load, OLD_JOB=continuity.OLD_JOB)
    requested = []
    def transfer(row, root, *, control_check, **resources):
        control_check(); path = transport.safe_path(root, row['restore_relative_path'])
        existed = path.exists()
        if not existed:
            requested.append(row['restore_relative_path'])
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + '.partial'); temporary.write_bytes(payload)
            os.link(temporary, path); temporary.unlink()
        assert path.read_bytes() == payload
        control_check()
        return {'path': row['restore_relative_path'], 'bytes': len(payload), 'sha256': sha,
            'status': 'existing_exact_bytes_reused' if existed else 'new_exact_bytes_atomic_publish',
            'network_bytes': 0 if existed else len(payload)}
    def verify(root, *, control_check):
        files = []
        for row in tiny_rows:
            control_check(); assert (root / row['restore_relative_path']).read_bytes() == payload
            files.append({'path': row['restore_relative_path'], 'bytes': len(payload), 'sha256': sha})
        return dict(schema_version=1, status='FROZEN_174_LOCAL_EDF_BYTES_VERIFIED_SCIENTIFIC_GATES_PENDING',
            frozen_manifest_sha256=transport.FROZEN_SHA256, file_count=174, verified_bytes=total, files=files,
            transport='official_nemar_same_byte_edf_not_r2_key_receipt', target_header_event_qc_and_input_hash_acceptance=False,
            accounting_budget_checkpoint_acceptance=False, source_and_actual_training_runtime_acceptance=False,
            new_source_fits=0, target_fits=0, target_predictions=0, training_authorization=False)
    fake_transport = SimpleNamespace(FROZEN_SHA256=transport.FROZEN_SHA256, CHUNK=transport.CHUNK,
        frozen_plan=lambda: {'files': tiny_rows, 'total_bytes': total, 'file_count': 174, 'license': {'identifier': 'CC-BY-4.0'}},
        safe_path=transport.safe_path, digest_file=transport.digest_file, transport_one=transfer, verify_cached_manifest=verify)
    monkeypatch.setattr(M, 'load_module', lambda name: {'transport': fake_transport, 'continuity': fake_continuity, 'priority': gate}[name])
    revision = 'a' * 40
    review_path = tmp_path / 'parent.json'; review_path.write_text(json.dumps(parent_record(source, revision)))
    slot_path = tmp_path / 'slot.json'; slot_path.write_text(json.dumps(slot()))
    def args_for(name):
        root = tmp_path / name; monkeypatch.setattr(M, 'ROOT', root)
        first = root / tiny_rows[0]['restore_relative_path']; first.parent.mkdir(parents=True); first.write_bytes(payload)
        return SimpleNamespace(data_dir=root, delivery_revision=revision, source_restore_root=restore,
            source_acceptance_root=acceptance, continuity_report=continuity_path,
            review_record=review_path, priority_receipt=slot_path)
    args = args_for('target-success')
    result = M.run(args)
    assert result['files_verified'] == 174 and result['verified_bytes'] == total
    assert result['old_counters'] is None and result['training_authorization'] is False
    assert len(requested) == 173 and len(set(requested)) == 173
    receipt = json.loads((args.data_dir / M.BYTE_RECEIPT).read_text())
    assert receipt['file_count'] == 174 and receipt['training_authorization'] is False
    with pytest.raises(ValueError, match='consumed_claim'):
        M.run(args)

    # A completed byte JSON is still insufficient if the actual outer call fails.
    args = args_for('target-late-revocation')
    original_atomic = M.atomic
    def revoke_after_summary(path, value):
        original_atomic(path, value)
        if path.name == M.SUMMARY:
            changed = slot(); changed['slot_rationale'] = 'Synthetic revocation by replacement bytes'
            slot_path.write_text(json.dumps(changed))
    monkeypatch.setattr(M, 'atomic', revoke_after_summary)
    with pytest.raises(ValueError, match='slot_replaced_or_revoked'):
        M.run(args)
    last = json.loads((args.data_dir / M.JOURNAL).read_text().splitlines()[-1])
    assert last['phase'] == 'failed_or_blocked_preserve_no_retry'
    assert last['error_code'] == 'target_slot_replaced_or_revoked'
    assert not (args.data_dir / 'outer_exit.json').exists()
