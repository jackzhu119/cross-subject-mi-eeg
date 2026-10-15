"""Read-only validation of retained wheels with five exact manpage exceptions.

This is an operational repair of the 1efe9d1 wheel destination guard. It does
not extract, alter, download, install or import any wheel. The original helper
remains unchanged; its storage ceiling and all ordinary ZIP guards still apply.
The exception identity is the entire official wheel SHA plus member path, type,
length and SHA. No other ``data`` or ``headers`` destination is approved.
"""
from __future__ import annotations

from email.parser import BytesParser
import hashlib
from pathlib import Path
import stat
import urllib.parse
import zipfile


EMPTY_SHA256 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
FONTTOOLS_SHA256 = 'eb3c98cac93aac4b9f6e3ce2008325340b234cc9b0338ca6b513f31962a1e278'
SYMPY_SHA256 = 'e091cc3e99d2141a0ba2847328f5479b05d94a6635cb96148ccb3f34671bd8f5'
FONTTOOLS_PREFIX = 'fonttools-4.67.0.data/data/'
SYMPY_PREFIX = 'sympy-1.14.0.data/data/'
APPROVED = {
    FONTTOOLS_SHA256: {
        'distribution': ('fonttools', '4.67.0'),
        'members': {
            FONTTOOLS_PREFIX + 'share/': (0, EMPTY_SHA256, True),
            FONTTOOLS_PREFIX + 'share/man/': (0, EMPTY_SHA256, True),
            FONTTOOLS_PREFIX + 'share/man/man1/': (0, EMPTY_SHA256, True),
            FONTTOOLS_PREFIX + 'share/man/man1/ttx.1': (
                5377, '70b6e6fe938e8f50bbe93d905ef0f1cf00e3f6093e193779473b6f4ccb28b85c', False),
        },
    },
    SYMPY_SHA256: {
        'distribution': ('sympy', '1.14.0'),
        'members': {
            SYMPY_PREFIX + 'share/man/man1/isympy.1': (
                6659, 'f4365d48e2102e292b0131e56e4743674e0b0508a0643504d3fa025c10ef741b', False),
        },
    },
}


def _ordinary_child(path):
    """Reject existing symlink ancestors, including the supplied child itself."""
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('repair_child_absolute_path_required')
    if path != Path(str(path.resolve(strict=True))):
        raise ValueError('repair_child_symlink_or_noncanonical_path')
    for part in (path, *path.parents):
        if part.is_symlink() or not part.is_dir():
            raise ValueError('repair_child_symlink_or_non_directory_ancestor')
    return path


def _destination(environment, member):
    """PEP 427 data scheme is this venv prefix, never a donor/global prefix."""
    child = _ordinary_child(environment)
    components = member.rstrip('/').split('/')[2:]
    if components not in (['share'], ['share', 'man'], ['share', 'man', 'man1'],
                           ['share', 'man', 'man1', 'ttx.1'],
                           ['share', 'man', 'man1', 'isympy.1']):
        raise ValueError('unapproved_manpage_destination')
    destination = child.joinpath(*components)
    for node in (*destination.parents, destination):
        if node == child.parent:
            continue
        if node == child or child in node.parents:
            if node.is_symlink():
                raise ValueError('manpage_destination_symlink_escape')
            if node.exists() and node != destination and not node.is_dir():
                raise ValueError('manpage_destination_non_directory_ancestor')
    if destination.resolve(strict=False) != destination:
        raise ValueError('manpage_destination_not_confined_to_child')
    return destination


def _approve_member(wheel_sha256, item, archive, member, environment):
    """This narrow predicate is deliberately not configurable by CLI or JSON."""
    policy = APPROVED.get(wheel_sha256)
    if policy is None or policy['distribution'] != (item['name'].lower(), item['version']):
        raise ValueError('wheel_data_or_headers_destination_requires_separate_review')
    expected = policy['members'].get(member.filename)
    if expected is None:
        raise ValueError('wheel_data_or_headers_destination_requires_separate_review')
    count, digest, directory = expected
    kind = stat.S_IFMT(member.external_attr >> 16)
    if kind not in (0, stat.S_IFDIR if directory else stat.S_IFREG):
        raise ValueError('approved_manpage_member_type_mismatch')
    if member.is_dir() != directory or member.file_size != count:
        raise ValueError('approved_manpage_member_type_or_size_mismatch')
    if hashlib.sha256(archive.read(member)).hexdigest() != digest:
        raise ValueError('approved_manpage_member_sha_mismatch')
    destination = _destination(environment, member.filename)
    if destination.exists() and destination.is_dir() != directory:
        raise ValueError('approved_manpage_existing_destination_type_mismatch')
    return {'wheel_sha256': wheel_sha256, 'member': member.filename,
            'bytes': count, 'sha256': digest, 'is_directory': directory,
            'destination': str(destination)}


def validate_cached_wheels(folder, items, protected=(), *, runtime, environment):
    """Validate all retained bytes; return unchanged budget formula plus audit.

    ``runtime`` must be the independently authenticated original helper supplied
    by the repair controller. This function never calls pip or resolves packages.
    The controller separately binds the exact 79-item failure resolution.
    """
    runtime.validate_plan({'install': items}, protected)
    _ordinary_child(environment)
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError('wheel_cache_regular_directory_required')
    for node in folder.parents:
        if node.is_symlink():
            raise ValueError('wheel_cache_symlink_ancestor')
    files = list(folder.glob('*.whl'))
    if len(files) != len(items) or len(list(folder.iterdir())) != len(files):
        raise ValueError('wheel_plan_file_count_mismatch')
    if any(p.is_symlink() or not p.is_file() for p in files):
        raise ValueError('wheel_cache_regular_files_required')
    expected = {x['download_info']['archive_info']['hashes']['sha256']: x for x in items}
    actual = {p: runtime.sha(p) for p in files}
    if len(expected) != len(items) or set(actual.values()) != set(expected):
        raise ValueError('wheel_bytes_differ_from_resolved_plan')
    compressed = expanded = 0
    approved = []
    observed_special = {}
    for path in sorted(files):
        wheel_sha256 = actual[path]
        resolved = expected[wheel_sha256]
        url = urllib.parse.urlsplit(resolved['download_info']['url'])
        if (url.scheme != 'https' or url.hostname != 'files.pythonhosted.org'
                or url.username or url.password or url.fragment or url.query
                or urllib.parse.unquote(Path(url.path).name) != path.name):
            raise ValueError('unreviewed_cached_wheel_origin_or_filename')
        size = path.stat().st_size
        if size > runtime.MAX_WHEEL_BYTES:
            raise ValueError('single_wheel_storage_cap')
        compressed += size
        with zipfile.ZipFile(path) as z:
            names = [m.filename for m in z.infolist()]
            if len(names) != len(set(names)):
                raise ValueError('duplicate_wheel_members')
            metadata_names = [n for n in names if len(Path(n).parts) == 2 and n.endswith('.dist-info/METADATA')]
            if len(metadata_names) != 1:
                raise ValueError('wheel_single_distribution_metadata_required')
            if z.getinfo(metadata_names[0]).file_size > 1024**2:
                raise ValueError('wheel_metadata_size_cap')
            meta = BytesParser().parsebytes(z.read(metadata_names[0]))
            item = resolved['metadata']
            if runtime.norm(meta.get('Name', '')) != runtime.norm(item['name']) or meta.get('Version') != item['version']:
                raise ValueError('wheel_distribution_identity_different_from_plan')
            for m in z.infolist():
                p = Path(m.filename)
                raw_parts = m.filename.rstrip('/').split('/')
                if (p.is_absolute() or '..' in p.parts or '\\' in m.filename
                        or '\x00' in m.filename or any(s in ('', '.') for s in raw_parts)):
                    raise ValueError('unsafe_wheel_member')
                kind = stat.S_IFMT(m.external_attr >> 16)
                if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise ValueError('wheel_symlink_or_special_member')
                parts = p.parts
                if not parts:
                    raise ValueError('wheel_empty_member')
                top = parts[0]
                if top.endswith('.data'):
                    if len(parts) < 3:
                        if m.is_dir():
                            continue
                        raise ValueError('malformed_wheel_data_destination')
                    if parts[1] in ('purelib', 'platlib'):
                        top = parts[2]
                    elif parts[1] == 'scripts':
                        if parts[2].startswith(('python', 'pip')):
                            raise ValueError('wheel_cannot_replace_environment_interpreter')
                    else:
                        approved.append(_approve_member(wheel_sha256, item, z, m, environment))
                        observed_special.setdefault(wheel_sha256, set()).add(m.filename)
                if top in set(protected) or top in ('torch', 'torchgen', 'functorch', 'torchaudio', 'torio', 'triton', 'nvidia'):
                    raise ValueError('wheel_writes_into_protected_gpu_component')
                vetted_setuptools_hook = (parts == ('distutils-precedence.pth',)
                    and runtime.norm(item['name']) == 'setuptools' and m.file_size <= 1024
                    and hashlib.sha256(z.read(m)).hexdigest() == runtime.SETUPTOOLS_PTH_SHA)
                if (p.name.endswith('.pth') and not vetted_setuptools_hook) or p.name in ('sitecustomize.py', 'usercustomize.py'):
                    raise ValueError('wheel_may_inherit_or_execute_foreign_startup_code')
                expanded += m.file_size
        if wheel_sha256 in APPROVED and observed_special.get(wheel_sha256, set()) != set(APPROVED[wheel_sha256]['members']):
            raise ValueError('approved_manpage_wheel_member_set_incomplete')
    peak = compressed + 2 * expanded + 256 * 1024**2
    if peak > runtime.new_storage_cap():
        raise ValueError('new_runtime_peak_exceeds_3GiB')
    return {'wheel_compressed_bytes': compressed, 'wheel_expanded_bytes': expanded,
            'estimated_peak_new_bytes': peak, 'maximum_new_bytes': runtime.MAX_NEW_BYTES,
            'approved_manpage_members': approved}


def verify_installed_manpages(environment, approved_members):
    """Read back both documented files at the same venv-only destinations."""
    child = _ordinary_child(environment)
    expected_paths = {'share/man/man1/ttx.1', 'share/man/man1/isympy.1'}
    files = [x for x in approved_members if not x['is_directory']]
    if {str(Path(x['destination']).relative_to(child)) for x in files} != expected_paths or len(files) != 2:
        raise ValueError('both_approved_installed_manpages_required')
    for item in approved_members:
        destination = _destination(child, item['member'])
        if str(destination) != item['destination']:
            raise ValueError('approved_manpage_audit_destination_changed')
        if item['is_directory']:
            if not destination.is_dir():
                raise ValueError('installed_manpage_directory_missing')
        elif (not destination.is_file() or destination.stat().st_size != item['bytes']
                or hashlib.sha256(destination.read_bytes()).hexdigest() != item['sha256']):
            raise ValueError('installed_manpage_file_missing_or_changed')
    return {'status': 'BOTH_EXACT_MANPAGES_INSTALLED_IN_CHILD_ONLY', 'files': files}
