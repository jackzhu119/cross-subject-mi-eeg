"""HPC transport for the frozen Yang ZIP; scientific/vendor code is unchanged.

Figshare supplies a signed GET download. HEAD on that signed object may be
forbidden. Resolution therefore requests a one-byte GET range and validates the
same frozen object before reusing the original ZIP-directory parser.
"""
from __future__ import annotations

import hashlib
import http.client
import json
from pathlib import Path
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

VENDOR = Path(__file__).resolve().parents[1] / 'vendor' / 'eligible_v3'
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))
import p1_rangezip as frozen

FILE_ID = 51001884
ARTICLE_METADATA_URL = 'https://api.figshare.com/v2/articles/22671172/versions/5'
ROUTES = (
    ('figshare_download', frozen.YANG_URL),
    ('figshare_api_download', 'https://api.figshare.com/v2/file/download/51001884'),
)
STORAGE_HOST = 's3-eu-west-1.amazonaws.com'
STORAGE_PATH = '/ptemp-plus-8475456492/51001884/WBCIC_SHUMotorImagerydataset.zip'
_SOURCE_PATHS = {
    'ndownloader.figshare.com': '/files/51001884',
    'api.figshare.com': '/v2/file/download/51001884',
}


class YangTransportError(OSError):
    """Controlled network failure: no private signed URL in its message."""
    def __init__(self, code, *, status=None):
        super().__init__(code)
        self.error_code = code
        if status is not None:
            self.http_status = status


class _ExpiredLink(YangTransportError):
    pass


def _validate_download_url(url):
    try:
        parsed = urllib.parse.urlsplit(url)
        valid = (isinstance(url, str) and len(url) <= 16384
                 and all(ord(c) >= 33 and ord(c) != 127 for c in url)
                 and parsed.scheme == 'https' and parsed.port is None
                 and parsed.username is None and parsed.password is None
                 and len(parsed.query) <= 8192 and not parsed.fragment and '#' not in url)
        if parsed.hostname in _SOURCE_PATHS:
            valid = valid and parsed.netloc == parsed.hostname and parsed.path == _SOURCE_PATHS[parsed.hostname] and not parsed.query
        elif parsed.hostname == STORAGE_HOST:
            valid = valid and parsed.netloc == STORAGE_HOST and parsed.path == STORAGE_PATH
        else:
            valid = False
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError('Yang download redirect is outside the verified official object')
    return url


class _OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_download_url(req.full_url)
        _validate_download_url(newurl)
        if req.get_method() != 'GET' or code not in {301, 302, 303, 307, 308}:
            raise ValueError('Yang download uses only verified official GET redirects')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _network_retryable(error):
    if isinstance(error, urllib.error.HTTPError):
        return error.code in {408, 429, 500, 502, 503, 504}
    if isinstance(error, YangTransportError):
        return getattr(error, 'http_status', None) in {408, 429, 500, 502, 503, 504}
    if isinstance(error, urllib.error.URLError):
        return _network_retryable(error.reason)
    if isinstance(error, ssl.SSLError):
        return False
    return isinstance(error, (TimeoutError, ConnectionError, socket.gaierror, http.client.IncompleteRead)) or (
        isinstance(error, OSError) and getattr(error, 'errno', None) in {100, 101, 113})


def _controlled_error(error, code):
    if isinstance(error, YangTransportError):
        return error
    result = YangTransportError(code, status=getattr(error, 'code', None)
                                if isinstance(error, urllib.error.HTTPError) else None)
    # Preserve only sanitized typed causes. HTTPError may carry a private
    # signed URL, and urllib reasons can include private proxy strings.
    reason = error.reason if isinstance(error, urllib.error.URLError) else error
    if isinstance(reason, ssl.SSLError):
        result.reason = ssl.SSLError('Yang TLS verification failed')
    elif isinstance(reason, socket.gaierror):
        result.reason = socket.gaierror(reason.errno, 'Yang name resolution failed')
    elif isinstance(reason, TimeoutError):
        result.reason = TimeoutError('Yang network timeout')
    elif isinstance(reason, http.client.IncompleteRead):
        result.reason = http.client.IncompleteRead(b'', reason.expected)
    elif isinstance(reason, ConnectionError):
        result.reason = ConnectionError('Yang connection failed')
    elif isinstance(reason, OSError) and not isinstance(reason, urllib.error.HTTPError):
        result.reason = OSError(reason.errno, 'Yang network request failed')
    return result


def verify_official_file_metadata(opener=None):
    """Optional public-metadata check; never substitutes for frozen ZIP hashes."""
    opener = opener or urllib.request.build_opener()
    request = urllib.request.Request(ARTICLE_METADATA_URL, headers={'Accept': 'application/json'})
    with opener.open(request, timeout=15) as response:
        if response.status != 200:
            raise YangTransportError('yang_metadata_status', status=response.status)
        body = response.read(262145)
    if len(body) > 262144:
        raise ValueError('Yang metadata response exceeded its bound')
    record = json.loads(body)
    rows = [item for item in record.get('files', []) if item.get('id') == FILE_ID]
    if len(rows) != 1:
        raise ValueError('Official Yang metadata does not identify the frozen file')
    row = rows[0]
    if (record.get('doi') != '10.25452/figshare.plus.22671172.v5'
            or row.get('size') != frozen.YANG_BYTES
            or row.get('supplied_md5') != frozen.YANG_ARCHIVE_MD5
            or row.get('computed_md5') != frozen.YANG_ARCHIVE_MD5
            or row.get('download_url') != frozen.YANG_URL):
        raise ValueError('Official Yang metadata differs from the frozen object')
    license_record = record.get('license', {})
    if license_record.get('name') != 'CC BY 4.0':
        raise ValueError('Official Yang license differs from the recorded license')
    return {'file_id': FILE_ID, 'archive_bytes': frozen.YANG_BYTES,
            'published_md5_matches_frozen_pin': True, 'license': 'CC BY 4.0',
            'doi': record['doi'], 'whole_archive_md5_verified': False}


class YangRangeReader(frozen.HTTPRangeReader):
    """Seekable strict ranges, with two verified official entry routes."""
    def __init__(self, *, timeout=30, retries=4, chunk_bytes=8 * 1024 * 1024,
                 max_total_bytes=None, routes=None, opener=None):
        self._routes = tuple(ROUTES if routes is None else routes)
        if not self._routes:
            raise ValueError('At least one verified Yang route is required')
        for route_id, url in self._routes:
            if not isinstance(route_id, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,50}', route_id):
                raise ValueError('Invalid public Yang route identifier')
            _validate_download_url(url)
            if urllib.parse.urlsplit(url).hostname == STORAGE_HOST:
                raise ValueError('A private storage signature is not a persistent route')
        self._opener = opener or urllib.request.build_opener(_OfficialRedirect())
        self._route_index = 0
        super().__init__(frozen.YANG_URL, frozen.YANG_BYTES, timeout=timeout, retries=retries,
                         chunk_bytes=chunk_bytes, max_total_bytes=max_total_bytes)

    def _budget(self, count):
        if self.max_total_bytes is not None and self.bytes_received + count > self.max_total_bytes:
            raise ValueError('Metadata-only network byte limit exceeded')

    def _expire_or_deny(self, error):
        status = error.code
        expired = False
        _validate_download_url(error.url)
        if status == 403 and urllib.parse.urlsplit(error.url).hostname == STORAGE_HOST:
            remaining = 8193 if self.max_total_bytes is None else max(0, self.max_total_bytes - self.bytes_received)
            body = error.read(min(8193, remaining))
            self.bytes_received += len(body)
            if len(body) <= 8192:
                try:
                    root = ET.fromstring(body)
                    code = root.findtext('Code')
                    message = root.findtext('Message')
                    expired = code in {'ExpiredToken', 'RequestExpired'} or (
                        code == 'AccessDenied' and message == 'Request has expired')
                except ET.ParseError:
                    pass
        error.close()
        if expired:
            raise _ExpiredLink('yang_public_signed_link_expired', status=403) from None
        raise YangTransportError('yang_http_' + str(status), status=status) from None

    def _request_range(self, url, start, count):
        _validate_download_url(url)
        self._budget(count)
        expected_range = f'bytes {start}-{start + count - 1}/{self.size}'
        request = urllib.request.Request(url, method='GET', headers={
            'Range': f'bytes={start}-{start + count - 1}', 'Accept-Encoding': 'identity',
            'User-Agent': 'Paper1-HPC-data/1.0', 'Cache-Control': 'no-cache'})
        self.request_count += 1
        try:
            response = self._opener.open(request, timeout=self.timeout)
        except urllib.error.HTTPError as error:
            self._expire_or_deny(error)
        with response:
            _validate_download_url(response.geturl())
            if response.status != 206:
                # A full 200 response might represent all 65 GB. Never read it.
                raise ValueError('Yang server did not honor the exact byte range')
            if response.headers.get('Content-Range') != expected_range:
                raise ValueError('Yang Content-Range differs from the frozen size or requested range')
            if response.headers.get('Content-Encoding', 'identity') != 'identity':
                raise ValueError('Yang range response is unexpectedly encoded')
            if response.headers.get('Content-Length') is not None and int(response.headers['Content-Length']) != count:
                raise ValueError('Yang range Content-Length differs')
            data = response.read(count + 1)
            self.bytes_received += len(data)
            if len(data) < count:
                raise http.client.IncompleteRead(data, count - len(data))
            if len(data) > count:
                raise ValueError('Yang range body exceeds the requested length')
            return data, response.geturl()

    def _resolve(self):
        last = None
        # Each source is attempted once. Only typed network/5xx failures rotate
        # sources; an explicit fresh 401/403 denial is never bypassed.
        for step in range(len(self._routes)):
            index = (self._route_index + step) % len(self._routes)
            route_id, url = self._routes[index]
            refreshed = False
            while True:
                try:
                    data, active = self._request_range(url, 0, 1)
                    self._active_url, self._route_index = active, index
                    self._cache.append((0, data))
                    self._cache = self._cache[-16:]
                    print(json.dumps({'event': 'yang_route_verified', 'route': route_id,
                                      'method': 'GET', 'range_probe_bytes': 1, 'http_status': 206,
                                      'storage_hostname': urllib.parse.urlsplit(active).hostname,
                                      'archive_bytes': self.size}), flush=True)
                    return
                except _ExpiredLink as error:
                    if refreshed:
                        last = error
                        break
                    refreshed = True
                except (OSError, urllib.error.URLError, http.client.HTTPException) as error:
                    last = error
                    if not _network_retryable(error):
                        raise _controlled_error(error, 'yang_resolution_failed') from None
                    break
        raise _controlled_error(last, 'yang_all_official_routes_temporarily_unavailable') from None

    def _get_range(self, start, count):
        end = start + count - 1
        for cached_start, cached_bytes in self._cache:
            if cached_start <= start and end < cached_start + len(cached_bytes):
                lo = start - cached_start
                return cached_bytes[lo:lo + count]
        refreshed, error = False, None
        for attempt in range(self.retries + 1):
            try:
                data, _ = self._request_range(self._active_url, start, count)
                if count <= 1048576:
                    self._cache.append((start, data))
                    self._cache = self._cache[-16:]
                return data
            except _ExpiredLink as current:
                error = current
                if refreshed:
                    raise YangTransportError('yang_signed_link_refresh_exhausted', status=403) from None
                refreshed = True
                self._resolve()
            except (OSError, urllib.error.URLError, http.client.HTTPException) as current:
                error = current
                if not _network_retryable(current):
                    raise _controlled_error(current, 'yang_range_failed') from None
                if attempt == self.retries:
                    break
                self._route_index = (self._route_index + 1) % len(self._routes)
                self._resolve()
            if attempt < self.retries:
                time.sleep(min(2 ** attempt, 8))
        raise _controlled_error(error, 'yang_range_retries_exhausted') from None


def open_yang_archive(*, verify_pin=True, max_total_bytes=None, routes=None, opener=None):
    """Original scientific ZIP parser with the HPC GET-only transport adapter."""
    reader = YangRangeReader(max_total_bytes=max_total_bytes, routes=routes, opener=opener)
    try:
        attestation, directory = frozen.zip_directory_attestation(reader)
        if verify_pin and attestation['central_directory_sha256'] != frozen.YANG_CENTRAL_SHA256:
            raise ValueError('Yang archive central-directory SHA256 differs from the frozen pin')
        archive = zipfile.ZipFile(reader)
        items = archive.infolist()
        if len(items) != attestation['member_count']:
            archive.close()
            raise ValueError('Yang ZIP member count differs from its directory')
        if len({item.filename for item in items}) != len(items):
            archive.close()
            raise ValueError('Duplicate Yang archive member paths are not accepted')
        return reader, archive, attestation, directory
    except BaseException:
        reader.close()
        raise
