"""Synthetic metadata comparison tests; no native package import or Pod access."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('paper1_compare_donor_transcript_tested',
    HERE / 'compare_donor_transcript.py')
compare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compare)


@pytest.fixture
def complete_fields():
    transcript, _ = compare.read(compare.TRANSCRIPT)
    root = Path(transcript['metadata_site'])
    helper_sha = hashlib.sha256(compare.HELPER.read_bytes()).hexdigest()
    distributions = {name: {
        'name': name, 'version': version, 'site_packages': str(root),
        'metadata_dir': str(root / f'{name.replace("-", "_")}-{version}.dist-info'),
        'metadata_sha256': 'a' * 64, 'record_sha256': 'b' * 64,
    } for name, version in transcript['distributions'].items()}
    inventory = {
        'status': 'GPU_DONOR_METADATA_EXACT_NOT_IMPORT_VERIFIED',
        'inventory_implementation_sha256': helper_sha,
        'python_version': transcript['python_version'], 'donor_python': transcript['donor_python'],
        'SOABI': transcript['SOABI'], 'platform': {'system': 'Linux', 'machine': 'x86_64'},
        'distributions': distributions, 'site_packages': [str(root)],
        'prefix': '/usr', 'base_prefix': '/usr', 'base_executable': '/usr/bin/python3',
        'cache_tag': 'cpython-312', 'free_bytes': 20 * 1024**3,
        'components': [{'name': 'torch', 'path': str(root / 'torch')}],
        'critical_module_files': {str(root / name / '__init__.py'): {
            'bytes': 19, 'sha256': 'c' * 64} for name in ('torch', 'torchaudio', 'triton')},
        'torch_imported_by_inventory': False, 'CUDA_operation_performed': False,
        'training_authorization': False, 'target_EEG_read': False,
        'training_consumer_imports_verified': False, 'new_fits': 0,
    }
    return inventory, transcript, helper_sha


def test_all_17_transcribed_versions_and_locations_match_without_inventing_original_json(complete_fields):
    inventory, transcript, helper_sha = complete_fields
    result = compare.compare(inventory, transcript, helper_sha)
    assert result['GPU_distributions_compared'] == 17
    assert result['helper_implementation_sha256'] == helper_sha
    for key in ('original2390byte_JSON_verified_here', 'original2390byte_JSON_reconstructed',
        'GPU_payload_bytes_exhaustively_verified', 'actual_training_consumer_imports_verified',
        'source_hash_acceptance_verified', 'paper2_environment_used_or_modified', 'training_authorization'):
        assert result[key] is False
    assert transcript['original_json_claim']['bytes'] == 2390
    assert transcript['original_json_claim']['original_bytes_independently_verified_here'] is False


@pytest.mark.parametrize('name', [
    'torch', 'torchaudio', 'triton', 'nvidia-cublas-cu12', 'nvidia-cuda-cupti-cu12',
    'nvidia-cuda-nvrtc-cu12', 'nvidia-cuda-runtime-cu12', 'nvidia-cudnn-cu12',
    'nvidia-cufft-cu12', 'nvidia-cufile-cu12', 'nvidia-curand-cu12',
    'nvidia-cusolver-cu12', 'nvidia-cusparse-cu12', 'nvidia-cusparselt-cu12',
    'nvidia-nccl-cu12', 'nvidia-nvjitlink-cu12', 'nvidia-nvtx-cu12'])
def test_every_transcribed_gpu_version_is_checked(complete_fields, name):
    inventory, transcript, helper_sha = complete_fields
    inventory['distributions'][name]['version'] = '0.invalid'
    with pytest.raises(ValueError, match='donor_version_or_metadata_location_mismatch:' + name):
        compare.compare(inventory, transcript, helper_sha)


@pytest.mark.parametrize('name', ['torch', 'torchaudio', 'triton', 'nvidia-nccl-cu12'])
def test_gpu_metadata_location_cannot_point_to_paper2_or_alternate_site(complete_fields, name):
    inventory, transcript, helper_sha = complete_fields
    inventory['distributions'][name]['site_packages'] = '/workspace/.venvs/paper2-gpu/lib/python3.11/site-packages'
    with pytest.raises(ValueError, match='metadata_location_mismatch:' + name):
        compare.compare(inventory, transcript, helper_sha)


@pytest.mark.parametrize('key,value', [
    ('python_version', '3.11.16'), ('donor_python', '/workspace/.venvs/paper2-gpu/bin/python'),
    ('SOABI', 'cpython-311-x86_64-linux-gnu'),
    ('status', 'CANDIDATE_ONLY'), ('inventory_implementation_sha256', 'f' * 64)])
def test_wrong_interpreter_abi_or_fixed_helper_binding_is_rejected(complete_fields, key, value):
    inventory, transcript, helper_sha = complete_fields
    inventory[key] = value
    with pytest.raises(ValueError, match='fixed_helper_inventory|transcript_identity_mismatch'):
        compare.compare(inventory, transcript, helper_sha)


@pytest.mark.parametrize('change', ['missing', 'additional'])
def test_exact_gpu_distribution_set_required(complete_fields, change):
    inventory, transcript, helper_sha = complete_fields
    if change == 'missing':
        del inventory['distributions']['triton']
    else:
        inventory['distributions']['nvidia-foreign-cu13'] = deepcopy(inventory['distributions']['torch'])
    with pytest.raises(ValueError, match='distribution_set_mismatch'):
        compare.compare(inventory, transcript, helper_sha)


@pytest.mark.parametrize('field', ['metadata_sha256', 'record_sha256'])
@pytest.mark.parametrize('value', [None, '', 'not-sha', 'A' * 64])
def test_metadata_and_record_need_typed_lowercase_sha256(complete_fields, field, value):
    inventory, transcript, helper_sha = complete_fields
    inventory['distributions']['torch'][field] = value
    with pytest.raises(ValueError, match='distribution_byte_identities_required:torch'):
        compare.compare(inventory, transcript, helper_sha)


def test_metadata_directory_cannot_leave_transcribed_site(complete_fields):
    inventory, transcript, helper_sha = complete_fields
    inventory['distributions']['triton']['metadata_dir'] = '/other/triton-3.4.0.dist-info'
    with pytest.raises(ValueError, match='metadata_directory_mismatch:triton'):
        compare.compare(inventory, transcript, helper_sha)


@pytest.mark.parametrize('field', ['prefix', 'base_prefix', 'base_executable', 'cache_tag', 'components', 'critical_module_files'])
def test_readable_transcript_cannot_supply_missing_helper_inventory_fields(complete_fields, field):
    inventory, transcript, helper_sha = complete_fields
    del inventory[field]
    with pytest.raises(ValueError, match='full_inventory_fields_missing'):
        compare.compare(inventory, transcript, helper_sha)


@pytest.mark.parametrize('value', [None, True, -1, '1000'])
def test_measured_free_bytes_must_be_nonnegative_integer(complete_fields, value):
    inventory, transcript, helper_sha = complete_fields
    inventory['free_bytes'] = value
    with pytest.raises(ValueError, match='full_inventory_fields_missing'):
        compare.compare(inventory, transcript, helper_sha)


@pytest.mark.parametrize('name', ['torch', 'torchaudio', 'triton'])
def test_each_critical_entry_module_needs_hash(complete_fields, name):
    inventory, transcript, helper_sha = complete_fields
    del inventory['critical_module_files'][str(Path(transcript['metadata_site']) / name / '__init__.py')]
    with pytest.raises(ValueError, match='critical_module_identity_missing:' + name):
        compare.compare(inventory, transcript, helper_sha)


@pytest.mark.parametrize('field', ['torch_imported_by_inventory', 'CUDA_operation_performed',
    'training_authorization', 'target_EEG_read', 'training_consumer_imports_verified'])
@pytest.mark.parametrize('value', [True, 0, None])
def test_matching_metadata_never_upgrades_scope_to_runtime_or_training(complete_fields, field, value):
    inventory, transcript, helper_sha = complete_fields
    inventory[field] = value
    with pytest.raises(ValueError, match='metadata_only_scope_changed'):
        compare.compare(inventory, transcript, helper_sha)


@pytest.mark.parametrize('value', [True, 1, None, '0'])
def test_metadata_inventory_cannot_claim_a_fit(complete_fields, value):
    inventory, transcript, helper_sha = complete_fields
    inventory['new_fits'] = value
    with pytest.raises(ValueError, match='metadata_only_fit_scope_changed'):
        compare.compare(inventory, transcript, helper_sha)


@pytest.mark.parametrize('raw,reason', [
    ('{"a":1,"a":2}', 'duplicate_metadata_key'),
    ('{"a":NaN}', 'nonfinite_metadata'), ('[]', 'metadata_object_required')])
def test_metadata_reader_rejects_ambiguous_or_unbounded_values(tmp_path, raw, reason):
    path = tmp_path / 'inventory.json'; path.write_text(raw)
    with pytest.raises(ValueError, match=reason):
        compare.read(path)


def test_metadata_reader_hashes_actual_bytes_without_reserializing(tmp_path):
    raw = b'{ "field" : 1 }\n'
    path = tmp_path / 'inventory.json'; path.write_bytes(raw)
    value, digest = compare.read(path)
    assert value == {'field': 1}
    assert digest == hashlib.sha256(raw).hexdigest()
    assert digest != hashlib.sha256(json.dumps(value).encode()).hexdigest()


def test_comparison_paths_resolve_current_repository_and_real_helper():
    assert compare.ROOT == HERE.parents[2]
    assert compare.HELPER == compare.ROOT / 'research_runs/REDESIGN_HANDOFF_20261014/runtime_transition/donor_gpu_inventory.py'
    assert compare.HELPER.is_file()
