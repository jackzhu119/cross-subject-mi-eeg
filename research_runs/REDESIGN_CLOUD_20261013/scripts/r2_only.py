"""Strict R2 import: expected identities come from frozen local manifests only."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
from urllib.parse import urlsplit
import uuid

CHUNK = 1024 * 1024
RESERVE = 5 * 1024**3


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value or any(ord(c) < 32 for c in value):
        raise ValueError('unsafe_relative_path')
    p = PurePosixPath(value)
    if p.is_absolute() or any(c in ('', '.', '..') for c in value.split('/')):
        raise ValueError('unsafe_relative_path')
    return value


def regular_path(root, name):
    name = relative(name)
    root = Path(root).absolute()
    p = root / name
    for parent in (root, *root.parents, p, *p.parents):
        if parent.is_symlink():
            raise ValueError('symlink_rejected')
    return p


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(CHUNK), b''):
            h.update(block)
    return h.hexdigest()


def environment_client():
    """Use already injected bindings only; no credential cache, prompt or discovery."""
    names = ('R2_ENDPOINT', 'R2_BUCKET', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY')
    if any(not os.environ.get(k) for k in names):
        raise ValueError('r2_existing_bindings_required')
    u = urlsplit(os.environ['R2_ENDPOINT'])
    if (u.scheme != 'https' or not u.hostname or not u.hostname.endswith('.r2.cloudflarestorage.com')
            or u.username or u.password or u.query or u.fragment or u.path not in ('', '/') or u.port not in (None, 443)):
        raise ValueError('r2_endpoint_invalid')
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', os.environ['R2_BUCKET']):
        raise ValueError('r2_bucket_invalid')
    import boto3
    from botocore.config import Config
    return boto3.client('s3', endpoint_url=os.environ['R2_ENDPOINT'],
        aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'], aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],
        region_name='auto', config=Config(connect_timeout=10, read_timeout=60,
            retries={'max_attempts': 0}, s3={'addressing_style': 'path'})), os.environ['R2_BUCKET']


def frozen_entries(root):
    root = Path(root)
    source = json.loads((root / 'research_runs/Q8-E001/results/source_files.json').read_text())
    target = json.loads((root / 'research_runs/REDESIGN_SOURCE_SELECTION_20261012/evidence/dataset_sources/dreyer_nemar_acquisition_edf_manifest.json').read_text())['files']
    entries = [{'path': 'bnci/' + Path(r['path']).name, 'bytes': r['bytes'], 'sha256': r['sha256']} for r in source]
    entries += [{'path': 'dreyer_acquisition/' + r['path'], 'bytes': r['size'], 'sha256': r['checksum']} for r in target]
    if len(source) != 18 or len(target) != 174 or len({r['path'] for r in entries}) != 192:
        raise ValueError('frozen_manifest_incomplete')
    return entries


def validate_mapping(mapping, expected):
    rows = mapping.get('files', [])
    if mapping.get('schema_version') != 1 or not isinstance(rows, list):
        raise ValueError('r2_mapping_schema')
    index = {}
    keys = set()
    for row in rows:
        name, key = relative(row['path']), relative(row['object_key'])
        if name in index or key in keys:
            raise ValueError('duplicate_mapping')
        index[name] = row
        keys.add(key)
    if set(index) != {r['path'] for r in expected}:
        raise ValueError('r2_mapping_coverage')
    for row in expected:
        actual = index[row['path']]
        if type(actual.get('bytes')) is not int or any(actual.get(k) != row[k] for k in ('bytes', 'sha256')):
            raise ValueError('r2_mapping_not_frozen_identity')
    return index


def import_files(root, mapping, expected, client, bucket, *, reserve=RESERVE + 1024**3):
    index = validate_mapping(mapping, expected)
    root = Path(root)
    regular_path(root, 'probe')
    root.mkdir(parents=True, exist_ok=True)
    missing = []
    for row in expected:
        p = regular_path(root, row['path'])
        if p.exists():
            if not p.is_file() or p.stat().st_size != row['bytes'] or digest(p) != row['sha256']:
                raise ValueError('existing_cache_hash_mismatch')
        else:
            missing.append(row)
    if shutil.disk_usage(root).free < sum(r['bytes'] for r in missing) + reserve:
        raise ValueError('insufficient_disk_for_r2_import_and_reserve')
    for row in missing:
        p = regular_path(root, row['path'])
        p.parent.mkdir(parents=True, exist_ok=True)
        temp = p.with_name(p.name + '.partial-' + uuid.uuid4().hex)
        body = None
        try:
            response = client.get_object(Bucket=bucket, Key=index[row['path']]['object_key'])
            body = response['Body']
            if response.get('ContentLength') != row['bytes']:
                raise ValueError('r2_object_size_mismatch')
            h, n = hashlib.sha256(), 0
            with temp.open('xb') as f:
                for block in iter(lambda: body.read(CHUNK), b''):
                    n += len(block)
                    if n > row['bytes']:
                        raise ValueError('r2_object_oversize')
                    h.update(block)
                    f.write(block)
                f.flush()
                os.fsync(f.fileno())
            if n != row['bytes'] or h.hexdigest() != row['sha256']:
                raise ValueError('r2_object_hash_mismatch')
            # Link is exclusive: do not overwrite files appearing during import.
            os.link(temp, p)
        except ValueError:
            raise
        except Exception:
            raise RuntimeError('r2_import_failed_no_fallback') from None
        finally:
            if body is not None:
                body.close()
            temp.unlink(missing_ok=True)
    return {'status': 'R2_ONLY_IMPORT_VERIFIED', 'files': expected, 'downloaded_files': len(missing),
            'reused_files': len(expected) - len(missing), 'official_source_requests': 0}


def import_from_environment(repo, data_dir):
    name, expected_sha = os.environ.get('MI_EEG_R2_IMPORT_MANIFEST'), os.environ.get('MI_EEG_R2_IMPORT_SHA256')
    if not name or not expected_sha or not re.fullmatch('[0-9a-f]{64}', expected_sha):
        raise ValueError('reviewed_r2_mapping_and_sha256_required')
    path = Path(name)
    if path.is_symlink() or not path.is_file() or digest(path) != expected_sha:
        raise ValueError('r2_mapping_hash_mismatch')
    mapping = json.loads(path.read_text())
    expected = frozen_entries(repo)
    validate_mapping(mapping, expected)  # Reject before any API access.
    client, bucket = environment_client()
    result = import_files(data_dir, mapping, expected, client, bucket)
    result['mapping_sha256'] = expected_sha
    return result
