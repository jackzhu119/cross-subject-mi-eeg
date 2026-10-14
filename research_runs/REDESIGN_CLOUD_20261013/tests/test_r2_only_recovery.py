"""Offline transport, corruption, interruption and restore tests; no live API calls."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import r2_only as r2
import private_recovery as recovery


class Missing(Exception):
    response = {'Error': {'Code': 'NoSuchKey'}}


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.calls = []
        self.fail_put = None
        self.corrupt = None
        self.after_get = None

    def get_object(self, Bucket, Key):
        self.calls.append(('get', Key))
        if Key not in self.objects:
            raise Missing()
        data = self.objects[Key]
        if Key == self.corrupt:
            data = bytes([data[0] ^ 1]) + data[1:]
        if self.after_get:
            self.after_get(Key)
        return {'Body': io.BytesIO(data), 'ContentLength': len(data), 'ETag': hashlib.sha256(data).hexdigest()}

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise Missing()
        return {'ContentLength': len(self.objects[Key])}

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.calls.append(('put', Key))
        if kwargs.get('IfNoneMatch') == '*' and Key in self.objects:
            raise RuntimeError('precondition')
        if 'IfMatch' in kwargs and (Key not in self.objects or hashlib.sha256(self.objects[Key]).hexdigest() != kwargs['IfMatch']):
            raise RuntimeError('precondition')
        data = Body.read() if hasattr(Body, 'read') else Body
        self.objects[Key] = data
        if self.fail_put and self.fail_put(Key):
            raise RuntimeError('lost response after successful write')
        return {'ETag': hashlib.sha256(data).hexdigest()}


def record(data=b'original EEG bytes'):
    return {'path': 'bnci/A01T.mat', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def mapping(row):
    return {'schema_version': 1, 'files': [{**row, 'object_key': 'private/raw/source'}]}


def test_r2_import_exact_and_reuse_no_second_get(tmp_path):
    client = FakeS3()
    client.objects['private/raw/source'] = b'original EEG bytes'
    row = record()
    receipt = r2.import_files(tmp_path, mapping(row), [row], client, 'bucket', reserve=0)
    assert receipt['downloaded_files'] == 1
    assert (tmp_path / row['path']).read_bytes() == client.objects['private/raw/source']
    before = len(client.calls)
    assert r2.import_files(tmp_path, mapping(row), [row], client, 'bucket', reserve=0)['reused_files'] == 1
    assert len(client.calls) == before


@pytest.mark.parametrize('change', ['sha256', 'bytes', 'coverage', 'duplicate', 'traversal'])
def test_invalid_mapping_rejected_before_network(tmp_path, change):
    row = record()
    m = mapping(row)
    if change == 'sha256': m['files'][0]['sha256'] = '0' * 64
    if change == 'bytes': m['files'][0]['bytes'] = True
    if change == 'coverage': m['files'] = []
    if change == 'duplicate': m['files'] *= 2
    if change == 'traversal': m['files'][0]['object_key'] = '../private'
    client = FakeS3()
    with pytest.raises(ValueError):
        r2.import_files(tmp_path, m, [row], client, 'bucket', reserve=0)
    assert not client.calls


@pytest.mark.parametrize('data', [b'wrong EEG bytes!!', b'', b'original EEG bytes EXTRA'])
def test_corrupt_short_oversize_never_committed(tmp_path, data):
    client = FakeS3()
    client.objects['private/raw/source'] = data
    with pytest.raises(ValueError):
        r2.import_files(tmp_path, mapping(record()), [record()], client, 'bucket', reserve=0)
    assert not list(tmp_path.rglob('*.mat'))
    assert not list(tmp_path.rglob('*.partial-*'))


def test_missing_object_no_fallback(tmp_path, monkeypatch):
    import urllib.request
    monkeypatch.setattr(urllib.request, 'urlopen', lambda *a, **k: pytest.fail('official fallback forbidden'))
    with pytest.raises(RuntimeError, match='no_fallback'):
        r2.import_files(tmp_path, mapping(record()), [record()], FakeS3(), 'bucket', reserve=0)


def test_existing_corruption_preserved(tmp_path):
    p = tmp_path / record()['path']
    p.parent.mkdir()
    p.write_bytes(b'bad')
    client = FakeS3()
    with pytest.raises(ValueError, match='existing_cache'):
        r2.import_files(tmp_path, mapping(record()), [record()], client, 'bucket', reserve=0)
    assert p.read_bytes() == b'bad' and not client.calls


def test_symlink_parent_rejected(tmp_path):
    root = tmp_path / 'cache'
    root.mkdir()
    (root / 'bnci').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        r2.import_files(root, mapping(record()), [record()], FakeS3(), 'bucket', reserve=0)


def make_job(tmp_path):
    job = tmp_path / 'job1'
    job.mkdir()
    for name in recovery.STATIC:
        (job / name).write_text(json.dumps({'identity': name}))
    (job / 'source').mkdir()
    (job / 'source/budget_ledger.json').write_text(json.dumps({'actual_neural_fits_started': 0,
        'actual_neural_fits_completed': 0, 'optimizer_updates': 0}))
    (job / 'supervisor.log').write_bytes(b'normal log\nGH_TOKEN=TEST_SECRET\nhttps://host/path?signature=secret\n')
    return job


def new_recovery(job, client):
    return recovery.Recovery(job, client, 'bucket', secrets=('TEST_SECRET',), reserve=0)


def test_snapshot_roundtrip_and_log_sanitization(tmp_path):
    job, client = make_job(tmp_path), FakeS3()
    r = new_recovery(job, client)
    result = r.snapshot('preflight')
    assert result['full_readback_verified']
    restored = tmp_path / 'restored'
    receipt = recovery.restore_verified(client, 'bucket', job.name, restored, reserve=0)
    assert receipt['automatic_resume'] is False
    assert (restored / 'source/budget_ledger.json').read_bytes() == (job / 'source/budget_ledger.json').read_bytes()
    log = (restored / 'logs/supervisor.redacted.log').read_bytes()
    assert b'TEST_SECRET' not in log and b'?signature' not in log and b'normal log' in log
    assert not list(job.glob('.redacted-*'))
    assert not any('raw' in n for n in receipt['files'])


def test_remote_pending_blocks_restore_and_restart(tmp_path):
    job, client = make_job(tmp_path), FakeS3()
    r = new_recovery(job, client)
    r.snapshot('before')
    r.begin('optimizer_update', 1)
    with pytest.raises(ValueError, match='pending'):
        recovery.restore_verified(client, 'bucket', job.name, tmp_path / 'restore', reserve=0)
    with pytest.raises(ValueError, match='pending'):
        new_recovery(job, client)


def test_lost_write_response_does_not_retry_or_clear_intent(tmp_path):
    job, client = make_job(tmp_path), FakeS3()
    r = new_recovery(job, client)
    r.snapshot('before')
    client.fail_put = lambda key: key.endswith('/HEAD.json')
    with pytest.raises(RuntimeError, match='uncertain'):
        r.begin('consume_fit_ordinal', 1)
    assert json.loads(client.objects[r.key])['state'] == 'PENDING'
    assert len([x for x in client.calls if x == ('put', r.key)]) == 2


def test_two_writers_cannot_replace_head(tmp_path):
    job, client = make_job(tmp_path), FakeS3()
    first = new_recovery(job, client)
    first.snapshot('before')
    second = new_recovery(job, client)
    first.begin('optimizer_update', 1)
    with pytest.raises(RuntimeError, match='uncertain'):
        second.begin('optimizer_update', 1)
    assert json.loads(client.objects[first.key])['state'] == 'PENDING'


def test_corrupt_blob_blocks_restore_without_success_marker(tmp_path):
    job, client = make_job(tmp_path), FakeS3()
    r = new_recovery(job, client)
    r.snapshot('before')
    _, manifest = recovery.read_committed(r.store, r.prefix, job.name)
    client.corrupt = next(iter(manifest['files'].values()))['key']
    with pytest.raises(ValueError, match='hash_mismatch'):
        recovery.restore_verified(client, 'bucket', job.name, tmp_path / 'restore', reserve=0)
    assert not (tmp_path / 'restore/RESTORE_VERIFIED.json').exists()


def test_no_overwrite_on_restore(tmp_path):
    job, client = make_job(tmp_path), FakeS3()
    r = new_recovery(job, client)
    r.snapshot('before')
    with pytest.raises(ValueError, match='new_review'):
        recovery.restore_verified(client, 'bucket', job.name, job, reserve=0)


def test_source_intent_or_inconsistent_ledger_blocks_commit(tmp_path):
    job, client = make_job(tmp_path), FakeS3()
    r = new_recovery(job, client)
    r.snapshot('before')
    r.begin('optimizer_update', 1)
    (job / 'source/update_intent.json').write_text('{}')
    with pytest.raises(ValueError, match='unresolved'):
        r.snapshot('bad')
    assert json.loads(client.objects[r.key])['state'] == 'PENDING'
    (job / 'source/update_intent.json').unlink()
    (job / 'source/fit_receipt.json').write_text('{"status":"started"}')
    with pytest.raises(ValueError, match='counts'):
        r.snapshot('bad')


def test_terminal_log_does_not_clear_pending(tmp_path):
    job, client = make_job(tmp_path), FakeS3()
    r = new_recovery(job, client)
    r.snapshot('before')
    r.begin('optimizer_update', 1)
    before = client.objects[r.key]
    result = recovery.backup_terminal_log(job, client, 'bucket', ('TEST_SECRET',))
    assert result['status'] == 'TERMINAL_LOG_PREFIX_VERIFIED'
    assert client.objects[r.key] == before


def test_env_only_credentials_never_create_cache(tmp_path):
    from cloud_transport import secure_credentials
    env = {'MI_EEG_ENV_ONLY_CREDENTIALS': '1', 'GH_TOKEN': 'fixture-token'}
    assert secure_credentials(environ=env, private_root=tmp_path / 'credentials')['GH_TOKEN'] == 'fixture-token'
    assert not (tmp_path / 'credentials').exists()


def test_import_disk_shortfall_before_api(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(r2.shutil, 'disk_usage', lambda p: SimpleNamespace(free=1))
    client = FakeS3()
    with pytest.raises(ValueError, match='insufficient_disk'):
        r2.import_files(tmp_path, mapping(record()), [record()], client, 'bucket', reserve=0)
    assert not client.calls


def test_active_batch_state_roundtrip_keeps_model_rng_optimizer_and_counter(tmp_path):
    import torch
    job, client = make_job(tmp_path), FakeS3()
    r = new_recovery(job, client)
    r.snapshot('before-fit')
    r.begin('consume_fit_ordinal', 1)
    fit = job / 'source/inner/cell'
    fit.mkdir(parents=True)
    identity = dict(architecture='fixture', seed=1, epochs=2, cell_kind='synthetic')
    (fit / 'fit_receipt.json').write_text(json.dumps({**identity, 'status': 'started', 'configuration_sha256': 'frozen'}))
    ledger = {'actual_neural_fits_started': 1, 'actual_neural_fits_completed': 0, 'optimizer_updates': 7}
    (job / 'source/budget_ledger.json').write_text(json.dumps(ledger))
    state = {'global_updates': 7, 'fit_identity': identity, 'config_sha256': 'frozen',
             'model_state': {'weight': torch.tensor([2.5])}, 'optimizer_state': {'counter': 7},
             'rng': {'torch': torch.get_rng_state()}, 'batch_offset': 64, 'epoch': 2, 'order': torch.arange(128)}
    torch.save(state, fit / 'resume_state.pt')
    r.snapshot('batch')
    dest = tmp_path / 'restore'
    recovery.restore_verified(client, 'bucket', job.name, dest, reserve=0)
    restored = torch.load(dest / 'source/inner/cell/resume_state.pt', weights_only=True)
    assert restored['global_updates'] == 7
    assert restored['optimizer_state'] == state['optimizer_state']
    assert torch.equal(restored['rng']['torch'], state['rng']['torch'])
    assert torch.equal(restored['model_state']['weight'], state['model_state']['weight'])
    state['global_updates'] = 8
    torch.save(state, fit / 'resume_state.pt')
    with pytest.raises(ValueError, match='update_inconsistent'):
        r.snapshot('inconsistent')


def test_manifest_upload_failure_never_marks_pending_committed(tmp_path):
    job, client = make_job(tmp_path), FakeS3()
    r = new_recovery(job, client)
    r.snapshot('before')
    r.begin('optimizer_update', 1)
    client.fail_put = lambda key: '/manifests/' in key
    with pytest.raises(RuntimeError, match='uncertain'):
        r.snapshot('after')
    assert json.loads(client.objects[r.key])['state'] == 'PENDING'


def test_remote_head_change_during_restore_never_issues_receipt(tmp_path):
    job, client = make_job(tmp_path), FakeS3()
    r = new_recovery(job, client)
    r.snapshot('before')
    def change(key):
        if '/blobs/' in key:
            client.objects[r.key] = recovery.encoded({'state': 'PENDING'})
    client.after_get = change
    with pytest.raises(ValueError, match='head_changed'):
        recovery.restore_verified(client, 'bucket', job.name, tmp_path / 'restore', reserve=0)
    assert not (tmp_path / 'restore/RESTORE_VERIFIED.json').exists()


def test_source_symlink_directory_never_uploaded(tmp_path):
    job, client = make_job(tmp_path), FakeS3()
    external = tmp_path / 'external'
    external.mkdir()
    (external / 'secret.json').write_text('{}')
    (job / 'source/linked').symlink_to(external, target_is_directory=True)
    r = new_recovery(job, client)
    with pytest.raises(ValueError, match='symlink'):
        r.snapshot('bad')
    assert not any(call[0] == 'put' for call in client.calls)


def test_real_frozen_source_mapping_has_exact_18_identities():
    root = Path(__file__).resolve().parents[3]
    expected = [r for r in r2.frozen_entries(root) if r['path'].startswith('bnci/')]
    path = root / 'research_runs/REDESIGN_HANDOFF_20261014/source_r2_mapping.json'
    assert len(r2.validate_mapping(json.loads(path.read_text()), expected)) == 18
    assert sum(r['bytes'] for r in expected) == 779873919


def test_new_host_compare_records_mismatch_without_mutating_freeze(tmp_path, monkeypatch):
    import numpy as np
    import scipy
    import pandas as pd
    from types import SimpleNamespace
    import reconstruct_source_readonly as probe
    monkeypatch.setattr(np, '__version__', '2.3.5')
    monkeypatch.setattr(scipy, '__version__', '1.17.0')
    monkeypatch.setattr(pd, '__version__', '2.2.3')
    monkeypatch.setattr(probe, 'ROOT', tmp_path)
    monkeypatch.setattr(probe, 'AUDIT', tmp_path / 'audit')
    monkeypatch.setattr(probe, 'verify_science', lambda: {'frozen': 'unchanged'})
    config = tmp_path / 'research_runs/REDESIGN_CLOUD_20261013/config/experiment.json'
    config.parent.mkdir(parents=True)
    config.write_text('{}')
    evidence = tmp_path / 'audit/evidence'
    evidence.mkdir(parents=True)
    expected = {'array_hashes': {'broad': 'old'}, 'source_labels_sha256': 'labels',
                'source_metadata_sha256': 'metadata', 'source_sample_ids_sha256': 'ids',
                'preprocessing': {'native_filter_sos_250_hz': {'broad': [[1., 2.]]}}}
    (evidence / 'source_exact_input_fingerprints_receipt.json').write_text(json.dumps({'source_file_provenance': expected}))
    (evidence / 'source_exact_input_fingerprints.csv').write_text('source_sample_id,broad_sha256\ns1,old\n')
    actual = {**expected, 'array_hashes': {'broad': 'new'}, 'n_raw_files': 18}
    monkeypatch.setitem(sys.modules, 'core_source_inputs', SimpleNamespace(
        load_source19=lambda *a: ({'broad': np.zeros((1, 2, 3))}, [{'sample_id': 's1'}], actual),
        array_hash=lambda a: 'new'))
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    report = probe.compare(tmp_path / 'bnci')
    assert report['status'] == 'NEW_HOST_SOURCE_INPUT_MISMATCH_BLOCKED'
    assert report['per_trial_mismatches']['broad']['count'] == 1
    assert report['old_failure_root_cause_established'] is False
    assert report['new_model_fits'] == 0 and report['training_authorization'] is False
    assert all(p.read_bytes() == data for p, data in before.items())


def test_new_host_diagnostic_rejects_unpinned_runtime(monkeypatch):
    import reconstruct_source_readonly as probe
    import numpy
    monkeypatch.setattr(numpy, '__version__', '0.0.0')
    with pytest.raises(ValueError, match='exact_diagnostic'):
        probe.compare(Path('/nonexistent'))


def test_immutable_blob_cannot_overwrite_previous_snapshot(tmp_path):
    client = FakeS3()
    path = tmp_path / 'model.pt'
    path.write_bytes(b'old content')
    store = recovery.Store(client, 'bucket')
    row = store.blob('private/job', path)
    before = client.objects[row['key']]
    # A fresh writer fully rechecks the immutable existing object without PUT.
    other = recovery.Store(client, 'bucket')
    calls_before = len([c for c in client.calls if c == ('put', row['key'])])
    assert other.blob('private/job', path) == row
    assert len([c for c in client.calls if c == ('put', row['key'])]) == calls_before
    assert client.objects[row['key']] == before


def test_unauthorized_head_is_not_retried():
    class Unauthorized(Exception):
        response = {'Error': {'Code': 'Unauthorized'}}
    class Denied(FakeS3):
        def get_object(self, **kwargs):
            self.calls.append(('get', kwargs['Key']))
            raise Unauthorized()
        def head_object(self, **kwargs):
            pytest.fail('No followup request after Unauthorized')
    client = Denied()
    with pytest.raises(RuntimeError, match='head_unknown'):
        recovery.Store(client, 'bucket').head('private/job/HEAD.json')
    assert len(client.calls) == 1
