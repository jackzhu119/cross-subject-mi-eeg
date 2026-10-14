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
    cloud_config = json.loads((ROOT / 'research_runs/REDESIGN_CLOUD_20261013/config/experiment.json').read_text())
    cloud_config_sha = a._sha(json.dumps(cloud_config, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())
    m.update({'result/report.json': encoded(report), 'result/native_audit.json': encoded({**expected, 'array_hashes': old['actual_array_hashes'],
        'preprocessing': {**expected['preprocessing'], 'config_canonical_sha256': cloud_config_sha}}),
        'result/trial_hash_comparison.csv': out.getvalue().encode(),
        'result/supervision.json': encoded({'exit_code': 0, 'timeout': False, 'new_fits': 0, 'training_authorization': False}),
        'result/worker.log': b'Synthetic fixture: no actual diagnostic performed.\n',
        'full-diagnostic.exit-code': b'0\n', 'README.md': b'Synthetic software-test fixture, not actual evidence.\n', 'timing.json': b'{"synthetic_fixture":true}\n',
        'new-host-source-report.json': (ROOT / (a.OFFICIAL + 'v2_result_20261014T111526Z/new-host-source-report.json')).read_bytes()})
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
    assert result['internal_manifests_checked'] == {'manifest.json': 12}
    assert result['physical_regular_members'] == 13
    assert result['members'] == 12
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
    assert a.audit_members(m, ROOT)['internal_manifests_checked']['SHA256SUMS.txt'] == 12


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

# Exact text fixtures for schema checks; stored as inert byte literals only.
KNOWN_LAUNCH_SCRIPT = b'#!/usr/bin/env bash\nset -Eeuo pipefail\nset -o noclobber\nexec > /workspace/paper1-official-source-bootstrap/launch-full-source-fixed-zi-run01.log 2>&1\ntrap \'rc=$?; echo OUTER_EXIT_CODE=$rc; echo END=$(date -u +%Y-%m-%dT%H:%M:%SZ)\' EXIT\necho START=$(date -u +%Y-%m-%dT%H:%M:%SZ)\necho DISPATCH_PID=$$\nps -eo pid,ppid,comm | grep -E \'python|pip|uv|bash|timeout|torch\' || true\nnvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader\ndf -B1 /workspace\ntest "$(df -B1 --output=avail /workspace | tail -1)" -gt 6442450944\ntest ! -e /workspace/paper1-readonly-probe/full-source-fixed-zi-diagnostic-run01\ntest "$(git -C /workspace/paper1-source-diagnostic-c802 rev-parse HEAD)" = c802e65709103189becf7e6ff3a55c99a405a7e8\ntest -z "$(git -C /workspace/paper1-source-diagnostic-c802 status --porcelain)"\ncd /workspace/paper1-official-source-bootstrap\ntest ! -e diagnose_full_source_fixed_zi.py\ncurl --fail --silent --show-error --max-time 60 --max-redirs 0 --proto \'=https\' --retry 0 \'https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/5f20b35ab720f05ee208d4ceb12d582148719bf8/research_runs/REDESIGN_HANDOFF_20261014/official_source_diagnostic/diagnose_full_source_fixed_zi.py\' -o diagnose_full_source_fixed_zi.py\nprintf \'%s\\n\' \'7a192acf5c4911e010c1fd48d0f96af2c808d93a929644c3c228e06aa5fe4124  diagnose_full_source_fixed_zi.py\' \'18c51bbe10d4113c2ad92a6d7dad332590ae2941aeb15a0a70012f09a2527014  probe_fixed_zi_mediation.py\' \'e6aaad1be0e30496c809bb5dfe795f0ce81055adf5e7bdef5e1382b177348c44  fixed_zi_mediation_design.json\' \'88e5b75d18e913640988419d9f693e9650116a13049e5b8e683a9a74ee8073e3  /workspace/paper1-readonly-probe/fixed-zi-mediation-run01/report.json\' \'a481ee98d6a1184dd6a696754b8c47a9a3bcfc6b92941393a90e7dcecbbd0a2b  /workspace/paper1-readonly-probe/new-host-source-report.json\' | sha256sum -c -\n/workspace/paper1-diagnostic-runtime/bin/python /workspace/paper1-official-source-bootstrap/diagnose_full_source_fixed_zi.py --checkout /workspace/paper1-source-diagnostic-c802 --data-dir /workspace/paper1-readonly-probe/data --helper /workspace/paper1-official-source-bootstrap/probe_fixed_zi_mediation.py --design /workspace/paper1-official-source-bootstrap/fixed_zi_mediation_design.json --six-report /workspace/paper1-readonly-probe/fixed-zi-mediation-run01/report.json --original-report /workspace/paper1-readonly-probe/new-host-source-report.json --output-dir /workspace/paper1-readonly-probe/full-source-fixed-zi-diagnostic-run01\necho FULL_DIAGNOSTIC_COMPLETED\n'
KNOWN_LAUNCH_LOG = b'START=2026-10-14T12:29:03Z\nDISPATCH_PID=26135\n   3721     128 bash\n  26133    3721 bash\n  26135   26133 bash\nFilesystem       1B-blocks        Used   Available Use% Mounted on\noverlay        32212254720 10727948288 21484306432  34% /\ndiagnose_full_source_fixed_zi.py: OK\nprobe_fixed_zi_mediation.py: OK\nfixed_zi_mediation_design.json: OK\n/workspace/paper1-readonly-probe/fixed-zi-mediation-run01/report.json: OK\n/workspace/paper1-readonly-probe/new-host-source-report.json: OK\nFULL_DIAGNOSTIC_COMPLETED\nOUTER_EXIT_CODE=0\nEND=2026-10-14T12:29:58Z\n'


def actual_layout_fixture(members):
    """Same member schema, synthetic full report; no actual audit substituted."""
    for name in ('timing.json', 'README.md', 'full-diagnostic.exit-code'):
        members.pop(name)
    members['prior_six/report.json'] = (ROOT / (a.OFFICIAL + 'fixed_zi_result_20261014T1200Z/report.json')).read_bytes()
    members['bootstrap/launch-full-source-fixed-zi-run01.sh'] = KNOWN_LAUNCH_SCRIPT
    members['bootstrap/launch-full-source-fixed-zi-run01.log'] = KNOWN_LAUNCH_LOG
    return with_manifest(members)


def test_actual_schema_counts_manifest_separately_from_payload(members):
    result = a.audit_members(actual_layout_fixture(members), ROOT)
    assert result['members'] == 12
    assert result['physical_regular_members'] == 13
    assert result['inventory_members'] == 1
    assert result['internal_manifests_checked'] == {'manifest.json': 12}
    assert result['launch_records_checked']['elapsed_seconds'] == 55
    assert result['launch_records_checked']['archived_script_executed_by_this_auditor'] is False


def test_actual_manifest_list_schema(members):
    m = actual_layout_fixture(members)
    inventory = json.loads(m['manifest.json'])['files']
    m['manifest.json'] = encoded({'files': [{'path': n, **record} for n, record in inventory.items()], 'new_fits': 0, 'contains_EEG_arrays': False})
    assert a.audit_members(m, ROOT)['internal_manifests_checked'] == {'manifest.json': 12}


def test_unknown_shell_rejected(members):
    m = actual_layout_fixture(members)
    m['bootstrap/unknown.sh'] = m.pop('bootstrap/launch-full-source-fixed-zi-run01.sh')
    with pytest.raises(a.AuditError, match='non_evidence_or_array_member'):
        a.audit_members(with_manifest(m), ROOT)


def test_changed_launch_shell_rejected(members):
    m = actual_layout_fixture(members); m['bootstrap/launch-full-source-fixed-zi-run01.sh'] += b'\n'
    with pytest.raises(a.AuditError, match='non_evidence_or_array_member'):
        a.audit_members(with_manifest(m), ROOT)


def test_changed_launcher_log_rejected(members):
    m = actual_layout_fixture(members)
    m['bootstrap/launch-full-source-fixed-zi-run01.log'] = KNOWN_LAUNCH_LOG.replace(b'OUTER_EXIT_CODE=0', b'OUTER_EXIT_CODE=2')
    with pytest.raises(a.AuditError, match='full_launch_record_changed'):
        a.audit_members(with_manifest(m), ROOT)


def test_missing_launch_record_rejected(members):
    m = actual_layout_fixture(members); m.pop('bootstrap/launch-full-source-fixed-zi-run01.log')
    m['extra.json'] = b'{}'
    with pytest.raises(a.AuditError, match='full_launch_records_incomplete'):
        a.audit_members(with_manifest(m), ROOT)


def test_archived_original_native_report_exact_sha_required(members):
    members['new-host-source-report.json'] += b'\n'
    with pytest.raises(a.AuditError, match='archived_original_native_report_changed'):
        a.audit_members(with_manifest(members), ROOT)


def test_cloud_config_scope_hash_must_come_from_bound_config(members):
    obj = json.loads(members['result/native_audit.json'])
    obj['preprocessing']['config_canonical_sha256'] = '0' * 64
    members['result/native_audit.json'] = encoded(obj)
    with pytest.raises(a.AuditError, match='native_source_audit_changed'):
        a.audit_members(with_manifest(members), ROOT)


def test_old_base_config_hash_does_not_impersonate_actual_execution_config(members):
    old_sha = json.loads((ROOT / (a.EVIDENCE + 'source_exact_input_fingerprints_receipt.json')).read_text())['source_file_provenance']['preprocessing']['config_canonical_sha256']
    obj = json.loads(members['result/native_audit.json']); obj['preprocessing']['config_canonical_sha256'] = old_sha
    members['result/native_audit.json'] = encoded(obj)
    with pytest.raises(a.AuditError, match='native_source_audit_changed'):
        a.audit_members(with_manifest(members), ROOT)


def test_manifest_false_zero_must_not_authorize_fits(members):
    manifest = json.loads(members['manifest.json']); manifest['new_fits'] = False
    members['manifest.json'] = encoded(manifest)
    with pytest.raises(a.AuditError, match='manifest_fit_scope_changed'):
        a.audit_members(members, ROOT)


def test_manifest_EEG_array_claim_is_rejected(members):
    manifest = json.loads(members['manifest.json']); manifest['contains_EEG_arrays'] = True
    members['manifest.json'] = encoded(manifest)
    with pytest.raises(a.AuditError, match='manifest_declares_EEG_arrays'):
        a.audit_members(members, ROOT)
