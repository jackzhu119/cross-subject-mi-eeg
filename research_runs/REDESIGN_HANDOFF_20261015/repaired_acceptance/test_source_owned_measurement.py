"""Two synthetic filesystem-publication tests; no EEG, network, or fitting."""
import errno
import importlib.util
import os
from pathlib import Path

import pytest


HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location('source_owned_measurement_tests_subject',
    HERE / 'source_owned_measurement.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def fixture_tree(tmp_path):
    root = tmp_path / 'source'
    (root / 'bnci').mkdir(parents=True)
    (root / 'claim.jsonl').write_bytes(b'claim\n')
    (root / 'receipt.json').write_bytes(b'{}\n')
    rows = [{'filename': name, 'bytes': 7} for name in sorted(M.SANCTIONED_FILENAMES)]
    kwargs = {'receipt_name': 'receipt.json', 'attempt': 'source-repair-run01',
              'partial_rows': rows, 'required_paths': ('claim.jsonl',)}
    return root, rows, kwargs


def allocated(root):
    return sum(path.lstat().st_blocks * 512 for path in (root, *root.rglob('*')))


def test_receipt_atomic_replace_remeasurement_is_narrow_and_bounded(tmp_path, monkeypatch):
    root, rows, kwargs = fixture_tree(tmp_path)
    temporary = root / ('receipt.json.tmp-' + 'a' * 32)
    temporary.write_bytes(b'{"new":true}\n')
    original = Path.lstat
    moved = False
    def racing_lstat(path):
        nonlocal moved
        if path == temporary and not moved:
            moved = True
            os.replace(temporary, root / 'receipt.json')
        return original(path)
    events = []
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'lstat', racing_lstat)
        value = M.owned_bytes(root, on_event=events.append, **kwargs)
    assert moved and value == allocated(root) and value > 0
    assert len(events) == 1 and events[0]['relative_filename'] == temporary.name
    assert events[0]['errno'] == errno.ENOENT and events[0]['scan_index'] == 1
    assert events[0]['action'] == 'remeasure_complete_tree'

    # An ordinary required file, a missing root, and a symlink cannot become zero.
    (root / 'claim.jsonl').unlink()
    with pytest.raises(FileNotFoundError) as missing_required:
        M.owned_bytes(root, **kwargs)
    assert missing_required.value.controlled_diagnostic == {
        'relative_filename': 'claim.jsonl', 'errno': errno.ENOENT,
        'stage': 'required_paths_before_scan',
        'code_location': 'source_owned_measurement.py:owned_bytes'}
    (root / 'claim.jsonl').write_bytes(b'claim\n')
    with pytest.raises(FileNotFoundError):
        M.owned_bytes(tmp_path / 'absent', **kwargs)
    (root / 'ordinary-link').symlink_to(root / 'receipt.json')
    with pytest.raises(ValueError, match='symlink_or_special'):
        M.owned_bytes(root, **kwargs)
    (root / 'ordinary-link').unlink()

    # A literal unknown receipt suffix never receives the temporary exception.
    unknown = root / 'receipt.json.tmp-not-a-uuid'
    unknown.write_bytes(b'unknown')
    def missing_unknown(path):
        if path == unknown:
            raise FileNotFoundError(errno.ENOENT, 'synthetic', str(path))
        return original(path)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'lstat', missing_unknown)
        with pytest.raises(FileNotFoundError):
            M.owned_bytes(root, **kwargs)
    unknown.unlink()

    # Even repeated sanctioned transient observations exhaust the finite cap.
    temporary.write_bytes(b'{}\n')
    attempts = 0
    def always_missing_tmp(path):
        nonlocal attempts
        if path == temporary:
            attempts += 1
            raise FileNotFoundError(errno.ENOENT, 'synthetic', str(path))
        return original(path)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'lstat', always_missing_tmp)
        with pytest.raises(FileNotFoundError, match='transient_retry_limit') as exhausted:
            M.owned_bytes(root, **kwargs)
    assert attempts == 3
    assert exhausted.value.controlled_diagnostic['relative_filename'] == temporary.name


def test_partial_link_unlink_publication_remeasures_without_broad_enoent_allowance(tmp_path, monkeypatch):
    root, rows, kwargs = fixture_tree(tmp_path)
    row = rows[0]
    final = root / 'bnci' / row['filename']
    partial = final.with_name('.' + final.name + '.' + kwargs['attempt'] + '.partial')
    partial.write_bytes(b'synth01')
    original = Path.lstat
    published = False
    def racing_lstat(path):
        nonlocal published
        if path == partial and not published:
            published = True
            os.link(partial, final)
            partial.unlink()
        return original(path)
    events = []
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'lstat', racing_lstat)
        value = M.owned_bytes(root, on_event=events.append, **kwargs)
    assert published and value == allocated(root) and value > 0
    assert events[0]['relative_filename'] == 'bnci/' + partial.name
    assert events[0]['action'] == 'remeasure_complete_tree'

    # A disappeared ordinary MAT is never a publication exception.
    def missing_mat(path):
        if path == final:
            raise FileNotFoundError(errno.ENOENT, 'synthetic', str(path))
        return original(path)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'lstat', missing_mat)
        with pytest.raises(FileNotFoundError) as missing_mat_error:
            M.owned_bytes(root, **kwargs)
    assert missing_mat_error.value.controlled_diagnostic['relative_filename'] == 'bnci/' + final.name

    # A vanished partial with no frozen-size final fails instead of undercounting.
    final.unlink()
    partial.write_bytes(b'synth01')
    def vanish_without_publish(path):
        if path == partial:
            partial.unlink()
        return original(path)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'lstat', vanish_without_publish)
        with pytest.raises(FileNotFoundError):
            M.owned_bytes(root, **kwargs)
    final.write_bytes(b'wrong-size')
    partial.write_bytes(b'synth01')
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'lstat', vanish_without_publish)
        with pytest.raises(ValueError, match='paired_final_frozen_size'):
            M.owned_bytes(root, **kwargs)
