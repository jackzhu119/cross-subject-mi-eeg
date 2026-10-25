"""Download the archived eligible-v3 inputs before Slurm compute jobs (stdlib only)."""
from __future__ import annotations
import argparse
import base64
import errno
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
from p1_rangezip import member_record, selected_yang_members
from .yang_transport import open_yang_archive
from . import yang_privacy

STORAGE_HOST = 'nemar.s3.us-east-2.amazonaws.com'
YANG_LOCAL_ARCHIVE_NAME = 'WBCIC_SHU_Motor_Imagery_dataset.zip'
CHUNK = 8 * 1024 * 1024
_ROUTE_CONNECTION_ERRNOS = frozenset((errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ENETDOWN))
_SYSTEM_CA_BUNDLES = (
    '/etc/pki/tls/certs/ca-bundle.crt',
    '/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem',
    '/etc/ssl/certs/ca-certificates.crt',
)


def configure_download_trust():
    """Bind only this downloader to a verified existing CA store.

    OpenSSL may load capath roots lazily, so an existing hashed CA directory
    is accepted when its context still requires certificates and hostnames.
    Actual HTTPS requests must subsequently verify the peer as usual.
    """
    explicit = {}
    for key, directory in (('PAPER1_CA_BUNDLE', False), ('SSL_CERT_FILE', False), ('SSL_CERT_DIR', True)):
        if key in os.environ:
            path = Path(os.environ[key]).expanduser()
            valid = path.is_dir() if directory else path.is_file()
            if not os.environ[key] or not valid:
                raise ValueError('Invalid explicit download CA path: ' + key)
            explicit[key] = str(path)
    source, selected = 'python_default', None
    cafile = explicit.get('PAPER1_CA_BUNDLE') or explicit.get('SSL_CERT_FILE')
    capath = explicit.get('SSL_CERT_DIR')
    if cafile or capath:
        source = 'PAPER1_CA_BUNDLE' if explicit.get('PAPER1_CA_BUNDLE') else (
            'SSL_CERT_FILE' if cafile else 'SSL_CERT_DIR')
    else:
        selected = next((value for value in _SYSTEM_CA_BUNDLES if Path(value).is_file()), None)
        cafile = selected
        if selected:
            source = 'system_ca_bundle'
    try:
        context = ssl.create_default_context(cafile=cafile, capath=capath)
    except (OSError, ssl.SSLError):
        raise ValueError('Configured download CA store could not be loaded: ' + source) from None
    if context.verify_mode != ssl.CERT_REQUIRED or context.check_hostname is not True:
        raise ValueError('Download CA context must verify certificates and hostnames')
    count = context.cert_store_stats().get('x509_ca', 0)
    if not capath and not cafile:
        capath = ssl.get_default_verify_paths().capath
    hashed_capath = bool(capath and Path(capath).is_dir() and any(
        re.fullmatch(r'[0-9a-fA-F]{8}\.[0-9]+', path.name) and path.is_file()
        for path in Path(capath).iterdir()))
    if not count and not hashed_capath:
        raise ValueError('No trusted roots in the configured download CA store')
    if cafile:
        os.environ['SSL_CERT_FILE'] = cafile
    if explicit.get('SSL_CERT_DIR'):
        os.environ['SSL_CERT_DIR'] = explicit['SSL_CERT_DIR']
    report = {'event': 'download_tls_trust', 'source': source,
              'system_bundle': selected, 'trusted_ca_certificates': count,
              'hashed_ca_directory_available': hashed_capath,
              'certificate_verification_required': True, 'hostname_verification_required': True}
    print(json.dumps(report, sort_keys=True), flush=True)
    return report


class DatasetTransportFailure(RuntimeError):
    """Independent transfers remain incomplete; only bounded safe metadata."""
    def __init__(self, failures):
        def retryable(detail):
            status = detail.get('http_status')
            if status is not None:
                return status in {408, 429, 500, 502, 503, 504}
            return detail.get('category') in {'dns', 'connection', 'timeout', 'incomplete_read'}
        # A real denial or TLS failure must not become an infinite network retry
        # merely because another source happened to time out in the same pass.
        selected = next((row for row in failures if not retryable(row['details'])), failures[0])
        self.details = {**selected['details'], 'error_class': type(self).__name__,
                        'failed_datasets': [row['dataset'] for row in failures]}
        super().__init__('Independent dataset transfers incomplete: ' + ','.join(self.details['failed_datasets']))


def safe_error_details(error):
    """Describe bounded exception metadata without rendering messages or URLs."""
    if isinstance(error, DatasetTransportFailure):
        return dict(error.details)
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
        elif (isinstance(current, ConnectionError)
              or isinstance(current, OSError) and number in _ROUTE_CONNECTION_ERRNOS):
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
    timeout = 8 if urlsplit(url).netloc == 'bnci-horizon-2020.eu' else 60
    return urllib.request.build_opener(NoRedirect()).open(
        urllib.request.Request(url, headers=headers), timeout=timeout)


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


def _check_bnci_download_head():
    """Verify the repaired CA/path using HEAD only; do not read EEG bytes."""
    row = json.loads((VENDOR / 'config/bnci_manifest.json').read_text())['files'][0]
    basename = Path(urlsplit(row['url']).path).name
    alias = validate_bnci_location(row, 'https://lampx.tugraz.at/~bci/database/001-2014/' + basename)
    request = urllib.request.Request(alias, method='HEAD', headers={'Accept-Encoding': 'identity'})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=10) as response:
        if response.status != 200 or int(response.headers.get('Content-Length', '-1')) != row['size']:
            raise ValueError('Official HEAD did not match the frozen object length')
    print(json.dumps({'status': 'DOWNLOAD_ROUTE_TLS_HEAD_VERIFIED', 'http_status': 200,
                      'hostname': 'lampx.tugraz.at', 'expected_bytes': row['size'],
                      'eeg_body_read': False, 'full_file_sha256_verified': False}), flush=True)


def check_download_route(raw_dir=None):
    """Check remaining source routes, not full downloads or model inputs.

    Temporary network failures are reported for the background per-source
    retry path; scientific pin mismatches remain immediate errors.
    """
    if raw_dir is None:
        return _check_bnci_download_head()
    raw_dir = Path(raw_dir)
    checked, unavailable = [], []
    for dataset in ('bnci', 'yang', 'dreyer'):
        try:
            if dataset in {'bnci', 'dreyer'} and _pinned_native_ready(raw_dir, dataset):
                result = {'dataset': dataset, 'status': 'CACHED_NATIVE_INPUTS_VERIFIED'}
            elif dataset == 'bnci':
                _check_bnci_download_head()
                result = {'dataset': dataset, 'status': 'OFFICIAL_HEAD_VERIFIED'}
            elif dataset == 'yang':
                inventory, rows = _yang_pins_for_root(raw_dir / 'yang')
                if _yang_payloads_cached(raw_dir / 'yang', inventory, rows):
                    result = {'dataset': dataset, 'status': 'CACHED_YANG_PAYLOADS_VERIFIED',
                              'selected_members': len(rows),
                              'native_validation_may_be_pending': not yang_privacy.is_active(raw_dir / 'yang')}
                    checked.append(result)
                    print(json.dumps(result, sort_keys=True), flush=True)
                    continue
                if yang_privacy.is_active(raw_dir / 'yang'):
                    from .yang_nemar_download import official_object
                    row = next(r for r in rows if r['path'].endswith('/evt.bdf'))
                    with official_object(row, row['size'] - 1) as response:
                        if (response.status != 206 or response.headers.get('Content-Range') !=
                                'bytes %d-%d/%d' % (row['size'] - 1, row['size'] - 1, row['size'])
                                or len(response.read(2)) != 1):
                            raise ValueError('Privacy source one-byte range differs')
                    checked.append({'dataset': dataset, 'status': 'NEMAR_PRIVACY_NATIVE_ROUTE_VERIFIED',
                                    'source_profile': yang_privacy.PROFILE, 'range_probe_bytes': 1,
                                    'full_file_sha256_verified': False})
                    print(json.dumps(checked[-1], sort_keys=True), flush=True)
                    continue
                reader, archive, attestation, _ = _open_yang_source(raw_dir / 'yang', max_total_bytes=1024 * 1024)
                try:
                    if _archive_identity(attestation) != _archive_identity(inventory):
                        raise ValueError('Yang route metadata differs from the frozen ZIP identity')
                    members = selected_yang_members(archive)
                    pins = {row['path']: row for row in rows}
                    if len(members) != len(rows):
                        raise ValueError('Yang selected member inventory differs')
                    for member in members:
                        record = member_record(member)
                        if record != {key: pins[member.filename][key] for key in record}:
                            raise ValueError('Yang selected member differs from its frozen pin')
                    result = {'dataset': dataset, 'status': ('YANG_LOCAL_ZIP_DIRECTORY_VERIFIED'
                              if getattr(reader, 'source_kind', None) == 'local_official_zip'
                              else 'YANG_GET_RANGE_DIRECTORY_VERIFIED'),
                              'archive_bytes': attestation['archive_bytes'],
                              'central_directory_sha256': attestation['central_directory_sha256'],
                              'selected_members': len(members), 'eeg_payload_read': False}
                finally:
                    archive.close()
                    reader.close()
            else:
                row = json.loads((VENDOR / 'config/dreyer_manifest.json').read_text())['files'][0]
                with open_object(row, row['size'] - 1, nemar=True) as response:
                    if len(response.read(2)) != 1:
                        raise ValueError('Dreyer bounded range probe length differs')
                result = {'dataset': dataset, 'status': 'DREYER_GET_RANGE_VERIFIED',
                          'range_probe_bytes': 1, 'expected_file_bytes': row['size'],
                          'full_file_sha256_verified': False}
            checked.append(result)
            print(json.dumps(result, sort_keys=True), flush=True)
        except Exception as error:
            details = safe_error_details(error)
            if not _independent_network_failure(error, details):
                raise
            unavailable.append({'dataset': dataset, **details})
            print(json.dumps({'event': 'source_route_temporarily_unavailable',
                              'dataset': dataset, **details}, sort_keys=True), flush=True)
    report = {'status': 'DOWNLOAD_SOURCES_PREFLIGHT_VERIFIED' if not unavailable else 'DOWNLOAD_SOURCES_RETRY_PENDING',
              'checked_sources': checked, 'unavailable_sources': unavailable,
              'full_all_dataset_sha256_verified': False, 'model_fits': 0,
              'updated_at_utc': utc_now()}
    atomic_json(raw_dir / 'download_route_status.json', report)
    print(json.dumps(report, sort_keys=True), flush=True)
    return report


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
                and (isinstance(reason, (socket.gaierror, TimeoutError, ConnectionError, ssl.SSLError))
                     or isinstance(reason, OSError) and reason.errno in _ROUTE_CONNECTION_ERRNOS)
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
            failure.http_status = status
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


def transfer_object(root, row, *, nemar=False, attempts=4, object_opener=None):
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
                with (object_opener or open_object)(row, offset, nemar=nemar) as response:
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


def _yang_pins_for_root(root):
    if yang_privacy.is_active(root):
        return None, yang_privacy.pins(root)
    return yang_pins()


def _privacy_yang_manifest(root, rows, completed):
    """Report actual corrected identities, retaining original pins as ancestry."""
    contract = yang_privacy.load_contract()
    files = []
    for row in rows:
        entry = {'path': row['path'], 'size': row['size'], 'sha256': completed[row['path']],
                 'original_sha256': row.get('original_sha256'),
                 'original_zip_crc32': row['original_zip_crc32']}
        if 'crc32' in row:
            entry['crc32'] = row['crc32']
        files.append(entry)
    stable = {'dataset': 'Yang2025-2C', 'source_profile': yang_privacy.PROFILE,
              'data_doi': '10.25452/figshare.plus.22671172.v5',
              'provider_data_doi': '10.82901/nemar.nm000348', 'license': 'CC BY 4.0',
              'provider_dataset': contract['provider_dataset'], 'provider_version': contract['provider_version'],
              'profile_identity': {key: value for key, value in yang_privacy.current_identity().items()
                                   if key != 'adapter_sha256'},
              'integrity_scope': 'official privacy-corrected native full SHA256; six unchanged metadata CRC32; original SHA/ZIP CRC retained only as ancestry',
              'original_zip_crc_for_corrected_bdf_verified': False,
              'whole_archive_md5_verified': False, 'files': files}
    atomic_json(Path(root) / '_download_manifest.json', stable)
    return stable


def _publish_privacy_yang_offline(root):
    from .yang_nemar_download import _metadata_crc
    rows = yang_privacy.pins(root)
    completed = {}
    for row in rows:
        digest = verified_existing(root, row)
        if digest != row['sha256']:
            raise ValueError('Privacy native input incomplete; finish native transfer first')
        _metadata_crc(root, row)
        completed[row['path']] = digest
    return _privacy_yang_manifest(root, rows, completed)


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


def _open_yang_source(root, **kwargs):
    """An uploaded original ZIP is optional; an invalid one is never bypassed."""
    source = Path(root) / YANG_LOCAL_ARCHIVE_NAME
    if source.exists() or source.is_symlink():
        return open_yang_archive(local_archive=source, **kwargs)
    return open_yang_archive(**kwargs)


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
    if yang_privacy.is_active(root):
        from .yang_nemar_download import download
        rows = yang_privacy.pins(root)
        return _privacy_yang_manifest(root, rows, download(root, progress=progress))
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
    reader, archive, attestation, _ = _open_yang_source(root)
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
    if yang_privacy.is_active(root):
        return _publish_privacy_yang_offline(root)
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
    if yang_privacy.is_active(root):
        return acquire_yang_transport(root)
    inventory, rows = yang_pins()
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    completed = {row['path']: verified_existing(root, row) for row in rows}
    pending = [row for row in rows if completed[row['path']] is None]
    if pending:
        remaining = sum(row['size'] for row in pending)
        if shutil.disk_usage(root).free < remaining + 4 * 1024 ** 3:
            raise ValueError('Yang needs remaining raw bytes plus 4 GiB for transfer/cache; free storage first')
        reader, archive, attestation, _ = _open_yang_source(root)
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
            _, expected = _yang_pins_for_root(root)
            if yang_privacy.is_active(root) and observed.get('source_profile') != yang_privacy.PROFILE:
                raise ValueError('Yang manifest does not identify the selected privacy source')
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


def _yang_payloads_cached(root, inventory, rows):
    """Bounded saved receipts/stat only; never scan native payload hashes."""
    root = Path(root)
    native_only = yang_privacy.is_active(root)
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
        elif native_only or not _compressed_ready(root, row, inventory):
            return False
    return True


def network_payloads_ready(raw_dir):
    """Metadata/stat readiness; no network, decompression, EEG import or rehash."""
    raw_dir = Path(raw_dir)
    if not all(_pinned_native_ready(raw_dir, dataset) for dataset in ('bnci', 'dreyer')):
        return False
    inventory, rows = _yang_pins_for_root(raw_dir / 'yang')
    return _yang_payloads_cached(raw_dir / 'yang', inventory, rows)


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


def _independent_network_failure(error, details):
    """Continue independent sources, never hide integrity or local I/O errors."""
    if (isinstance(error, (ValueError, TypeError, AssertionError))
            and not isinstance(error, ssl.SSLError)
            and not (type(getattr(error, 'http_status', None)) is int and 400 <= error.http_status <= 599)):
        return False
    rows = [details] + [row for row in details.get('causes', []) if isinstance(row, dict)]
    if any(row.get('errno') in {1, 2, 5, 13, 28, 30, 122}
           and row.get('error_class') not in {'SSLError', 'SSLCertVerificationError'} for row in rows):
        return False
    category = details.get('category')
    if category == 'http':
        return type(details.get('http_status')) is int and 400 <= details['http_status'] <= 599
    return category in {'dns', 'connection', 'timeout', 'incomplete_read', 'tls', 'tls_certificate'}


def _transport_independent_datasets(raw_dir, datasets):
    """One pass per source, keeping completed inputs when another is unavailable."""
    counts = {'bnci': 18, 'yang': 312, 'dreyer': 174}
    privacy_native = yang_privacy.is_active(Path(raw_dir) / 'yang')
    completed = {name: 0 for name in datasets}
    # Full native manifests/receipts can seed an exact cached count without
    # repeating SHA scans. Incomplete sources are advanced by real callbacks.
    for name in datasets:
        if name in {'bnci', 'dreyer'} and _pinned_native_ready(raw_dir, name):
            completed[name] = counts[name]
    attempt = os.environ.get('PAPER1_TRANSFER_ATTEMPT', '')
    if not re.fullmatch(r'[0-9a-f]{32}', attempt):
        attempt = os.urandom(16).hex()
    failures = []
    for dataset in datasets:
        log('begin download/continue ' + dataset)
        def progress(done, total, dataset=dataset):
            if type(done) is not int or done < 0 or done > counts[dataset]:
                raise ValueError('Invalid completed transport object count')
            completed[dataset] = max(completed[dataset], done)
            atomic_json(Path(raw_dir) / 'transport_status.json', {
                'stage': 'network_transport', 'dataset': dataset,
                'completed_objects': sum(completed.values()), 'total_objects': sum(counts[d] for d in datasets),
                'dataset_completed_objects': completed[dataset], 'dataset_total_objects': counts[dataset],
                'completed_by_dataset': dict(completed), 'unavailable_datasets': [row['dataset'] for row in failures],
                'updated_at_utc': utc_now(), 'model_fits': 0,
                'yang_source_profile': yang_privacy.PROFILE if privacy_native else 'figshare_v5_original',
                'native_yang_validation_pending': not (privacy_native and completed.get('yang') == 312)})
        progress(completed[dataset], counts[dataset])
        try:
            if dataset == 'yang':
                acquire_yang_transport(Path(raw_dir) / dataset, progress=progress)
            else:
                acquire_pinned(dataset, Path(raw_dir) / dataset, progress=progress)
        except Exception as error:
            details = safe_error_details(error)
            if not _independent_network_failure(error, details):
                raise
            path = Path(raw_dir) / '.dataset-transfer-failures' / (attempt + '-' + dataset + '.json')
            if not path.exists():
                atomic_json(path, {'schema_version': 1, 'attempt_id': attempt, 'dataset': dataset,
                                   'updated_at_utc': utc_now(), **details})
            failures.append({'dataset': dataset, 'details': details})
            print(json.dumps({'event': 'dataset_transfer_unavailable', 'dataset': dataset,
                              'other_sources_continue': True, **details}, sort_keys=True), flush=True)
            progress(completed[dataset], counts[dataset])
        else:
            # A successful source method has completed its frozen inventory.
            # A failed method never receives this full-source increment.
            progress(counts[dataset], counts[dataset])
    if failures:
        atomic_json(Path(raw_dir) / 'acquisition_status.json', {
            'status': 'NETWORK_PARTIAL_SOURCES_UNAVAILABLE', 'mode': 'transport-only',
            'unavailable_datasets': [row['dataset'] for row in failures],
            'completed_objects': sum(completed.values()), 'total_objects': sum(counts[d] for d in datasets),
            'network_payloads_ready': False, 'model_fits': 0, 'updated_at_utc': utc_now()})
        raise DatasetTransportFailure(failures)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', required=True, type=Path)
    parser.add_argument('--dataset', choices=['all', 'bnci', 'yang', 'dreyer'], default='all')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--transport-only', action='store_true', help='Download native/ZIP-compressed payloads without decoding Yang')
    mode.add_argument('--offline-publish', action='store_true', help='Verify/publish cached payloads without network access')
    mode.add_argument('--check-download-route', action='store_true', help='Check official source routes with bounded HEAD/GET metadata requests')
    args = parser.parse_args(argv)
    if not args.offline_publish:
        configure_download_trust()
    if args.check_download_route:
        check_download_route(args.raw_dir)
        return 0
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    with acquisition_lock(args.raw_dir):
        datasets = ['bnci', 'yang', 'dreyer'] if args.dataset == 'all' else [args.dataset]
        if args.offline_publish:
            ready = publish_offline(args.raw_dir, datasets)
        elif args.transport_only:
            _transport_independent_datasets(args.raw_dir, datasets)
            ready = quick_raw_ready(args.raw_dir)
        else:
            for dataset in datasets:
                log('begin download/continue ' + dataset)
                if dataset == 'yang':
                    acquire_yang(args.raw_dir / dataset)
                else:
                    acquire_pinned(dataset, args.raw_dir / dataset)
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
