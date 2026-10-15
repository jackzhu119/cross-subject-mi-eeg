"""Strict, separately reviewed NEMAR canonical GET plus at most one storage GET.

No CLI or automatic recovery. A signed storage URL exists only transiently in
memory; its exact path is derived from frozen SHA256E metadata, never reported as
an observed live-path match. Scientific bytes and all original storage guards
remain those of the unchanged pinned official_edf_transport helper.
"""
from contextlib import contextmanager
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shutil
import stat
import urllib.error
import urllib.request
from urllib.parse import urlsplit

HERE = Path(__file__).absolute().parent
ORIGINAL_SHA = '1aa2da0b710b3ef109d00d19c75a00fda013a79f947e9aebbe3480c8e99b895f'
STORAGE_HOST = 'nemar.s3.us-east-2.amazonaws.com'
MAX_QUERY = 8192


def _original():
    path = HERE / 'official_edf_transport.py'
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file() or path.stat().st_size > 65536:
        raise ValueError('fixed_original_transport_required')
    if hashlib.sha256(path.read_bytes()).hexdigest() != ORIGINAL_SHA:
        raise ValueError('fixed_original_transport_changed')
    spec = importlib.util.spec_from_file_location('_paper1_unchanged_official_transport_single_hop', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORIGINAL = _original()
CHUNK, GIB, NBYTES = ORIGINAL.CHUNK, ORIGINAL.GIB, ORIGINAL.NBYTES
frozen_plan = ORIGINAL.frozen_plan
safe_path = ORIGINAL.safe_path
digest_file = ORIGINAL.digest_file
verify_cached_manifest = ORIGINAL.verify_cached_manifest
FROZEN_SHA256 = ORIGINAL.FROZEN_SHA256


class ControlledTransportError(ValueError):
    """Only a controlled code and non-secret whitelisted HTTP observations."""
    def __init__(self, code, safe_metadata=None):
        if not isinstance(code, str) or not re.fullmatch('[a-z][a-z0-9_]{0,95}', code):
            code = 'controlled_transport_failed'
        super().__init__(code)
        self.code = code
        self.safe_metadata = dict(safe_metadata or {})


def _safe_http(status=None, location=None):
    # Unknown origins are deliberately classified rather than copied verbatim.
    result = {'http_status': status if type(status) is int and 100 <= status <= 599 else None,
        'location_scheme': None, 'location_hostname': None, 'location_port': None,
        'query_present': False, 'fragment_present': False}
    if isinstance(location, str):
        if len(location) > MAX_QUERY + 1024:
            result.update(query_present='?' in location, fragment_present='#' in location)
            return result
        try:
            parts = urlsplit(location)
            port = parts.port
        except ValueError:
            return result
        result.update(location_scheme=parts.scheme if parts.scheme in ('https', 'http') else 'other',
            location_hostname=parts.hostname if parts.hostname in ('data.nemar.org', STORAGE_HOST) else 'other',
            location_port=port, query_present='?' in location, fragment_present='#' in location)
    return result


def _frozen_row(row):
    invalid = False
    try:
        ORIGINAL.validate_row(row)
        invalid = {r['provider_path']: r for r in frozen_plan()['files']}.get(row['provider_path']) != row
    except Exception:
        invalid = True
    if invalid:
        raise ControlledTransportError('exact_frozen_canonical_row_required')


def _storage_url(row, location):
    safe = _safe_http(302, location)
    invalid = (not isinstance(location, str) or len(location) > MAX_QUERY + 1024
        or any(ord(c) < 33 or ord(c) == 127 for c in location))
    parts = None
    if not invalid:
        try:
            parts = urlsplit(location)
            invalid = (parts.scheme != 'https' or parts.netloc != STORAGE_HOST or parts.hostname != STORAGE_HOST
                or parts.username is not None or parts.password is not None or parts.port is not None
                or '#' in location or parts.fragment or len(parts.query) > MAX_QUERY
                or parts.path != '/nm000250/objects/SHA256E-s' + str(row['bytes']) + '--' + row['sha256'] + '.edf')
        except ValueError:
            invalid = True
    if invalid:
        raise ControlledTransportError('location_not_exact_derived_frozen_storage_object', safe)
    return location


def _secure_factory():
    opener = ORIGINAL.secure_opener()
    opener.addheaders = []
    return opener


_opener_factory = _secure_factory  # Private offline-test seam, never a CLI/transport argument.


def _request(url, stage):
    response, status, location, failed = None, None, None, None
    try:
        request = urllib.request.Request(url, headers={'Accept-Encoding': 'identity'}, method='GET')
        response = _opener_factory().open(request, timeout=30)
    except urllib.error.HTTPError as error:
        status = error.code
        location = error.headers.get('Location') if error.headers is not None else None
        try:
            error.close()
        except Exception:
            pass
    except Exception:
        failed = stage + '_request_open_failed'
    # Raise outside the except blocks: no raw HTTP exception with signed URL is
    # retained as __context__, message, metadata, or rendered exception chain.
    if failed:
        raise ControlledTransportError(failed)
    if response is not None:
        status = response.status
        location = response.headers.get('Location')
    return response, status, location


def _close(response):
    if response is not None:
        try:
            response.close()
        except Exception:
            pass


@contextmanager
def open_frozen_object(row, *, control_check):
    _frozen_row(row)
    control_check()
    response, status, location = _request(row['url'], 'canonical')
    route = {'http_status': 200, 'canonical_http_status': status, 'one_hop_host': None,
        'query_present': False, 'fragment_present': False, 'redirects_followed': 0}
    expected_url = row['url']
    if status == 302:
        _close(response)
        transient_url = _storage_url(row, location)
        control_check()  # A302 is not a grant to continue after slot revocation.
        response, status, location = _request(transient_url, 'storage')
        if type(status) is not int or status != 200:
            _close(response)
            raise ControlledTransportError('storage_http_status_rejected', _safe_http(status, location))
        expected_url = transient_url
        route.update(one_hop_host=STORAGE_HOST, query_present='?' in transient_url, redirects_followed=1)
    elif type(status) is not int or status != 200:
        _close(response)
        raise ControlledTransportError('canonical_http_status_rejected', _safe_http(status, location))
    try:
        # Check the actual transient response URL, never replace/fake geturl().
        if response is None or response.geturl() != expected_url:
            raise ControlledTransportError('actual_response_url_changed', _safe_http(status))
        yield response, route
    finally:
        _close(response)


def _strict_transport_one(row, root, *, control_check, min_free_bytes, paper2_reserve_bytes,
                          max_new_bytes):
    _frozen_row(row)
    for name, value in (('min_free_bytes', min_free_bytes), ('paper2_reserve_bytes', paper2_reserve_bytes),
                        ('max_new_bytes', max_new_bytes)):
        if type(value) is not int or value < 0:
            raise ControlledTransportError('integer_resource_limit_required')
    if min_free_bytes < 10 * GIB or max_new_bytes > NBYTES or max_new_bytes < row['bytes']:
        raise ControlledTransportError('transport_disk_or_byte_cap_invalid')
    control_check()
    target = safe_path(root, row['restore_relative_path'])
    if target.exists():
        if not stat.S_ISREG(target.stat().st_mode) or target.stat().st_size != row['bytes'] or digest_file(target) != row['sha256']:
            raise ControlledTransportError('existing_object_corrupt_preserved')
        control_check()
        return {'path': row['restore_relative_path'], 'bytes': row['bytes'], 'sha256': row['sha256'],
                'status': 'existing_exact_bytes_reused', 'network_bytes': 0}
    temporary = target.with_name(target.name + '.partial')
    if temporary.exists() or temporary.is_symlink():
        raise ControlledTransportError('existing_partial_preserved_manual_review_required')
    ancestor = target.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    required = row['bytes'] + min_free_bytes + paper2_reserve_bytes
    if shutil.disk_usage(ancestor).free < required:
        raise ControlledTransportError('insufficient_disk_for_object_floor_and_paper2_reserve')
    target.parent.mkdir(parents=True, exist_ok=True)
    safe_path(root, row['restore_relative_path'])
    control_check()
    with open_frozen_object(row, control_check=control_check) as (response, http_route):
        content_length = response.headers.get('Content-Length')
        if not isinstance(content_length, str) or not content_length.isdecimal() or int(content_length) != row['bytes']:
            raise ControlledTransportError('http_content_length_not_exact_frozen_size')
        if response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
            raise ControlledTransportError('http_content_encoding_not_identity')
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(temporary, flags, 0o600)
        total, hashed = 0, hashlib.sha256()
        with os.fdopen(fd, 'wb') as output:
            while True:
                control_check()
                if shutil.disk_usage(target.parent).free < min_free_bytes + paper2_reserve_bytes:
                    raise ControlledTransportError('paper2_reserved_free_space_reached_partial_preserved')
                block = response.read(min(CHUNK, row['bytes'] - total + 1))
                if not block:
                    break
                total += len(block)
                if total > row['bytes'] or total > max_new_bytes:
                    raise ControlledTransportError('http_body_exceeds_frozen_size_partial_preserved')
                control_check()
                if shutil.disk_usage(target.parent).free < min_free_bytes + paper2_reserve_bytes + len(block):
                    raise ControlledTransportError('paper2_reserved_free_space_before_write_partial_preserved')
                output.write(block)
                hashed.update(block)
            output.flush()
            os.fsync(output.fileno())
        if total != row['bytes'] or hashed.hexdigest() != row['sha256']:
            raise ControlledTransportError('download_size_or_sha256_mismatch_partial_preserved')
        control_check()
        os.link(temporary, target, follow_symlinks=False)
        temporary.unlink()
        directory_fd = os.open(target.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    return {'path': row['restore_relative_path'], 'bytes': total, 'sha256': hashed.hexdigest(),
            'status': 'new_exact_bytes_atomic_publish', 'network_bytes': total, 'http_route': http_route}


def transport_one(row, root, *, control_check, min_free_bytes, paper2_reserve_bytes, max_new_bytes):
    failed = None; sanitized = None
    try:
        return _strict_transport_one(row, root, control_check=control_check, min_free_bytes=min_free_bytes,
            paper2_reserve_bytes=paper2_reserve_bytes, max_new_bytes=max_new_bytes)
    except ControlledTransportError as error:
        sanitized = (error.code, dict(error.safe_metadata))
    except Exception:
        failed = 'controlled_transport_or_resource_failure_partial_preserved'
    if sanitized is not None:
        # A new exception has no inner frames/locals containing the transient
        # signed URL, original network exception, or response Location.
        raise ControlledTransportError(*sanitized)
    if failed:
        raise ControlledTransportError(failed)
