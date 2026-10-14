"""Future raw-source restoration only; default is metadata plan, not execution.

This separates source byte restoration from old diagnostic/reconstruction code.
--restore uses ONLY existing environment bindings and named frozen R2 keys.
No target EEG, numerical source transform, model, credentials prompt/cache,
scientific job initialization, budget record or provider control is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import transition_target_gate as gate

ROOT = Path(__file__).resolve().parents[3]
MAPPING_SHA = '7d5ec2e9ddec16d2be5cb3778037c96dabb6559b8c208ad4cca9923c67407663'


def inspect_mapping(repo, path):
    expected, _ = gate.identity(repo)
    expected = [row for row in expected if row['path'].startswith('bnci/')]
    mapping, _ = gate.read_json(path, MAPPING_SHA)
    checked = gate.mapping_review(mapping, expected)
    if len(expected) != 18 or checked['covered_files'] != 18 or checked['missing_source_files']:
        raise ValueError('exact_complete_source_only_mapping_required')
    return expected, mapping


def run(args):
    actual = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != args.code_revision:
        raise ValueError('restore_code_revision_mismatch')
    identities = {}
    helper = ROOT / 'research_runs/REDESIGN_CLOUD_20261013/scripts/r2_only.py'
    mapping_path = ROOT / 'research_runs/REDESIGN_HANDOFF_20261014/source_r2_mapping.json'
    for path in (Path(__file__), Path(gate.__file__), helper, mapping_path):
        rel = str(path.relative_to(ROOT))
        committed = subprocess.check_output(['git', '-C', str(ROOT), 'show', actual + ':' + rel])
        if path.is_symlink() or path.read_bytes() != committed:
            raise ValueError('restore_execution_file_changed')
        identities[rel] = hashlib.sha256(committed).hexdigest()
    expected, mapping = inspect_mapping(ROOT, mapping_path)
    plan = {'status': 'SOURCE_RAW_RESTORE_PLAN_ONLY', 'code_revision': actual,
        'execution_files': identities, 'source_files': 18, 'source_bytes': 779873919,
        'mapping_sha256': MAPPING_SHA, 'data_dir': str(args.data_dir),
        'source_transform_or_acceptance_run': False, 'new_fits': 0,
        'target_EEG_read': False, 'training_authorization': False,
        'credential_prompt_or_cache': False, 'existing_binding_accessed': False,
        'original_budget_changed': False}
    if not args.restore:
        print(json.dumps(plan, indent=2)); return
    if args.output is None or args.output.exists() or args.output.is_symlink():
        raise ValueError('new_restore_receipt_required')
    data = args.data_dir.resolve()
    out = args.output.resolve()
    if data.is_relative_to(ROOT) or out.is_relative_to(ROOT) or out.is_relative_to(data):
        raise ValueError('raw_cache_and_receipt_must_be_outside_checkout_and_separate')
    gate.reject_symlinks(args.data_dir)
    gate.reject_symlinks(args.output)
    sys.path.insert(0, str(helper.parent))
    import r2_only
    # Coverage fails before touching bindings or R2. The existing helper checks
    # every present file and downloads missing bytes only, with size/fullSHA.
    r2_only.validate_mapping(mapping, expected)
    client, bucket = r2_only.environment_client()
    imported = r2_only.import_files(args.data_dir, mapping, expected, client, bucket)
    plan.update(status='SOURCE_RAW_BYTES_RESTORED_VERIFIED_NO_NUMERICAL_ACCEPTANCE',
        existing_binding_accessed=True, import_receipt=imported)
    with args.output.open('x') as f:
        json.dump(plan, f, indent=2); f.write('\n')
    print(json.dumps({'status': plan['status'], 'receipt': str(args.output),
                     'training_authorization': False, 'new_fits': 0}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--code-revision', required=True)
    p.add_argument('--data-dir', type=Path, required=True)
    p.add_argument('--output', type=Path)
    p.add_argument('--restore', action='store_true')
    run(p.parse_args())


if __name__ == '__main__':
    main()
