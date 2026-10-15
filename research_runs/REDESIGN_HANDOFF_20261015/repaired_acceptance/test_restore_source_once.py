"""Synthetic, offline tests: no live network, MAT, environment or GPU access."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import sys
from types import SimpleNamespace

import pytest

PATH = Path(__file__).with_name('restore_source_once.py')
spec = importlib.util.spec_from_file_location('source_restore_bridge_tests', PATH)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
ORIGINAL = PATH.parents[2] / 'REDESIGN_HANDOFF_20261014' / 'official_source_diagnostic' / 'restore_source_official_lampx_v2.py'
spec = importlib.util.spec_from_file_location('original_source_transport_for_bridge_tests', ORIGINAL)
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)


class Gate:
    max_new_bytes = 3 * m.GIB
    min_free_bytes = 10 * m.GIB
    reserve_bytes = 5 * m.GIB
    max_wall_seconds = 1200
    review_sha256 = 'a' * 64
    slot_sha256 = 'b' * 64

    def __init__(self):
        self.checks = 0

    def check(self):
        self.checks += 1

    def remaining_seconds(self):
        return 1100


def row(name='A01T.mat', data=b'only-synthetic-transport-bytes'):
    return dict(filename=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                url='https://bnci-horizon-2020.eu/database/data-sets/001-2014/' + name)


class Response(io.BytesIO):
    status = 200

    def __init__(self, payload, url):
        super().__init__(payload)
        self.headers = {'Content-Length': str(len(payload))}
        self.url = url

    def geturl(self):
        return self.url


class Opener:
    def __init__(self, item, payload):
        self.item, self.payload = item, payload
        self.source_redirect = SimpleNamespace(routes=[])

    def open(self, request, timeout):
        assert request.full_url == self.item['url']
        assert 0 < timeout <= 30
        return Response(self.payload, self.item['url'])


def claim(root):
    return {'attempt': 'synthetic-run', 'source_root': str(root), 'phase': 'single_attempt_claimed'}


def initialized(root):
    (root / 'bnci').mkdir(parents=True)
    (root / m.JOURNAL).write_text(json.dumps(claim(root)) + '\n')


@pytest.fixture
def free_disk(monkeypatch):
    monkeypatch.setattr(m.shutil, 'disk_usage', lambda path: SimpleNamespace(free=50 * m.GIB))


@pytest.fixture(autouse=True)
def synthetic_runtime(tmp_path_factory, monkeypatch):
    environment = tmp_path_factory.mktemp('retained-runtime-metadata')
    monkeypatch.setattr(m, 'ENVIRONMENT', environment)
    return environment


def test_actual_frozen_manifest_and_transport_helper_identity_only():
    assert m.sha(ORIGINAL) == m.HELPER_SHA
    manifest = ORIGINAL.with_name('source_official_manifest.json')
    assert m.sha(manifest) == m.MANIFEST_SHA
    rows = original.load_manifest(manifest)
    assert len(rows) == 18
    assert sum(item['bytes'] for item in rows) == m.SOURCE_BYTES == 779873919


def test_bound_code_or_manifest_drift_is_checked_again(tmp_path, monkeypatch):
    helper = tmp_path / 'helper'; helper.write_bytes(b'helper')
    manifest = tmp_path / 'manifest'; manifest.write_bytes(b'manifest')
    monkeypatch.setattr(m, 'HELPER_REL', 'helper')
    monkeypatch.setattr(m, 'MANIFEST_REL', 'manifest')
    monkeypatch.setattr(m, 'HELPER_SHA', m.sha(helper))
    monkeypatch.setattr(m, 'MANIFEST_SHA', m.sha(manifest))
    gate = Gate(); gate.script_sha = m.sha(PATH)
    m.bind_fixed_inputs(gate, tmp_path)
    gate.check()
    manifest.write_bytes(b'changed')
    with pytest.raises(ValueError, match='bound_code_or_manifest_changed'):
        gate.check()


def test_only_fixed_isolated_data_root_is_writable(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'SOURCE_ROOT', tmp_path / 'intended')
    with pytest.raises(ValueError, match='exact_isolated_root'):
        m.validate_root(tmp_path / 'other')
    assert not (tmp_path / 'other').exists()


def test_symlink_root_rejected(tmp_path, monkeypatch):
    (tmp_path / 'real').mkdir()
    (tmp_path / 'link').symlink_to(tmp_path / 'real', target_is_directory=True)
    monkeypatch.setattr(m, 'SOURCE_ROOT', tmp_path / 'link')
    with pytest.raises(ValueError, match='symlink'):
        m.validate_root(tmp_path / 'link')


def test_raw_path_inside_checkout_rejected(tmp_path, monkeypatch):
    (tmp_path / '.git').mkdir()
    monkeypatch.setattr(m, 'SOURCE_ROOT', tmp_path / 'data')
    with pytest.raises(ValueError, match='outside_repository'):
        m.validate_root(tmp_path / 'data')


def test_fifo_member_rejected(tmp_path, monkeypatch):
    root = tmp_path / 'source'
    root.mkdir()
    os.mkfifo(root / 'fifo')
    monkeypatch.setattr(m, 'SOURCE_ROOT', root)
    with pytest.raises(ValueError, match='special_or_symlink'):
        m.validate_root(root)


def test_genuine_cache_is_verified_then_reused_without_any_get(tmp_path, free_disk, monkeypatch):
    initialized(tmp_path)
    payload = b'only-synthetic-transport-bytes'
    item = row(data=payload)
    (tmp_path / 'bnci' / item['filename']).write_bytes(payload)
    def forbidden(*args, **kwargs):
        pytest.fail('An exact cache must never cause another GET')
    monkeypatch.setattr(original, 'official_opener', forbidden)
    result = m.execute_transfer(tmp_path, [item], original, Gate(), claim(tmp_path))
    assert result['files'][0]['status'] == 'REUSED_VERIFIED_CACHE'
    assert result['status'] == 'SOURCE18_EXACT_BYTES_RESTORED_NUMERICAL_ACCEPTANCE_PENDING'
    assert result['diagnostic_rerun'] is result['runtime_imported'] is False
    assert result['training_authorization'] is False
    assert result['old_accounting_status'] == 'UNKNOWN_NOT_ZERO'


def test_wrong_later_cached_file_prevents_any_network_and_keeps_bytes(tmp_path):
    (tmp_path / 'bnci').mkdir()
    later = tmp_path / 'bnci/A02T.mat'
    later.write_bytes(b'bad')
    with pytest.raises(ValueError, match='size_sha256'):
        m.cache_preflight(tmp_path, [row(), row('A02T.mat')], original)
    assert later.read_bytes() == b'bad'
    assert not (tmp_path / m.JOURNAL).exists()


@pytest.mark.parametrize('extra', ['.A01T.mat.old.partial', 'target.edf', 'other.mat'])
def test_unreviewed_cache_or_failed_partial_never_deleted_or_retried(tmp_path, extra):
    (tmp_path / 'bnci').mkdir()
    (tmp_path / 'bnci' / extra).write_bytes(b'preserve')
    with pytest.raises(ValueError, match='unreviewed_existing_cache'):
        m.cache_preflight(tmp_path, [row()], original)
    assert (tmp_path / 'bnci' / extra).read_bytes() == b'preserve'


@pytest.mark.parametrize('marker', [m.JOURNAL, m.RECEIPT, m.LOG])
def test_attempt_consumed_by_any_existing_own_marker(tmp_path, marker):
    (tmp_path / marker).write_bytes(b'old')
    with pytest.raises(ValueError, match='already_consumed'):
        m.cache_preflight(tmp_path, [row()], original)


def test_existing_unrelated_root_members_rejected(tmp_path):
    (tmp_path / 'paper2-env').mkdir()
    with pytest.raises(ValueError, match='unreviewed_existing_root'):
        m.cache_preflight(tmp_path, [row()], original)


def test_preserves_baseline_inside_one_gib_total_cap(tmp_path, free_disk, monkeypatch):
    monkeypatch.setattr(m, 'owned_bytes', lambda unused: m.GIB - 200)
    with pytest.raises(ValueError, match='total_allocation_cap'):
        m.resource_check(tmp_path, Gate(), before_next_write=201)


def test_slot_smaller_total_cap_is_honored(tmp_path, free_disk, monkeypatch):
    gate = Gate(); gate.max_new_bytes = 200
    monkeypatch.setattr(m, 'owned_bytes', lambda unused: 199)
    with pytest.raises(ValueError, match='total_allocation_cap'):
        m.resource_check(tmp_path, gate, before_next_write=2)


def test_retained_runtime_baseline_is_never_reset_to_zero(tmp_path, free_disk):
    value = m.resource_check(tmp_path, Gate())
    assert value['retained_runtime_owned_bytes'] == m.BASE_OWNED == 869490688
    assert value['combined_owned_bytes'] >= m.BASE_OWNED
    assert value['runtime_historical_owned_bytes_preserved'] == m.BASE_OWNED


def test_actual_runtime_growth_and_source_share_original_three_gib_cap(tmp_path, free_disk, monkeypatch):
    monkeypatch.setattr(m, 'runtime_allocated', lambda unused: m.HISTORICAL_ENV_DU + 2 * m.GIB)
    monkeypatch.setattr(m, 'owned_bytes', lambda unused: 256 * 1024**2)
    with pytest.raises(ValueError, match='combined_retained_runtime_and_source_cap'):
        m.resource_check(tmp_path, Gate())


def test_stricter_slot_cap_covers_runtime_plus_source(tmp_path, free_disk):
    gate = Gate(); gate.max_new_bytes = m.BASE_OWNED - 1
    with pytest.raises(ValueError, match='combined_retained_runtime_and_source_cap'):
        m.resource_check(tmp_path, gate)


def test_runtime_directory_must_actually_exist(tmp_path, free_disk, monkeypatch):
    monkeypatch.setattr(m, 'ENVIRONMENT', tmp_path / 'missing')
    with pytest.raises(ValueError, match='retained_runtime_directory_required'):
        m.resource_check(tmp_path, Gate())


def test_runtime_root_symlink_is_not_accepted(tmp_path, free_disk, synthetic_runtime, monkeypatch):
    link = tmp_path / 'runtime-link'; link.symlink_to(synthetic_runtime, target_is_directory=True)
    source = tmp_path / 'source'; source.mkdir()
    monkeypatch.setattr(m, 'ENVIRONMENT', link)
    with pytest.raises(ValueError, match='symlink_path_forbidden'):
        m.resource_check(source, Gate())


def test_runtime_gpu_donor_symlink_is_not_followed_or_counted(tmp_path, synthetic_runtime):
    donor = tmp_path / 'donor'; donor.mkdir()
    (donor / 'synthetic-gpu-bytes').write_bytes(b'x' * 1024**2)
    before = m.runtime_allocated(synthetic_runtime)
    (synthetic_runtime / 'torch').symlink_to(donor, target_is_directory=True)
    assert m.runtime_allocated(synthetic_runtime) == before


def test_actual_paper2_reserve_is_added_after_stricter_floor(tmp_path, monkeypatch):
    gate = Gate(); gate.reserve_bytes = 7 * m.GIB; gate.min_free_bytes = 11 * m.GIB
    monkeypatch.setattr(m.shutil, 'disk_usage', lambda unused: SimpleNamespace(free=18 * m.GIB - 1))
    with pytest.raises(ValueError, match='actual_paper2_reserve'):
        m.resource_check(tmp_path, gate)


def test_reserve_cannot_fall_below_five_gib(tmp_path, monkeypatch):
    gate = Gate(); gate.reserve_bytes = 0
    monkeypatch.setattr(m.shutil, 'disk_usage', lambda unused: SimpleNamespace(free=15 * m.GIB - 1))
    with pytest.raises(ValueError, match='actual_paper2_reserve'):
        m.resource_check(tmp_path, gate)


def test_gate_revocation_checked_before_resource_read(tmp_path, monkeypatch):
    gate = Gate()
    def revoked(): raise ValueError('revoked')
    gate.check = revoked
    monkeypatch.setattr(m, 'owned_bytes', lambda unused: pytest.fail('revoked before resources'))
    with pytest.raises(ValueError, match='revoked'):
        m.resource_check(tmp_path, gate)


@pytest.mark.parametrize('size', [0, -1, True, m.CHUNK + 1, '1'])
def test_response_reads_remain_bounded(size):
    response = m.CheckedResponse(Response(b'data', row()['url']), lambda **kw: None)
    with pytest.raises(ValueError, match='bounded_response_read'):
        response.read(size)


def test_response_gate_is_checked_before_each_read_and_reserves_next_chunk():
    checks = []
    response = m.CheckedResponse(Response(b'data', row()['url']), lambda **kw: checks.append(kw))
    assert response.read(2) == b'da'
    assert response.read(2) == b'ta'
    assert checks == [{'before_next_write': 65538}, {'before_next_write': 65538}]


def test_exact_official_synthetic_stream_retains_transport_identity(tmp_path, free_disk, monkeypatch):
    initialized(tmp_path)
    payload = b'only-synthetic-transport-bytes'
    item = row(data=payload)
    monkeypatch.setattr(original, 'official_opener', lambda r: Opener(r, payload))
    gate = Gate()
    result = m.execute_transfer(tmp_path, [item], original, gate, claim(tmp_path))
    assert (tmp_path / 'bnci' / item['filename']).read_bytes() == payload
    assert result['files'][0]['response_route']['mode'] == 'ORIGINAL_DIRECT_200'
    assert gate.checks >= 5
    assert result['official_manifest_sha256'] == m.MANIFEST_SHA


def test_wrong_stream_keeps_failed_partial_and_single_attempt_journal(tmp_path, free_disk, monkeypatch):
    initialized(tmp_path)
    payload = b'bad-but-same-length-transport!'
    item = row()
    monkeypatch.setattr(original, 'official_opener', lambda r: Opener(r, payload))
    with pytest.raises(ValueError):
        m.execute_transfer(tmp_path, [item], original, Gate(), claim(tmp_path))
    assert not (tmp_path / 'bnci' / item['filename']).exists()
    assert len(list((tmp_path / 'bnci').glob('.*.partial'))) == 1
    assert (tmp_path / m.JOURNAL).exists()
    report = json.loads((tmp_path / m.RECEIPT).read_text())
    assert report['status'] == 'SOURCE_RESTORE_FAILED_OR_BLOCKED_KEEP_PARTIALS_NO_RETRY'


def test_json_initial_claim_is_exclusive(tmp_path):
    path = tmp_path / 'claim'
    m.write_json_once(path, {'original': True})
    with pytest.raises(FileExistsError):
        m.write_json_once(path, {'original': False})
    assert json.loads(path.read_text()) == {'original': True}


def test_worker_claim_requires_actual_own_parent(tmp_path):
    gate = Gate(); args = SimpleNamespace(delivery_revision='c' * 40)
    value = dict(phase='single_attempt_claimed', delivery_revision=args.delivery_revision,
        controller_sha256=m.sha(PATH), review_sha256=gate.review_sha256,
        slot_sha256=gate.slot_sha256, source_root=str(tmp_path), parent_pid=-1)
    (tmp_path / m.JOURNAL).write_text(json.dumps(value) + '\n')
    with pytest.raises(ValueError, match='live_own_parent'):
        m.validate_claim(args, tmp_path, gate)


def test_worker_claim_rejects_other_slot(tmp_path):
    gate = Gate(); args = SimpleNamespace(delivery_revision='c' * 40)
    value = dict(phase='single_attempt_claimed', delivery_revision=args.delivery_revision,
        controller_sha256=m.sha(PATH), review_sha256=gate.review_sha256,
        slot_sha256='d' * 64, source_root=str(tmp_path), parent_pid=os.getppid())
    (tmp_path / m.JOURNAL).write_text(json.dumps(value) + '\n')
    with pytest.raises(ValueError, match='matching_parent_claim'):
        m.validate_claim(args, tmp_path, gate)


def test_worker_stops_only_its_new_process_group(monkeypatch):
    calls = []
    class Child:
        pid = 123456
        def poll(self): return None
        def wait(self, timeout): calls.append(('wait', timeout))
    monkeypatch.setattr(m.os, 'killpg', lambda pid, sig: calls.append((pid, sig)))
    m.stop_own_worker(Child())
    assert calls == [(123456, signal.SIGTERM), ('wait', 5)]


def test_source_restore_has_no_install_fit_inference_or_original_main_calls():
    import ast
    tree = ast.parse(PATH.read_text())
    attrs = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not {'restore', 'supervise', 'claim_single_revision_attempt', 'main', 'fit', 'predict', 'loadmat'} & attrs
    assert 'download_one' in attrs and 'verify' in attrs


def test_gate_operation_is_distinct_from_runtime_import_and_source_acceptance(monkeypatch):
    captured = []
    fake = SimpleNamespace(Gate=lambda *args: captured.append(args))
    monkeypatch.setattr(m, 'module', lambda *args: fake)
    args = SimpleNamespace(review_record='review', priority_receipt='slot', delivery_revision='c' * 40)
    m.gate_for(args)
    assert captured[0][2] == 'source_raw_restore'


def test_fresh_gates_and_all_cache_preflight_precede_any_write(tmp_path, monkeypatch):
    root = tmp_path / 'never-created'
    gate = Gate()
    monkeypatch.setattr(m, 'gate_for', lambda args: gate)
    monkeypatch.setattr(m, 'SOURCE_ROOT', root)
    monkeypatch.setattr(m, 'fixed_helper', lambda unused: (original, [row()]))
    monkeypatch.setattr(m, 'bind_fixed_inputs', lambda *args: None)
    def blocked(*args): raise ValueError('cache_preflight_blocked')
    monkeypatch.setattr(m, 'cache_preflight', blocked)
    args = SimpleNamespace(data_dir=root, code_dir=tmp_path, worker=False)
    with pytest.raises(ValueError, match='cache_preflight_blocked'):
        m.run(args)
    assert not root.exists()
    assert gate.checks >= 1


def test_failed_worker_launch_consumes_attempt_and_never_retries(tmp_path, free_disk, monkeypatch):
    root = tmp_path / 'source'
    monkeypatch.setattr(m, 'SOURCE_ROOT', root)
    monkeypatch.setattr(m, 'gate_for', lambda args: Gate())
    monkeypatch.setattr(m, 'fixed_helper', lambda unused: (original, [row()]))
    monkeypatch.setattr(m, 'bind_fixed_inputs', lambda *args: None)
    attempts = []
    def fail(*args, **kwargs):
        attempts.append(args)
        raise OSError('synthetic-popen-failure')
    monkeypatch.setattr(m.subprocess, 'Popen', fail)
    args = SimpleNamespace(data_dir=root, code_dir=tmp_path, worker=False,
        review_record=tmp_path / 'review', priority_receipt=tmp_path / 'slot', delivery_revision='c' * 40)
    with pytest.raises(OSError): m.run(args)
    assert len(attempts) == 1
    assert (root / m.JOURNAL).is_file()
    with pytest.raises(ValueError, match='already_consumed'): m.run(args)
    assert len(attempts) == 1
