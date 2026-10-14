#!/usr/bin/env python3
"""Explicit, bounded official-origin restoration for source diagnostics only.

No R2, target EEG, model fitting, credential handling or budget modification.
Default is manifest validation only. --execute starts one supervised worker.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import ssl
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlsplit
import uuid

MANIFEST_SHA256 = 'e553d65cd86e5309e077ccfea21a9bee6020c5d9d5040de12089c2b859770b86'
HOST = 'bnci-horizon-2020.eu'
DESTINATION_HOST = 'lampx.tugraz.at'
DESTINATION_PREFIX = '/~bci/database/001-2014/'
PRIOR_ATTEMPT = '20261014T105918Z-77294d31f0f5'
PRIOR_TRANSFER_SHA256 = 'd82adda1acce512581f31eb031bef22ce7ffb0e4a40b6b47eb9c379ae63a524f'
PRIOR_SUPERVISION_SHA256 = '617753ea87fbccd70e6ac3c0d99f96499f511cfa9e5afb317809f2a524073987'
PREFIX = '/database/data-sets/001-2014/'
MAX_SECONDS = 1800
SOCKET_SECONDS = 30
RESERVE_BYTES = 6 * 1024**3
CHUNK = 1024**2


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(CHUNK), b''):
            h.update(b)
    return h.hexdigest()


def no_symlink(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlink_rejected')
    return path


def validate_url(url, filename):
    u = urlsplit(url)
    if (u.scheme != 'https' or u.netloc != HOST or u.username or u.password
            or u.path != PREFIX + filename or u.query or u.fragment):
        raise ValueError('redirect_or_url_outside_exact_official_https_file')
    return url


def load_manifest(path):
    path = no_symlink(path)
    if sha(path) != MANIFEST_SHA256:
        raise ValueError('frozen_official_manifest_hash_mismatch')
    obj = json.loads(path.read_text())
    rows = obj['files']
    names = {f'A{i:02d}{s}.mat' for i in range(1,10) for s in ('T','E')}
    if len(rows) != 18 or {r['filename'] for r in rows} != names:
        raise ValueError('frozen_source_coverage_changed')
    for row in rows:
        validate_url(row['url'], row['filename'])
        if type(row['bytes']) is not int or row['bytes'] <= 0 or not re.fullmatch('[0-9a-f]{64}', row['sha256']):
            raise ValueError('frozen_source_identity_invalid')
    if sum(r['bytes'] for r in rows) != 779873919:
        raise ValueError('frozen_source_total_changed')
    return rows


def lampx_url(filename):
    if filename not in {f'A{i:02d}{suffix}.mat' for i in range(1,10) for suffix in ('T','E')}:
        raise ValueError('not_a_frozen_source_filename')
    return 'https://' + DESTINATION_HOST + DESTINATION_PREFIX + filename


class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, filename):
        super().__init__()
        self.filename, self.routes = filename, []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Accept one actual Location from the exact original GET, not a preselected mirror.
        if self.routes or code not in (301,302,303,307,308):
            raise ValueError('only_one_original_to_lampx_hop_allowed')
        validate_url(req.full_url, self.filename)
        if req.get_method() != 'GET':
            raise ValueError('original_get_required')
        destination = lampx_url(self.filename)
        if newurl != destination or headers.get('Location') != destination:
            raise ValueError('redirect_not_exact_same_file_lampx_location')
        result = super().redirect_request(req, fp, code, msg, headers, newurl)
        self.routes.append({'origin_url': req.full_url, 'http_status': code,
                            'location': destination, 'evidence': 'ACTUAL_ORIGIN_RESPONSE_LOCATION'})
        return result


def official_opener(row):
    context = ssl.create_default_context()
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    handler = OfficialRedirect(row['filename'])
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=context), handler)
    opener.source_redirect = handler
    return opener


def verified_response_route(row, response, opener):
    routes = getattr(getattr(opener, 'source_redirect', None), 'routes', [])
    final = response.geturl()
    if final == row['url'] and not routes:
        return {'initial_url': row['url'], 'final_url': final, 'hops': [], 'mode': 'ORIGINAL_DIRECT_200'}
    expected = lampx_url(row['filename'])
    if final != expected or len(routes) != 1 or routes[0]['origin_url'] != row['url'] or routes[0]['location'] != expected:
        raise ValueError('final_destination_without_verified_origin_redirect')
    return {'initial_url': row['url'], 'final_url': final, 'hops': routes, 'mode': 'VERIFIED_ONE_HOP_ORIGIN_LOCATION'}


def verify(path, row):
    no_symlink(path)
    if not path.is_file() or path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
        raise ValueError('existing_or_restored_source_size_sha256_mismatch')


def download_one(row, directory, attempt, deadline, *, opener_factory=official_opener, route_callback=None):
    p = no_symlink(Path(directory) / row['filename'])
    if p.exists():
        verify(p, row)
        return {'filename': row['filename'], 'status': 'REUSED_VERIFIED_CACHE', 'bytes': row['bytes'], 'sha256': row['sha256']}
    validate_url(row['url'], row['filename'])
    if time.monotonic() >= deadline:
        raise TimeoutError('diagnostic_transfer_deadline')
    partial = p.with_name('.' + p.name + '.' + attempt + '.partial')
    # Retained on every failure; never mistaken for a verified .mat file.
    with partial.open('xb') as output:
        opener = opener_factory(row)
        request = urllib.request.Request(row['url'], headers={'User-Agent': 'MI-EEG-frozen-source-diagnostic', 'Accept-Encoding': 'identity'})
        with opener.open(request, timeout=min(SOCKET_SECONDS, max(.001, deadline-time.monotonic()))) as response:
            if response.status != 200:
                raise ValueError('official_response_not_200')
            route = verified_response_route(row, response, opener)
            if route_callback is not None:
                route_callback(route)
            if response.headers.get('Content-Length') is not None and int(response.headers['Content-Length']) != row['bytes']:
                raise ValueError('official_content_length_mismatch')
            n, digest = 0, hashlib.sha256()
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError('diagnostic_transfer_deadline')
                block = response.read(CHUNK)
                if not block:
                    break
                n += len(block)
                output.write(block)
                digest.update(block)
                if n > row['bytes']:
                    raise ValueError('official_stream_oversize')
            output.flush()
            os.fsync(output.fileno())
            if n != row['bytes'] or digest.hexdigest() != row['sha256']:
                raise ValueError('official_complete_size_sha256_mismatch')
    verify(partial, row)
    # Exclusive install; a concurrent destination is never overwritten.
    os.link(partial, p)
    partial.unlink()
    return {'filename': row['filename'], 'status': 'RESTORED_OFFICIAL_EXACT_BYTES', 'bytes': row['bytes'], 'sha256': row['sha256'], 'response_route': route}


def atomic_json(path, value):
    path = no_symlink(path)
    tmp = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    with tmp.open('x') as f:
        json.dump(value, f, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


@contextmanager
def data_lock(root):
    root = no_symlink(root)
    root.mkdir(parents=True, exist_ok=True)
    fd = os.open(root / '.source-official-diagnostic.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('another_source_restoration_active') from None
        yield
    finally:
        os.close(fd)


def restore(rows, data_dir, evidence_dir, attempt, *, opener_factory=official_opener, reserve=RESERVE_BYTES, seconds=MAX_SECONDS):
    deadline = time.monotonic() + seconds
    data_dir, evidence_dir = no_symlink(data_dir), no_symlink(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = evidence_dir / (attempt + '-transfer.json')
    if receipt_path.exists():
        raise ValueError('attempt_receipt_already_exists')
    report = {'status': 'STARTED_SOURCE_RESTORATION_NOT_RECONSTRUCTION', 'attempt': attempt,
              'started_at_utc': now(), 'manifest_sha256': MANIFEST_SHA256,
              'maximum_seconds': seconds, 'file_attempts': 1, 'automatic_retries': 0,
              'source_expected_files': len(rows), 'files': [], 'scientific_fits': 0,
              'target_EEG_accessed': False, 'R2_requests': 0, 'budget_modified': False,
              'old_failed_job': '20261014T071918Z-exploratory-89b0c07d', 'old_failure_root_cause_resolved': False,
              'transport_revision': 'LAMPX_ONE_HOP_V2', 'prior_transport_attempt': PRIOR_ATTEMPT,
              'actual_response_routes': {}, 'new_bounded_attempts_authorized': 1}
    atomic_json(receipt_path, report)
    try:
        with data_lock(data_dir):
            directory = no_symlink(data_dir / 'bnci')
            directory.mkdir(exist_ok=True)
            missing = []
            # Check ALL existing files before any network request.
            for row in rows:
                path = no_symlink(directory / row['filename'])
                if path.exists():
                    verify(path, row)
                else:
                    missing.append(row)
            if shutil.disk_usage(data_dir).free < sum(r['bytes'] for r in missing) + reserve:
                raise ValueError('insufficient_disk_for_fixed_source_and_reserve')
            for row in rows:
                report['active_file'] = row['filename']
                atomic_json(receipt_path, report)
                def record_route(route):
                    report['actual_response_routes'][row['filename']] = route
                    atomic_json(receipt_path, report)
                result = download_one(row, directory, attempt, deadline, opener_factory=opener_factory, route_callback=record_route)
                report['files'].append(result)
                atomic_json(receipt_path, report)
            for row in rows:
                verify(directory / row['filename'], row)
            report['status'] = 'ALL_SOURCE_ORIGINALS_EXACT_BYTES_VERIFIED_NOT_INPUT_RECONSTRUCTION'
    except Exception as error:
        report.update(status='FAILED_OR_BLOCKED_SOURCE_RESTORATION', error_type=type(error).__name__)
        # No arbitrary HTTP response, headers, credential-bearing text or tracebacks.
        if type(getattr(error, 'code', None)) is int:
            report['http_status'] = error.code
        if isinstance(error, ValueError):
            report['error_code'] = str(error) if re.fullmatch('[a-z0-9_]+',str(error)) else 'invalid_transfer_metadata'
        report['retained_partials'] = [p.name for p in (data_dir/'bnci').glob('.A*.partial')]
        raise
    finally:
        report['finished_at_utc'] = now()
        report['request_routes_not_observed'] = [r['filename'] for r in rows if r['filename'] not in report['actual_response_routes']]
        atomic_json(receipt_path, report)


def supervise(command, log, *, timeout=MAX_SECONDS):
    with Path(log).open('xb') as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=stream, start_new_session=True)
        try:
            return process.wait(timeout=timeout), False
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
            except ProcessLookupError:
                pass
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            return 124, True


def claim_single_revision_attempt(data_dir, evidence_dir, attempt):
    data_dir, evidence_dir = no_symlink(data_dir), no_symlink(evidence_dir)
    for suffix, expected in (('transfer',PRIOR_TRANSFER_SHA256),('supervision',PRIOR_SUPERVISION_SHA256)):
        p = no_symlink(evidence_dir / (PRIOR_ATTEMPT + '-' + suffix + '.json'))
        if not p.is_file() or sha(p) != expected:
            raise ValueError('prior_failure_evidence_missing_or_changed')
    partial = no_symlink(data_dir / 'bnci' / ('.A01E.mat.' + PRIOR_ATTEMPT + '.partial'))
    if not partial.is_file() or partial.stat().st_size != 0:
        raise ValueError('prior_empty_partial_missing_or_changed')
    with data_lock(data_dir):
        marker = no_symlink(data_dir / '.official-lampx-v2-one-attempt.json')
        # Exclusive durable claim. Even uncertain startup consumes this single authorization.
        with marker.open('x') as f:
            json.dump({'revision':'LAMPX_ONE_HOP_V2','attempt':attempt,'prior_attempt':PRIOR_ATTEMPT,
                       'script_sha256':sha(Path(__file__)),'claimed_at_utc':now(),
                       'authorized_new_attempts':1,'automatic_retry':False},f,indent=2)
            f.write('\n');f.flush();os.fsync(f.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name('source_official_manifest.json'))
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--worker-attempt', help=argparse.SUPPRESS)
    args = parser.parse_args()
    rows = load_manifest(args.manifest)
    for path in (args.data_dir, args.evidence_dir):
        no_symlink(path)
        if '.git' in path.parts:
            raise ValueError('repository_storage_rejected')
        if any((p/'.git').is_file() or (p/'.git/HEAD').is_file() for p in (path.absolute(), *path.absolute().parents)):
            raise ValueError('raw_and_logs_must_be_outside_checkout')
    if not args.execute:
        print(json.dumps({'status': 'MANIFEST_ONLY_NO_NETWORK', 'files':len(rows), 'bytes':sum(r['bytes'] for r in rows), 'maximum_seconds':MAX_SECONDS, 'automatic_retries':0}))
        return
    if args.worker_attempt:
        if not re.fullmatch(r'[0-9TZ-]+-[0-9a-f]{12}',args.worker_attempt):
            raise ValueError('invalid_attempt')
        claim = no_symlink(args.data_dir / '.official-lampx-v2-one-attempt.json')
        claim_record = json.loads(claim.read_text()) if claim.is_file() else {}
        if claim_record.get('attempt') != args.worker_attempt or claim_record.get('script_sha256') != sha(Path(__file__)):
            raise ValueError('matching_parent_single_attempt_claim_required')
        try:
            restore(rows,args.data_dir,args.evidence_dir,args.worker_attempt)
        except Exception as error:
            print(json.dumps({'status':'SOURCE_RESTORATION_BLOCKED','error_type':type(error).__name__}),flush=True)
            raise SystemExit(2) from None
        return
    attempt = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:12]
    claim_single_revision_attempt(args.data_dir,args.evidence_dir,attempt)
    command = [sys.executable,str(Path(__file__).resolve()),'--manifest',str(args.manifest.resolve()),
               '--data-dir',str(args.data_dir.resolve()),'--evidence-dir',str(args.evidence_dir.resolve()),'--execute','--worker-attempt',attempt]
    code,timed_out = supervise(command,args.evidence_dir/(attempt+'-worker.log'))
    result = {'attempt':attempt,'worker_exit_code':code,'whole_operation_timeout':timed_out,
              'maximum_seconds':MAX_SECONDS,'termination_grace_seconds':5,'fits':0,'training_authorization':False,
              'old_failure_root_cause_resolved':False,'process_exit_is_not_platform_shutdown':True,
              'transport_revision':'LAMPX_ONE_HOP_V2','prior_transport_attempt':PRIOR_ATTEMPT}
    atomic_json(args.evidence_dir/(attempt+'-supervision.json'),result)
    print(json.dumps(result),flush=True)
    raise SystemExit(code)


if __name__ == '__main__':
    main()
