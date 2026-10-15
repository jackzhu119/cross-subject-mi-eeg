"""Synthetic metadata guards only; no source reconstruction, fits or inference."""
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('deadline_amendment', HERE / 'validate_deadline_amendment.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def records():
    return (json.loads((HERE / 'deadline_only_amendment.json').read_bytes()),
            json.loads((HERE / 'historical_budget_authorization_d612f0cc.json').read_bytes()))


def test_archived_receipt_and_record_are_exact_and_read_only():
    paths = list(HERE.glob('*.json'))
    before = {p: p.read_bytes() for p in paths}
    result = gate.audit(at_utc='2026-10-15T00:48:15+00:00')
    assert result['status'] == 'SOURCED_DEADLINE_ONLY_RECORD_VALID_EXECUTION_STILL_BLOCKED'
    assert result['training_authorization'] is False
    assert result['new_budget_authorization'] is False
    assert result['deadline_not_yet_expired_at_validation'] is True
    assert result['actual_spend_usd'] is None and result['remaining_budget_usd'] is None
    assert result['production_budget_gate_changed'] is False
    assert result['fresh_remote_readback_performed'] is False
    assert before == {p: p.read_bytes() for p in paths}


@pytest.mark.parametrize('at,not_expired', [
    ('2026-10-16T09:53:59+00:00', True),
    ('2026-10-16T09:54:00+00:00', False),
    ('2026-10-16T09:54:01+00:00', False),
    ('2026-10-16T02:54:00-07:00', False),
])
def test_absolute_deadline_has_no_refresh(at, not_expired):
    result = gate.audit(at_utc=at)
    assert result['deadline_not_yet_expired_at_validation'] is not_expired
    assert result['amended_execution_deadline_utc'] == gate.NEW_DEADLINE
    assert result['training_authorization'] is False


def test_naive_timestamp_not_accepted():
    with pytest.raises(ValueError, match='aware_UTC_time_required'):
        gate.audit(at_utc='2026-10-16T09:54:00')


@pytest.mark.parametrize('key,value', [
    ('maximum_total_usd', 11), ('non_gpu_reserved_usd', 1),
    ('maximum_gpu_hours', 16), ('maximum_neural_fits', 27),
    ('maximum_optimizer_updates', 34441), ('maximum_gpu_hourly_rate_usd', 0.8),
    ('maximum_total_usd', True), ('maximum_neural_fits', 26.0),
    ('target_fits_authorized', True), ('optional_grouping_authorized', True),
])
def test_no_ceiling_expansion_or_bool_integer_confusion(key, value):
    record, old = records()
    record['unchanged_ceiling_constraints'][key] = value
    with pytest.raises(ValueError, match='unchanged_ceiling_changed'):
        gate.validate_record(record, old)


@pytest.mark.parametrize('key', [
    'training_authorization', 'new_budget_authorization', 'automatic_resume',
    'create_or_replace_budget_receipt', 'Pod_operations', 'package_installation',
    'target_EEG_read', 'credentials_or_security_changes',
])
def test_every_operational_permission_stays_false(key):
    record, old = records()
    record['permissions'][key] = True
    with pytest.raises(ValueError, match='execution_permission_not_allowed'):
        gate.validate_record(record, old)


@pytest.mark.parametrize('key', ['actual_spend_usd', 'remaining_budget_usd',
    'actual_cumulative_gpu_hours', 'current_machine_authorization',
    'current_account_identity', 'restored_checkpoint_identity'])
def test_missing_evidence_cannot_be_filled_with_zero_or_identity(key):
    record, old = records()
    record['observed_accounting_state'][key] = 0
    with pytest.raises(ValueError, match='accounting_not_independently_observed'):
        gate.validate_record(record, old)


@pytest.mark.parametrize('section,key,value,error', [
    ('original_budget_authorization', 'authorized_at_utc', '2026-10-15T00:48:15+00:00', 'old_budget_anchor_changed'),
    ('original_budget_authorization', 'expires_at_utc', gate.NEW_DEADLINE, 'old_budget_anchor_changed'),
    ('original_budget_authorization', 'original_receipt_modified', True, 'old_budget_anchor_changed'),
    ('preservation_requirements', 'paper2_priority_absolute', False, 'preservation_requirement_changed'),
    ('preservation_requirements', 'dot_sole_pod_operator', False, 'preservation_requirement_changed'),
    ('preservation_requirements', 'maximum_gpu_hours_not_reset_or_expanded', False, 'preservation_requirement_changed'),
    ('authorization_source', 'independently_retrieved_conversation', True, 'transcript_scope_changed'),
    ('observed_accounting_state', 'zero_new_fits_proves_zero_cost', True, 'accounting_not_independently_observed'),
])
def test_origin_preservation_and_evidence_scope(section, key, value, error):
    record, old = records()
    record[section][key] = value
    with pytest.raises(ValueError, match=error):
        gate.validate_record(record, old)


@pytest.mark.parametrize('key,value,error', [
    ('old_job_id', 'new-task', 'old_job_identity_mismatch'),
    ('amended_execution_deadline_utc', '2026-10-17T09:54:00+00:00', 'deadline_changed'),
    ('pending_before_execution', [], 'pending_gates_changed'),
    ('status', 'PASS_BOUNDED_MACHINE_BUDGET', 'execution_receipt_not_allowed'),
])
def test_no_implicit_new_job_release_or_deadline_extension(key, value, error):
    record, old = records()
    record[key] = value
    with pytest.raises(ValueError, match=error):
        gate.validate_record(record, old)


def test_old_receipt_is_not_an_operationally_changed_copy():
    record, old = records()
    old['expires_at_utc'] = gate.NEW_DEADLINE
    with pytest.raises(ValueError, match='old_budget_origin_or_deadline_changed'):
        gate.validate_record(record, old)


def test_historical_quote_is_not_replaced_by_current_quote():
    record, old = records()
    old['approved_hourly_rate_usd'] = 0.24
    with pytest.raises(ValueError, match='historical_quote_changed'):
        gate.validate_record(record, old)


def test_any_byte_edit_is_rejected_before_semantic_review(tmp_path):
    path = tmp_path / 'record.json'
    path.write_bytes((HERE / 'deadline_only_amendment.json').read_bytes() + b'\n')
    with pytest.raises(ValueError, match='metadata_sha256_mismatch'):
        gate.audit(record_path=path)


@pytest.mark.parametrize('body,error', [
    (b'{"a": 1, "a": 2}', 'duplicate_json_key'),
    (b'{"a": NaN}', 'nonfinite_json_rejected'),
    (b'[]', 'json_object_required'),
])
def test_json_parser_rejects_ambiguous_or_nonfinite_metadata(tmp_path, body, error):
    path = tmp_path / 'record.json'
    path.write_bytes(body)
    with pytest.raises(ValueError, match=error):
        gate.read_json(path, hashlib.sha256(body).hexdigest())


def test_symlink_file_rejected(tmp_path):
    path = tmp_path / 'record.json'
    path.symlink_to(HERE / 'deadline_only_amendment.json')
    with pytest.raises(ValueError, match='symlink_rejected'):
        gate.audit(record_path=path)


def test_symlink_ancestor_rejected(tmp_path):
    path = tmp_path / 'metadata'
    path.symlink_to(HERE, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink_rejected'):
        gate.audit(record_path=path / 'deadline_only_amendment.json')


def test_oversized_metadata_rejected(tmp_path):
    path = tmp_path / 'record.json'
    path.write_bytes(b' ' * 65537)
    with pytest.raises(ValueError, match='bounded_regular_json_required'):
        gate.audit(record_path=path)


def test_source_timestamp_is_not_invented_at_second_precision():
    record, old = records()
    record['authorization_source']['supplied_transcript'][1]['timestamp_precision'] = 'second'
    with pytest.raises(ValueError, match='supplied_transcript_changed'):
        gate.validate_record(record, old)


def test_cli_failure_never_prints_document_or_error_payload(monkeypatch, capsys, tmp_path):
    path = tmp_path / 'record.json'
    path.write_text('private-marker')
    monkeypatch.setattr('sys.argv', ['validator', '--record', str(path)])
    assert gate.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result['training_authorization'] is False
    assert 'private-marker' not in str(result)
