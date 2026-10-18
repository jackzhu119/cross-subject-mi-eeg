#!/usr/bin/env python3
"""Build from a clean public frozen bundle into a NEW directory; never patch in place.

Use only a clean public Git checkout, not a server directory containing credentials.
This tool reads only the pinned public manifest paths, checks every hash before
writing, and refuses an existing destination. It never dispatches a process.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

SOURCE_MANIFEST_SHA = 'c73dde8be3e521e2c8b07dbf1ee508db1192510cabce8c9a9ead5be75af98564'
SOURCE_DATA_SHA = 'd4d166e6cc9d5f674f65a3227dfa02b158b9ce8b5bcdb17b8b5d7a9d4f459ba1'
SOURCE_RUNNER_SHA = '57d3501e43f8c43b6cd611b710b4a22f5c17f200a15f0819d2c15ae9f9adbe12'
OLD = '            require(reader.header["start_date_time"] == event_audit["start_date_time"], "Yang signal/event recording clocks differ")'
NEW = '''            from yang_clock_policy import validate_yang_clock
            event_audit["clock_policy"] = validate_yang_clock(
                person, si, reader.header["start_date_time"], event_audit["start_date_time"],
                verified.used[path.relative_to(verified.root).as_posix()],
                verified.used[events_path.relative_to(verified.root).as_posix()],
                reader.header["fixed_header_sha256"], event_audit["header_sha256"])'''


def build(source, destination):
    if destination.exists() or destination.is_symlink():
        raise ValueError('destination must be new; original code is never replaced')
    manifest_raw = (source / 'BUNDLE_MANIFEST.json').read_bytes()
    if hashlib.sha256(manifest_raw).hexdigest() != SOURCE_MANIFEST_SHA:
        raise ValueError('unsupported public manifest; no source files read')
    manifest = json.loads(manifest_raw)
    content = {}
    for row in manifest['files']:
        relative = Path(row['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('invalid public manifest path')
        path = source / relative
        if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):
            raise ValueError('public bundle symlink')
        raw = path.read_bytes()
        if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('public bundle hash mismatch: ' + row['path'])
        content[row['path']] = raw
    for name, digest in [('p1_data.py', SOURCE_DATA_SHA), ('p1_runner.py', SOURCE_RUNNER_SHA)]:
        if hashlib.sha256(content[name]).hexdigest() != digest:
            raise ValueError('unsupported scientific bundle')
    data = content['p1_data.py'].decode()
    if data.count(OLD) != 1:
        raise ValueError('scientific patch context mismatch')
    content['p1_data.py'] = data.replace(OLD, NEW).encode()
    # Different run AND processed-cache paths preserve failed run identities and old inputs.
    runner = content['p1_runner.py'].decode()
    old = 'args.root.resolve()/"data/processed18"'
    if runner.count(old) != 1:
        raise ValueError('cache isolation context mismatch')
    runner = runner.replace(old, 'args.root.resolve()/"data/processed18_clockfix_v2_20261018"')
    runner = runner.replace('default="expansion18_v1"', 'default="expansion18_clockfix_v2_20261018"')
    content['p1_runner.py'] = runner.encode()
    from yang_clock_policy import registry
    registry()  # Require the complete production registry before publishing any code.
    for name in ('yang_clock_policy.py', 'yang_clock_registry.py'):
        content[name] = Path(__file__).with_name(name).read_bytes()
    content['config/yang_clock_registry_v5.json'] = Path(__file__).with_name('yang_clock_registry_v5.json').read_bytes()
    new_manifest = {**manifest, 'recovery_parent_manifest_sha256':
                    hashlib.sha256((source / 'BUNDLE_MANIFEST.json').read_bytes()).hexdigest(),
                    'files': [{'path': k, 'bytes': len(v), 'sha256': hashlib.sha256(v).hexdigest()}
                              for k, v in sorted(content.items())]}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='p1-reviewed-copy-', dir=destination.parent) as temporary:
        staging = Path(temporary) / 'code'
        staging.mkdir()
        for name, raw in content.items():
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        (staging / 'BUNDLE_MANIFEST.json').write_text(json.dumps(new_manifest, indent=2) + '\n')
        # Preserve the prior manifest separately as immutable provenance.
        (staging / 'RECOVERY_PARENT_MANIFEST.json').write_bytes((source / 'BUNDLE_MANIFEST.json').read_bytes())
        staging.rename(destination)
    return new_manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('clean_public_bundle', type=Path)
    parser.add_argument('new_code_directory', type=Path)
    args = parser.parse_args()
    build(args.clean_public_bundle, args.new_code_directory)
    print('Built isolated reviewed copy; no training started.')
