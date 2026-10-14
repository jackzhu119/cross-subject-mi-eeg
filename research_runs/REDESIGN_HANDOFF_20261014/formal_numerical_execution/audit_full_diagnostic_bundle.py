"""Read-only, bounded audit of the named full-source diagnostic private archive.

This checks evidence, not EEG arrays, training inputs, authorization, or old-host
BLAS identity. It never extracts members or executes archived Python scripts.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
import zipfile

EXPECTED_ARCHIVE_SHA256 = '2871f422755bf5d0b939d0db59fc41547b192d6c939db1a6a13b97a91ba49ae9'
EXPECTED_ARCHIVE_BYTES = 134436
EXPECTED_PAYLOAD_MEMBERS = 12
EXPECTED_MEMBERS = EXPECTED_PAYLOAD_MEMBERS  # Compatibility alias; excludes inventory files.
EXPECTED_PHYSICAL_MEMBERS = 13
MAX_MEMBER_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_BYTES = 256 * 1024
MAX_ENTRIES = 32
OFFICIAL = 'research_runs/REDESIGN_HANDOFF_20261014/official_source_diagnostic/'
EVIDENCE = 'research_runs/REDESIGN_EXPLORATORY_20261013/evidence/'
PUBLIC_IDENTITIES = {
    'research_runs/REDESIGN_CLOUD_20261013/config/experiment.json': '8ba78d4ead0e41fc5a5fc6f9890b750f0bdfdaba74a57efab5422b43d57feff0',
    'research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts/core_source_inputs.py': '03f47bceb3998e407a28e7da56da4875b5d3e1e38746d196739be7262be7cff5',
    'src/mi_eeg/data/q15_context.py': '849ee22e2a1c1987c2a83ed3a837f9f358b505133ce2ffe13ee876f01adc3d61',
    'research_runs/Q8-E001/results/source_files.json': '0ccef780ed5bfbc2d430b8caf0c108641fb230a2dc27e4189e7e771c999f64a6',
    EVIDENCE + 'source_exact_input_fingerprints.csv': 'e142e927228d9c46afb872fa649335cc6e9ec286b1d291b94ac0e43a6d59e4cf',
    EVIDENCE + 'source_exact_input_fingerprints_receipt.json': '66c5aa472809cf29fe68b7b56401c4f0aa4b4f577156425a1f4e1fc20d45d8dd',
}
BOUND_PUBLIC_FILES = {
    **PUBLIC_IDENTITIES,
    OFFICIAL + 'diagnose_full_source_fixed_zi.py': '7a192acf5c4911e010c1fd48d0f96af2c808d93a929644c3c228e06aa5fe4124',
    OFFICIAL + 'probe_fixed_zi_mediation.py': '18c51bbe10d4113c2ad92a6d7dad332590ae2941aeb15a0a70012f09a2527014',
    OFFICIAL + 'fixed_zi_mediation_design.json': 'e6aaad1be0e30496c809bb5dfe795f0ce81055adf5e7bdef5e1382b177348c44',
    OFFICIAL + 'fixed_zi_result_20261014T1200Z/report.json': '88e5b75d18e913640988419d9f693e9650116a13049e5b8e683a9a74ee8073e3',
    OFFICIAL + 'v2_result_20261014T111526Z/new-host-source-report.json': 'a481ee98d6a1184dd6a696754b8c47a9a3bcfc6b92941393a90e7dcecbbd0a2b',
}
BOUND_LAUNCH_FILES = {
    'launch-full-source-fixed-zi-run01.sh': '107692de7c470b49c543fa13989790edcf0ea83fd9adf80f3ee15ffff89876e2',
    'launch-full-source-fixed-zi-run01.log': '27a82b83b608f58f97e152aa1399af2244c6dc9e78494425443224b43bf6fa4c',
}
ARRAY_EXTENSIONS = {'.mat', '.npy', '.npz', '.edf', '.gdf', '.h5', '.hdf5', '.pkl', '.pickle', '.pt', '.pth', '.safetensors', '.bin'}
TEXT_EXTENSIONS = {'.json', '.csv', '.py', '.txt', '.log', '.md', '.sha256', '.exit-code'}
CSV_FIELDS = ['sample_id', 'native_mu_sha256', 'fixed_zi_mu_sha256', 'frozen_mu_sha256', 'changed_elements', 'fixed_zi_matches']


class AuditError(ValueError):
    """An exact evidence or safe-archive condition was not satisfied."""


def _require(condition, code):
    if not condition:
        raise AuditError(code)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _safe_name(name):
    _require(isinstance(name, str) and name and '\\' not in name and '\0' not in name, 'unsafe_member_name')
    _require(not name.startswith('/') and not re.match(r'^[A-Za-z]:', name), 'absolute_member_path')
    parts = name.rstrip('/').split('/')
    _require(all(p not in ('', '.', '..') for p in parts), 'member_path_traversal_or_alias')
    return str(PurePosixPath(*parts))


def _validate_members(members):
    total = 0
    for name, data in members.items():
        _require(_safe_name(name) == name, 'noncanonical_member_name')
        suffix = Path(name).suffix.lower()
        allowed_shell = PurePosixPath(name).name == 'launch-full-source-fixed-zi-run01.sh' and _sha(data) == BOUND_LAUNCH_FILES['launch-full-source-fixed-zi-run01.sh']
        _require(suffix not in ARRAY_EXTENSIONS and (suffix in TEXT_EXTENSIONS or allowed_shell), 'non_evidence_or_array_member')
        _require(isinstance(data, bytes) and len(data) <= MAX_MEMBER_BYTES, 'member_size_limit')
        _require(b'\x00' not in data, 'binary_member_forbidden')
        try:
            data.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise AuditError('non_utf8_member') from exc
        total += len(data)
    _require(total <= MAX_TOTAL_BYTES, 'archive_expansion_limit')


def read_archive_members(path):
    """Return safe regular text members without writing any archive member."""
    path = Path(path)
    _require(not path.is_symlink() and path.is_file(), 'regular_archive_required')
    _require(path.stat().st_size <= MAX_ARCHIVE_BYTES, 'archive_size_limit')
    data = path.read_bytes()
    _require(len(data) <= MAX_ARCHIVE_BYTES, 'archive_size_limit')
    return _read_archive_bytes(data)


def _read_archive_bytes(data):
    # Parse the same immutable byte snapshot that audit_bundle hashes.
    source = io.BytesIO(data)
    members = {}
    seen = set()
    total = 0

    def put(raw_name, size, data, is_directory=False):
        nonlocal total
        name = _safe_name(raw_name)
        _require(name not in seen, 'duplicate_member')
        seen.add(name)
        _require(len(seen) <= MAX_ENTRIES, 'archive_entry_limit')
        if is_directory:
            return
        _require(0 <= size <= MAX_MEMBER_BYTES, 'member_size_limit')
        _require(len(data) == size, 'member_size_mismatch')
        total += size
        _require(total <= MAX_TOTAL_BYTES, 'archive_expansion_limit')
        members[name] = data

    if zipfile.is_zipfile(source):
        source.seek(0)
        with zipfile.ZipFile(source) as archive:
            _require(len(archive.infolist()) <= MAX_ENTRIES, 'archive_entry_limit')
            for info in archive.infolist():
                _safe_name(info.filename)
                _require(not info.flag_bits & 1, 'encrypted_member_forbidden')
                mode = info.external_attr >> 16
                kind = stat.S_IFMT(mode)
                _require(kind in (0, stat.S_IFREG, stat.S_IFDIR), 'zip_link_or_special_member')
                _require(info.file_size <= MAX_MEMBER_BYTES, 'member_size_limit')
                data = b'' if info.is_dir() else archive.read(info)
                put(info.filename, info.file_size, data, info.is_dir())
    else:
        try:
            source.seek(0)
            with tarfile.open(fileobj=source, mode='r:*') as archive:
                for info in archive:
                    _safe_name(info.name)
                    _require(info.isfile() or info.isdir(), 'tar_link_or_special_member')
                    _require(info.size <= MAX_MEMBER_BYTES, 'member_size_limit')
                    stream = archive.extractfile(info) if info.isfile() else None
                    data = stream.read(MAX_MEMBER_BYTES + 1) if stream else b''
                    put(info.name, info.size, data, info.isdir())
        except tarfile.TarError as exc:
            raise AuditError('unsupported_or_invalid_archive') from exc
    _validate_members(members)
    return members


def _json(data):
    def no_duplicates(items):
        result = {}
        for key, value in items:
            _require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=no_duplicates,
                          parse_constant=lambda value: (_ for _ in ()).throw(AuditError('nonfinite_json_value')))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError('invalid_json_evidence') from exc


def _member(members, basename):
    candidates = [n for n in members if PurePosixPath(n).name == basename]
    _require(len(candidates) == 1, 'missing_or_ambiguous_evidence:' + basename)
    return members[candidates[0]]


def _full_report(members):
    """Separate full and prior six-trial scopes by status plus pinned bytes."""
    candidates = []
    six_sha = BOUND_PUBLIC_FILES[OFFICIAL + 'fixed_zi_result_20261014T1200Z/report.json']
    for name, data in members.items():
        if PurePosixPath(name).name != 'report.json':
            continue
        report = _json(data)
        if isinstance(report, dict) and report.get('status') == 'FULL_DIAGNOSTIC_MATCH_TRAINING_STILL_BLOCKED':
            candidates.append((name, report))
        else:
            _require(_sha(data) == six_sha, 'unbound_prior_report_scope:' + name)
    _require(len(candidates) == 1, 'missing_or_ambiguous_full_diagnostic_report')
    return candidates[0]


def _scoped_member(members, basename, report_name):
    name = str(PurePosixPath(report_name).parent / basename)
    if name in members:
        return members[name]
    # Legacy archive layouts may flatten unique evidence members.
    return _member(members, basename)


def _bound_references(checkout):
    checkout = Path(checkout)
    checked = {}
    for name, digest in BOUND_PUBLIC_FILES.items():
        path = checkout / name
        _require(not path.is_symlink() and path.is_file(), 'public_evidence_not_regular:' + name)
        data = path.read_bytes()
        _require(_sha(data) == digest, 'public_evidence_changed:' + name)
        checked[name] = data
    return checked


def _manifest_record(record):
    if isinstance(record, str):
        return {'sha256': record}
    _require(isinstance(record, dict) and 'sha256' in record, 'invalid_manifest_record')
    return record


def _validate_manifests(members):
    """Check recognized optional inventories against every non-inventory member."""
    inventories = {}
    for name, data in members.items():
        base = PurePosixPath(name).name.lower()
        if base in ('sha256sums.txt', 'sha256sums', 'manifest.sha256', 'checksums.sha256'):
            inventory = {}
            for line in data.decode().splitlines():
                if not line.strip():
                    continue
                match = re.fullmatch(r'([0-9a-f]{64})\s+\*?(.+)', line)
                _require(match is not None, 'invalid_checksum_manifest_line')
                item = _safe_name(match.group(2))
                _require(item not in inventory, 'duplicate_manifest_member')
                inventory[item] = {'sha256': match.group(1)}
            inventories[name] = inventory
        elif base.endswith('manifest.json') or base == 'inventory.json':
            obj = _json(data)
            _require(isinstance(obj, dict), 'invalid_manifest_object')
            if 'new_fits' in obj:
                _require(type(obj['new_fits']) is int and obj['new_fits'] == 0, 'manifest_fit_scope_changed')
            if 'contains_EEG_arrays' in obj:
                _require(obj['contains_EEG_arrays'] is False, 'manifest_declares_EEG_arrays')
            entries = obj.get('members', obj.get('files'))
            _require(entries is not None, 'manifest_member_inventory_missing')
            if isinstance(entries, dict):
                inventory = {_safe_name(n): _manifest_record(v) for n, v in entries.items()}
            else:
                _require(isinstance(entries, list), 'invalid_manifest_entries')
                inventory = {}
                for record in entries:
                    _require(isinstance(record, dict), 'invalid_manifest_record')
                    item = _safe_name(record.get('path', record.get('name', record.get('filename'))))
                    _require(item not in inventory, 'duplicate_manifest_member')
                    inventory[item] = _manifest_record(record)
            inventories[name] = inventory
    expected = set(members) - set(inventories)
    for name, inventory in inventories.items():
        _require(set(inventory) == expected, 'manifest_member_set_changed:' + name)
        for item, record in inventory.items():
            _require(record['sha256'] == _sha(members[item]), 'manifest_member_hash_mismatch:' + item)
            if 'bytes' in record:
                _require(type(record['bytes']) is int and record['bytes'] == len(members[item]), 'manifest_member_size_mismatch:' + item)
    return {n: len(v) for n, v in inventories.items()}


def _validate_launch_records(members, *, required):
    present = {PurePosixPath(n).name for n in members} & set(BOUND_LAUNCH_FILES)
    if not present and not required:
        return None
    _require(present == set(BOUND_LAUNCH_FILES), 'full_launch_records_incomplete')
    for basename, digest in BOUND_LAUNCH_FILES.items():
        _require(_sha(_member(members, basename)) == digest, 'full_launch_record_changed:' + basename)
    log = _member(members, 'launch-full-source-fixed-zi-run01.log').decode().splitlines()
    for line in ('START=2026-10-14T12:29:03Z', 'END=2026-10-14T12:29:58Z', 'OUTER_EXIT_CODE=0', 'FULL_DIAGNOSTIC_COMPLETED'):
        _require(log.count(line) == 1, 'full_launch_completion_or_timing_changed')
    _require(log.index('START=2026-10-14T12:29:03Z') < log.index('FULL_DIAGNOSTIC_COMPLETED') < log.index('OUTER_EXIT_CODE=0') < log.index('END=2026-10-14T12:29:58Z'), 'full_launch_record_order_changed')
    return {'script_and_log_exact_hashes': BOUND_LAUNCH_FILES, 'started_at_utc': '2026-10-14T12:29:03Z',
            'ended_at_utc': '2026-10-14T12:29:58Z', 'elapsed_seconds': 55, 'outer_exit_code': 0,
            'completion_marker_verified': True, 'archived_script_executed_by_this_auditor': False}


def audit_members(members, checkout, *, require_member_count=True):
    """Audit semantic evidence; this lower layer does NOT certify archive identity.

    Tests may build synthetic evidence here. Production must call audit_bundle,
    which has no option for replacing the expected package SHA or byte length.
    """
    _validate_members(members)
    refs = _bound_references(checkout)
    for basename in ('diagnose_full_source_fixed_zi.py', 'probe_fixed_zi_mediation.py', 'fixed_zi_mediation_design.json'):
        _require(_member(members, basename) == refs[OFFICIAL + basename], 'diagnostic_implementation_changed:' + basename)
    manifests = _validate_manifests(members)
    payload_count = len(members) - len(manifests)
    if require_member_count:
        _require(payload_count == EXPECTED_PAYLOAD_MEMBERS, 'archive_member_count_changed')
    launch_records = _validate_launch_records(members, required=False)
    for name, data in members.items():
        if PurePosixPath(name).name == 'new-host-source-report.json':
            _require(data == refs[OFFICIAL + 'v2_result_20261014T111526Z/new-host-source-report.json'], 'archived_original_native_report_changed')
    expected = _json(refs[EVIDENCE + 'source_exact_input_fingerprints_receipt.json'])['source_file_provenance']
    old = _json(refs[OFFICIAL + 'v2_result_20261014T111526Z/new-host-source-report.json'])
    six = _json(refs[OFFICIAL + 'fixed_zi_result_20261014T1200Z/report.json'])
    report_name, report = _full_report(members)
    native = _json(_scoped_member(members, 'native_audit.json', report_name))
    supervision = _json(_scoped_member(members, 'supervision.json', report_name))
    _require(isinstance(report, dict) and report.get('status') == 'FULL_DIAGNOSTIC_MATCH_TRAINING_STILL_BLOCKED', 'full_diagnostic_not_complete')
    _require(type(supervision.get('exit_code')) is int and supervision['exit_code'] == 0 and supervision.get('timeout') is False, 'diagnostic_worker_exit_not_zero')
    for basename in (PurePosixPath(n).name for n in members):
        if basename.endswith('.exit-code'):
            _require(_member(members, basename).strip() == b'0', 'outer_diagnostic_exit_not_zero')
    false_report_flags = ('target_EEG_read', 'scientific_arrays_saved_or_replaced', 'production_native_pipeline_passed', 'training_authorization', 'historical_generator_OpenBLAS_identity_established')
    _require(all(report.get(k) is False for k in false_report_flags), 'diagnostic_scope_or_authorization_changed')
    _require(type(report.get('new_fits')) is int and report['new_fits'] == 0, 'diagnostic_fit_count_changed')
    _require(type(supervision.get('new_fits')) is int and supervision['new_fits'] == 0 and supervision.get('training_authorization') is False, 'supervision_scope_changed')
    _require(report.get('trials') == 2592 and report.get('raw_files') == 18, 'report_population_changed')
    _require(report.get('frozen_file_identities') == PUBLIC_IDENTITIES, 'report_frozen_identity_changed')
    _require(report.get('native_array_hashes') == old['actual_array_hashes'], 'native_whole_array_evidence_changed')
    _require(report.get('diagnostic_bundle_array_hashes') == expected['array_hashes'] and report.get('frozen_array_hashes') == expected['array_hashes'], 'fixed_whole_array_hash_mismatch')
    _require(report.get('identity_hashes_match') is True and report.get('six_trial_stage_anchors_match') is True, 'identity_or_six_anchor_assertion_failed')
    anomalies = old['per_trial_mismatches']['mu']['first_sample_ids']
    expected_mismatches = {band: old['per_trial_mismatches'][band]['first_sample_ids'] for band in ('broad', 'mu', 'beta')}
    _require(report.get('native_per_trial_mismatches') == expected_mismatches, 'original_native_anomaly_evidence_changed')
    _require(report.get('fixed_zi_mu_mismatches') == [], 'fixed_trial_mismatches_present')
    _require(report.get('changed_from_native') == [{'sample_id': sid, 'elements': 1} for sid in anomalies], 'changed_element_inventory_changed')
    # The diagnostic executed the exact pinned cloud config, while the earlier
    # source fingerprint receipt hashed its smaller base source config. Keep
    # every preprocessing field exact; derive this metadata-only full-config
    # identity from the already byte-bound cloud config, never from the archive.
    cloud_config = _json(refs['research_runs/REDESIGN_CLOUD_20261013/config/experiment.json'])
    cloud_config_canonical_sha = _sha(json.dumps(cloud_config, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())
    expected_native = {**expected, 'array_hashes': old['actual_array_hashes'],
        'preprocessing': {**expected['preprocessing'], 'config_canonical_sha256': cloud_config_canonical_sha}}
    _require(native == expected_native, 'native_source_audit_changed')
    _require(all(type(native[k]) is int and native[k] == 0 for k in ('new_model_fits', 'target_fits')) and
             native.get('target_eeg_read') is False and native.get('target_predictions_computed') is False, 'native_audit_scope_changed')
    _require(native['n_runs'] == 108 and sum(r['bytes'] for r in native['raw_files_verified']) == 779873919, 'native_run_or_byte_count_changed')
    fingerprints = list(csv.DictReader(io.StringIO(refs[EVIDENCE + 'source_exact_input_fingerprints.csv'].decode())))
    _require(len(fingerprints) == 2592, 'frozen_trial_count_changed')
    reader = csv.DictReader(io.StringIO(_scoped_member(members, 'trial_hash_comparison.csv', report_name).decode()))
    _require(reader.fieldnames == CSV_FIELDS, 'comparison_csv_schema_changed')
    rows = list(reader)
    _require(len(rows) == 2592 and len({r['sample_id'] for r in rows}) == 2592, 'comparison_csv_ID_count_or_duplicates')
    _require([r['sample_id'] for r in rows] == [r['source_sample_id'] for r in fingerprints], 'comparison_csv_order_changed')
    anchors = {r['sample_id']: r for r in six['results']}
    mismatch_ids = []
    changed_ids = []
    for row, frozen in zip(rows, fingerprints):
        sid = row['sample_id']
        wanted = frozen['mu_sha256']
        _require(row['frozen_mu_sha256'] == wanted and row['fixed_zi_mu_sha256'] == wanted and row['fixed_zi_matches'] == 'True', 'fixed_per_trial_hash_mismatch:' + sid)
        actual_native = anchors[sid]['branches']['native_calibration']['stages']['final_float32'] if sid in anchors else wanted
        _require(row['native_mu_sha256'] == actual_native, 'native_per_trial_hash_mismatch:' + sid)
        _require(row['changed_elements'] == ('1' if sid in anomalies else '0'), 'per_trial_changed_count_mismatch:' + sid)
        if row['native_mu_sha256'] != wanted:
            mismatch_ids.append(sid)
        if row['changed_elements'] != '0':
            changed_ids.append(sid)
        if sid in anchors:
            _require(row['fixed_zi_mu_sha256'] == anchors[sid]['branches']['fixed_zi_counterfactual']['stages']['final_float32'], 'six_anchor_final_hash_mismatch:' + sid)
    _require(mismatch_ids == anomalies and changed_ids == anomalies and set(anchors).issubset({r['sample_id'] for r in rows}), 'native_anomaly_or_anchor_inventory_changed')
    return {'status': 'FULL_DIAGNOSTIC_SEMANTICS_PASSED_ARCHIVE_IDENTITY_NOT_CHECKED',
            'training_authorization': False, 'new_fits': 0, 'target_EEG_read': False,
            'historical_generator_OpenBLAS_identity_established': False,
            'members': payload_count, 'physical_regular_members': len(members), 'inventory_members': len(manifests), 'launch_records_checked': launch_records, 'full_report_member': report_name, 'trials': 2592, 'unique_sample_ids': 2592,
            'raw_files': 18, 'raw_file_bytes': 779873919, 'runs': 108,
            'native_mu_anomalies_retained': anomalies, 'all_fixed_mu_trial_hashes_match': True,
            'all_reported_fixed_array_hashes_match': True, 'frozen_source_identity_hashes_match': True,
            'unchanged_broad_beta_native_audit_matches': True,
            'six_stage_anchor_assertion_bound_to_exact_script_and_prior_report': True,
            'six_final_trial_hashes_checked': 6, 'internal_manifests_checked': manifests,
            'diagnostic_cloud_config_canonical_sha256': cloud_config_canonical_sha,
            'historical_receipt_base_source_config_canonical_sha256': expected['preprocessing']['config_canonical_sha256'],
            'config_hash_scope_explanation': 'Diagnostic hashes byte-bound full cloud config; prior fingerprint receipt hashes earlier base source config. All numeric preprocessing fields remain exact.',
            'bound_public_files': BOUND_PUBLIC_FILES,
            'member_inventory': {n: {'bytes': len(v), 'sha256': _sha(v)} for n, v in sorted(members.items())},
            'limitations': ['No archived code executed or EEG loaded.', 'Reported whole-array hashes and intermediate six-stage assertions are evidence checks, not recomputation.', 'This diagnostic audit does not authorize training or prove historical machine identity.']}


def audit_bundle(path, checkout):
    """Certify the one named immutable private bundle, then audit its evidence."""
    path = Path(path)
    _require(not path.is_symlink() and path.is_file(), 'regular_archive_required')
    _require(path.stat().st_size == EXPECTED_ARCHIVE_BYTES, 'immutable_archive_byte_length_changed')
    data = path.read_bytes()
    _require(len(data) == EXPECTED_ARCHIVE_BYTES and _sha(data) == EXPECTED_ARCHIVE_SHA256, 'immutable_archive_sha256_changed')
    members = _read_archive_bytes(data)
    _require(len(members) == EXPECTED_PHYSICAL_MEMBERS, 'immutable_archive_physical_member_count_changed')
    _member(members, 'new-host-source-report.json')
    _validate_launch_records(members, required=True)
    result = audit_members(members, checkout)
    result.update({'status': 'FULL_DIAGNOSTIC_PRIVATE_BUNDLE_AUDIT_PASSED_TRAINING_BLOCKED',
                   'archive_bytes': len(data), 'archive_sha256': _sha(data)})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--checkout', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit_bundle(args.archive, args.checkout)
    except (AuditError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        print(json.dumps({'status': 'FULL_DIAGNOSTIC_BUNDLE_AUDIT_BLOCKED', 'error_code': str(exc), 'training_authorization': False, 'new_fits': 0}))
        raise SystemExit(2)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
