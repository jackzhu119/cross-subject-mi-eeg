"""Synthetic metadata guard tests. No EEG/R2/model execution."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import pytest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('transition_gate_under_test', HERE / 'transition_target_gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


@pytest.fixture
def entries():
    return [{'path': 'bnci/A01T.mat', 'bytes': 12, 'sha256': 'a' * 64},
            {'path': 'dreyer_acquisition/sourcedata/sub-01/eeg/run.edf', 'bytes': 34, 'sha256': 'b' * 64}]


def rows(entries):
    return {'schema_version': 1, 'files': [{**r, 'object_key': 'existing/' + r['path']} for r in entries]}


def test_complete_mapping_remains_metadata_only(entries):
    result = gate.mapping_review(rows(entries), entries)
    assert result['all_192_file_identities_mapped'] is True
    assert result['objects_accessible'] is None
    assert result['remote_raw_hashes_verified'] is None
    assert result['object_keys_generated_or_guessed'] is False


def test_partial_mapping_counts_unmapped_target(entries):
    result = gate.mapping_review(rows(entries[:1]), entries)
    assert result['all_192_file_identities_mapped'] is False
    assert result['missing_target_files'] == 1
    assert result['missing_source_files'] == 0
    assert result['missing_raw_bytes'] == 34
    assert result['minimum_import_free_bytes_if_all_raw_absent'] == 46 + 6 * gate.GIB


@pytest.mark.parametrize('field,value', [('bytes', True), ('bytes', 13), ('sha256', 'c' * 64), ('object_key', None), ('object_key', '../x'), ('path', '/x')])
def test_changed_mapping_rejected(entries, field, value):
    mapping = rows(entries)
    mapping['files'][0][field] = value
    with pytest.raises(ValueError):
        gate.mapping_review(mapping, entries)


def test_extra_mapping_path_rejected(entries):
    mapping = rows(entries)
    mapping['files'].append({**entries[0], 'path': 'bnci/other.mat', 'object_key': 'another'})
    with pytest.raises(ValueError):
        gate.mapping_review(mapping, entries)


@pytest.mark.parametrize('duplicate', ['path', 'object_key'])
def test_duplicates_rejected(entries, duplicate):
    mapping = rows(entries)
    mapping['files'][1][duplicate] = mapping['files'][0][duplicate]
    with pytest.raises(ValueError):
        gate.mapping_review(mapping, entries)


def test_missing_old_root_unknown_not_zero(tmp_path):
    result = gate.old_record_review(tmp_path / 'gone', datetime(2026, 10, 14, 17, tzinfo=timezone.utc))
    assert result['state'] == 'OLD_WORK_ROOT_NOT_ACCESSIBLE_NOT_OBSERVED'
    assert result['counters'] is None
    assert result['same_machine_identity_proven'] is None
    assert result['private_checkpoint_backup_verified'] is None
    assert result['original_budget_clock_state'] == 'EXPIRED'
    assert result['budget_clock_rebased'] is False


def test_empty_old_root_does_not_claim_observed_records(tmp_path):
    result = gate.old_record_review(tmp_path)
    assert result['state'] == 'OLD_WORK_ROOT_ACCESSIBLE_ACCOUNTING_NOT_OBSERVED'
    assert result['counters'] is None


def old_fixture(tmp_path):
    root = tmp_path / 'old'
    job = root / ('code-' + gate.OLD_REVISION) / 'research_runs/REDESIGN_CLOUD_20261013/jobs' / gate.OLD_JOB
    write(root / 'execution_registration.json', {'job_id': gate.OLD_JOB, 'code_revision': gate.OLD_REVISION})
    write(root / 'budget_origin.json', {'started_at_utc': gate.OLD_STARTED})
    write(job / 'launch_record.json', {'job_id': gate.OLD_JOB, 'code_revision': gate.OLD_REVISION})
    write(job / 'job_status.json', {'job_id': gate.OLD_JOB, 'actual_neural_fits_started': 0,
          'actual_neural_fits_completed': 0, 'optimizer_updates': 0, 'target_fits': 0,
          'target_predictions_computed': False})
    return root, job


def test_observed_old_zero_not_identity_or_resume(tmp_path):
    root, job = old_fixture(tmp_path)
    before = {p: p.read_bytes() for p in root.rglob('*.json')}
    result = gate.old_record_review(root)
    assert result['counters']['actual_neural_fits_started'] == 0
    assert result['zero_fit_checkpoint_absence_verified'] is None
    assert result['budget_migration_authorized'] is False
    assert {p: p.read_bytes() for p in root.rglob('*.json')} == before


@pytest.mark.parametrize('key', ['job_id', 'code_revision'])
def test_wrong_old_registration_rejected(tmp_path, key):
    root, _ = old_fixture(tmp_path)
    p = root / 'execution_registration.json'
    obj = json.loads(p.read_text()); obj[key] = 'wrong'; write(p, obj)
    with pytest.raises(ValueError):
        gate.old_record_review(root)


def test_budget_rebase_rejected(tmp_path):
    root, _ = old_fixture(tmp_path)
    write(root / 'budget_origin.json', {'started_at_utc': '2026-10-14T14:23:46+00:00'})
    with pytest.raises(ValueError, match='budget_origin_changed'):
        gate.old_record_review(root)


def test_status_ledger_counters_disagree_rejected(tmp_path):
    root, job = old_fixture(tmp_path)
    obj = json.loads((job / 'job_status.json').read_text())
    obj['actual_neural_fits_started'] = 1
    write(job / 'source/budget_ledger.json', obj)
    with pytest.raises(ValueError, match='counters_disagree'):
        gate.old_record_review(root)


def test_target_boundary_rejected(tmp_path):
    root, job = old_fixture(tmp_path)
    obj = json.loads((job / 'job_status.json').read_text()); obj['target_fits'] = 1
    write(job / 'job_status.json', obj)
    with pytest.raises(ValueError, match='target_boundary'):
        gate.old_record_review(root)


@pytest.mark.parametrize('payload', ['{"x":1,"x":2}', '{"x":NaN}'])
def test_ambiguous_json_rejected(tmp_path, payload):
    p = tmp_path / 'record.json'; p.write_text(payload)
    with pytest.raises(ValueError):
        gate.read_json(p)


def test_symlink_rejected(tmp_path):
    target = tmp_path / 'real.json'; target.write_text('{}')
    p = tmp_path / 'link.json'; p.symlink_to(target)
    with pytest.raises(ValueError, match='symlink'):
        gate.read_json(p)


def test_template_is_deliberately_pending():
    template = json.loads((HERE / 'transition_plan.template.json').read_text())
    assert gate.plan_review(template)['state'] == 'PLAN_INSPECTED_NOT_AN_EXECUTION_AUTHORIZATION'
    assert all(r['state'] == 'UNKNOWN' for r in template['pending_gates'].values())


@pytest.mark.parametrize('edit', ['authorize', 'new_budget', 'deadline', 'pass', 'missing_gate', 'source_hash', 'extra_pass', 'invalid_gate'])
def test_plan_cannot_clear_or_replace_gates(edit):
    template = json.loads((HERE / 'transition_plan.template.json').read_text())
    if edit == 'authorize': template['training_authorization'] = True
    elif edit == 'new_budget': template['new_budget_authorization'] = {'hours': 8}
    elif edit == 'deadline': template['original_expires_at_utc'] = 'later'
    elif edit == 'pass': template['pending_gates']['old_identity_and_counters']['state'] = 'PASS'
    elif edit == 'missing_gate': del template['pending_gates']['checkpoint_and_remote_backup']
    elif edit == 'source_hash': template['source_exact_input_receipt_sha256'] = 'a' * 64
    elif edit == 'extra_pass': template['approval'] = 'PASS'
    elif edit == 'invalid_gate': template['pending_gates']['old_identity_and_counters'] = []
    with pytest.raises(ValueError):
        gate.plan_review(template)
