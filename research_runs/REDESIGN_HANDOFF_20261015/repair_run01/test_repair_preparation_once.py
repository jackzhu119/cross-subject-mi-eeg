"""Synthetic gate tests only: no pip child, network, EEG or GPU execution."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('repair_once_test_subject', HERE / 'repair_preparation_once.py')
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


@pytest.fixture
def review():
    value = json.loads((HERE / 'repair_parent_review.PLAN_ONLY.json').read_text())
    value.update(status='DOT_PARENT_SINGLE_OFFLINE_REPAIR_APPROVED', repair_revision='e' * 40,
        repair_controller_sha256='a' * 64, manpage_policy_sha256='b' * 64,
        wheel_cache_index_sha256='c' * 64, reviewed_at_utc='2026-10-15T04:00:00Z',
        expires_at_utc='2026-10-15T04:20:00Z', review_notes='Actual synthetic test review')
    value.update({key: True for key in r.REVIEW_TRUE})
    return value


def validate(value, now=datetime(2026, 10, 15, 4, 1, tzinfo=timezone.utc)):
    return r.validate_review(value, SimpleNamespace(timestamp=timestamp),
        'a' * 64, 'b' * 64, 'c' * 64, now, 'e' * 40)


def test_actual_repair_review_binding(review):
    assert validate(review)[2] == 1200


def test_plan_only_template_is_not_authorization():
    with pytest.raises(ValueError):
        validate(json.loads((HERE / 'repair_parent_review.PLAN_ONLY.json').read_text()))


@pytest.mark.parametrize('key', sorted(r.REVIEW_TRUE))
def test_each_positive_review_required(review, key):
    review[key] = False
    with pytest.raises(ValueError, match='cannot_grant'):
        validate(review)


@pytest.mark.parametrize('key', sorted(r.REVIEW_FALSE))
def test_each_forbidden_authority_rejected(review, key):
    review[key] = True
    with pytest.raises(ValueError, match='cannot_grant'):
        validate(review)


@pytest.mark.parametrize('key', ['failure_archive_sha256', 'wheel_resolution_sha256',
    'donor_report_sha256', 'base_revision', 'repair_revision', 'repair_controller_sha256',
    'manpage_policy_sha256', 'wheel_cache_index_sha256', 'environment', 'issuer'])
def test_each_identity_binding_required(review, key):
    review[key] = 'other'
    with pytest.raises(ValueError, match='binding'):
        validate(review)


@pytest.mark.parametrize('key,value', [('reviewed_at_utc','2026-10-15T03:54:43Z'),
    ('reviewed_at_utc','2026-10-15T04:02:00Z'),
    ('expires_at_utc','2026-10-15T04:01:00Z'),
    ('expires_at_utc','2026-10-16T09:54:01Z'),
    ('maximum_wall_seconds',0), ('maximum_wall_seconds',1201), ('maximum_wall_seconds',True),
    ('schema_version',True), ('review_notes',' ')])
def test_review_time_bounds_and_true_integers(review,key,value):
    review[key] = value
    with pytest.raises(ValueError):
        validate(review)


def seed_site(tmp_path):
    site = tmp_path / 'site'; site.mkdir()
    source = tmp_path / 'donor'; source.mkdir()
    (site / 'torch').symlink_to(source, target_is_directory=True)
    (site / 'pip').mkdir()
    meta = site / 'pip-24.0.dist-info'; meta.mkdir()
    (meta / 'METADATA').write_text('Name: pip\nVersion: 24.0\n')
    (meta / 'RECORD').write_text('pip/__init__.py,,\n')
    return site, {'components': [{'name': 'torch', 'path': str(source)}]}


def test_fresh_site_observation_does_not_claim_historical_inventory(tmp_path):
    site, donor = seed_site(tmp_path)
    value = r.validate_seed_site(site, donor)
    assert value['version'] == '24.0'
    assert value['historical_site_inventory_available'] is False
    assert value['freshly_observed_only'] is True


@pytest.mark.parametrize('extra', ['numpy', 'numpy-2.3.5.dist-info', 'foreign.pth',
                                 'sitecustomize.py', '__pycache__', 'setuptools'])
def test_scientific_or_foreign_site_entry_blocks_uninstalled_claim(tmp_path, extra):
    site, donor = seed_site(tmp_path)
    (site / extra).touch()
    with pytest.raises(ValueError, match='only_seed_pip'):
        r.validate_seed_site(site, donor)


def test_changed_donor_link_blocks(tmp_path):
    site, donor = seed_site(tmp_path)
    (site / 'torch').unlink(); (site / 'torch').mkdir()
    with pytest.raises(ValueError, match='mapping_changed'):
        r.validate_seed_site(site, donor)


def test_seed_pip_nested_symlink_blocks(tmp_path):
    site, donor = seed_site(tmp_path)
    (site / 'pip' / 'escape').symlink_to(tmp_path / 'donor')
    with pytest.raises(ValueError, match='symlink_or_special'):
        r.validate_seed_site(site, donor)


def test_single_use_journal_consumes_attempt_and_preserves_failure(tmp_path):
    path = tmp_path / 'journal'
    j = r.Journal(path, {'training_authorization': False})
    j.append('REPAIR_FAILED_OR_CANCELLED_NO_AUTOMATIC_RETRY', {'error': 'synthetic'})
    j.close()
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        r.Journal(path, {})
    assert path.read_bytes() == before
    records = [json.loads(row) for row in before.splitlines()]
    assert records[0]['stage'] == 'REPAIR_ATTEMPT_CONSUMED_BEFORE_INSTALL'
    assert records[-1]['stage'] == 'REPAIR_FAILED_OR_CANCELLED_NO_AUTOMATIC_RETRY'


def test_journal_symlink_never_followed(tmp_path):
    old = tmp_path / 'old'; old.write_text('preserve')
    link = tmp_path / 'link'; link.symlink_to(old)
    with pytest.raises(ValueError):
        r.Journal(link, {})
    assert old.read_text() == 'preserve'


def test_offline_install_exact_paths_no_resolver_or_venv():
    paths = [Path('/safe/first.whl'), Path('/safe/second.whl')]
    commands = r.offline_commands(paths)
    assert len(commands) == 2
    install = commands[0]
    for flag in ('--no-deps', '--no-index', '--no-cache-dir', '--disable-pip-version-check'):
        assert flag in install
    assert install[-2:] == list(map(str, paths))
    assert not {'--dry-run', '--index-url', '--upgrade', '--force-reinstall', 'venv'} & set(install)
    assert commands[1][-2:] == ['pip', 'check']


def test_total_storage_carries_partial_instead_of_new_allowance(tmp_path, monkeypatch):
    env = tmp_path / 'env'; env.mkdir()
    monkeypatch.setattr(r, 'ENVIRONMENT', env)
    cap = 3 * r.GIB
    permit = SimpleNamespace(assert_active=lambda: None, paper2_reserve_bytes=5*r.GIB,
        max_new_bytes=cap, min_free_bytes=10*r.GIB)
    monkeypatch.setattr(r.shutil, 'disk_usage', lambda _: SimpleNamespace(free=20*r.GIB))
    ctrl = SimpleNamespace(allocated=lambda p: cap if p == env else 1)
    with pytest.raises(ValueError, match='total3GiB'):
        r.resource_check(ctrl, [], permit)


def test_floor_retains_paper2_reserve(tmp_path, monkeypatch):
    env = tmp_path / 'env'; env.mkdir(); monkeypatch.setattr(r, 'ENVIRONMENT', env)
    permit = SimpleNamespace(assert_active=lambda: None, paper2_reserve_bytes=5*r.GIB,
        max_new_bytes=3*r.GIB, min_free_bytes=10*r.GIB)
    monkeypatch.setattr(r.shutil, 'disk_usage', lambda _: SimpleNamespace(free=15*r.GIB-1))
    with pytest.raises(ValueError, match='reserve_floor'):
        r.resource_check(SimpleNamespace(allocated=lambda _: 0), [], permit)


def test_revoked_slot_blocks_before_resource_observation(tmp_path):
    def revoked(): raise ValueError('revoked')
    permit = SimpleNamespace(assert_active=revoked)
    with pytest.raises(ValueError, match='revoked'):
        r.resource_check(None, [], permit)


def test_duplicate_or_missing79_cache_blocks(tmp_path):
    with pytest.raises(ValueError, match='exact_original79'):
        r.validate_cached_index([], {'wheels': []}, tmp_path)


@pytest.fixture
def cache79(tmp_path):
    folder = tmp_path / 'wheels'; folder.mkdir()
    items, rows = [], []
    for i in range(79):
        filename = f'package{i}-1.0-py3-none-any.whl'
        raw = f'original synthetic wheel {i}'.encode()
        (folder / filename).write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        url = 'https://files.pythonhosted.org/packages/' + filename
        rows.append({'file': filename, 'bytes': len(raw), 'sha256': digest,
            'name': f'package{i}', 'version': '1.0', 'official_url': url})
        items.append({'metadata': {'name': f'package{i}', 'version': '1.0'},
            'download_info': {'url': url, 'archive_info': {'hashes': {'sha256': digest}}}})
    return items, {'wheels': rows}, folder


def test_complete_exact79_cache_gate(cache79):
    items, index, folder = cache79
    assert len(r.validate_cached_index(items, index, folder)) == 79


def test_same_size_changed_original_wheel_blocks(cache79):
    items, index, folder = cache79
    path = folder / index['wheels'][0]['file']
    path.write_bytes(b'X' * path.stat().st_size)
    with pytest.raises(ValueError, match='original_wheel_bytes_changed'):
        r.validate_cached_index(items, index, folder)


def test_changed_official_url_binding_blocks(cache79):
    items, index, folder = cache79
    items[0]['download_info']['url'] += '?changed=1'
    with pytest.raises(ValueError, match='url_or_hash_binding'):
        r.validate_cached_index(items, index, folder)


def test_extra_cached_file_blocks_before_install(cache79):
    items, index, folder = cache79
    (folder / 'extra').write_text('not approved')
    with pytest.raises(ValueError, match='cache_filenames'):
        r.validate_cached_index(items, index, folder)


def test_cached_wheel_symlink_blocks(cache79):
    items, index, folder = cache79
    path = folder / index['wheels'][0]['file']
    other = folder.parent / 'old'; other.write_bytes(path.read_bytes())
    path.unlink(); path.symlink_to(other)
    with pytest.raises(ValueError, match='without_symlink'):
        r.validate_cached_index(items, index, folder)


def test_original_resolution_not_redownloaded_and_no_source_preparation_call():
    source = (HERE / 'repair_preparation_once.py').read_text()
    assert 'runtime.prepare(' not in source
    assert 'runtime.download_wheels(' not in source
    assert 'ctrl.run(' not in source
    assert 'runtime_repair_run01.json' in source
    assert 'future_acceptance_adapter_review_required' in source
