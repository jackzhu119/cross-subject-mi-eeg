"""Synthetic receipt tests only: no Pod, package install, EEG or model work."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys

import pytest

SPEC = importlib.util.spec_from_file_location('paper1_priority_gate_tested',
    Path(__file__).with_name('priority_gate.py'))
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)
NOW = datetime(2026, 10, 15, 1, 0, tzinfo=timezone.utc)


def receipt(**changes):
    result = {
        'schema_version': 1, 'status': gate.STATUS, 'issuer': 'dot',
        'pod_id': gate.POD_ID, 'container_id': gate.CONTAINER_ID,
        'operation': 'runtime_preparation',
        'issued_at_utc': (NOW - timedelta(minutes=1)).isoformat(),
        'not_before_utc': (NOW - timedelta(minutes=1)).isoformat(),
        'expires_at_utc': (NOW + timedelta(minutes=9)).isoformat(),
        'max_new_bytes': gate.MAX_NEW_BYTES,
        'min_free_bytes': gate.MIN_FREE_BYTES,
        'paper2_reserve_bytes': 1024**3,
        'slot_rationale': 'Synthetic test: dot granted an isolated preparation slot.'}
    result.update({key: True for key in gate._TRUE_FIELDS})
    result.update({key: False for key in gate._FALSE_FIELDS})
    result.update(changes)
    return result


def write(tmp_path, **changes):
    path = tmp_path / 'receipt.json'
    path.write_text(json.dumps(receipt(**changes)))
    return path


def test_valid_grant_immutable_and_readonly(tmp_path):
    path = write(tmp_path)
    before = path.read_bytes(), path.stat().st_mtime_ns
    permit = gate.validate_receipt(path, current=NOW)
    assert permit.operation == 'runtime_preparation'
    assert permit.required_free_bytes == 11 * 1024**3
    assert permit.max_new_bytes == 3 * 1024**3
    assert permit.assert_active(current=NOW) is permit
    assert len(permit.receipt_sha256) == 64
    with pytest.raises(TypeError):
        permit.receipt['training_authorization'] = True
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('operation', sorted(gate.OPERATIONS))
def test_separate_exact_operation(tmp_path, operation):
    path = write(tmp_path, operation=operation)
    gate.validate_receipt(path, expected_operation=operation, current=NOW)
    other = next(value for value in gate.OPERATIONS if value != operation)
    with pytest.raises(ValueError, match='operation_mismatch'):
        gate.validate_receipt(path, expected_operation=other, current=NOW)


@pytest.mark.parametrize('value', ['training', ['metadata', 'runtime_preparation'], None, 'prepare_runtime'])
def test_receipt_cannot_grant_multiple_or_unknown_operation(tmp_path, value):
    with pytest.raises(ValueError, match='exact_one_operation'):
        gate.validate_receipt(write(tmp_path, operation=value), current=NOW)


@pytest.mark.parametrize('field,value', [
    ('schema_version', True), ('schema_version', 2),
    ('status', 'PLAN_ONLY_NOT_A_DOT_GRANT'), ('issuer', 'user'),
    ('pod_id', 'old-pod'), ('container_id', 'b5646c12356b'),
    *[(key, False) for key in gate._TRUE_FIELDS],
    *[(key, 1) for key in gate._TRUE_FIELDS],
    *[(key, True) for key in gate._FALSE_FIELDS],
    *[(key, 0) for key in gate._FALSE_FIELDS],
    ('max_new_bytes', 3 * 1024**3 + 1), ('max_new_bytes', -1),
    ('max_new_bytes', True), ('min_free_bytes', False),
    ('min_free_bytes', 10 * 1024**3 - 1),
    ('paper2_reserve_bytes', -1), ('paper2_reserve_bytes', True),
    ('paper2_reserve_bytes', None), ('slot_rationale', ''), ('slot_rationale', None),
])
def test_fail_closed_fields(tmp_path, field, value):
    with pytest.raises(ValueError):
        gate.validate_receipt(write(tmp_path, **{field: value}), current=NOW)


@pytest.mark.parametrize('field,value', [
    ('issued_at_utc', None), ('issued_at_utc', 'not-a-time'),
    ('issued_at_utc', '2026-10-15T00:00:00'),
    ('issued_at_utc', '2026-10-15T00:00:00+01:00'),
    ('issued_at_utc', (NOW + timedelta(minutes=1)).isoformat()),
    ('issued_at_utc', (NOW - timedelta(minutes=31)).isoformat()),
    ('not_before_utc', (NOW + timedelta(minutes=1)).isoformat()),
    ('not_before_utc', (NOW - timedelta(minutes=2)).isoformat()),
    ('expires_at_utc', NOW.isoformat()),
    ('expires_at_utc', (NOW - timedelta(minutes=1)).isoformat()),
    ('expires_at_utc', (NOW + timedelta(minutes=30)).isoformat()),
    ('expires_at_utc', (gate.AUTHORIZATION_DEADLINE + timedelta(seconds=1)).isoformat()),
])
def test_fail_closed_times(tmp_path, field, value):
    with pytest.raises(ValueError):
        gate.validate_receipt(write(tmp_path, **{field: value}), current=NOW)


def test_exact_thirty_minute_slot_and_authorization_boundary(tmp_path):
    start = gate.AUTHORIZATION_DEADLINE - timedelta(minutes=30)
    path = write(tmp_path, issued_at_utc=start.isoformat(), not_before_utc=start.isoformat(),
                 expires_at_utc=gate.AUTHORIZATION_DEADLINE.isoformat())
    permit = gate.validate_receipt(path, current=start)
    permit.assert_active(current=gate.AUTHORIZATION_DEADLINE - timedelta(microseconds=1))
    with pytest.raises(ValueError, match='expired'):
        permit.assert_active(current=gate.AUTHORIZATION_DEADLINE)


@pytest.mark.parametrize('mutation', ['unlink', 'change', 'replacement', 'revocation', 'symlink'])
def test_controller_rechecks_same_snapshot_before_next_step(tmp_path, mutation):
    path = write(tmp_path)
    permit = gate.validate_receipt(path, current=NOW)
    if mutation == 'unlink':
        path.unlink()
    elif mutation == 'change':
        path.write_bytes(path.read_bytes() + b'\n')
    elif mutation == 'replacement':
        replacement = tmp_path / 'replacement.json'
        replacement.write_bytes(path.read_bytes())
        replacement.replace(path)
    elif mutation == 'revocation':
        path.write_text(json.dumps(receipt(status='REVOKED')))
    else:
        target = tmp_path / 'target.json'
        target.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(target)
    with pytest.raises(ValueError):
        permit.assert_active(current=NOW)


def test_controller_expires_without_modification(tmp_path):
    permit = gate.validate_receipt(write(tmp_path), current=NOW)
    with pytest.raises(ValueError, match='expired'):
        permit.assert_active(current=NOW + timedelta(minutes=9))


def test_plan_only_template_never_passes():
    with pytest.raises(ValueError):
        gate.validate_receipt(Path(__file__).with_name('paper2_priority_slot.PLAN_ONLY.json'), current=NOW)


def test_duplicate_extra_missing_keys_rejected(tmp_path):
    path = write(tmp_path)
    original = path.read_text()
    for raw in [original[:-1] + ', "training_authorization": false}',
                original[:-1] + ', "extra": true}', '{}', '[]', '{', '\x00']:
        path.write_text(raw)
        with pytest.raises(ValueError):
            gate.validate_receipt(path, current=NOW)


def test_symlink_parent_rejected(tmp_path):
    folder = tmp_path / 'actual'
    folder.mkdir()
    path = folder / 'receipt.json'
    path.write_text(json.dumps(receipt()))
    link = tmp_path / 'linked'
    link.symlink_to(folder, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        gate.validate_receipt(link / path.name, current=NOW)


def test_file_type_size_missing_invalid_clock(tmp_path):
    with pytest.raises(ValueError):
        gate.validate_receipt(tmp_path / 'missing', current=NOW)
    with pytest.raises(ValueError):
        gate.validate_receipt(tmp_path, current=NOW)
    path = write(tmp_path)
    with pytest.raises(ValueError, match='aware_datetime'):
        gate.validate_receipt(path, current=NOW.replace(tzinfo=None))
    path.write_bytes(b' ' * (gate.MAX_RECEIPT_BYTES + 1))
    with pytest.raises(ValueError):
        gate.validate_receipt(path, current=NOW)
