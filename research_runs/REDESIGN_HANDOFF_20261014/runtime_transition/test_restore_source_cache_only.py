"""Metadata/software fixtures: never restore EEG, call R2 or import a model."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location('source_cache_restoration_tested', HERE / 'restore_source_cache_only.py')
restore = importlib.util.module_from_spec(spec); spec.loader.exec_module(restore)


def source_rows():
    return [{'path': f'bnci/A{i:02d}{s}.mat', 'bytes': 1, 'sha256': 'a' * 64}
        for i in range(1, 10) for s in ('T', 'E')]


def mapping(rows):
    return {'schema_version': 1, 'files': [{**r, 'object_key': 'existing/' + r['path']} for r in rows]}


def test_source_restoration_plan_excludes_all_target_rows(monkeypatch, tmp_path):
    source = source_rows()
    rows = source + [{'path': 'dreyer_acquisition/never-read.edf', 'bytes': 2, 'sha256': 'b' * 64}]
    monkeypatch.setattr(restore.gate, 'identity', lambda _: (rows, {}))
    monkeypatch.setattr(restore.gate, 'read_json', lambda *args: (mapping(source), restore.MAPPING_SHA))
    got, _ = restore.inspect_mapping(tmp_path, tmp_path / 'mapping')
    assert got == source


@pytest.mark.parametrize('change', ['missing', 'target', 'wrong_hash'])
def test_source_restore_cannot_accept_partial_target_or_changed_source_identity(monkeypatch, tmp_path, change):
    source = source_rows(); actual = mapping(source)
    if change == 'missing':
        actual['files'].pop()
    elif change == 'target':
        actual['files'].append({'path': 'dreyer_acquisition/extra.edf', 'bytes': 2, 'sha256': 'b' * 64, 'object_key': 'existing/extra'})
    else:
        actual['files'][0]['sha256'] = 'c' * 64
    monkeypatch.setattr(restore.gate, 'identity', lambda _: (source, {}))
    monkeypatch.setattr(restore.gate, 'read_json', lambda *args: (actual, restore.MAPPING_SHA))
    with pytest.raises(ValueError):
        restore.inspect_mapping(tmp_path, tmp_path / 'mapping')
