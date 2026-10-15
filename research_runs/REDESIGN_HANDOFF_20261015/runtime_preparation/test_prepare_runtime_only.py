"""Synthetic controller guards only: no installer, network, EEG or CUDA child."""
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
from types import SimpleNamespace
from datetime import datetime, timezone

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('paper1_prep_controller_test', HERE / 'prepare_runtime_only.py')
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)
NOW = datetime(2026, 10, 15, 4, 0, tzinfo=timezone.utc)


def review():
    value = json.loads((HERE / 'dot_parent_review.PLAN_ONLY.json').read_text())
    value.update(status='DOT_PARENT_RUNTIME_PREPARATION_REVIEW_APPROVED',
        reviewed_at_utc='2026-10-15T03:59:00Z', expires_at_utc='2026-10-15T04:15:00Z',
        bounded_binary_wheel_policy_reviewed=True, preparation_cost_handling_reviewed=True)
    return value


def test_actual_review_with_scope_remains_no_training():
    start, end, seconds = controller.validate_review(review(), NOW)
    assert start <= NOW < end
    assert seconds == 1200


@pytest.mark.parametrize('field,value', [
    ('status', 'PLAN_ONLY_NOT_APPROVED'), ('issuer', 'dot'),
    ('code_revision', '0' * 40), ('helper_sha256', '0' * 64),
    ('donor_report_sha256', '0' * 64), ('accepted_plan_sha256', '0' * 64),
    ('environment', '/workspace/.venvs/paper2-gpu'),
    ('bounded_binary_wheel_policy_reviewed', False),
    ('resolver_closure_not_yet_observed', False),
    ('preparation_cost_handling_reviewed', False),
    ('old_accounting_unknown_retained', False),
    ('paper2_absolute_priority', False), ('budget_reset_authorized', True),
    ('budget_expansion_authorized', True), ('training_authorization', True),
    ('maximum_wall_seconds', 1201), ('maximum_wall_seconds', True),
    ('reviewed_at_utc', '2026-10-15T04:01:00Z'),
    ('expires_at_utc', '2026-10-15T03:59:30Z'),
    ('expires_at_utc', '2026-10-16T09:54:01Z'),
    ('reviewed_at_utc', '2026-10-15T03:59:00'), ('review_notes', '')])
def test_reject_wrong_parent_scope_and_deadline(field, value):
    record = review(); record[field] = value
    with pytest.raises(ValueError):
        controller.validate_review(record, NOW)


def test_duplicate_and_wrong_exact_bytes_rejected(tmp_path):
    path = tmp_path / 'record.json'; path.write_text('{"a":1,"a":2}')
    with pytest.raises(ValueError, match='duplicate'):
        controller.regular_json(path, 1024)
    path.write_text('{}')
    with pytest.raises(ValueError, match='size'):
        controller.regular_json(path, 1024, expected_size=3)
    with pytest.raises(ValueError, match='sha256'):
        controller.regular_json(path, 1024, expected_sha='0' * 64)


def test_fresh_distinct_outputs_only(tmp_path, monkeypatch):
    monkeypatch.setattr(controller, 'ENVIRONMENT', tmp_path / 'new-runtime')
    output, log, install = (tmp_path / name for name in ('out', 'stderr', 'install'))
    assert controller.safe_outputs(output, log, install, (), workspace=tmp_path)[0] == output
    output.write_text('retain original')
    with pytest.raises(ValueError, match='fresh'):
        controller.safe_outputs(output, log, install, (), workspace=tmp_path)
    assert output.read_text() == 'retain original'


def test_overlap_and_symlink_outputs_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(controller, 'ENVIRONMENT', tmp_path / 'new-runtime')
    output, log, install = (tmp_path / name for name in ('out', 'stderr', 'install'))
    with pytest.raises(ValueError, match='distinct'):
        controller.safe_outputs(output, output, install, (), workspace=tmp_path)
    with pytest.raises(ValueError, match='protected'):
        controller.safe_outputs(output, log, install, (output,), workspace=tmp_path)
    log.symlink_to(tmp_path / 'absent')
    with pytest.raises(ValueError, match='fresh'):
        controller.safe_outputs(output, log, install, (), workspace=tmp_path)


def test_exact_prepare_child_never_plan_gpu_fit_or_global_pip():
    cmd = controller.child_command(Path('/workspace/fixed'), Path('/workspace/donor.json'),
        Path('/workspace/new-slot.json'), Path('/workspace/new-install.log'))
    assert cmd[:3] == ['/usr/bin/python3', '-I', '-B']
    assert cmd.count('--prepare') == 1 and cmd.count('--log') == 1
    assert cmd[cmd.index('--code-revision') + 1] == controller.REVISION
    assert 'apt' not in cmd and 'pip' not in cmd and '--system-site-packages' not in cmd


def test_owned_allocation_does_not_follow_donated_cuda(tmp_path):
    outside = tmp_path / 'outside'; outside.mkdir(); (outside / 'cuda').write_bytes(b'x' * 32768)
    child = tmp_path / 'child'; child.mkdir(); (child / 'nvidia').symlink_to(outside)
    assert controller.allocated(child) < controller.allocated(outside)


def test_resource_floor_and_combined_storage_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(controller, 'ENVIRONMENT', tmp_path / 'child')
    permit = SimpleNamespace(assert_active=lambda: None, max_new_bytes=3 * controller.GIB,
        min_free_bytes=10 * controller.GIB, paper2_reserve_bytes=5 * controller.GIB)
    monkeypatch.setattr(controller.shutil, 'disk_usage', lambda _: SimpleNamespace(free=14 * controller.GIB))
    with pytest.raises(ValueError, match='floor'):
        controller.resource_check((), permit, tmp_path)
    monkeypatch.setattr(controller.shutil, 'disk_usage', lambda _: SimpleNamespace(free=20 * controller.GIB))
    monkeypatch.setattr(controller, 'allocated', lambda _: 4 * controller.GIB)
    with pytest.raises(ValueError, match='storage_cap'):
        controller.resource_check((), permit, tmp_path)


def test_process_identity_and_fallback_never_kill_foreign_or_reused_pid():
    known = {}; table = {100: (1, 100, 11), 101: (100, 101, 12),
        102: (101, 101, 13), 200: (1, 200, 99)}
    controller.remember_descendants(100, known, table)
    assert known == {100: 11, 101: 12, 102: 13}
    later = {100: (1, 100, 11), 101: (1, 101, 888), 102: (1, 101, 13), 200: (1, 200, 99)}
    sent = []
    process = SimpleNamespace(pid=100, wait=lambda timeout: 0, poll=lambda: 0)
    controller.stop_owned(process, known, table_fn=lambda: later,
        kill=lambda pid, sig: sent.append((pid, sig)), pause=lambda _: None)
    assert sent[0] == (100, signal.SIGINT)
    assert {pid for pid, _ in sent} == {100, 102}


def test_finished_unobserved_child_pid_reuse_never_bootstraps_ownership():
    process = SimpleNamespace(pid=100, poll=lambda: 0)
    def forbidden_table():
        raise AssertionError('must not read a reused root PID after reaping')
    controller.stop_owned(process, {}, table_fn=forbidden_table,
        kill=lambda *_: pytest.fail('foreign reused PID signaled'))


def test_accepted_plan_rejects_false_acceptance_or_changed_reserve():
    plan = {'status': 'ISOLATED_RUNTIME_PLAN_ONLY_REVIEW_REQUIRED',
        'code_revision': controller.REVISION, 'environment': str(controller.ENVIRONMENT),
        'donor_report_sha256': controller.DONOR_SHA, 'new_fits': 0,
        'actual_maximum_new_bytes': 3 * controller.GIB,
        'paper2_additional_reserved_bytes': 5 * controller.GIB,
        'actual_required_free_floor_bytes': 15 * controller.GIB}
    for key in ('training_authorization', 'source_acceptance_run', 'target_EEG_read',
                'budget_updated', 'cuda_packages_downloaded', 'donor_modified'):
        plan[key] = False
    controller.validate_plan(plan)
    plan['source_acceptance_run'] = True
    with pytest.raises(ValueError, match='scope_changed'):
        controller.validate_plan(plan)
    plan['source_acceptance_run'] = False; plan['paper2_additional_reserved_bytes'] = 0
    with pytest.raises(ValueError, match='binding_mismatch'):
        controller.validate_plan(plan)
