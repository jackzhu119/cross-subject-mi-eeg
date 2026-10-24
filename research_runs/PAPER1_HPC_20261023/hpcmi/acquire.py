"""Download the archived eligible-v3 inputs before Slurm compute jobs (stdlib only)."""
from __future__ import annotations
import argparse
import base64
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
import socket
import ssl
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


def safe_error_details(error):
    """Describe bounded exception metadata without rendering messages or URLs."""
    queue, seen, causes = [error], set(), []
    detail = {'error_class': type(error).__name__, 'category': 'unknown'}
    specific = []
    phases = {'canonical_open', 'official_mirror_open', 'official_redirect_validation'}
    while queue and len(seen) < 6:
        current = queue.pop(0)
        if id(current) in seen or not isinstance(current, BaseException):
            continue
        seen.add(id(current))
        row = {'error_class': type(current).__name__}
        number = getattr(current, 'errno', None)
        if type(number) is int:
            row['errno'] = number
            detail.setdefault('errno', number)
        phase = getattr(current, 'request_phase', None)
        if isinstance(phase, str) and phase in phases:
            detail['request_phase'] = phase
        status = getattr(current, 'http_status', None)
        if isinstance(current, urllib.error.HTTPError):
            status = current.code
            row['location_present'] = bool(current.headers and current.headers.get('Location'))
        elif type(getattr(current, 'location_present', None)) is bool:
            row['location_present'] = current.location_present
        if type(status) is int and 100 <= status <= 599:
            row['http_status'] = status
            detail['http_status'] = status
            specific.append('http')
        if isinstance(current, socket.gaierror):
            specific.append('dns')
        elif isinstance(current, ssl.SSLCertVerificationError):
            specific.append('tls_certificate')
            code = getattr(current, 'verify_code', None)
            if type(code) is int:
                row['ssl_verify_code'] = code
                detail['ssl_verify_code'] = code
        elif isinstance(current, ssl.SSLError):
            specific.append('tls')
        elif isinstance(current, TimeoutError):
            specific.append('timeout')
        elif isinstance(current, http.client.IncompleteRead):
            specific.append('incomplete_read')
            partial = current.partial
            if isinstance(partial, (bytes, bytearray)):
                row['partial_bytes'] = len(partial)
            if type(current.expected) is int:
                row['expected_additional_bytes'] = current.expected
        elif isinstance(current, ConnectionError):
            specific.append('connection')
        elif isinstance(current, OSError) and detail['category'] == 'unknown':
            detail['category'] = 'os_error'
        causes.append(row)
        # from None suppresses display, but its original context is retained.
        # In particular URLError.reason may hold DNS/TLS details; never str it.
        for child in (getattr(current, 'reason', None), current.__cause__, current.__context__):
            if isinstance(child, BaseException) and id(child) not in seen:
                queue.append(child)
    if specific:
        detail['category'] = specific[-1]
    detail['causes'] = causes
    return detail


def record_transport_failure(error, argv=None, environ=None):
    """Bind one child failure to its driver attempt without rendering secrets."""
    env = os.environ if environ is None else environ
    attempt = env.get('PAPER1_TRANSFER_ATTEMPT', '')
    if not isinstance(attempt, str) or not re.fullmatch(r'[0-9a-f]{32}', attempt):
        return None
    arguments = list(sys.argv[1:] if argv is None else argv)
    values = []
    for index, value in enumerate(arguments):
        if value == '--raw-dir' and index + 1 < len(arguments):
            values.append(arguments[index + 1])
        elif isinstance(value, str) and value.startswith('--raw-dir='):
            values.append(value.split('=', 1)[1])
    if len(values) != 1 or not values[0]:
        return None
    try:
        root = Path(values[0]).expanduser().resolve()
        path = root / '.transport-failures' / (attempt + '.json')
        if path.exists():
            return path  # An attempt's first failure is retained unchanged.
        atomic_json(path, {'schema_version': 1, 'attempt_id': attempt,
                           'updated_at_utc': utc_now(), **safe_error_details(error)})
        return path
    except Exception:
        # Failure evidence is best effort; never replace the real child error.
        return None


def report_transfer_error(row, error, stage, attempt, attempts, offset, retry):
    name = row.get('path')
    if (not isinstance(name, str) or len(name) > 1024
            or not re.fullmatch(r'[A-Za-z0-9_. /()-]+', name)
            or Path(name).is_absolute() or '..' in Path(name).parts):
        name = '<unavailable>'
    details = safe_error_details(error)
    print(json.dumps({'event': 'download_error', 'file': name,
                      'stage': details.pop('request_phase', stage),
                      'attempt': attempt + 1, 'attempt_limit': attempts,
                      'offset_bytes': offset, 'will_retry': retry, **details},
                     sort_keys=True), flush=True)


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
    location_present = False
    try:
        response = _open_no_redirect(row['url'], offset)
    except urllib.error.HTTPError as exc:
        status = exc.code
        location_present = bool(exc.headers and exc.headers.get('Location'))
        if status == 302 and (nemar or urlsplit(row['url']).netloc == 'bnci-horizon-2020.eu'):
            transient = exc.headers.get('Location') if exc.headers else None
        exc.close()
    except urllib.error.URLError as error:
        # Only a typed connection/TLS failure may use the independently verified
        # official alias. A text reason, proxy denial or HTTP error is not such
        # evidence and must not cause an alternate-host attempt.
        reason = error.reason
        if (not nemar and urlsplit(row['url']).netloc == 'bnci-horizon-2020.eu'
                and isinstance(reason, (socket.gaierror, TimeoutError, ConnectionError, ssl.SSLError))
                and not isinstance(reason, urllib.error.HTTPError)):
            basename = Path(urlsplit(row['url']).path).name
            transient = validate_bnci_location(row, 'https://lampx.tugraz.at/~bci/database/001-2014/' + basename)
            print(json.dumps({'event': 'official_alias_attempt', 'file': basename,
                              'stage': 'canonical_open', 'offset_bytes': offset,
                              'alias_hostname': 'lampx.tugraz.at',
                              'school_failure_cause_established': False,
                              **safe_error_details(error)}, sort_keys=True), flush=True)
        else:
            failure = OSError('Canonical public object connection failed')
            failure.request_phase = 'canonical_open'
            raise failure from None
    if status is not None and transient is None:
        # Never retry or bypass an explicit denial, and never print signed URLs.
        failure = ValueError('Canonical public object HTTP %s' % status)
        failure.request_phase = 'canonical_open'
        failure.http_status = status
        failure.location_present = location_present
        raise failure
    if transient is not None:
        try:
            transient = validate_nemar_location(row, transient) if nemar else validate_bnci_location(row, transient)
        except ValueError as failure:
            failure.request_phase = 'official_redirect_validation'
            failure.http_status = status
            failure.location_present = True
            raise
        try:
            response = _open_no_redirect(transient, offset)
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            failure = ValueError('Exact official storage object HTTP %s' % status)
            failure.request_phase = 'official_mirror_open'
            raise failure from None
        except urllib.error.URLError:
            failure = OSError('Exact official storage connection failed')
            failure.request_phase = 'official_mirror_open'
            raise failure from None
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
        stage = 'open_object'
        try:
            if offset < row['size']:
                with open_object(row, offset, nemar=nemar) as response:
                    stage = 'response_headers'
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
                    stage = 'open_partial'
                    with partial.open(mode) as out:
                        while True:
                            stage = 'read_body'
                            block = response.read(min(CHUNK, row['size'] - out.tell() + 1))
                            if not block:
                                break
                            stage = 'write_partial'
                            out.write(block)
                            if out.tell() > row['size']:
                                raise ValueError('Oversized raw response retained')
                            if time.monotonic() - last > 30:
                                log('download %s %d/%d bytes' % (row['path'], out.tell(), row['size']))
                                last = time.monotonic()
                        stage = 'flush_partial'
                        out.flush()
                        stage = 'fsync_partial'
                        os.fsync(out.fileno())
            stage = 'verify_size'
            if partial.stat().st_size != row['size']:
                raise OSError('Incomplete object')
            stage = 'hash_partial'
            digest = sha256_file(partial)
            if digest != row['sha256']:
                raise ValueError('Raw SHA256 mismatch; partial retained: ' + row['path'])
            stage = 'publish_file'
            os.replace(partial, target)
            stage = 'write_receipt'
            _record(root, row, digest)
            return digest
        except (OSError, TimeoutError, http.client.HTTPException) as exc:
            report_transfer_error(row, exc, stage, attempt, attempts, offset, attempt + 1 < attempts)
            if attempt + 1 == attempts:
                raise RuntimeError('Transfer interrupted; same command resumes ' + row['path']) from exc
            time.sleep(min(2 ** attempt, 8))
        except ValueError as exc:
            report_transfer_error(row, exc, stage, attempt, attempts, offset, False)
            raise
    raise AssertionError('unreachable')


def acquire_pinned(dataset, root, progress=None):
    manifest = json.loads((VENDOR / 'config' / (dataset + '_manifest.json')).read_text())
    count = 18 if dataset == 'bnci' else 174
    if len(manifest['files']) != count:
        raise ValueError('Pinned inventory changed')
    for index, row in enumerate(manifest['files'], 1):
        transfer_object(root, row, nemar=dataset == 'dreyer')
        log('%s %d/%d raw objects verified' % (dataset, index, count))
        if progress is not None:
            progress(index, count)
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


def _archive_identity(inventory):
    keys = ('archive_url', 'archive_bytes', 'central_directory_offset',
            'central_directory_bytes', 'central_directory_sha256', 'member_count', 'eocd_offset')
    return {key: inventory[key] for key in keys}


def _transport_receipt(root, row):
    return Path(root) / '.transport' / (hashlib.sha256(row['path'].encode()).hexdigest() + '.json')


def _yang_pin(row):
    keys = ('path', 'size', 'compressed_bytes', 'crc32', 'header_offset', 'compression')
    value = {key: row[key] for key in keys}
    if row.get('sha256'):
        value['sha256'] = row['sha256']
    return value


def _yang_local_header(reader, info, row):
    if member_record(info) != {key: row[key] for key in member_record(info)}:
        raise ValueError('Live Yang member differs from frozen directory inventory')
    reader.seek(info.header_offset)
    header = reader.read(30)
    if len(header) != 30:
        raise ValueError('Truncated Yang local ZIP header')
    values = struct.unpack('<4s5H3L2H', header)
    if (values[0] != b'PK\x03\x04' or values[2] & 1
            or values[3] != info.compress_type or info.compress_type not in (0, 8)):
        raise ValueError('Unexpected Yang local ZIP header')
    filename_len, extra_len = values[-2:]
    name, extra = reader.read(filename_len), reader.read(extra_len)
    encoding = 'utf-8' if values[2] & 0x800 else 'cp437'
    if (len(name) != filename_len or len(extra) != extra_len
            or name.decode(encoding) != info.filename):
        raise ValueError('Yang ZIP local member name or extra-field length changed')
    raw = header + name + extra
    data_offset = info.header_offset + len(raw)
    return data_offset, {'bytes_b64': base64.b64encode(raw).decode('ascii'),
                         'sha256': hashlib.sha256(raw).hexdigest(), 'data_offset': data_offset}


def _compressed_ready(root, row, inventory):
    """Read bounded saved metadata only; native CRC/SHA remain pending."""
    path = _transport_receipt(root, row)
    if not path.is_file():
        return False
    if path.stat().st_size > 200000:
        raise ValueError('Oversized Yang transport receipt retained')
    receipt = json.loads(path.read_text())
    if (receipt.get('schema_version') != 1
            or receipt.get('status') != 'COMPRESSED_TRANSPORT_COMPLETE_NATIVE_VALIDATION_PENDING'
            or receipt.get('archive') != _archive_identity(inventory)
            or receipt.get('pin') != _yang_pin(row)):
        raise ValueError('Yang transport identity differs from frozen inventory')
    local = receipt.get('local_header', {})
    try:
        raw = base64.b64decode(local['bytes_b64'], validate=True)
        if not 30 <= len(raw) <= 30 + 65535 + 65535:
            raise ValueError('Invalid local-header bound')
        values = struct.unpack('<4s5H3L2H', raw[:30])
        filename_len, extra_len = values[-2:]
        name = raw[30:30 + filename_len]
        encoding = 'utf-8' if values[2] & 0x800 else 'cp437'
        if (len(raw) != 30 + filename_len + extra_len or values[0] != b'PK\x03\x04'
                or values[2] & 1 or values[3] != row['compression']
                or name.decode(encoding) != row['path']
                or hashlib.sha256(raw).hexdigest() != local['sha256']
                or local['data_offset'] != row['header_offset'] + len(raw)
                or local['data_offset'] + row['compressed_bytes'] > inventory['central_directory_offset']):
            raise ValueError('Yang saved local-header attestation differs')
    except (KeyError, TypeError, UnicodeError, struct.error) as exc:
        raise ValueError('Invalid Yang saved local-header attestation') from exc
    target = safe_child(root, row['path'])
    compressed = target.with_name(target.name + '.compressed.part')
    if not compressed.is_file():
        return False
    if compressed.stat().st_size != row['compressed_bytes']:
        raise ValueError('Yang completed compressed cache length changed; retained')
    if stat_identity(compressed) != receipt.get('compressed_stat'):
        raise ValueError('Yang completed compressed cache identity changed; retained')
    return True


def _download_yang_compressed(reader, info, row, root, *, inventory=None):
    data_offset, local_header = _yang_local_header(reader, info, row)
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
    if inventory is not None:
        atomic_json(_transport_receipt(root, row), {
            'schema_version': 1, 'status': 'COMPRESSED_TRANSPORT_COMPLETE_NATIVE_VALIDATION_PENDING',
            'archive': _archive_identity(inventory), 'pin': _yang_pin(row),
            'local_header': local_header, 'compressed_stat': stat_identity(compressed),
            'completed_at_utc': utc_now(), 'native_sha256_verified': False,
            'integrity_scope': 'Pinned live ZIP directory/local header and complete compressed byte length; native CRC/SHA checked offline'})
    return compressed


def _publish_yang_compressed(row, root):
    """Decode one cached member offline; frozen size/CRC/SHA precede publish."""
    target = safe_child(root, row['path'])
    compressed = target.with_name(target.name + '.compressed.part')
    if not compressed.is_file() or compressed.stat().st_size != row['compressed_bytes']:
        raise ValueError('Missing or incomplete Yang compressed cache; retained')
    if row['compression'] not in (0, 8):
        raise ValueError('Frozen Yang compression method unsupported')
    decoder = zlib.decompressobj(-15) if row['compression'] == 8 else None
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
    compressed.unlink()
    return sha


def _yang_member(reader, info, row, root):
    """Original combined transport/publication route, retained for compatibility."""
    existing = verified_existing(root, row)
    if existing:
        return existing
    _download_yang_compressed(reader, info, row, root)
    return _publish_yang_compressed(row, root)


def acquire_yang_transport(root, progress=None):
    """Network I/O only: keep compressed bytes; never decode a Yang member."""
    inventory, rows = yang_pins()
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    pending = [row for row in rows if verified_existing(root, row) is None
               and not _compressed_ready(root, row, inventory)]
    completed = len(rows) - len(pending)
    if progress is not None:
        progress(completed, len(rows))
    if not pending:
        return
    remaining = 0
    for row in pending:
        target = safe_child(root, row['path'])
        compressed = target.with_name(target.name + '.compressed.part')
        existing = compressed.stat().st_size if compressed.is_file() else 0
        if existing > row['compressed_bytes']:
            raise ValueError('Oversized compressed Yang partial retained')
        remaining += row['compressed_bytes'] - existing
    if shutil.disk_usage(root).free < remaining + 4 * 1024 ** 3:
        raise ValueError('Yang transport needs remaining compressed bytes plus 4 GiB')
    reader, archive, attestation, _ = open_yang_archive()
    try:
        if _archive_identity(attestation) != _archive_identity(inventory):
            raise ValueError('Live Yang archive differs from frozen attestation')
        by_name = {info.filename: info for info in selected_yang_members(archive)}
        for index, row in enumerate(pending, 1):
            _download_yang_compressed(reader, by_name[row['path']], row, root, inventory=inventory)
            log('yang compressed transport %d/%d complete; native validation pending' % (index, len(pending)))
            if progress is not None:
                progress(completed + index, len(rows))
    finally:
        archive.close()
        reader.close()


def _yang_manifest(root, inventory, rows, completed):
    stable = {'dataset': 'Yang2025-2C', 'data_doi': '10.25452/figshare.plus.22671172.v5',
              'license': 'CC BY 4.0', 'archive_url': inventory['archive_url'],
              'central_directory_sha256': inventory['central_directory_sha256'],
              'whole_archive_md5_verified': False,
              'integrity_scope': 'pinned ZIP directory; all 306 EEG/event SHA256; six metadata CRC32 plus recorded SHA256',
              'files': [{'path': r['path'], 'size': r['size'], 'sha256': completed[r['path']],
                         'crc32': r['crc32']} for r in rows]}
    atomic_json(Path(root) / '_download_manifest.json', stable)
    return stable


def publish_yang_offline(root):
    inventory, rows = yang_pins()
    root = Path(root)
    completed = {}
    for index, row in enumerate(rows, 1):
        completed[row['path']] = verified_existing(root, row)
        if completed[row['path']] is None:
            if not _compressed_ready(root, row, inventory):
                raise ValueError('Yang transport is incomplete; finish network transport first')
            completed[row['path']] = _publish_yang_compressed(row, root)
        log('yang offline %d/%d members native CRC/SHA verified' % (index, len(rows)))
    return _yang_manifest(root, inventory, rows, completed)


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
    return _yang_manifest(root, inventory, rows, completed)


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


def _pinned_native_ready(raw_dir, dataset, *, verify_unreceipted=False):
    root = Path(raw_dir) / dataset
    pin = json.loads((VENDOR / 'config' / (dataset + '_manifest.json')).read_text())
    manifest_path = root / '_download_manifest.json'
    if not manifest_path.is_file():
        return False
    saved = json.loads(manifest_path.read_text())
    if saved != pin:
        raise ValueError('Native transport manifest differs from frozen inventory: ' + dataset)
    for row in pin['files']:
        target = safe_child(root, row['path'])
        if not target.is_file():
            return False
        if verify_unreceipted:
            if verified_existing(root, row) != row['sha256']:
                return False
        else:
            receipt_path = _receipt_path(root, row['path'])
            if not receipt_path.is_file():
                return False
            receipt = json.loads(receipt_path.read_text())
            if (target.stat().st_size != row['size'] or receipt.get('stat') != stat_identity(target)
                    or receipt.get('expected_sha256') != row['sha256']
                    or receipt.get('expected_bytes') != row['size']
                    or receipt.get('sha256') != row['sha256'] or receipt.get('path') != row['path']):
                raise ValueError('Native transport file/receipt changed: ' + row['path'])
    return True


def network_payloads_ready(raw_dir):
    """Metadata/stat readiness; no network, decompression, EEG import or rehash."""
    raw_dir = Path(raw_dir)
    if not all(_pinned_native_ready(raw_dir, dataset) for dataset in ('bnci', 'dreyer')):
        return False
    inventory, rows = yang_pins()
    root = raw_dir / 'yang'
    for row in rows:
        target = safe_child(root, row['path'])
        receipt_path = _receipt_path(root, row['path'])
        if target.is_file() and receipt_path.is_file():
            receipt = json.loads(receipt_path.read_text())
            if (target.stat().st_size != row['size'] or receipt.get('stat') != stat_identity(target)
                    or receipt.get('expected_sha256') != row.get('sha256')
                    or receipt.get('expected_bytes') != row['size']
                    or receipt.get('path') != row['path']
                    or not re.fullmatch(r'[0-9a-f]{64}', str(receipt.get('sha256', '')))
                    or (row.get('sha256') and receipt.get('sha256') != row['sha256'])):
                raise ValueError('Yang native transport file/receipt changed: ' + row['path'])
        elif not _compressed_ready(root, row, inventory):
            return False
    return True


def publish_offline(raw_dir, datasets=('bnci', 'yang', 'dreyer')):
    """Publish cached inputs without calling any HTTP or ZIP archive reader."""
    raw_dir = Path(raw_dir)
    for dataset in datasets:
        if dataset == 'yang':
            publish_yang_offline(raw_dir / dataset)
        elif not _pinned_native_ready(raw_dir, dataset, verify_unreceipted=True):
            raise ValueError('Native dataset transport incomplete: ' + dataset)
    return quick_raw_ready(raw_dir)


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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--transport-only', action='store_true', help='Download native/ZIP-compressed payloads without decoding Yang')
    mode.add_argument('--offline-publish', action='store_true', help='Verify/publish cached payloads without network access')
    args = parser.parse_args(argv)
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    with acquisition_lock(args.raw_dir):
        datasets = ['bnci', 'yang', 'dreyer'] if args.dataset == 'all' else [args.dataset]
        if args.offline_publish:
            ready = publish_offline(args.raw_dir, datasets)
        else:
            counts = {'bnci': 18, 'yang': 312, 'dreyer': 174}
            completed_before = 0
            for dataset in datasets:
                log('begin download/continue ' + dataset)
                def progress(completed, total, dataset=dataset, before=completed_before):
                    atomic_json(args.raw_dir / 'transport_status.json', {
                        'stage': 'network_transport', 'dataset': dataset,
                        'completed_objects': before + completed,
                        'total_objects': sum(counts[d] for d in datasets),
                        'dataset_completed_objects': completed, 'dataset_total_objects': total,
                        'updated_at_utc': utc_now(), 'model_fits': 0,
                        'native_yang_validation_pending': True})
                report = progress if args.transport_only else None
                if dataset == 'yang':
                    if args.transport_only:
                        acquire_yang_transport(args.raw_dir / dataset, progress=report)
                    else:
                        acquire_yang(args.raw_dir / dataset)
                else:
                    acquire_pinned(dataset, args.raw_dir / dataset, progress=report)
                completed_before += counts[dataset]
            ready = quick_raw_ready(args.raw_dir)
        network_ready = network_payloads_ready(args.raw_dir)
        if network_ready:
            summary = {
                'status': 'NETWORK_PAYLOADS_COMPLETE_NATIVE_YANG_VALIDATION_PENDING' if not ready else 'ALL_NATIVE_INPUTS_VERIFIED',
                'updated_at_utc': utc_now(), 'model_fits': 0,
                'native_yang_validation_pending': not ready,
                'native_integrity_validation_required_before_training': True}
            if args.transport_only:
                summary['yang_decompressed_in_this_transport'] = False
            atomic_json(args.raw_dir / 'network_payloads_ready.json', summary)
        atomic_json(args.raw_dir / 'acquisition_status.json', {
            'status': 'ALL_RAW_DATASETS_READY' if ready else (
                'NETWORK_PAYLOADS_READY' if network_ready else 'REQUESTED_DOWNLOADS_COMPLETE'),
            'mode': 'offline-publish' if args.offline_publish else ('transport-only' if args.transport_only else 'combined'),
            'datasets': args.dataset, 'updated_at_utc': utc_now(), 'model_fits': 0})
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        record_transport_failure(exc)
        # RangeZIP may retain a public signed redirect in an inner exception.
        # Report the actual failing outer stack without private URL cause chains.
        traceback.print_exception(type(exc), exc, exc.__traceback__, chain=False)
        raise SystemExit(1)
