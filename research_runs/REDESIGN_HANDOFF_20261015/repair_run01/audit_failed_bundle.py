#!/usr/bin/env python3
"""Read-only audit of one pinned failure evidence archive; executes no payload."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
from urllib.parse import unquote, urlsplit

ARCHIVE_BYTES = 423996
ARCHIVE_SHA256 = '7c83bcb991857dd99b7cda2b4bd8f9fe467d87217fb3a73c408b7b1474f4b3a0'
RESOLUTION_SHA256 = 'a0ed2680c8e057a60aec9cde0d736c9869f3ea9e747f5a6216d79766d07f9b5a'
CONTROLLER_SHA256 = '7a1fbc9b364c8dd42faf6894450ae065a49d59a977d4c5470a3c2daffff50cc3'
DONOR_SHA256 = '3a83a9cf93cca3e9813056645bc73f26a9429ee6f1f7bc06f2ae78a1c36471b1'
PLAN_SHA256 = 'e4852d1e2517abc69464c22e69658c2618d8e3950184fa40eb4c8a2af6ce5a0c'
REQUIREMENTS_SHA256 = '7322d4f85f25064ef8c29efa502c67417fc9b8a0d3297692263c1e618804769a'
REVISION = '1efe9d1ba2ab8671ad1bf76c360e067fb63fd7ac'
ENVIRONMENT = '/workspace/paper1-training-runtime-cp312-run01'


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate_json_key')
        result[key] = value
    return result


def read_json(value: bytes):
    return json.loads(value, object_pairs_hook=unique_object)


def normalized(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def inspect_archive(path: Path):
    require(path.is_file() and not path.is_symlink(), 'regular_archive_required')
    archive = path.read_bytes()
    require(len(archive) == ARCHIVE_BYTES and digest(archive) == ARCHIVE_SHA256,
            'archive_identity_mismatch')
    payloads = {}
    # Identity is fixed above; still reject malformed names/types and expansion.
    with tarfile.open(path, 'r:gz') as source:
        members = source.getmembers()
        require(len(members) == 27, 'member_count_mismatch')
        require(sum(member.size for member in members) <= 2 * 1024**2,
                'expanded_archive_cap')
        for member in members:
            p = PurePosixPath(member.name)
            require(member.isfile() and not member.issym() and not member.islnk(),
                    'nonregular_archive_member')
            require(not p.is_absolute() and '..' not in p.parts and
                    '\\' not in member.name and p.as_posix() == member.name,
                    'unsafe_archive_member')
            require(member.name not in payloads, 'duplicate_archive_member')
            stream = source.extractfile(member)
            require(stream is not None, 'missing_archive_stream')
            content = stream.read(member.size + 1)
            require(len(content) == member.size, 'member_size_mismatch')
            payloads[member.name] = content
    manifest = read_json(payloads['MANIFEST.json'])
    require(manifest['schema'] == 'paper1-failed-preparation-evidence-v1',
            'manifest_schema_mismatch')
    rows = manifest['payloads']
    require(len(rows) == 26 and len({x['path'] for x in rows}) == 26,
            'manifest_payload_count_or_duplicates')
    require({x['path'] for x in rows} == set(payloads) - {'MANIFEST.json'},
            'manifest_members_mismatch')
    for row in rows:
        content = payloads[row['path']]
        require(len(content) == row['bytes'] and digest(content) == row['sha256'],
                'payload_identity_mismatch:' + row['path'])
    return payloads, rows, manifest


def audit(path: Path):
    payloads, payload_rows, manifest = inspect_archive(path)
    obj = lambda name: read_json(payloads[name])
    require(len(payloads['source/prepare_runtime_only.py']) == 22347 and
            digest(payloads['source/prepare_runtime_only.py']) == CONTROLLER_SHA256,
            'controller_identity_mismatch')
    require(digest(payloads['inputs/gpu_donor_inventory.json']) == DONOR_SHA256,
            'donor_identity_mismatch')
    require(digest(payloads['inputs/accepted-plan.stdout.json']) == PLAN_SHA256,
            'accepted_plan_identity_mismatch')
    resolution_bytes = payloads['partial-environment/wheel-resolution.json']
    require(len(resolution_bytes) == 1399863 and
            digest(resolution_bytes) == RESOLUTION_SHA256,
            'resolution_identity_mismatch')
    resolution = read_json(resolution_bytes)
    diagnostic = obj('dispatch/failure-wheel-layout-diagnostic.json')
    install = resolution['install']
    wheels = diagnostic['wheels']
    require(len(install) == len(wheels) == diagnostic['wheel_count'] == 79,
            'closure_count_mismatch')
    require(diagnostic['all_downloaded_wheel_hashes_match_resolution'] is True,
            'recorded_wheel_hash_check_failed')
    require(len({x['file'] for x in wheels}) == 79 and
            len({normalized(x['name']) for x in wheels}) == 79,
            'duplicate_closure_identity')
    by_name = {normalized(row['metadata']['name']): row for row in install}
    require(len(by_name) == 79, 'duplicate_resolver_distribution')
    for wheel in wheels:
        item = by_name[normalized(wheel['name'])]
        info = item['download_info']
        url = urlsplit(info['url'])
        require(url.scheme == 'https' and url.hostname == 'files.pythonhosted.org'
                and url.port is None and url.username is None and
                url.password is None and not url.query and not url.fragment,
                'unapproved_recorded_wheel_url')
        require(PurePosixPath(unquote(url.path)).name == wheel['file'] and
                wheel['file'].endswith('.whl') and
                wheel['official_url'] == info['url'], 'wheel_url_identity_mismatch')
        require(wheel['version'] == item['metadata']['version'] and
                info['archive_info']['hashes']['sha256'] == wheel['sha256'] and
                info['archive_info'].get('hash') == 'sha256=' + wheel['sha256'] and
                re.fullmatch('[0-9a-f]{64}', wheel['sha256']) and
                type(wheel['bytes']) is int and wheel['bytes'] > 0 and
                wheel['hash_matches_resolution'] is True,
                'wheel_recorded_identity_mismatch')
        require(not normalized(wheel['name']).startswith('nvidia-') and
                normalized(wheel['name']) not in ('torch', 'torchaudio', 'triton'),
                'gpu_distribution_present_in_closure')
    requirement_lines = payloads['partial-environment/resolved-lightweight-wheels.txt'].decode().splitlines()
    expected_requirements = [f'{row["metadata"]["name"]}=={row["metadata"]["version"]} --hash=sha256:{row["download_info"]["archive_info"]["hashes"]["sha256"]}' for row in install]
    require(requirement_lines == expected_requirements,
            'hashed_requirements_differ_from_resolution')
    pinned = {'numpy': '2.3.5', 'scipy': '1.17.0', 'pandas': '2.2.3',
              'scikit-learn': '1.8.0', 'mne': '1.13.2',
              'braindecode': '1.5.1', 'skorch': '1.4.0',
              'h5py': '3.16.0', 'threadpoolctl': '3.6.0',
              'einops': '0.8.2', 'joblib': '1.5.3',
              'boto3': '1.40.61', 'pytest': '9.1.1'}
    for name, version in pinned.items():
        require(by_name[name]['metadata']['version'] == version,
                'frozen_scientific_version_changed:' + name)
    guard_members = obj('dispatch/guard-member-hashes.json')
    require(len(guard_members) == 5, 'unexpected_guard_member_count')
    expected_guard = {
        'fonttools-4.67.0.data/data/share/': (0, True, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
        'fonttools-4.67.0.data/data/share/man/': (0, True, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
        'fonttools-4.67.0.data/data/share/man/man1/': (0, True, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
        'fonttools-4.67.0.data/data/share/man/man1/ttx.1': (5377, False, '70b6e6fe938e8f50bbe93d905ef0f1cf00e3f6093e193779473b6f4ccb28b85c'),
        'sympy-1.14.0.data/data/share/man/man1/isympy.1': (6659, False, 'f4365d48e2102e292b0131e56e4743674e0b0508a0643504d3fa025c10ef741b'),
    }
    wheel_by_file = {w['file']: w for w in wheels}
    require({row['member'] for row in guard_members} == set(expected_guard),
            'guard_member_set_mismatch')
    for row in guard_members:
        require((row['bytes'], row['is_directory'], row['sha256']) ==
                expected_guard[row['member']], 'guard_member_identity_mismatch')
        require(wheel_by_file[row['wheel']]['sha256'] == row['wheel_sha256'],
                'guard_wheel_identity_mismatch')
    completion = obj('dispatch/completion.json')
    receipt = obj('controller/paper1-runtime-prepare-run01.stdout.json.dispatch.json')
    review = obj('dispatch/parent-review.json')
    slot = obj('dispatch/runtime-preparation-slot.json')
    postflight = obj('dispatch/postflight.json')
    actual_plan = obj('partial-environment/runtime_plan.json')
    accepted_plan = obj('inputs/accepted-plan.stdout.json')
    require(actual_plan['execution_files']['research_runs/REDESIGN_CLOUD_20261013/requirements.txt']
            == REQUIREMENTS_SHA256, 'committed_requirements_identity_mismatch')
    require({key for key in actual_plan.keys() | accepted_plan.keys()
             if actual_plan.get(key) != accepted_plan.get(key)} ==
            {'donor_metadata', 'observed_free_bytes', 'paper2_priority_receipt_sha256'},
            'preparation_plan_differed_from_accepted_science')
    require({key for key in actual_plan['donor_metadata'].keys() |
             accepted_plan['donor_metadata'].keys()
             if actual_plan['donor_metadata'].get(key) !=
             accepted_plan['donor_metadata'].get(key)} == {'free_bytes'},
            'preparation_donor_metadata_changed')
    require(completion['started_utc'] == '2026-10-15T03:54:00.757256+00:00' and
            completion['ended_utc'] == '2026-10-15T03:54:43.978652+00:00' and
            completion['exit_code'] == 3 and receipt['child_exit_code'] == 1,
            'actual_failure_identity_mismatch')
    require(receipt['fixed_helper_revision'] == REVISION and
            receipt['controller_sha256'] == CONTROLLER_SHA256 and
            receipt['accepted_plan_sha256'] == PLAN_SHA256 and
            receipt['donor_report_sha256'] == DONOR_SHA256,
            'dispatch_identity_mismatch')
    require(receipt['parent_review_sha256'] == digest(payloads['dispatch/parent-review.json']) and
            receipt['slot_sha256'] == digest(payloads['dispatch/runtime-preparation-slot.json']),
            'dispatch_parent_or_slot_binding_mismatch')
    require(review['status'] == 'DOT_PARENT_RUNTIME_PREPARATION_REVIEW_APPROVED'
            and review['issuer'] == 'dot_parent' and review['environment'] == ENVIRONMENT
            and review['training_authorization'] is False, 'parent_review_mismatch')
    require(slot['status'] == 'DOT_OPERATION_SLOT_GRANTED' and slot['issuer'] == 'dot'
            and slot['operation'] == 'runtime_preparation'
            and slot['pod_id'] == '52ivinpjwv947i'
            and slot['container_id'] == 'a7d3f0e408a4'
            and slot['max_new_bytes'] == 3 * 1024**3
            and slot['min_free_bytes'] == 10 * 1024**3
            and slot['paper2_reserve_bytes'] == 5 * 1024**3
            and slot['training_authorization'] is False, 'historical_slot_mismatch')
    moment = lambda text: datetime.fromisoformat(text.replace('Z', '+00:00'))
    start = moment(completion['started_utc'])
    end = moment(completion['ended_utc'])
    require(moment(review['reviewed_at_utc']) <= moment(slot['issued_at_utc']) <= start <= end
            <= moment(slot['expires_at_utc']) <= moment(review['expires_at_utc'])
            and moment(slot['not_before_utc']) <= start,
            'historical_review_or_slot_time_invalid')
    cfg = payloads['partial-environment/pyvenv.cfg'].decode().splitlines()
    require('include-system-site-packages = false' in cfg and
            'version = 3.12.3' in cfg and 'executable = /usr/bin/python3.12' in cfg,
            'partial_python_or_site_isolation_mismatch')
    require(postflight['environment_du'] == '165703680\t' + ENVIRONMENT + '\n'
            and postflight['runtime_preparation_receipt_exists'] is False
            and postflight['retained_partial'] is True
            and postflight['retry_performed'] is False
            and receipt['observed_peak_owned_allocated_bytes'] == 168755200,
            'recorded_partial_state_mismatch')
    failure_log = payloads['controller/paper1-runtime-prepare-run01.stderr.log'].decode()
    require('line 205, in wheel_budget' in failure_log and
            'wheel_data_or_headers_destination_requires_separate_review' in failure_log,
            'failure_not_expected_guard')
    install_log = payloads['controller/paper1-runtime-prepare-run01.install.log'].decode()
    require('Would install ' in install_log and 'Successfully installed ' not in install_log,
            'scientific_wheel_installation_observed')
    require(receipt['new_fits'] == 0 and receipt['target_EEG_read'] is False and
            receipt['runtime_import_acceptance_passed'] is False and
            receipt['source_acceptance_passed'] is False and
            receipt['old_cost_known'] is False and
            receipt['budget_reset'] is False and receipt['budget_expanded'] is False and
            receipt['training_authorization'] is False,
            'scope_or_authorization_changed')
    audit_result = {
        'schema_version': 1,
        'status': 'FAILED_PREPARATION_EVIDENCE_INDEPENDENTLY_VERIFIED_REPAIR_STILL_REQUIRED',
        'archive': {'bytes': ARCHIVE_BYTES, 'sha256': ARCHIVE_SHA256,
                    'manifest_sha256': digest(payloads['MANIFEST.json']),
                    'regular_payload_count': 26,
                    'all_payload_bytes_and_hashes_verified': True},
        'source_controller': {'bytes': 22347, 'sha256': CONTROLLER_SHA256,
                              'fixed_commit': 'b07892c320e25e3465c50ea3a31d1a21bf722df3'},
        'recorded_execution': {'started_utc': completion['started_utc'],
                               'ended_utc': completion['ended_utc'],
                               'outer_exit': 3, 'inner_exit': 1,
                               'helper_revision': REVISION,
                               'failure_guard_line': 205,
                               'automatic_retry': False,
                               'new_fits': 0},
        'closure': {'resolution_bytes': 1399863,
                    'resolution_sha256': RESOLUTION_SHA256,
                    'unique_distributions': 79,
                    'compressed_bytes_as_recorded': sum(row['bytes'] for row in wheels),
                    'all_recorded_urls_https_files_pythonhosted_org': True,
                    'all_recorded_names_versions_hashes_match_resolution': True,
                    'hashed_requirements_match_resolution': True,
                    'no_torch_torchaudio_triton_or_nvidia_wheels': True,
                    'frozen_scientific_versions_match': pinned,
                    'committed_direct_requirements_count': 13,
                    'committed_requirements_revision': REVISION,
                    'committed_requirements_sha256': REQUIREMENTS_SHA256,
                    'precise_guard_member_count': 5},
        'partial_state_as_recorded': {'environment': ENVIRONMENT,
                                      'allocated_bytes': 165703680,
                                      'peak_owned_allocated_bytes': 168755200,
                                      'runtime_preparation_receipt_exists': False,
                                      'postflight_free_bytes': postflight['free_bytes'],
                                      'python': '3.12.3',
                                      'include_system_site_packages': False,
                                      'scientific_wheels_not_installed_by_failed_helper': True},
        'limitations': [
            'These are authenticated archived observations, not a current Pod preflight.',
            'No wheel binaries are in the archive: member and wheel hashes are archived observations; retained wheel bytes require fresh local verification by dot before repair.',
            'No complete installed-distribution inventory is in this archive: exact allowed uninstalled partial state must be independently checked before repair.',
            'No wheel or archived script was executed, downloaded, installed, or imported during this audit.',
            'Preparation does not authorize GPU imports, source acceptance, target EEG reads, or fitting.',
            'Old total cost and cumulative GPU hours remain unknown; no budget or deadline is reset.',
        ],
        'runtime_import_acceptance_passed': False,
        'source_acceptance_passed': False,
        'training_authorization': False,
    }
    index = {
        'schema_version': 1,
        'status': 'FROZEN_RECORDED_WHEEL_CACHE_IDENTITIES_FRESH_LOCAL_VERIFICATION_REQUIRED',
        'archive_sha256': ARCHIVE_SHA256,
        'archive_bytes': ARCHIVE_BYTES,
        'resolution_sha256': RESOLUTION_SHA256,
        'resolution_bytes': 1399863,
        'environment': ENVIRONMENT,
        'helper_revision': REVISION,
        'controller_sha256': CONTROLLER_SHA256,
        'wheel_count': 79,
        'wheels': [{key: wheel[key] for key in
                    ('file', 'bytes', 'sha256', 'name', 'version', 'official_url')}
                   for wheel in sorted(wheels, key=lambda row: row['file'])],
        'guard_members': guard_members,
        'evidence_payloads': sorted(payload_rows, key=lambda row: row['path']),
        'all_wheel_bytes_independently_available_in_archive': False,
        'training_authorization': False,
    }
    return audit_result, index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    result, _ = audit(args.archive)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
