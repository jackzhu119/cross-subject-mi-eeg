"""Synthetic metadata ownership tests only; no actual MAT, network or Pod."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import importlib.util
import json

import pytest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('source_compatibility_under_test', HERE / 'restore_source_after_failure_once.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(m.base, 'SOURCE_ROOT', tmp_path)
    (tmp_path / 'bnci').mkdir()
    for name in m.OLD_FILES:
        (tmp_path / name).write_bytes(b'synthetic preserved metadata')
    (tmp_path / m.OLD_TMP).write_bytes(b'')
    (tmp_path / 'source_restore_repair_run01.outer_exit.json').write_bytes(b'synthetic failed exit3')
    monkeypatch.setattr(m, 'OLD_FILES', {n: m.base.sha(tmp_path / n) for n in m.OLD_FILES})
    monkeypatch.setattr(m, 'PREFLIGHT_PRESERVED_FILES', {n: m.base.sha(tmp_path / n) for n in m.PREFLIGHT_PRESERVED_FILES})
    # Public frozen sizes/identities only. Synthetic content is checked by a stub;
    # the actual helper.verify implementation is unchanged and separately pinned.
    manifest = HERE.parents[1] / 'REDESIGN_HANDOFF_20261014/official_source_diagnostic/source_official_manifest.json'
    rows = json.loads(manifest.read_text())['files']
    for name in m.PRESENT:
        (tmp_path / 'bnci' / name).write_bytes(b'synthetic content only')
    checked = []
    def verify(path, row):
        assert path.read_bytes() == b'synthetic content only'
        checked.append(row['filename'])
    return tmp_path, rows, SimpleNamespace(verify=verify), checked


def test_exact_preserved_tmp_and_failed_outer_allow_unconsumed_preflight(cache):
    root, rows, helper, checked = cache
    before = {n: (root / n).read_bytes() for n in {**m.OLD_FILES, **m.PREFLIGHT_PRESERVED_FILES}}
    result = m.cache_preflight(root, rows, helper)
    assert len(result) == 12 and set(checked) == m.PRESENT
    assert sum(row['bytes'] for row in result) == 513941297
    assert all((root / n).read_bytes() == value for n, value in before.items())
    assert not any((root / n).exists() for n in [m.JOURNAL, m.RECEIPT, m.LOG])


def test_other_tmp_nonempty_exact_tmp_symlink_or_consumed_claim_still_stop(cache):
    root, rows, helper, checked = cache
    other = root / 'source_restore_run01.json.tmp-00000000000000000000000000000000'
    other.write_bytes(b'')
    with pytest.raises(ValueError, match='unreviewed_member'):m.cache_preflight(root, rows, helper)
    assert checked == []
    other.unlink()  # Synthetic test fixture only; production never deletes it.
    exact = root / m.OLD_TMP
    exact.write_bytes(b'changed')
    with pytest.raises(ValueError, match='record_missing_or_changed'):m.cache_preflight(root, rows, helper)
    exact.unlink(); exact.symlink_to(root / 'source_restore_run01.log')
    with pytest.raises(ValueError, match='symlink'):m.cache_preflight(root, rows, helper)
    exact.unlink(); exact.write_bytes(b'')
    (root / m.JOURNAL).write_bytes(b'synthetic existing claim')
    with pytest.raises(ValueError, match='unreviewed_member'):m.cache_preflight(root, rows, helper)


def test_missing_tmp_or_changed_preserved_outer_is_not_ignored(cache):
    root, rows, helper, checked = cache
    exact = root / m.OLD_TMP; exact.unlink()
    with pytest.raises(FileNotFoundError):m.cache_preflight(root, rows, helper)
    exact.write_bytes(b'')
    outer = root / 'source_restore_repair_run01.outer_exit.json'
    outer.write_bytes(b'modified failed exit')
    with pytest.raises(ValueError, match='record_missing_or_changed'):m.cache_preflight(root, rows, helper)
    assert checked == []
