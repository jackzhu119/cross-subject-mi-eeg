"""Compare a complete future helper inventory with the author's readable fields.

No live observation, imports of numerical/GPU packages, package changes or EEG
reads. Matching metadata is NOT native payload equality or a training gate.
The separately claimed2390-byte original JSON is not reconstructed here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HELPER = ROOT / 'research_runs/REDESIGN_HANDOFF_20261014/runtime_transition/donor_gpu_inventory.py'
TRANSCRIPT = HERE / 'donor_metadata_transcript.json'


def read(path, cap=2 * 1024**2):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file() or path.stat().st_size > cap:
        raise ValueError('bounded_regular_metadata_file_required')
    raw = path.read_bytes()
    def unique(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError('duplicate_metadata_key')
            result[name] = value
        return result
    value = json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_metadata')))
    if not isinstance(value, dict):
        raise ValueError('metadata_object_required')
    return value, hashlib.sha256(raw).hexdigest()


def compare(inventory, transcript, helper_sha):
    if (inventory.get('status') != 'GPU_DONOR_METADATA_EXACT_NOT_IMPORT_VERIFIED'
            or inventory.get('inventory_implementation_sha256') != helper_sha):
        raise ValueError('complete_fixed_helper_inventory_required')
    for key in ('python_version', 'donor_python', 'SOABI'):
        if inventory.get(key) != transcript[key]:
            raise ValueError('donor_transcript_identity_mismatch:' + key)
    if inventory.get('platform') != {'system': 'Linux', 'machine': 'x86_64'}:
        raise ValueError('donor_platform_not_verified')
    distributions = inventory.get('distributions', {})
    if set(distributions) != set(transcript['distributions']):
        raise ValueError('donor_GPU_distribution_set_mismatch')
    for name, version in transcript['distributions'].items():
        row = distributions[name]
        if row.get('version') != version or row.get('site_packages') != transcript['metadata_site']:
            raise ValueError('donor_version_or_metadata_location_mismatch:' + name)
        if not all(isinstance(row.get(k), str) and re.fullmatch('[0-9a-f]{64}', row[k])
                   for k in ('metadata_sha256', 'record_sha256')):
            raise ValueError('donor_distribution_byte_identities_required:' + name)
        if Path(row.get('metadata_dir', '')).parent != Path(transcript['metadata_site']):
            raise ValueError('donor_metadata_directory_mismatch:' + name)
    if inventory.get('site_packages') != [transcript['metadata_site']]:
        raise ValueError('donor_sites_not_identical_to_transcript')
    if (not all(inventory.get(k) for k in ('prefix', 'base_prefix', 'base_executable', 'cache_tag', 'components', 'critical_module_files'))
            or type(inventory.get('free_bytes')) is not int or inventory['free_bytes'] < 0):
        raise ValueError('full_inventory_fields_missing_do_not_infer_from_transcript')
    for name in ('torch', 'torchaudio', 'triton'):
        path = str(Path(transcript['metadata_site']) / name / '__init__.py')
        row = inventory['critical_module_files'].get(path, {})
        if not re.fullmatch('[0-9a-f]{64}', str(row.get('sha256', ''))):
            raise ValueError('critical_module_identity_missing:' + name)
    for key in ('torch_imported_by_inventory', 'CUDA_operation_performed',
                'training_authorization', 'target_EEG_read', 'training_consumer_imports_verified'):
        if inventory.get(key) is not False:
            raise ValueError('metadata_only_scope_changed:' + key)
    if type(inventory.get('new_fits')) is not int or inventory['new_fits'] != 0:
        raise ValueError('metadata_only_fit_scope_changed')
    return {'status': 'COMPLETE_HELPER_METADATA_MATCHES_TRANSCRIBED_FIELDS_RUNTIME_STILL_PENDING',
        'GPU_distributions_compared': len(distributions),
        'helper_implementation_sha256': helper_sha,
        'original2390byte_JSON_verified_here': False,
        'original2390byte_JSON_reconstructed': False,
        'GPU_payload_bytes_exhaustively_verified': False,
        'actual_training_consumer_imports_verified': False,
        'source_hash_acceptance_verified': False,
        'paper2_environment_used_or_modified': False, 'training_authorization': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inventory', type=Path, required=True)
    args = p.parse_args()
    report, inventory_sha = read(args.inventory)
    transcript, transcript_sha = read(TRANSCRIPT)
    result = compare(report, transcript, hashlib.sha256(HELPER.read_bytes()).hexdigest())
    result.update(inventory_file_sha256=inventory_sha, transcript_file_sha256=transcript_sha)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
