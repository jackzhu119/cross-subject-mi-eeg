"""Freeze complete real evidence; never infer missing content digests from headers."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from yang_clock_registry import (ARCHIVE_URL, ARCHIVE_BYTES, CENTRAL_SHA256,
                                 AUTHOR_READER_SHA256, ClockRegistry)

HEADER_REPORT_SHA = '1e33e10db313df6b256200b9a6aceb3c499e3ad5254bb32a13efd8567d3410cd'
HEADER_REPORT_BYTES = 141210


def freeze(headers_path, content_manifest_path, inventory_path, fresh_receipt_path, destination):
    if destination.exists():
        raise ValueError('refuse to overwrite a reviewed registry')
    raw = headers_path.read_bytes()
    if len(raw) != HEADER_REPORT_BYTES or hashlib.sha256(raw).hexdigest() != HEADER_REPORT_SHA:
        raise ValueError('full original header-report bytes/hash required; chat excerpt is insufficient')
    headers = json.loads(raw)
    manifest_raw = content_manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    records = {}
    for row in manifest['files']:
        if row['path'] in records:
            raise ValueError('duplicate content-manifest path')
        records[row['path']] = row
    fresh_raw = fresh_receipt_path.read_bytes()
    if hashlib.sha256(fresh_raw).hexdigest() != '86d52a530aa171e8c74455248f1f1e265c4c7ed8c1c1696741a52bd5b3152817':
        raise ValueError('fresh full-file receipt changed')
    fresh = json.loads(fresh_raw)
    if (len(manifest_raw) != 68346 or hashlib.sha256(manifest_raw).hexdigest() != '1b7b49a7f29911209b3e79665fab1fd5bf86dced24f4a54a5f1f8d37b437a5f7'
            or manifest['original_receipt_sha256'] != fresh['download_receipt_sha256']):
        raise ValueError('download receipt differs from fresh verification parent')
    current = {r['path']:r for r in fresh['files']}
    required = {p['directory']+'/'+name for p in headers['pairs'] if not p['clock_bytes_equal']
                for name in ('data.bdf','evt.bdf')}
    if len(current) != 124 or set(current) != required or sum(r['bytes'] for r in current.values()) != 27609173212:
        raise ValueError('fresh full-file verification coverage mismatch')
    pairs = []
    for pair in headers['pairs']:
        match = re.fullmatch(r'WBCIC_SHU Motor Imagery dataset/sourcedata/2C dataset/sub-(\d{3})/ses-(\d{2})/eeg', pair['directory'])
        if not match:
            raise ValueError('unexpected header-report pair path')
        out = {'subject': int(match[1]), 'session': int(match[2])}
        for role, name in [('signal','data.bdf'),('event','evt.bdf')]:
            path = pair['directory'] + '/' + name
            if path not in records:
                raise ValueError('missing full-content receipt for ' + path)
            head, content = pair[role], records[path]
            size = content.get('size', content.get('bytes'))
            if size != head['bytes']:
                raise ValueError('header report and full-content receipt disagree on file size')
            if bytes.fromhex(head['start_date_hex']).decode('latin1') != head['start_date'] or bytes.fromhex(head['start_time_hex']).decode('latin1') != head['start_time']:
                raise ValueError('header text and original bytes disagree')
            if path in current:
                check = current[path]
                if (check['status'] != 'MATCH' or check['full_bytes_read'] is not True
                        or check['bytes'] != size or check['sha256'] != content['sha256']
                        or check['expected_sha256'] != content['sha256']
                        or check['header_sha256'] != head['header_sha256']):
                    raise ValueError('fresh full-file and header evidence disagree')
            out[role] = {'path': path, 'bytes': size, 'sha256': content['sha256'],
                         'header_sha256': head['header_sha256'],
                         'start_date_time': head['start_date'] + head['start_time']}
        pairs.append(out)
    obj = {'schema_version': 1, 'archive_url': ARCHIVE_URL, 'archive_bytes': ARCHIVE_BYTES,
           'central_directory_sha256': CENTRAL_SHA256, 'author_reader_sha256': AUTHOR_READER_SHA256,
           'header_report_sha256': HEADER_REPORT_SHA,
           'content_manifest_projection_sha256': hashlib.sha256(manifest_raw).hexdigest(),
           'original_download_receipt_sha256': manifest['original_receipt_sha256'],
           'fresh_mismatch_receipt_sha256': hashlib.sha256(fresh_raw).hexdigest(),
           'fresh_verification_scope': {'files':124, 'bytes':27609173212, 'remaining_files_rechecked_at_runtime':182},
           'content_hash_scope': 'digests_from_supplied_full_file_receipts; runtime_VerifiedFiles_rehashes_each_file',
           'pairs': sorted(pairs, key=lambda p:(p['subject'],p['session']))}
    serialized = (json.dumps(obj, indent=2) + '\n').encode()
    digest = hashlib.sha256(serialized).hexdigest()
    # Validate in an exclusive temporary file before publishing the registry.
    import tempfile
    with tempfile.TemporaryDirectory() as temporary:
        tmp = Path(temporary) / 'registry.json'
        tmp.write_bytes(serialized)
        ClockRegistry(tmp, digest, json.loads(inventory_path.read_text()))
    with destination.open('xb') as stream:
        stream.write(serialized)
    return digest


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('headers',type=Path)
    parser.add_argument('content_manifest',type=Path)
    parser.add_argument('frozen_zip_inventory',type=Path)
    parser.add_argument('fresh_receipt',type=Path)
    parser.add_argument('new_registry',type=Path)
    args=parser.parse_args()
    print(freeze(args.headers,args.content_manifest,args.frozen_zip_inventory,args.fresh_receipt,args.new_registry))
