"""Native transport for an explicitly selected, separately pinned privacy source.

This module never activates a source profile and never validates a corrected
file against its ancestor's SHA or ZIP CRC. Scientific policy selection belongs
to the versioned contract and the preparation adapter.
"""
from contextlib import contextmanager
from pathlib import Path
import re
import urllib.error
from urllib.parse import quote, urlsplit
import zlib

SOURCE = 'https://data.nemar.org/nm000348/v1.0.5/'
STORAGE = 'nemar.s3.us-east-2.amazonaws.com'
PREFIX = 'WBCIC_SHU Motor Imagery dataset/'
METADATA = frozenset(('CHANGES', 'README.md', 'dataset_description.json',
                      'participants.json', 'participants_2C.tsv', 'participants_3C.tsv'))


def _source_url(row):
    path = row.get('path', '')
    if not isinstance(path, str) or not path.startswith(PREFIX):
        raise ValueError('Privacy source local path is outside the fixed inventory')
    relative = path[len(PREFIX):]
    matched = re.fullmatch(r'sourcedata/2C dataset/sub-(\d{3})/ses-(\d{2})/eeg/(data|evt)\.bdf', relative)
    if matched:
        if not 1 <= int(matched[1]) <= 51 or not 1 <= int(matched[2]) <= 3 or 'crc32' in row:
            raise ValueError('Privacy BDF source identity or current CRC declaration differs')
        remote = relative
    elif relative in METADATA:
        if not re.fullmatch('[a-f0-9]{8}', row.get('crc32', '')):
            raise ValueError('Original metadata CRC is required')
        remote = 'sourcedata/' + relative
    else:
        raise ValueError('Privacy source member is outside the fixed inventory')
    if type(row.get('size')) is not int or row['size'] <= 0 or not re.fullmatch('[a-f0-9]{64}', row.get('sha256', '')):
        raise ValueError('Pinned privacy native size and full SHA256 are required')
    expected = SOURCE + quote(remote, safe='/')
    if row.get('url') != expected:
        raise ValueError('Privacy source URL differs from its pinned native member')
    return expected


def _storage_url(row, location):
    try:
        parsed = urlsplit(location)
        expected = '/nm000348/objects/SHA256E-s%d--%s.bdf' % (row['size'], row['sha256'])
        valid = (isinstance(location, str) and len(location) <= 16384
                 and all(ord(c) >= 33 and ord(c) != 127 for c in location)
                 and parsed.scheme == 'https' and parsed.netloc == STORAGE
                 and parsed.path == expected and not parsed.fragment and '#' not in location
                 and len(parsed.query) <= 8192
                 and parsed.username is None and parsed.password is None
                 and row['path'].endswith('.bdf'))
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError('Privacy source redirect is not the exact pinned HTTPS object')
    return location


def _http_failure(error, phase):
    failure = ValueError('Official privacy source HTTP %d' % error.code)
    failure.http_status = error.code
    failure.request_phase = phase
    failure.location_present = bool(error.headers and error.headers.get('Location'))
    error.close()
    return failure


@contextmanager
def official_object(row, offset=0, *, nemar=True):
    """One exact official source hop; private query values remain in memory."""
    from . import acquire as a
    url = _source_url(row)
    if type(offset) is not int or not 0 <= offset < row['size']:
        raise ValueError('Privacy native range offset differs from the pinned size')
    response = None
    expected_url = url
    location = None
    try:
        try:
            response = a._open_no_redirect(url, offset)
        except urllib.error.HTTPError as error:
            if error.code != 302:
                raise _http_failure(error, 'canonical_open') from None
            location = error.headers.get('Location', '') if error.headers else ''
            error.close()
        # Leave the handled 302 exception before opening storage. Otherwise a
        # later storage 5xx can inherit the old 302 as exception context and
        # overwrite the current status in the existing safe diagnostic walker.
        if location is not None:
            expected_url = _storage_url(row, location)
            try:
                response = a._open_no_redirect(expected_url, offset)
            except urllib.error.HTTPError as error:
                raise _http_failure(error, 'official_mirror_open') from None
        if response.geturl() != expected_url:
            raise ValueError('Privacy source returned an unexpected additional redirect')
        yield response
    except urllib.error.URLError as error:
        # Keep typed causes for existing safe diagnostics without displaying URLs.
        failure = OSError('Official privacy source connection failed')
        failure.request_phase = 'official_mirror_open' if expected_url != url else 'canonical_open'
        failure.reason = error.reason
        raise failure from None
    finally:
        if response is not None:
            response.close()


def _selected_rows(root):
    from .yang_privacy import is_active, pins
    if not is_active(root):
        raise ValueError('Privacy native source requires explicit profile activation')
    rows = pins(root)
    for row in rows:
        _source_url(row)
    return rows


def _metadata_crc(root, row):
    if 'crc32' not in row:
        return
    from . import acquire as a
    checksum = 0
    with a.safe_child(root, row['path']).open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            checksum = zlib.crc32(block, checksum)
    if '%08x' % (checksum & 0xffffffff) != row['crc32']:
        raise ValueError('Privacy metadata original CRC differs; file retained')


def download(root, progress=None):
    """Reuse current receipts and partials; return actual completed native hashes."""
    from . import acquire as a
    root = Path(root)
    rows = _selected_rows(root)
    completed = {}
    for row in rows:
        digest = a.verified_existing(root, row)
        if digest is not None:
            _metadata_crc(root, row)
            completed[row['path']] = digest
    if progress:
        progress(len(completed), len(rows))
    remaining = 0
    for row in rows:
        if row['path'] in completed:
            continue
        target = a.safe_child(root, row['path'])
        partial = target.with_name(target.name + '.part')
        existing = partial.stat().st_size if partial.is_file() else 0
        if existing > row['size']:
            raise ValueError('Oversized privacy native partial retained')
        remaining += row['size'] - existing
    if remaining and a.shutil.disk_usage(root).free < remaining + 4 * 1024 ** 3:
        raise ValueError('Yang privacy transport needs remaining native bytes plus 4 GiB')
    for row in rows:
        if row['path'] in completed:
            continue
        digest = a.transfer_object(root, row, nemar=True, object_opener=official_object)
        _metadata_crc(root, row)
        completed[row['path']] = digest
        a.log('yang privacy %d/%d native objects current SHA256 verified' % (len(completed), len(rows)))
        if progress:
            progress(len(completed), len(rows))
    return completed
