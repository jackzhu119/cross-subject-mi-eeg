"""Synthetic integration tests; no Pod, install, network, CUDA or EEG access."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import zipfile

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LEGACY = ROOT / 'research_runs/REDESIGN_HANDOFF_20261014/runtime_transition'
SPEC = importlib.util.spec_from_file_location('paper1_control_integration_runtime',
    LEGACY / 'isolated_training_runtime.py')
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


@pytest.fixture(autouse=True)
def isolated_global_permit(monkeypatch):
    # This module owns a separate helper instance. A synthetic armed permit must
    # never leak into the existing runtime test module or another test case.
    monkeypatch.setattr(runtime, 'ACTIVE_PRIORITY', None)


def permit(**changes):
    fields = dict(max_new_bytes=runtime.MAX_NEW_BYTES,
        min_free_bytes=runtime.MIN_FREE_BYTES, paper2_reserve_bytes=1024**3,
        receipt_sha256='a' * 64, assert_active=lambda: None)
    fields.update(changes)
    return SimpleNamespace(**fields)


@pytest.mark.parametrize('minimum,reserve,expected', [
    (10, 0, 10), (10, 4, 14), (12, 4, 16), (9, 4, 14)])
def test_paper2_reservation_is_added_after_the_stricter_free_floor(monkeypatch, minimum, reserve, expected):
    monkeypatch.setattr(runtime, 'ACTIVE_PRIORITY', permit(
        min_free_bytes=minimum * 1024**3, paper2_reserve_bytes=reserve * 1024**3))
    assert runtime.free_floor() == expected * 1024**3


@pytest.mark.parametrize('requested,expected', [(0, 0), (1, 1), (2, 2), (3, 3), (4, 3)])
def test_slot_can_tighten_but_not_expand_runtime_allocation_cap(monkeypatch, requested, expected):
    monkeypatch.setattr(runtime, 'ACTIVE_PRIORITY', permit(max_new_bytes=requested * 1024**3))
    assert runtime.new_storage_cap() == expected * 1024**3


def test_absent_slot_blocks_prepare_before_donor_read_or_artifact_mutation(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, 'fixed_checkout', lambda _: {})
    monkeypatch.setattr(runtime, 'donor_observation', lambda _: pytest.fail('must not inspect donor without slot'))
    args = SimpleNamespace(code_revision='a' * 40, priority_receipt=None,
        environment=tmp_path / 'child', log=tmp_path / 'installer.log',
        donor_report=tmp_path / 'must-not-be-read.json')
    with pytest.raises(ValueError, match='fresh_dot_paper2_priority_slot_required'):
        runtime.prepare(args)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('replacement', [None, 'unavailable-slot.json'])
def test_rejected_rearming_cannot_reuse_the_previous_permit(tmp_path, monkeypatch, replacement):
    monkeypatch.setattr(runtime, 'ACTIVE_PRIORITY', permit())
    with pytest.raises(ValueError):
        runtime.arm_priority(None if replacement is None else tmp_path / replacement,
            'runtime_preparation')
    with pytest.raises(ValueError, match='fresh_dot_priority_slot_not_validated'):
        runtime.priority_checkpoint()
    with pytest.raises(ValueError, match='fresh_dot_priority_slot_not_validated'):
        runtime.free_floor()


def test_revoked_download_slot_makes_no_network_request(tmp_path, monkeypatch):
    def revoked():
        raise ValueError('synthetic_slot_revoked')
    monkeypatch.setattr(runtime, 'ACTIVE_PRIORITY', permit(assert_active=revoked))
    monkeypatch.setattr(runtime.urllib.request, 'urlopen',
        lambda *a, **k: pytest.fail('no network request after slot revocation'))
    with pytest.raises(ValueError, match='synthetic_slot_revoked'):
        runtime.download_wheels([{}], tmp_path, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_absent_slot_blocks_acceptance_before_receipt_or_source_read(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, 'isolated_training_runtime', runtime)
    monkeypatch.setattr(sys, 'path', list(sys.path))
    spec = importlib.util.spec_from_file_location('paper1_control_integration_acceptance',
        LEGACY / 'accept_training_runtime_source.py')
    acceptance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(acceptance)
    monkeypatch.setattr(runtime, 'fixed_checkout', lambda _: {})
    monkeypatch.setattr(acceptance.subprocess, 'check_output',
        lambda *args, **kwargs: Path(acceptance.__file__).read_bytes())
    args = SimpleNamespace(code_revision='a' * 40, priority_receipt=None,
        runtime_receipt=tmp_path / 'must-not-be-read.json')
    with pytest.raises(ValueError, match='fresh_dot_paper2_priority_slot_required'):
        acceptance.run(args)
    assert list(tmp_path.iterdir()) == []


def test_revocation_before_owned_command_creates_no_log_temp_or_process(tmp_path, monkeypatch):
    child = tmp_path / 'new-child'; child.mkdir()
    log = tmp_path / 'installer.log'
    def revoked():
        raise ValueError('synthetic_slot_revoked')
    monkeypatch.setattr(runtime, 'ACTIVE_PRIORITY', permit(assert_active=revoked))
    monkeypatch.setattr(runtime.subprocess, 'Popen', lambda *a, **k: pytest.fail('no process may start'))
    with pytest.raises(ValueError, match='slot_revoked'):
        runtime.run_command(['synthetic-not-executed'], log, child)
    assert not log.exists()
    assert list(child.iterdir()) == []


def test_slot_revocation_stops_only_the_owned_installer_process(tmp_path, monkeypatch):
    child = tmp_path / 'new-child'; child.mkdir()
    calls = []
    checkpoints = 0
    def active_then_revoked():
        nonlocal checkpoints
        checkpoints += 1
        if checkpoints > 1:
            raise ValueError('synthetic_slot_revoked')
    monkeypatch.setattr(runtime, 'ACTIVE_PRIORITY', permit(assert_active=active_then_revoked))
    owned = SimpleNamespace(pid=987654, returncode=None, poll=lambda: None)
    monkeypatch.setattr(runtime.subprocess, 'Popen',
        lambda command, **kwargs: (calls.append(('start', command, kwargs)) or owned))
    monkeypatch.setattr(runtime, 'stop_owned_child', lambda process: calls.append(('stop', process)))
    with pytest.raises(ValueError, match='slot_revoked'):
        runtime.run_command(['synthetic-not-executed'], tmp_path / 'installer.log', child)
    assert len(calls) == 2
    assert calls[1] == ('stop', owned)
    assert calls[0][2]['start_new_session'] is True


@pytest.mark.parametrize('reason', ['paper2_reserve', 'smaller_slot_cap'])
def test_owned_installer_obeys_slot_disk_limits_without_touching_other_processes(tmp_path, monkeypatch, reason):
    child = tmp_path / 'new-child'; child.mkdir()
    owned = SimpleNamespace(pid=987654, returncode=None, poll=lambda: None)
    calls = []
    slot = permit(max_new_bytes=1024**3, paper2_reserve_bytes=4 * 1024**3)
    monkeypatch.setattr(runtime, 'ACTIVE_PRIORITY', slot)
    monkeypatch.setattr(runtime.subprocess, 'Popen', lambda *a, **k: owned)
    monkeypatch.setattr(runtime, 'stop_owned_child', calls.append)
    free = 13 * 1024**3 if reason == 'paper2_reserve' else 20 * 1024**3
    monkeypatch.setattr(runtime.shutil, 'disk_usage', lambda _: SimpleNamespace(free=free))
    monkeypatch.setattr(runtime, 'allocated', lambda _: 2 * 1024**3 if reason == 'smaller_slot_cap' else 0)
    with pytest.raises(ValueError, match='concurrent_storage_change|allocation_exceeds'):
        runtime.run_command(['synthetic-not-executed'], tmp_path / 'installer.log', child)
    assert calls == [owned]


def test_wheel_budget_obeys_stricter_slot_cap_not_only_default_3gib(tmp_path, monkeypatch):
    wheel = tmp_path / 'synthetic-1-py3-none-any.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('synthetic-1.dist-info/METADATA', 'Name: synthetic\nVersion: 1\n')
        archive.writestr('synthetic/__init__.py', '# not executed\n')
    items = [{'metadata': {'name': 'synthetic', 'version': '1'}, 'download_info': {
        'archive_info': {'hashes': {'sha256': runtime.sha(wheel)}}}}]
    monkeypatch.setattr(runtime, 'ACTIVE_PRIORITY', permit(max_new_bytes=256 * 1024**2))
    with pytest.raises(ValueError, match='new_runtime_peak_exceeds'):
        runtime.wheel_budget(tmp_path, items)


def test_no_cross_abi_or_paper2_payload_copy_in_runtime_policy():
    # This checks only source structure; actual origins/imports remain separate
    # gates. No donor or paper2 filesystem is opened by this test.
    source = Path(runtime.__file__).read_text()
    assert "Path('/workspace/.venvs/paper2-gpu')" in source
    assert 'dest.symlink_to(path' in source
    assert 'shutil.copy' not in source
    assert 'include-system-site-packages = false' in source
    assert 'paper1_requires_original_python_3_12_3_no_cross_ABI_donor' in source


def test_priority_module_and_helper_roots_point_to_same_checkout():
    assert runtime.ROOT == ROOT
    assert runtime.PRIORITY_PATH == HERE / 'priority_gate.py'
    assert runtime.PRIORITY_PATH.is_file()
