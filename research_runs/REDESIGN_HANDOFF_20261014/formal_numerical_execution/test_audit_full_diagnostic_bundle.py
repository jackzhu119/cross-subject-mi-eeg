"""Synthetic evidence fixtures only; never stand in for the actual private bundle."""
import copy
import csv
import importlib.util
import io
import json
from pathlib import Path
import stat
import tarfile
import zipfile

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location('bundle_auditor', HERE / 'audit_full_diagnostic_bundle.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def encoded(value):
    return json.dumps(value, indent=2).encode()


@pytest.fixture
def members():
    """Invent a complete report from public reference bytes, NOT actual evidence."""
    expected = json.loads((ROOT / (a.EVIDENCE + 'source_exact_input_fingerprints_receipt.json')).read_text())['source_file_provenance']
    old = json.loads((ROOT / (a.OFFICIAL + 'v2_result_20261014T111526Z/new-host-source-report.json')).read_text())
    six = json.loads((ROOT / (a.OFFICIAL + 'fixed_zi_result_20261014T1200Z/report.json')).read_text())
    anchors = {r['sample_id']: r for r in six['results']}
    anomalies = old['per_trial_mismatches']['mu']['first_sample_ids']
    report = {'status': 'FULL_DIAGNOSTIC_MATCH_TRAINING_STILL_BLOCKED', 'trials': 2592, 'raw_files': 18,
        'frozen_file_identities': a.PUBLIC_IDENTITIES, 'native_array_hashes': old['actual_array_hashes'],
        'diagnostic_bundle_array_hashes': expected['array_hashes'], 'frozen_array_hashes': expected['array_hashes'],
        'native_per_trial_mismatches': {k: old['per_trial_mismatches'][k]['first_sample_ids'] for k in ('broad', 'mu', 'beta')},
        'fixed_zi_mu_mismatches': [], 'changed_from_native': [{'sample_id': sid, 'elements': 1} for sid in anomalies],
        'identity_hashes_match': True, 'six_trial_stage_anchors_match': True, 'new_fits': 0,
        'target_EEG_read': False, 'scientific_arrays_saved_or_replaced': False, 'production_native_pipeline_passed': False,
        'training_authorization': False, 'historical_generator_OpenBLAS_identity_established': False}
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=a.CSV_FIELDS)
    writer.writeheader()
    with (ROOT / (a.EVIDENCE + 'source_exact_input_fingerprints.csv')).open() as stream:
        for frozen in csv.DictReader(stream):
            sid = frozen['source_sample_id']; mu = frozen['mu_sha256']
            writer.writerow({'sample_id': sid, 'native_mu_sha256': anchors[sid]['branches']['native_calibration']['stages']['final_float32'] if sid in anchors else mu,
                'fixed_zi_mu_sha256': mu, 'frozen_mu_sha256': mu, 'changed_elements': 1 if sid in anomalies else 0, 'fixed_zi_matches': True})
    m = {basename: (ROOT / (a.OFFICIAL + basename)).read_bytes() for basename in
         ('diagnose_full_source_fixed_zi.py', 'probe_fixed_zi_mediation.py', 'fixed_zi_mediation_design.json')}
    m.update({'result/report.json': encoded(report), 'result/native_audit.json': encoded({**expected, 'array_hashes': old['actual_array_hashes']}),
        'result/trial_hash_comparison.csv': out.getvalue().encode(),
        'result/supervision.json': encoded({'exit_code': 0, 'timeout': False, 'new_fits': 0, 'training_authorization': False}),
        'result/worker.log': b'Synthetic fixture: no actual diagnostic performed.\n',
        'full-diagnostic.exit-code': b'0\n', 'README.md': b'Synthetic software-test fixture, not actual evidence.\n', 'timing.json': b'{"synthetic_fixture":true}\n'})
    return with_manifest(m)


def with_manifest(m):
    m = {n: v for n, v in m.items() if n != 'manifest.json'}
    m['manifest.json'] = encoded({'files': {n: {'sha256': a._sha(v), 'bytes': len(v)} for n, v in m.items()}})
    return m


def update_json(members, name, mutate):
    obj = json.loads(members[name]); mutate(obj)
    members[name] = encoded(obj)
    return with_manifest(members)


def update_csv(members, mutate):
    reader = csv.DictReader(io.StringIO(members['result/trial_hash_comparison.csv'].decode()))
    rows = list(reader); mutate(rows)
    out = io.StringIO(newline=''); writer = csv.DictWriter(out, fieldnames=reader.fieldnames)
    writer.writeheader(); writer.writerows(rows)
    members['result/trial_hash_comparison.csv'] = out.getvalue().encode()
    return with_manifest(members)


def test_complete_synthetic_semantics_are_not_archive_certification(members):
    result = a.audit_members(members, ROOT)
    assert result['status'] == 'FULL_DIAGNOSTIC_SEMANTICS_PASSED_ARCHIVE_IDENTITY_NOT_CHECKED'
    assert result['training_authorization'] is False
    assert result['unique_sample_ids'] == 2592
    assert result['internal_manifests_checked'] == {'manifest.json': 11}
    assert result['six_final_trial_hashes_checked'] == 6


def test_public_bundle_gate_cannot_be_replaced_with_fixture(tmp_path, members):
    path = tmp_path / 'synthetic.zip'
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items(): archive.writestr(name, data)
    with pytest.raises(a.AuditError, match='immutable_archive_'):
        a.audit_bundle(path, ROOT)


def test_zip_reader_is_read_only(tmp_path, members):
    path = tmp_path / 'synthetic.zip'
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items(): archive.writestr(name, data)
    before = list(tmp_path.iterdir())
    assert a.read_archive_members(path) == members
    assert list(tmp_path.iterdir()) == before


@pytest.mark.parametrize('basename', ['diagnose_full_source_fixed_zi.py', 'probe_fixed_zi_mediation.py', 'fixed_zi_mediation_design.json'])
def test_changed_implementation_rejected_even_with_rebuilt_manifest(members, basename):
    members[basename] += b'\n'
    with pytest.raises(a.AuditError, match='diagnostic_implementation_changed'):
        a.audit_members(with_manifest(members), ROOT)


@pytest.mark.parametrize('key,value', [
    ('status', 'COMPLETE'), ('trials', 2591), ('raw_files', 17), ('new_fits', 1), ('new_fits', False),
    ('target_EEG_read', True), ('training_authorization', True), ('production_native_pipeline_passed', True),
    ('scientific_arrays_saved_or_replaced', True), ('historical_generator_OpenBLAS_identity_established', True),
    ('identity_hashes_match', False), ('six_trial_stage_anchors_match', False), ('fixed_zi_mu_mismatches', ['bad']),
    ('native_per_trial_mismatches', {'broad': [], 'mu': [], 'beta': []}), ('changed_from_native', []),
    ('frozen_file_identities', {}), ('native_array_hashes', {}), ('frozen_array_hashes', {}), ('diagnostic_bundle_array_hashes', {})])
def test_changed_report_rejected(members, key, value):
    members = update_json(members, 'result/report.json', lambda obj: obj.update({key: value}))
    with pytest.raises(a.AuditError): a.audit_members(members, ROOT)


@pytest.mark.parametrize('key,value', [('exit_code', 2), ('exit_code', False), ('exit_code', None), ('timeout', True), ('new_fits', 1), ('training_authorization', True)])
def test_failed_or_scope_drift_supervision_rejected(members, key, value):
    members = update_json(members, 'result/supervision.json', lambda obj: obj.update({key: value}))
    with pytest.raises(a.AuditError): a.audit_members(members, ROOT)


@pytest.mark.parametrize('key', ['raw_files_verified', 'run_audit', 'preprocessing', 'source_labels_sha256', 'source_sample_ids_sha256', 'source_metadata_sha256', 'technical_exclusions', 'array_hashes'])
def test_native_audit_identity_and_full_roster_are_exact(members, key):
    members = update_json(members, 'result/native_audit.json', lambda obj: obj.update({key: 'changed'}))
    with pytest.raises(a.AuditError, match='native_source_audit_changed'):
        a.audit_members(members, ROOT)


@pytest.mark.parametrize('column,value', [('fixed_zi_mu_sha256', '0' * 64), ('frozen_mu_sha256', '0' * 64), ('native_mu_sha256', '0' * 64), ('changed_elements', '1'), ('fixed_zi_matches', 'False')])
def test_one_of_2592_csv_rows_cannot_be_changed(members, column, value):
    members = update_csv(members, lambda rows: rows[0].update({column: value}))
    with pytest.raises(a.AuditError): a.audit_members(members, ROOT)


def test_duplicate_csv_ID_rejected(members):
    members = update_csv(members, lambda rows: rows[1].update({'sample_id': rows[0]['sample_id']}))
    with pytest.raises(a.AuditError, match='ID_count_or_duplicates'): a.audit_members(members, ROOT)


def test_missing_csv_row_rejected(members):
    members = update_csv(members, lambda rows: rows.pop())
    with pytest.raises(a.AuditError, match='ID_count_or_duplicates'): a.audit_members(members, ROOT)


def test_csv_order_rejected(members):
    members = update_csv(members, lambda rows: rows.reverse())
    with pytest.raises(a.AuditError, match='order_changed'): a.audit_members(members, ROOT)


def test_original_anomaly_cannot_be_erased(members):
    def erase(rows):
        row = next(r for r in rows if r['sample_id'] == 's02_1test_r2_t36')
        row['native_mu_sha256'] = row['frozen_mu_sha256']
    with pytest.raises(a.AuditError, match='native_per_trial_hash_mismatch'):
        a.audit_members(update_csv(members, erase), ROOT)


def test_manifest_checks_actual_bytes(members):
    members['result/worker.log'] += b'changed\n'
    with pytest.raises(a.AuditError, match='manifest_member_hash_mismatch'): a.audit_members(members, ROOT)


def test_manifest_requires_complete_inventory(members):
    manifest = json.loads(members['manifest.json']); manifest['files'].pop('result/worker.log')
    members['manifest.json'] = encoded(manifest)
    with pytest.raises(a.AuditError, match='manifest_member_set_changed'): a.audit_members(members, ROOT)


def test_manifest_size_must_match(members):
    manifest = json.loads(members['manifest.json']); manifest['files']['result/worker.log']['bytes'] += 1
    members['manifest.json'] = encoded(manifest)
    with pytest.raises(a.AuditError, match='manifest_member_size_mismatch'): a.audit_members(members, ROOT)


def test_text_checksum_manifest_also_verified(members):
    m = {n: v for n, v in members.items() if n != 'manifest.json'}
    m['SHA256SUMS.txt'] = ''.join(a._sha(v) + '  ' + n + '\n' for n, v in m.items()).encode()
    assert a.audit_members(m, ROOT)['internal_manifests_checked']['SHA256SUMS.txt'] == 11


def test_ambiguous_report_basename_rejected(members):
    members['extra/report.json'] = members.pop('timing.json')
    with pytest.raises(a.AuditError, match='unbound_prior_report_scope'): a.audit_members(with_manifest(members), ROOT)


def test_member_count_rejected(members):
    members.pop('timing.json')
    with pytest.raises(a.AuditError, match='member_count_changed'): a.audit_members(with_manifest(members), ROOT)


def test_outer_exit_rejected(members):
    members['full-diagnostic.exit-code'] = b'2\n'
    with pytest.raises(a.AuditError, match='outer_diagnostic_exit_not_zero'): a.audit_members(with_manifest(members), ROOT)


@pytest.mark.parametrize('bad', ['../report.json', '/report.json', 'a/../../report.json', './report.json', 'a//report.json', 'C:/report.json', 'a\\report.json'])
def test_zip_traversal_and_aliases_rejected(tmp_path, bad):
    path = tmp_path / 'bad.zip'
    with zipfile.ZipFile(path, 'w') as archive: archive.writestr(bad, b'{}')
    with pytest.raises(a.AuditError): a.read_archive_members(path)


def test_zip_symlink_rejected(tmp_path):
    path = tmp_path / 'bad.zip'; info = zipfile.ZipInfo('link.json')
    info.create_system = 3; info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(path, 'w') as archive: archive.writestr(info, '../target')
    with pytest.raises(a.AuditError, match='zip_link_or_special'): a.read_archive_members(path)


def test_duplicate_zip_members_rejected(tmp_path):
    path = tmp_path / 'bad.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('report.json', b'{}')
        with pytest.warns(UserWarning): archive.writestr('report.json', b'{}')
    with pytest.raises(a.AuditError, match='duplicate_member'): a.read_archive_members(path)


@pytest.mark.parametrize('name,data', [('eeg.npy', b'array'), ('model.pt', b'model'), ('x.json', b'\0binary'), ('x.txt', b'\xff')])
def test_binary_arrays_models_rejected(tmp_path, name, data):
    path = tmp_path / 'bad.zip'
    with zipfile.ZipFile(path, 'w') as archive: archive.writestr(name, data)
    with pytest.raises(a.AuditError): a.read_archive_members(path)


def test_archive_expansion_is_bounded(tmp_path):
    path = tmp_path / 'bad.zip'
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('bomb.txt', b'a' * (a.MAX_MEMBER_BYTES + 1))
    with pytest.raises(a.AuditError, match='member_size_limit'): a.read_archive_members(path)


@pytest.mark.parametrize('mode,suffix', [('w', '.tar'), ('w:gz', '.tar.gz')])
def test_tar_formats_read_without_extraction(tmp_path, mode, suffix):
    path = tmp_path / ('sample' + suffix)
    with tarfile.open(path, mode) as archive:
        info = tarfile.TarInfo('safe/report.json'); info.size = 2
        archive.addfile(info, io.BytesIO(b'{}'))
    assert a.read_archive_members(path) == {'safe/report.json': b'{}'}
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('kind', [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE])
def test_tar_links_and_special_files_rejected(tmp_path, kind):
    path = tmp_path / 'bad.tar'
    with tarfile.open(path, 'w') as archive:
        info = tarfile.TarInfo('link.json'); info.type = kind; info.linkname = 'other.json'
        archive.addfile(info)
    with pytest.raises(a.AuditError, match='tar_link_or_special'): a.read_archive_members(path)


def test_duplicate_json_keys_rejected():
    with pytest.raises(a.AuditError, match='duplicate_json_key'): a._json(b'{"x":1,"x":2}')


def test_nonfinite_json_rejected():
    with pytest.raises(a.AuditError, match='nonfinite_json'): a._json(b'{"x":NaN}')


def test_no_files_can_be_extracted_or_training_code_imported():
    source = (HERE / 'audit_full_diagnostic_bundle.py').read_text()
    assert '.extractall(' not in source
    assert 'import numpy' not in source
    assert 'import torch' not in source
    assert 'subprocess' not in source


def test_full_report_and_pinned_prior_six_report_are_separate_scopes(members):
    members.pop('timing.json')
    members['prior_six/report.json'] = (ROOT / (a.OFFICIAL + 'fixed_zi_result_20261014T1200Z/report.json')).read_bytes()
    result = a.audit_members(with_manifest(members), ROOT)
    assert result['full_report_member'] == 'result/report.json'
    assert result['members'] == 12


def test_full_and_prior_supervision_select_full_report_scope(members):
    members.pop('timing.json'); members.pop('README.md')
    members['prior_six/report.json'] = (ROOT / (a.OFFICIAL + 'fixed_zi_result_20261014T1200Z/report.json')).read_bytes()
    members['prior_six/supervision.json'] = encoded({'prior_scope_fixture': True, 'exit_code': 0})
    result = a.audit_members(with_manifest(members), ROOT)
    assert result['full_report_member'] == 'result/report.json'


def test_failed_full_supervision_not_masked_by_prior_scope(members):
    members.pop('timing.json'); members.pop('README.md')
    members['prior_six/report.json'] = (ROOT / (a.OFFICIAL + 'fixed_zi_result_20261014T1200Z/report.json')).read_bytes()
    members['prior_six/supervision.json'] = members['result/supervision.json']
    obj = json.loads(members['result/supervision.json']); obj['exit_code'] = 2
    members['result/supervision.json'] = encoded(obj)
    with pytest.raises(a.AuditError, match='diagnostic_worker_exit_not_zero'):
        a.audit_members(with_manifest(members), ROOT)


def test_two_matching_full_reports_rejected(members):
    members.pop('timing.json')
    members['other/report.json'] = members['result/report.json']
    with pytest.raises(a.AuditError, match='ambiguous_full_diagnostic_report'):
        a.audit_members(with_manifest(members), ROOT)


def test_changed_prior_six_report_rejected(members):
    members.pop('timing.json')
    members['prior_six/report.json'] = (ROOT / (a.OFFICIAL + 'fixed_zi_result_20261014T1200Z/report.json')).read_bytes() + b'\n'
    with pytest.raises(a.AuditError, match='unbound_prior_report_scope'):
        a.audit_members(with_manifest(members), ROOT)


def test_ambiguous_flattened_supervision_rejected(members):
    members.pop('timing.json')
    members['other/supervision.json'] = members.pop('result/supervision.json')
    members['prior_six/supervision.json'] = members['other/supervision.json']
    with pytest.raises(a.AuditError, match='missing_or_ambiguous_evidence:supervision.json'):
        a.audit_members(with_manifest(members), ROOT)


def test_native_fit_count_boolean_cannot_impersonate_zero(members):
    members = update_json(members, 'result/native_audit.json', lambda obj: obj.update({'new_model_fits': False}))
    with pytest.raises(a.AuditError, match='native_audit_scope_changed'):
        a.audit_members(members, ROOT)
