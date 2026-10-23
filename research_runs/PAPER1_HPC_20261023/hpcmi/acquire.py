"""Download the archived eligible-v3 inputs before Slurm compute jobs (stdlib only)."""
from __future__ import annotations
import argparse
import fcntl
import re
import traceback
from contextlib import contextmanager
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import zlib

VENDOR = Path(__file__).resolve().parents[1] / 'vendor' / 'eligible_v3'
sys.path.insert(0, str(VENDOR))
from p1_common import atomic_json, log, safe_child, sha256_file, utc_now
from p1_rangezip import open_yang_archive, member_record, selected_yang_members

STORAGE_HOST = 'nemar.s3.us-east-2.amazonaws.com'
CHUNK = 8 * 1024 * 1024


def stat_identity(path):
    value = Path(path).stat()
    return {'bytes': value.st_size, 'mtime_ns': value.st_mtime_ns}


def _receipt_path(root, relative):
    return Path(root) / '.verified' / (hashlib.sha256(relative.encode()).hexdigest() + '.json')


def _record(root, row, digest):
    target = safe_child(root, row['path'])
    atomic_json(_receipt_path(root, row['path']), {
        'schema_version': 1, 'status': 'SIZE_SHA256_VERIFIED', 'path': row['path'],
        'sha256': digest, 'stat': stat_identity(target), 'verified_at_utc': utc_now(),
        'expected_sha256': row.get('sha256'), 'expected_bytes': row['size']})


def verified_existing(root, row):
    target = safe_child(root, row['path'])
    if not target.exists():
        return None
    if not target.is_file() or target.stat().st_size != row['size']:
        raise ValueError('Existing raw object has wrong length; retained: ' + row['path'])
    receipt_path = _receipt_path(root, row['path'])
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if (receipt.get('stat') == stat_identity(target) and receipt.get('path') == row['path']
                and receipt.get('expected_sha256') == row.get('sha256')
                and receipt.get('expected_bytes') == row['size']):
            return receipt['sha256']
    digest = sha256_file(target)
    if row.get('sha256') and digest != row['sha256']:
        raise ValueError('Existing raw object SHA256 differs; retained: ' + row['path'])
    # Metadata with only ZIP CRC pins must be checked against its CRC as well.
    if 'crc32' in row:
        crc = 0
        with target.open('rb') as stream:
            for block in iter(lambda: stream.read(CHUNK), b''):
                crc = zlib.crc32(block, crc)
        if f'{crc & 0xffffffff:08x}' != row['crc32']:
            raise ValueError('Existing ZIP member CRC differs; retained: ' + row['path'])
    _record(root, row, digest)
    return digest


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open_no_redirect(url, offset=0):
    headers = {'Accept-Encoding': 'identity', 'User-Agent': 'Paper1-HPC-data/1.0'}
    if offset:
        headers['Range'] = 'bytes=%d-' % offset
    return urllib.request.build_opener(NoRedirect()).open(
        urllib.request.Request(url, headers=headers), timeout=60)


def validate_nemar_location(row, location):
    """Exact same storage-object rule as the reviewed 009a3629 single-hop adapter."""
    expected = '/nm000250/objects/SHA256E-s%d--%s.edf' % (row['size'], row['sha256'])
    try:
        parts = urlsplit(location)
        allowed = (len(location) <= 9216 and all(ord(c) >= 33 and ord(c) != 127 for c in location)
                   and parts.scheme == 'https' and parts.netloc == STORAGE_HOST
                   and parts.hostname == STORAGE_HOST and parts.port is None
                   and parts.username is None and parts.password is None and not parts.fragment
                   and '#' not in location and parts.path == expected and len(parts.query) <= 8192)
    except (TypeError, ValueError):
        allowed = False
    if not allowed:
        raise ValueError('NEMAR redirect is not the exact frozen HTTPS storage object')
    return location


def validate_bnci_location(row, location):
    canonical = urlsplit(row['url'])
    basename = Path(canonical.path).name
    if (canonical.scheme != 'https' or canonical.netloc != 'bnci-horizon-2020.eu'
            or not re.fullmatch(r'A0[1-9][ET]\.mat', basename)
            or canonical.path != '/database/data-sets/001-2014/' + basename
            or canonical.query or canonical.fragment):
        raise ValueError('BNCI canonical source is not an exact frozen MAT URL')
    expected = 'https://lampx.tugraz.at/~bci/database/001-2014/' + basename
    if location != expected:
        raise ValueError('BNCI redirect differs from the official exact MAT mirror')
    return expected


@contextmanager
def open_object(row, offset=0, *, nemar=False):
    transient = None
    response = None
    status = None
    try:
        response = _open_no_redirect(row['url'], offset)
    except urllib.error.HTTPError as exc:
        status = exc.code
        if status == 302 and (nemar or urlsplit(row['url']).netloc == 'bnci-horizon-2020.eu'):
            transient = exc.headers.get('Location')
        exc.close()
    except urllib.error.URLError:
        raise OSError('Canonical public object connection failed') from None
    if status is not None and transient is None:
        # Never retry or bypass an explicit denial, and never print signed URLs.
        raise ValueError('Canonical public object HTTP %s' % status)
    if transient is not None:
        transient = validate_nemar_location(row, transient) if nemar else validate_bnci_location(row, transient)
        try:
            response = _open_no_redirect(transient, offset)
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            raise ValueError('Exact official storage object HTTP %s' % status) from None
        except urllib.error.URLError:
            raise OSError('Exact official storage connection failed') from None
    try:
        if response is None:
            raise ValueError('No public object response')
        expected_url = transient if transient is not None else row['url']
        if response.geturl() != expected_url:
            raise ValueError('Unexpected additional redirect')
        yield response
    finally:
        if response is not None:
            response.close()


def transfer_object(root, row, *, nemar=False, attempts=4):
    digest = verified_existing(root, row)
    if digest:
        return digest
    target = safe_child(root, row['path'])
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + '.part')
    for attempt in range(attempts):
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > row['size']:
            raise ValueError('Oversized partial retained: ' + row['path'])
        try:
            if offset < row['size']:
                with open_object(row, offset, nemar=nemar) as response:
                    if response.status == 206:
                        if response.headers.get('Content-Range') != 'bytes %d-%d/%d' % (offset, row['size'] - 1, row['size']):
                            raise ValueError('Raw Content-Range changed')
                        mode = 'ab'
                    elif response.status == 200:
                        # A server may ignore Range; restart this incomplete file only.
                        mode, offset = 'wb', 0
                    else:
                        raise ValueError('Unexpected raw response status')
                    length = response.headers.get('Content-Length')
                    if length is not None and int(length) != row['size'] - offset:
                        raise ValueError('Raw Content-Length changed')
                    if response.headers.get('Content-Encoding', 'identity') != 'identity':
                        raise ValueError('Raw Content-Encoding changed')
                    last = time.monotonic()
                    with partial.open(mode) as out:
                        while True:
                            block = response.read(min(CHUNK, row['size'] - out.tell() + 1))
                            if not block:
                                break
                            out.write(block)
                            if out.tell() > row['size']:
                                raise ValueError('Oversized raw response retained')
                            if time.monotonic() - last > 30:
                                log('download %s %d/%d bytes' % (row['path'], out.tell(), row['size']))
                                last = time.monotonic()
                        out.flush()
                        os.fsync(out.fileno())
            if partial.stat().st_size != row['size']:
                raise OSError('Incomplete object')
            digest = sha256_file(partial)
            if digest != row['sha256']:
                raise ValueError('Raw SHA256 mismatch; partial retained: ' + row['path'])
            os.replace(partial, target)
            _record(root, row, digest)
            return digest
        except (OSError, TimeoutError, http.client.HTTPException) as exc:
            if attempt + 1 == attempts:
                raise RuntimeError('Transfer interrupted; same command resumes ' + row['path']) from exc
            time.sleep(min(2 ** attempt, 8))
    raise AssertionError('unreachable')


def acquire_pinned(dataset, root):
    manifest = json.loads((VENDOR / 'config' / (dataset + '_manifest.json')).read_text())
    count = 18 if dataset == 'bnci' else 174
    if len(manifest['files']) != count:
        raise ValueError('Pinned inventory changed')
    for index, row in enumerate(manifest['files'], 1):
        transfer_object(root, row, nemar=dataset == 'dreyer')
        log('%s %d/%d raw objects verified' % (dataset, index, count))
    atomic_json(Path(root) / '_download_manifest.json', manifest)
    return manifest


def yang_pins():
    inventory = json.loads((VENDOR / 'evidence/yang_v5_selected_inventory.json').read_text())
    clocks = json.loads((VENDOR / 'config/yang_clock_registry_v5.json').read_text())
    hashes = {r['path']: r for p in clocks['pairs'] for r in (p['signal'], p['event'])}
    rows = []
    for row in inventory['members']:
        pin = {**row, 'size': row['bytes']}
        if row['path'] in hashes:
            if row['bytes'] != hashes[row['path']]['bytes']:
                raise ValueError('Frozen Yang inventories disagree')
            pin['sha256'] = hashes[row['path']]['sha256']
        rows.append(pin)
    if len(rows) != 312 or len(hashes) != 306:
        raise ValueError('Incomplete frozen Yang inventory')
    return inventory, rows


def _yang_member(reader, info, row, root):
    """Resume compressed bytes; then decode/CRC/SHA one member before publishing."""
    existing = verified_existing(root, row)
    if existing:
        return existing
    reader.seek(info.header_offset)
    header = reader.read(30)
    values = struct.unpack('<4s5H3L2H', header)
    if values[0] != b'PK\x03\x04' or values[2] & 1 or values[3] != info.compress_type:
        raise ValueError('Unexpected Yang local ZIP header')
    filename_len, extra_len = values[-2:]
    name = reader.read(filename_len)
    encoding = 'utf-8' if values[2] & 0x800 else 'cp437'
    if name.decode(encoding) != info.filename:
        raise ValueError('Yang ZIP local member name changed')
    data_offset = info.header_offset + 30 + filename_len + extra_len
    target = safe_child(root, row['path'])
    target.parent.mkdir(parents=True, exist_ok=True)
    compressed = target.with_name(target.name + '.compressed.part')
    offset = compressed.stat().st_size if compressed.exists() else 0
    if offset > info.compress_size:
        raise ValueError('Oversized compressed Yang partial retained')
    with compressed.open('ab') as out:
        last = time.monotonic()
        while offset < info.compress_size:
            count = min(CHUNK, info.compress_size - offset)
            reader.seek(data_offset + offset)
            block = reader.read(count)
            if len(block) != count:
                raise OSError('Truncated Yang compressed member')
            out.write(block)
            offset += len(block)
            if time.monotonic() - last > 30:
                log('Yang %s compressed %d/%d bytes' % (row['path'], offset, info.compress_size))
                last = time.monotonic()
        out.flush()
        os.fsync(out.fileno())
    if info.compress_type not in (0, 8):
        raise ValueError('Frozen Yang compression method unsupported')
    decoder = zlib.decompressobj(-15) if info.compress_type == 8 else None
    partial = target.with_name(target.name + '.part')
    crc, size, digest = 0, 0, hashlib.sha256()
    with compressed.open('rb') as source, partial.open('wb') as out:
        for block in iter(lambda: source.read(CHUNK), b''):
            data = decoder.decompress(block) if decoder else block
            size += len(data)
            if size > row['size']:
                raise ValueError('Oversized decompressed Yang member retained')
            out.write(data)
            digest.update(data)
            crc = zlib.crc32(data, crc)
        if decoder and (not decoder.eof or decoder.unused_data):
            raise ValueError('Incomplete Yang deflate stream retained')
        out.flush()
        os.fsync(out.fileno())
    sha = digest.hexdigest()
    if (size != row['size'] or f'{crc & 0xffffffff:08x}' != row['crc32']
            or (row.get('sha256') and sha != row['sha256'])):
        raise ValueError('Yang size/CRC/SHA mismatch; partial retained: ' + row['path'])
    os.replace(partial, target)
    _record(root, row, sha)
    compressed.unlink()  # Reconstructible compressed cache; verified native file is durable.
    return sha


def acquire_yang(root):
    inventory, rows = yang_pins()
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    completed = {row['path']: verified_existing(root, row) for row in rows}
    pending = [row for row in rows if completed[row['path']] is None]
    if pending:
        remaining = sum(row['size'] for row in pending)
        if shutil.disk_usage(root).free < remaining + 4 * 1024 ** 3:
            raise ValueError('Yang needs remaining raw bytes plus 4 GiB for transfer/cache; free storage first')
        reader, archive, attestation, _ = open_yang_archive()
        try:
            selected = selected_yang_members(archive)
            by_name = {info.filename: info for info in selected}
            for index, row in enumerate(rows, 1):
                info = by_name[row['path']]
                if member_record(info) != {k: row[k] for k in member_record(info)}:
                    raise ValueError('Live Yang member differs from frozen directory inventory')
                if completed[row['path']] is None:
                    completed[row['path']] = _yang_member(reader, info, row, root)
                log('yang %d/%d members verified' % (index, len(rows)))
        finally:
            archive.close()
            reader.close()
    stable = {'dataset': 'Yang2025-2C', 'data_doi': '10.25452/figshare.plus.22671172.v5',
              'license': 'CC BY 4.0', 'archive_url': inventory['archive_url'],
              'central_directory_sha256': inventory['central_directory_sha256'],
              'whole_archive_md5_verified': False,
              'integrity_scope': 'pinned ZIP directory; all 306 EEG/event SHA256; six metadata CRC32 plus recorded SHA256',
              'files': [{'path': r['path'], 'size': r['size'], 'sha256': completed[r['path']],
                         'crc32': r['crc32']} for r in rows]}
    atomic_json(root / '_download_manifest.json', stable)
    return stable


def quick_raw_ready(raw_dir):
    """Check names, declared pins and byte lengths only; preparation verifies bytes."""
    raw_dir = Path(raw_dir)
    for dataset in ('bnci', 'yang', 'dreyer'):
        root = raw_dir / dataset
        manifest_path = root / '_download_manifest.json'
        if not manifest_path.is_file():
            return False
        observed = json.loads(manifest_path.read_text())
        records = {r['path']: r for r in observed['files']}
        if dataset == 'yang':
            _, expected = yang_pins()
        else:
            expected = json.loads((VENDOR / 'config' / (dataset + '_manifest.json')).read_text())['files']
        if set(records) != {r['path'] for r in expected}:
            raise ValueError('Raw manifest inventory changed: ' + dataset)
        for pin in expected:
            row = records[pin['path']]
            if row['size'] != pin['size'] or (pin.get('sha256') and row['sha256'] != pin['sha256']):
                raise ValueError('Raw manifest pin changed: ' + pin['path'])
            if not isinstance(row['sha256'], str) or len(row['sha256']) != 64:
                raise ValueError('Raw manifest has no complete SHA256')
            target = safe_child(root, pin['path'])
            if not target.is_file() or target.stat().st_size != pin['size']:
                return False
    return True


@contextmanager
def acquisition_lock(raw_dir):
    path = Path(raw_dir) / '.acquisition.lock'
    with path.open('a+') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Download already running for this raw directory; no second transfer started') from None
        try:
            stream.seek(0)
            stream.truncate()
            stream.write(str(os.getpid()) + '\n')
            stream.flush()
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)
    # Keep the inode. Deleting a lock file can allow concurrent lock owners.


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', required=True, type=Path)
    parser.add_argument('--dataset', choices=['all', 'bnci', 'yang', 'dreyer'], default='all')
    args = parser.parse_args(argv)
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    with acquisition_lock(args.raw_dir):
        for dataset in (['bnci', 'yang', 'dreyer'] if args.dataset == 'all' else [args.dataset]):
            log('begin download/continue ' + dataset)
            (acquire_yang(args.raw_dir / dataset) if dataset == 'yang'
             else acquire_pinned(dataset, args.raw_dir / dataset))
        atomic_json(args.raw_dir / 'acquisition_status.json', {'status': 'ALL_RAW_DATASETS_READY' if quick_raw_ready(args.raw_dir) else 'REQUESTED_DOWNLOADS_COMPLETE',
                    'datasets': args.dataset, 'updated_at_utc': utc_now(), 'model_fits': 0})
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        # RangeZIP may retain a public signed redirect in an inner exception.
        # Report the actual failing outer stack without private URL cause chains.
        traceback.print_exception(type(exc), exc, exc.__traceback__, chain=False)
        raise SystemExit(1)
