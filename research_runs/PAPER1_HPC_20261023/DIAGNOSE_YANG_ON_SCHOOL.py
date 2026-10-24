#!/usr/bin/env python3
"""Two bounded public GET probes; no cache, task, directory or EEG access."""
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import io
import http.client
import json
from pathlib import Path
import socket
import ssl
import sys
sys.dont_write_bytecode = True
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ERROR_CODES = frozenset(('AccessDenied', 'ExpiredToken', 'RequestExpired',
    'SignatureDoesNotMatch', 'AuthorizationQueryParametersError',
    'InvalidAccessKeyId', 'RequestTimeTooSkewed', 'InvalidToken'))


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def response_metadata(transport, url, status, headers):
    transport._validate_download_url(url)
    headers = headers or {}
    parsed = urllib.parse.urlsplit(url)
    media = headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
    kind = ('xml' if media in {'application/xml', 'text/xml'} else
            'html' if media == 'text/html' else 'plain' if media == 'text/plain' else
            'binary' if media == 'application/octet-stream' else 'other')
    row = {'request_hostname': parsed.hostname, 'response_hostname': parsed.hostname,
           'stage': 'storage' if parsed.hostname == transport.STORAGE_HOST else 'entry',
           'http_status': status, 'location_present': bool(headers.get('Location')),
           'content_type': kind, 'query_present': bool(parsed.query), 'signature_expired': None}
    try:
        date = parsedate_to_datetime(headers.get('Date', '')).astimezone(timezone.utc)
        row['response_date_utc'] = date.isoformat()
    except (ValueError, TypeError, OverflowError):
        pass
    age = headers.get('Age', '')
    if age.isdecimal() and len(age) <= 10:
        row['age_seconds'] = int(age)
    # Values never leave memory; only expiry relative to this process is emitted.
    query = urllib.parse.parse_qs(parsed.query, max_num_fields=40)
    try:
        expiry = None
        if 'Expires' in query and query['Expires'][0].isdecimal():
            expiry = datetime.fromtimestamp(int(query['Expires'][0]), timezone.utc)
        elif 'X-Amz-Date' in query and 'X-Amz-Expires' in query:
            expiry = datetime.strptime(query['X-Amz-Date'][0], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
            expiry += timedelta(seconds=int(query['X-Amz-Expires'][0]))
        if expiry is not None:
            row['signature_expired'] = expiry <= datetime.now(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        pass
    return row


def probe_route(transport, route_id, url, opener_factory=None):
    result = {'route': route_id, 'started_at_utc': utc_now(), 'hops': [],
              'body_bytes_read': 0, 'range_probe_verified': False}

    class TraceRedirect(transport._OfficialRedirect):
        count = 0

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            row = response_metadata(transport, req.full_url, code, headers)
            result['hops'].append(row)
            self.count += 1
            if self.count > 2:
                raise ValueError('Public redirect hop limit exceeded')
            try:
                following = super().redirect_request(req, fp, code, msg, headers, newurl)
            except ValueError:
                row['redirect_allowed'] = False
                raise
            row['redirect_allowed'] = True
            return following

    handler = TraceRedirect()
    opener = (opener_factory or urllib.request.build_opener)(handler)
    request = urllib.request.Request(url, method='GET', headers={
        'Range': 'bytes=0-0', 'Accept-Encoding': 'identity',
        'User-Agent': 'Paper1-HPC-data/1.0', 'Cache-Control': 'no-cache'})
    try:
        with opener.open(request, timeout=15) as response:
            result['hops'].append(response_metadata(transport, response.geturl(), response.status, response.headers))
            if (response.status != 206 or response.headers.get('Content-Range') !=
                    'bytes 0-0/65630556299' or response.headers.get('Content-Length') != '1' or
                    response.headers.get('Content-Encoding', 'identity') != 'identity'):
                raise ValueError('One-byte frozen-object range was not honored')
            body = response.read(2)
            result['body_bytes_read'] = len(body)
            if len(body) != 1:
                raise ValueError('One-byte response was incomplete')
            result['range_probe_verified'] = True
    except urllib.error.HTTPError as error:
        try:
            row = response_metadata(transport, error.url, error.code, error.headers)
            result['hops'].append(row)
            if row['stage'] == 'storage' and error.code == 403:
                body = error.read(8192)
                result['body_bytes_read'] = len(body)
                row['storage_error_code'] = 'unrecognized'
                row['known_expiry_error'] = False
                try:
                    root = ET.fromstring(body)
                    code = root.findtext('{*}Code')
                    if code in ERROR_CODES:
                        row['storage_error_code'] = code
                    row['known_expiry_error'] = code in {'ExpiredToken', 'RequestExpired'} or (
                        code == 'AccessDenied' and root.findtext('{*}Message') == 'Request has expired')
                except ET.ParseError:
                    pass
        except ValueError:
            result['failure_category'] = 'integrity_or_redirect_rejected'
        except (OSError, http.client.HTTPException):
            result['failure_category'] = 'error_body_unavailable'
        finally:
            error.close()
    except Exception as error:
        reason = error.reason if isinstance(error, urllib.error.URLError) else error
        result['failure_category'] = ('tls' if isinstance(reason, ssl.SSLError) else
            'dns' if isinstance(reason, socket.gaierror) else
            'integrity_or_redirect_rejected' if isinstance(error, ValueError) else
            'network_or_io' if isinstance(error, (OSError, urllib.error.URLError)) else 'unexpected_error')
    result['completed_at_utc'] = utc_now()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code', type=Path, default=Path('/public/home/zhuziyuan/projects/PAPER1_HPC_20261023'))
    args = parser.parse_args(argv)
    sys.path.insert(0, str(args.code.resolve()))
    from hpcmi.acquire import configure_download_trust
    from hpcmi import yang_transport as transport
    with redirect_stdout(io.StringIO()):
        trust = configure_download_trust()
    report = {'status': 'METADATA_DIAGNOSTIC_ONLY_NOT_SOURCE_OR_TRAINING_ACCEPTANCE',
              'scope': 'route_diagnostic_only', 'routes_share_storage_backend': True,
              'tls': trust, 'eeg_payload_read': False, 'zip_directory_read': False,
              'cache_or_tasks_modified': False, 'model_fits': 0,
              'routes': [probe_route(transport, route, url) for route, url in transport.ROUTES]}
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
