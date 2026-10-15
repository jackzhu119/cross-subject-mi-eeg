"""Synthetic receipt tests; no EEG, packages, external network or fit execution."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('receipt_union_under_test', HERE / 'transport_receipt_union.py')
union = importlib.util.module_from_spec(spec)
spec.loader.exec_module(union)


@pytest.fixture(scope='module')
def catalogue():
    return union.frozen_catalogue()  # Pinned public JSON/README only, no EEG.


def fixture_records(c):
    source = {'status': 'SOURCE18_EXACT_BYTES_RESTORED_NUMERICAL_ACCEPTANCE_PENDING',
        'source_expected_files': 18, 'source_expected_bytes': 779873919,
        'official_manifest_sha256': union.SOURCE_OFFICIAL_SHA,
        'source_root': '/workspace/synthetic-source', 'old_task': union.OLD_TASK,
        'diagnostic_rerun': False, 'runtime_imported': False, 'target_EEG_accessed': False,
        'training_authorization': False, 'new_fits': 0, 'budget_reset': False,
        'files': [{'filename': r['path'].split('/')[-1], 'status': 'REUSED_VERIFIED_CACHE',
                   'bytes': r['bytes'], 'sha256': r['sha256']} for r in c['source_files']]}
    target = {'schema_version': 1,
        'status': 'FROZEN_174_LOCAL_EDF_BYTES_VERIFIED_SCIENTIFIC_GATES_PENDING',
        'frozen_manifest_sha256': c['target_plan']['frozen_manifest_sha256'],
        'file_count': 174, 'verified_bytes': 2515343396, 'files': copy.deepcopy(c['target_files']),
        'transport': 'official_nemar_same_byte_edf_not_r2_key_receipt',
        'target_header_event_qc_and_input_hash_acceptance': False,
        'accounting_budget_checkpoint_acceptance': False,
        'source_and_actual_training_runtime_acceptance': False,
        'new_source_fits': 0, 'target_fits': 0, 'target_predictions': 0, 'training_authorization': False}
    formal = {'status': 'SOURCE_NUMERICAL_ACCEPTANCE_MATCH_TRAINING_STILL_BLOCKED',
        'code_revision': union.BASE_REVISION, 'source_complete_exact_hash_gate_passed': True,
        'source_array_hashes': copy.deepcopy(c['source_array_hashes']), 'source_files': 18,
        'source_runs': 108, 'source_trials': 2592, 'numerical_execution': copy.deepcopy(c['numerical_execution']),
        'training_consumer_imports_verified': True, 'private_full_package_independently_verified': True,
        'private_full_package_sha256': union.FULL_SHA, 'target_complete_restoration_verified': False,
        'target_frozen_input_mapping_verified': False, 'runtime_GPU_preflight_verified': False,
        'old_machine_identity_proven': False, 'budget_resume_authorized': False,
        'checkpoint_and_verified_backup_gates_passed': False, 'training_authorization': False,
        'new_fits': 0, 'target_EEG_read': False, 'target_predictions_computed': False,
        'source_arrays_serialized_or_replaced': False, 'historical_generation_BLAS_identity_established': False}
    runtime = {'status': 'REPAIRED_ACTUAL_TRAINING_RUNTIME_SOURCE_MATCH_OTHER_GATES_PENDING',
        'original_base_revision': union.BASE_REVISION, 'repair_archive_sha256': union.REPAIR_ARCHIVE_SHA,
        'independent_repair_receipt_sha256': union.REPAIR_RECEIPT_SHA,
        'historical_full_diagnostic_package_sha256': union.FULL_SHA,
        'historical_formal_diagnostic_archive_sha256': union.FORMAL_ARCHIVE_SHA,
        'strict_trial_and_aggregate_hash_gate_passed': True, 'actual_training_runtime_imports_verified': True,
        'source_arrays_serialized': False, 'historical_diagnostic_executed': False,
        'original_preparation_receipt_created': False, 'CUDA_initialized': False,
        'GPU_computation_verified': False, 'new_fits': 0, 'target_EEG_read': False,
        'target_fits': 0, 'training_authorization': False, 'old_accounting_reconciled': False,
        'old_cost_known': False, 'budget_reset': False, 'budget_expanded': False,
        'budget_transition_authorized': False, 'checkpoint_and_backup_transition_verified': False,
        'target_mapping_and_restore_accepted': False,
        'source_originals_verified': [{k: v for k, v in r.items() if k != 'status'} for r in source['files']]}
    records = {'source_restore': source, 'target_bytes': target, 'runtime_bound': runtime,
               'formal_source': formal}
    digests = {name: 'a' * 64 for name in union.RECORDS}
    runtime['new_container_source_restore_receipt_sha256'] = digests['source_restore']
    runtime['formal_source_acceptance_sha256'] = digests['formal_source']
    records['route_binding'] = {'schema_version': 1,
        'status': 'METADATA_ROUTE_BINDING_FOR_INDEPENDENT_REVIEW_NOT_EXECUTION',
        'old_job_id': union.OLD_TASK, 'source_root': source['source_root'],
        'target_root': '/workspace/synthetic-target',
        'source_restore_sha256': digests['source_restore'], 'target_bytes_sha256': digests['target_bytes'],
        'runtime_bound_sha256': digests['runtime_bound'], 'formal_source_sha256': digests['formal_source'],
        'source_manifest_sha256': union.SOURCE_SHA,
        'target_manifest_sha256': c['target_plan']['frozen_manifest_sha256'], 'training_authorization': False}
    return records, digests


def test_default_complete_frozen_catalogue(catalogue):
    result = union.pending_result(catalogue)
    assert result['file_count'] == len(result['files']) == 192
    assert result['total_bytes'] == sum(r['bytes'] for r in result['files']) == 3295217315
    assert result['source_file_count'] == 18 and result['target_file_count'] == 174
    assert result['license']['identifier'] == 'CC-BY-4.0'
    assert not result['actual_receipts_consumed']
    assert not result['byte_identity_receipt_metadata_matched']


def test_valid_metadata_candidate_has_no_scientific_authority(catalogue):
    records, digests = fixture_records(catalogue)
    result = union.bound_candidate(catalogue, records, digests)
    assert result['status'] == 'METADATA_BOUND_192_ROUTE_CANDIDATE_SCIENTIFIC_GATES_PENDING'
    assert result['source_cache_root'] == '/workspace/synthetic-source/bnci'
    assert result['target_cache_root'] == '/workspace/synthetic-target/dreyer_acquisition'
    assert result['source_array_hashes'] == catalogue['source_array_hashes']
    assert result['numerical_execution'] == catalogue['numerical_execution']
    assert result['independent_repair_receipt_sha256'] == union.REPAIR_RECEIPT_SHA
    for key in ('cache_roots_observed', 'raw_bytes_opened', 'actual_target_header_event_qc_input_acceptance',
                'actual_runtime_and_source_acceptance_granted_by_this_tool', 'accounting_and_checkpoint_acceptance',
                'verified_backup_acceptance', 'target_transport_authorization', 'target_scientific_consumption_authorization',
                'production_routing_modified', 'prepare_data_called', 'training_authorization'):
        assert result[key] is False


@pytest.mark.parametrize('which', ['source_restore', 'target_bytes'])
@pytest.mark.parametrize('mutation', ['duplicate', 'missing', 'extra', 'changed_path', 'changed_size', 'changed_hash',
                                     'size_bool', 'path_alias', 'extra_alias_field'])
def test_exact_receipt_inventory_required(catalogue, which, mutation):
    records, digests = fixture_records(catalogue)
    rows = records[which]['files']
    pathkey = 'filename' if which == 'source_restore' else 'path'
    if mutation == 'duplicate': rows[1] = copy.deepcopy(rows[0])
    elif mutation == 'missing': rows.pop()
    elif mutation == 'extra': rows.append(copy.deepcopy(rows[0]))
    elif mutation == 'changed_path': rows[0][pathkey] = 'unknown'
    elif mutation == 'changed_size': rows[0]['bytes'] += 1
    elif mutation == 'changed_hash': rows[0]['sha256'] = 'f' * 64
    elif mutation == 'size_bool': rows[0]['bytes'] = True
    elif mutation == 'path_alias': rows[0][pathkey] = './' + rows[0][pathkey]
    elif mutation == 'extra_alias_field': rows[0]['object_path'] = rows[0][pathkey]
    with pytest.raises(ValueError): union.bound_candidate(catalogue, records, digests)


@pytest.mark.parametrize('record,key,value', [
    ('source_restore', 'old_task', 'different-job'),
    ('source_restore', 'source_root', '/workspace/old-container-source'),
    ('route_binding', 'old_job_id', 'different-job'),
    ('route_binding', 'source_restore_sha256', 'b' * 64),
    ('route_binding', 'target_bytes_sha256', 'b' * 64),
    ('route_binding', 'runtime_bound_sha256', 'b' * 64),
    ('route_binding', 'formal_source_sha256', 'b' * 64),
    ('route_binding', 'source_manifest_sha256', 'b' * 64),
    ('route_binding', 'target_manifest_sha256', 'b' * 64),
    ('runtime_bound', 'new_container_source_restore_receipt_sha256', 'b' * 64),
    ('runtime_bound', 'formal_source_acceptance_sha256', 'b' * 64),
    ('runtime_bound', 'independent_repair_receipt_sha256', 'b' * 64),
    ('runtime_bound', 'original_preparation_receipt_created', True),
    ('source_restore', 'official_manifest_sha256', 'b' * 64),
    ('target_bytes', 'frozen_manifest_sha256', 'b' * 64),
    ('formal_source', 'private_full_package_sha256', 'b' * 64),
    ('formal_source', 'private_full_package_independently_verified', False),
    ('formal_source', 'training_consumer_imports_verified', False),
    ('formal_source', 'source_complete_exact_hash_gate_passed', False),
    ('formal_source', 'code_revision', 'b' * 40),
    ('formal_source', 'source_trials', 2591),
    ('formal_source', 'source_runs', 107),
    ('formal_source', 'source_files', True),
    ('formal_source', 'source_complete_exact_hash_gate_passed', 1),
    ('formal_source', 'training_authorization', 0),
    ('formal_source', 'new_fits', False),
    ('target_bytes', 'schema_version', True),
    ('target_bytes', 'target_predictions', False),
    ('target_bytes', 'target_header_event_qc_and_input_hash_acceptance', True),
    ('target_bytes', 'training_authorization', True),
    ('target_bytes', 'status', 'R2_ONLY_IMPORT_VERIFIED'),
    ('target_bytes', 'status', 'PASS'),
    ('runtime_bound', 'status', 'PASS'),
])
def test_independent_receipt_identity_and_scope_boundaries(catalogue, record, key, value):
    records, digests = fixture_records(catalogue)
    records[record][key] = value
    with pytest.raises(ValueError): union.bound_candidate(catalogue, records, digests)


@pytest.mark.parametrize('key', ['object_key', 'r2_enabled', 'r2_import_receipt', 'R2_ACCESS_KEY_ID'])
def test_r2_identity_cannot_be_fabricated(catalogue, key):
    records, digests = fixture_records(catalogue)
    records['source_restore']['extra'] = {key: 'not-real'}
    with pytest.raises(ValueError, match='R2_identity'): union.bound_candidate(catalogue, records, digests)


@pytest.mark.parametrize('path', ['/workspace/synthetic-source', '/workspace/synthetic-source/child',
    '/workspace', '/workspace/a/../b', '/workspace//b', '/workspace/b/', '/tmp/target',
    '/workspace/.venvs/paper2-gpu', '/workspace/paper1-training-runtime-cp312-run01/data'])
def test_roots_are_metadata_only_separate_and_canonical(catalogue, path):
    records, digests = fixture_records(catalogue)
    records['route_binding']['target_root'] = path
    with pytest.raises(ValueError): union.bound_candidate(catalogue, records, digests)


def test_formal_array_hash_and_policy_cannot_change(catalogue):
    records, digests = fixture_records(catalogue)
    records['formal_source']['source_array_hashes']['mu'] = 'b' * 64
    with pytest.raises(ValueError): union.bound_candidate(catalogue, records, digests)
    records, digests = fixture_records(catalogue)
    records['formal_source']['numerical_execution']['policy_sha256'] = 'b' * 64
    with pytest.raises(ValueError): union.bound_candidate(catalogue, records, digests)


@pytest.mark.parametrize('which', union.RECORDS)
def test_missing_independent_record_or_binding_rejected(catalogue, which):
    records, digests = fixture_records(catalogue)
    del records[which]
    with pytest.raises(ValueError): union.bound_candidate(catalogue, records, digests)
    records, digests = fixture_records(catalogue)
    del digests[which]
    with pytest.raises(ValueError): union.bound_candidate(catalogue, records, digests)


def test_no_raw_cache_or_network_open_in_candidate(catalogue, monkeypatch):
    records, digests = fixture_records(catalogue)
    monkeypatch.setattr(Path, 'open', lambda *a, **k: (_ for _ in ()).throw(AssertionError('No files in candidate validation')))
    monkeypatch.setattr(Path, 'stat', lambda *a, **k: (_ for _ in ()).throw(AssertionError('No physical cache claims')))
    assert union.bound_candidate(catalogue, records, digests)['training_authorization'] is False


def test_default_cli_needs_no_actual_receipts(catalogue, monkeypatch, capsys):
    monkeypatch.setattr(union, 'frozen_catalogue', lambda: catalogue)
    assert union.main([]) == 0
    assert json.loads(capsys.readouterr().out)['actual_receipts_consumed'] is False


def test_partial_cli_mode_rejected(catalogue, monkeypatch):
    monkeypatch.setattr(union, 'frozen_catalogue', lambda: catalogue)
    with pytest.raises(SystemExit): union.main(['--source-restore', '/workspace/not-read.json'])


def test_complete_cli_reads_only_five_independently_hashed_JSONs(catalogue, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(union, 'frozen_catalogue', lambda: catalogue)
    records, _ = fixture_records(catalogue)
    digests, paths = {}, {}
    for name in ('source_restore', 'target_bytes', 'formal_source', 'runtime_bound', 'route_binding'):
        if name == 'runtime_bound':
            records[name]['new_container_source_restore_receipt_sha256'] = digests['source_restore']
            records[name]['formal_source_acceptance_sha256'] = digests['formal_source']
        if name == 'route_binding':
            for record in ('source_restore', 'target_bytes', 'formal_source', 'runtime_bound'):
                records[name][record + '_sha256'] = digests[record]
        raw = (json.dumps(records[name]) + '\n').encode()
        paths[name] = tmp_path / (name + '.json')
        paths[name].write_bytes(raw)
        digests[name] = hashlib.sha256(raw).hexdigest()
    args = []
    for name in union.RECORDS:
        option = name.replace('_', '-')
        args.extend(['--' + option, str(paths[name]), '--' + option + '-sha256', digests[name]])
    assert union.main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['receipt_sha256'] == digests
    assert result['byte_identity_receipt_metadata_matched'] is True
    assert result['training_authorization'] is False
    # A changed named receipt cannot be accepted using its previous SHA.
    paths['target_bytes'].write_bytes(b'{}\n')
    with pytest.raises(ValueError, match='JSON_identity_changed'): union.main(args)


def test_cli_json_exclusive_output(catalogue, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(union, 'frozen_catalogue', lambda: catalogue)
    output = tmp_path / 'plan.json'
    assert union.main(['--output', str(output)]) == 0
    original = output.read_bytes()
    with pytest.raises(FileExistsError): union.main(['--output', str(output)])
    assert output.read_bytes() == original
    assert json.loads(original)['status'] == 'OFFLINE_FROZEN_192_CATALOGUE_ROUTE_PLAN_ONLY'


def test_read_json_requires_full_external_sha_and_real_regular_json(tmp_path):
    path = tmp_path / 'record.json'
    data = b'{"synthetic": true}\n'
    path.write_bytes(data)
    assert union.read_json(path, hashlib.sha256(data).hexdigest()) == {'synthetic': True}
    for wrong in ('a' * 64, 'abc', True):
        with pytest.raises(ValueError): union.read_json(path, wrong)
    link = tmp_path / 'link.json'
    link.symlink_to(path)
    with pytest.raises(ValueError): union.read_json(link, hashlib.sha256(data).hexdigest())
    not_json = tmp_path / 'raw.edf'
    not_json.write_bytes(b'not EEG, still not permitted')
    with pytest.raises(ValueError): union.read_json(not_json, 'a' * 64)


def test_duplicate_JSON_key_and_nonfinite_are_rejected(tmp_path):
    for body in (b'{"a":1,"a":2}', b'{"a":NaN}'):
        path = tmp_path / 'duplicate.json'
        path.write_bytes(body)
        with pytest.raises(ValueError): union.read_json(path, hashlib.sha256(body).hexdigest())


def test_changed_frozen_source_manifest_fails_before_target_helper(monkeypatch, tmp_path):
    monkeypatch.setattr(union, 'REPO', tmp_path)
    source = tmp_path / union.SOURCE_PATH
    source.parent.mkdir(parents=True)
    source.write_text('[]')
    with pytest.raises(ValueError, match='JSON_identity_changed'): union.frozen_catalogue()


def test_changed_fixed_official_helper_rejected(monkeypatch, tmp_path):
    old = union.REPO
    source = tmp_path / union.SOURCE_PATH
    source.parent.mkdir(parents=True)
    source.write_bytes((old / union.SOURCE_PATH).read_bytes())
    helper = tmp_path / union.TARGET_HELPER
    helper.parent.mkdir(parents=True)
    helper.write_text('raise AssertionError("must not execute changed helper")\n')
    monkeypatch.setattr(union, 'REPO', tmp_path)
    with pytest.raises(ValueError, match='fixed_official_metadata_helper_changed'): union.frozen_catalogue()
