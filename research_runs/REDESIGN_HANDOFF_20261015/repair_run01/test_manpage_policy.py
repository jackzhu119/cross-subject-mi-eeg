"""Synthetic ZIP safety tests only: no original wheels, install, network or EEG.

Exact official SHA positive cases mock only byte-digest observations for marked
synthetic payloads; they are unit tests, never actual wheel-byte verification.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import stat
from types import SimpleNamespace
import zipfile

import pytest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('repair_manpage_policy_tested', HERE / 'manpage_policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
spec = importlib.util.spec_from_file_location('repair_original_runtime_tested',
    HERE.parents[1] / 'REDESIGN_HANDOFF_20261014/runtime_transition/isolated_training_runtime.py')
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)


def make_wheel(folder, name='ordinary', version='1.0', members=(), filename=None):
    file = folder / (filename or f'{name}-{version}-py3-none-any.whl')
    with zipfile.ZipFile(file, 'w') as z:
        z.writestr(f'{name}-{version}.dist-info/METADATA', f'Name: {name}\nVersion: {version}\n')
        for member, payload, mode in members:
            info = zipfile.ZipInfo(member)
            info.external_attr = mode << 16
            z.writestr(info, payload)
    return file


def item(file, name='ordinary', version='1.0', digest=None):
    return {'metadata': {'name': name, 'version': version}, 'download_info': {
        'url': f'https://files.pythonhosted.org/packages/{file.name}',
        'archive_info': {'hashes': {'sha256': digest or original.sha(file)}}}}


@pytest.fixture
def fixture(tmp_path):
    cache = tmp_path / 'cache'; cache.mkdir()
    child = tmp_path / 'child'; child.mkdir()
    return cache, child


def validate(cache, child, items, runtime=original):
    return policy.validate_cached_wheels(cache, items, runtime=runtime, environment=child)


def manpage_fixture(cache, monkeypatch, extra=(), mutated=None):
    """Mock official digest checks explicitly; never claim real wheels exist."""
    payloads = {'ttx.1': b'f' * 5377, 'isympy.1': b's' * 6659}
    real_sha = hashlib.sha256
    digest_map = {payloads['ttx.1']: policy.APPROVED[policy.FONTTOOLS_SHA256]['members'][
        policy.FONTTOOLS_PREFIX + 'share/man/man1/ttx.1'][1],
        payloads['isympy.1']: policy.APPROVED[policy.SYMPY_SHA256]['members'][
        policy.SYMPY_PREFIX + 'share/man/man1/isympy.1'][1]}
    def digest(data):
        return SimpleNamespace(hexdigest=lambda: digest_map[data]) if data in digest_map else real_sha(data)
    monkeypatch.setattr(policy, 'hashlib', SimpleNamespace(sha256=digest))
    items = []
    for wheel_sha, record in policy.APPROVED.items():
        name, version = record['distribution']
        members = []
        for member, (_, _, directory) in record['members'].items():
            payload = b'' if directory else payloads[Path(member).name]
            if mutated and member == mutated[0]:
                payload = mutated[1]
            members.append((member, payload, stat.S_IFDIR | 0o755 if directory else stat.S_IFREG | 0o644))
        if name == 'fonttools':
            members += list(extra)
        file = make_wheel(cache, name, version, members)
        items.append(item(file, name, version, wheel_sha))
    runtime = SimpleNamespace(**{k: getattr(original, k) for k in (
        'validate_plan', 'norm', 'MAX_WHEEL_BYTES', 'MAX_NEW_BYTES', 'SETUPTOOLS_PTH_SHA', 'new_storage_cap')},
        sha=lambda path: policy.FONTTOOLS_SHA256 if Path(path).name.startswith('fonttools-') else policy.SYMPY_SHA256)
    return items, runtime


def test_original_helper_still_rejects_data_manpage(fixture):
    cache, child = fixture
    path = make_wheel(cache, members=[('ordinary-1.0.data/data/share/man/man1/x.1', b'doc', stat.S_IFREG | 0o644)])
    with pytest.raises(ValueError, match='separate_review'):
        original.wheel_budget(cache, [item(path)])


def test_normal_wheel_budget_formula_unchanged(fixture):
    cache, child = fixture
    path = make_wheel(cache, members=[('ordinary/__init__.py', b'', stat.S_IFREG | 0o644)])
    expected = original.wheel_budget(cache, [item(path)])
    actual = validate(cache, child, [item(path)])
    assert {key: actual[key] for key in expected} == expected
    assert actual['approved_manpage_members'] == []


def test_exact_five_member_exception_and_venv_destinations(fixture, monkeypatch):
    cache, child = fixture
    items, runtime = manpage_fixture(cache, monkeypatch)
    report = validate(cache, child, items, runtime)
    assert len(report['approved_manpage_members']) == 5
    assert {x['destination'] for x in report['approved_manpage_members'] if not x['is_directory']} == {
        str(child / 'share/man/man1/ttx.1'), str(child / 'share/man/man1/isympy.1')}
    assert not (child / 'share').exists()  # Pure validation never extracts.


@pytest.mark.parametrize('path', [
    'fonttools-4.67.0.data/data/share/man/man1/extra.1',
    'fonttools-4.67.0.data/headers/ttx.h',
    'fonttools-4.67.0.data/data/bin/ttx',
    'fonttools-4.67.0.data/data/../../escape',
    '/absolute', 'fonttools-4.67.0.data/data/share//man/man1/ttx.1',
    'fonttools-4.67.0.data/data/share/./man/man1/ttx.1',
    'fonttools-4.67.0.data/data/share\\man\\ttx.1'])
def test_exact_wheel_sha_does_not_approve_other_destinations(fixture, monkeypatch, path):
    cache, child = fixture
    items, runtime = manpage_fixture(cache, monkeypatch, extra=[(path, b'bad', stat.S_IFREG | 0o644)])
    with pytest.raises(ValueError):
        validate(cache, child, items, runtime)


@pytest.mark.parametrize('payload', [b'bad', b'X' * 5377])
def test_exact_member_requires_length_and_member_hash(fixture, monkeypatch, payload):
    cache, child = fixture
    items, runtime = manpage_fixture(cache, monkeypatch,
        mutated=(policy.FONTTOOLS_PREFIX + 'share/man/man1/ttx.1', payload))
    with pytest.raises(ValueError, match='approved_manpage_member'):
        validate(cache, child, items, runtime)


def test_same_manpage_path_in_unknown_wheel_not_allowed(fixture):
    cache, child = fixture
    file = make_wheel(cache, 'fonttools', '4.67.0', members=[(
        policy.FONTTOOLS_PREFIX + 'share/man/man1/ttx.1', b'other', stat.S_IFREG | 0o644)])
    with pytest.raises(ValueError, match='separate_review'):
        validate(cache, child, [item(file, 'fonttools', '4.67.0')])


def test_manpage_parent_symlink_cannot_escape(fixture, monkeypatch, tmp_path):
    cache, child = fixture
    external = tmp_path / 'external'; external.mkdir()
    (child / 'share').symlink_to(external, target_is_directory=True)
    items, runtime = manpage_fixture(cache, monkeypatch)
    with pytest.raises(ValueError, match='symlink'):
        validate(cache, child, items, runtime)


@pytest.mark.parametrize('member,kind', [
    ('ordinary/data', stat.S_IFLNK), ('ordinary/device', stat.S_IFCHR),
    ('ordinary/fifo', stat.S_IFIFO), ('ordinary/socket', stat.S_IFSOCK)])
def test_symlink_and_special_zip_members_stay_blocked(fixture, member, kind):
    cache, child = fixture
    file = make_wheel(cache, members=[(member, b'payload', kind | 0o644)])
    with pytest.raises(ValueError, match='symlink_or_special'):
        validate(cache, child, [item(file)])


@pytest.mark.parametrize('member', ['torch/__init__.py', 'nvidia/data', 'torio/file',
    'ordinary-1.0.data/purelib/triton/file', 'custom.pth', 'sitecustomize.py',
    'usercustomize.py', 'ordinary-1.0.data/scripts/python3'])
def test_original_gpu_startup_and_interpreter_guards_stay_blocked(fixture, member):
    cache, child = fixture
    file = make_wheel(cache, members=[(member, b'payload', stat.S_IFREG | 0o644)])
    with pytest.raises(ValueError):
        validate(cache, child, [item(file)])


def test_cache_wheel_symlink_blocked(fixture, tmp_path):
    cache, child = fixture
    external = make_wheel(tmp_path)
    (cache / external.name).symlink_to(external)
    with pytest.raises(ValueError, match='regular_files'):
        validate(cache, child, [item(external)])


def test_cache_bytes_must_match_resolution(fixture):
    cache, child = fixture
    file = make_wheel(cache)
    with pytest.raises(ValueError, match='wheel_bytes'):
        validate(cache, child, [item(file, digest='f' * 64)])


def test_cache_extra_file_blocked(fixture):
    cache, child = fixture
    file = make_wheel(cache)
    (cache / 'README').write_text('unplanned')
    with pytest.raises(ValueError, match='file_count'):
        validate(cache, child, [item(file)])


def test_member_omission_not_allowed(fixture, monkeypatch):
    cache, child = fixture
    items, runtime = manpage_fixture(cache, monkeypatch)
    file = next(cache.glob('fonttools*'))
    with zipfile.ZipFile(file) as archive:
        members = [(m.filename, archive.read(m), m.external_attr >> 16) for m in archive.infolist()
            if not m.filename.endswith('/ttx.1') and not m.filename.endswith('/METADATA')]
    file.unlink()
    make_wheel(cache, 'fonttools', '4.67.0', members)
    with pytest.raises(ValueError, match='member_set_incomplete'):
        validate(cache, child, items, runtime)


def test_installed_readback_requires_both_unmodified_files(fixture, monkeypatch):
    cache, child = fixture
    items, runtime = manpage_fixture(cache, monkeypatch)
    approved = validate(cache, child, items, runtime)['approved_manpage_members']
    with pytest.raises(ValueError, match='missing'):
        policy.verify_installed_manpages(child, approved)
    destination = child / 'share/man/man1'; destination.mkdir(parents=True)
    (destination / 'ttx.1').write_bytes(b'f' * 5377)
    (destination / 'isympy.1').write_bytes(b's' * 6659)
    assert policy.verify_installed_manpages(child, approved)['status'] == 'BOTH_EXACT_MANPAGES_INSTALLED_IN_CHILD_ONLY'
    (destination / 'ttx.1').write_bytes(b'X' * 5377)
    with pytest.raises(ValueError, match='changed'):
        policy.verify_installed_manpages(child, approved)


def test_no_storage_cap_expansion(fixture, monkeypatch):
    cache, child = fixture
    file = make_wheel(cache)
    monkeypatch.setattr(original, 'new_storage_cap', lambda: 1)
    with pytest.raises(ValueError, match='3GiB'):
        validate(cache, child, [item(file)])
