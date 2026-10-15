"""Run02 metadata/cache tests only; synthetic HTTP errors never issue requests."""
from datetime import datetime, timedelta, timezone
from email.message import Message
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import urllib.error

import pytest

HERE = Path(__file__).parent
FIXTURES = HERE / 'evidence'
PATH = HERE.parent / 'target_restore_run02.py'
SPEC = importlib.util.spec_from_file_location('paper1_target_run02_tests_subject', PATH)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
NOW = datetime(2026, 10, 15, 9, 0, tzinfo=timezone.utc)
PUBLIC = 'https://data.nemar.org/nm000250/v1.0.5/sourcedata/sub-01/eeg/sub-01_task-R1acquisition_eeg.edf'


class NoReadBody:
    def __init__(self):
        self.reads = 0
    def read(self, *args):
        self.reads += 1
        raise AssertionError('Response body must never be read for diagnostics')
    def close(self):
        pass


def http_error(code, location=None):
    headers = Message()
    if location is not None:
        headers['Location'] = location
    body = NoReadBody()
    return urllib.error.HTTPError(PUBLIC, code, 'Synthetic secret reason must not be logged', headers, body), body


def copy_prior_cache(root):
    root.mkdir()
    (root / 'target_restore_run01.claim.json').write_bytes((FIXTURES / 'run01.claim.json').read_bytes())
    journal = (FIXTURES / 'run01.journal.jsonl').read_bytes()
    (root / 'target_restore_run01.journal.jsonl').write_bytes(journal)
    (root / 'target_restore_run01.log').write_bytes(journal)
    return root


def helper():
    return SimpleNamespace(safe_path=lambda root, relative: M.safe(Path(root) / relative),
        digest_file=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest())


def args_prior(root):
    return SimpleNamespace(prior_outer=FIXTURES / 'run01.outer.json',
        same_pod_head=FIXTURES / 'same-pod-first-object-head-run01.json', data_dir=root)


def source_metadata():
    return {'metadata_sha256': {k: v[2] for k, v in M.load_module('continuity').BINDINGS.items()}}


def parent_record(source, revision):
    return dict(schema_version=1, status='DOT_PARENT_TARGET_RAW_RESTORE_APPROVED', issuer='dot_parent',
        operation=M.OPERATION, delivery_revision=revision, operation_script_sha256=M.digest(M.__file__),
        frozen_manifest_sha256=M.load_module('transport').FROZEN_SHA256,
        transport_helper_sha256=M.MODULES['transport'][1], priority_helper_sha256=M.MODULES['priority'][1],
        continuity_helper_sha256=M.MODULES['continuity'][1], continuity_report_sha256=M.CONTINUITY_SHA,
        source_runtime_metadata_sha256=source['metadata_sha256'], target_raw_byte_transport_authorized=True,
        paper2_absolute_priority=True, paper2_noninterference_reviewed=True,
        new_target_allocation_separate_from_retained_source_runtime=True,
        old_task_unknowns_and_failures_retained=True, financial_preconditions='superseded-by-user',
        training_authorization=False, GPU_fit_authorized=False, target_scientific_processing_authorized=False,
        source_EEG_read_authorized=False, new_resources_or_credentials_authorized=False,
        automatic_retry_authorized=False, reviewed_at_utc=(NOW - timedelta(seconds=4)).isoformat(),
        expires_at_utc=(NOW + timedelta(minutes=25)).isoformat(), maximum_wall_seconds=1200,
        recovery_identity=M.RECOVERY_ID, prior_failure_archive_sha256=M.FAILURE_ARCHIVE_SHA,
        prior_claim_sha256=M.PRIOR_FILES['target_restore_run01.claim.json'],
        prior_journal_sha256=M.PRIOR_FILES['target_restore_run01.journal.jsonl'],
        prior_outer_sha256=M.PRIOR_OUTER_SHA, same_pod_head_sha256=M.HEAD_SHA,
        one_additional_bounded_attempt_authorized=True)


def slot():
    gate = M.load_module('priority')
    return dict(schema_version=1, status=gate.STATUS, issuer='dot', pod_id=gate.POD_ID,
        container_id=gate.CONTAINER_ID, operation='target_raw_restore',
        issued_at_utc=(NOW - timedelta(seconds=2)).isoformat(),
        not_before_utc=(NOW - timedelta(seconds=1)).isoformat(),
        expires_at_utc=(NOW + timedelta(minutes=20)).isoformat(), max_new_bytes=3 * M.GIB,
        min_free_bytes=10 * M.GIB, paper2_reserve_bytes=5 * M.GIB,
        slot_rationale='Synthetic explicitly reviewed single HTTP recovery attempt',
        **{k: True for k in gate._TRUE_FIELDS}, **{k: False for k in gate._FALSE_FIELDS})


@pytest.mark.parametrize('status', [401, 403, 302])
def test_http_status_frozen_location_diagnostic_reads_no_body(status):
    error, body = http_error(status, PUBLIC)
    result = M.diagnostic(error)
    assert result['http_status'] == status
    assert result['public_location'] == PUBLIC
    assert result['location_present'] is True and result['unsafe_location_omitted'] is False
    assert result['response_body_read'] is False and result['automatic_retry'] is False
    assert result['redirects_followed'] == 0 and body.reads == 0
    assert 'secret reason' not in json.dumps(result)


@pytest.mark.parametrize('location', [PUBLIC + '?token=synthetic-secret',
    'https://private.invalid/path?key=synthetic-secret', 'https://data.nemar.org/nm000250/v1.0.5/unknown', None])
def test_nonfrozen_or_secret_location_is_withheld(location):
    error, body = http_error(403, location)
    result = M.diagnostic(error)
    assert result['public_location'] is None
    assert result['location_present'] is (location is not None)
    assert result['unsafe_location_omitted'] is (location is not None)
    assert 'synthetic-secret' not in json.dumps(result) and body.reads == 0


def test_exact_three_preserved_cache_metadata_and_no_edf_is_reused(tmp_path):
    root = copy_prior_cache(tmp_path / 'cache')
    rows = M.load_module('transport').frozen_plan()['files']
    before = {name: (root / name).read_bytes() for name in M.PRIOR_FILES}
    missing = M.cache_preflight(root, rows, helper())
    assert missing == rows and len(missing) == 174
    assert {p.name for p in root.iterdir()} == set(M.PRIOR_FILES)
    assert {name: (root / name).read_bytes() for name in M.PRIOR_FILES} == before


@pytest.mark.parametrize('case', ['tamper', 'missing', 'unknown_partial', 'any_edf', 'run02_claim'])
def test_any_unreviewed_cache_member_or_prior_record_drift_stops(tmp_path, case):
    root = copy_prior_cache(tmp_path / case)
    rows = M.load_module('transport').frozen_plan()['files']
    if case == 'tamper':
        (root / 'target_restore_run01.claim.json').write_text('{"tampered":true}')
    elif case == 'missing':
        (root / 'target_restore_run01.log').unlink()
    elif case == 'unknown_partial':
        (root / 'unreviewed.partial').write_bytes(b'synthetic-partial')
    elif case == 'any_edf':
        path = root / rows[0]['restore_relative_path']
        path.parent.mkdir(parents=True)
        path.write_bytes(b'synthetic-not-EDF')
    else:
        (root / M.CLAIM).write_text('{"existing_claim":true}')
    snapshot = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    with pytest.raises((ValueError, FileNotFoundError)):
        M.cache_preflight(root, rows, helper())
    assert {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()} == snapshot


def test_exact_prior_failure_head_and_original_controller_bindings(tmp_path, monkeypatch):
    root = copy_prior_cache(tmp_path / 'cache')
    args = args_prior(root)
    bindings = M.prior_failure_bindings(args, root)
    assert len(bindings) == 6
    assert all(M.digest(path) == sha for path, sha in bindings)
    assert M.FAILURE_ARCHIVE_SHA == '599a690184f657da06d2dcf35fd519fd6c8d4999115bc763396bf220d4242e43'
    assert M.digest(args.prior_outer) == M.PRIOR_OUTER_SHA
    assert M.digest(args.same_pod_head) == M.HEAD_SHA
    wrong_head = tmp_path / 'wrong-head.json'
    wrong_head.write_text('{}')
    args.same_pod_head = wrong_head
    with pytest.raises(ValueError, match='prior_failure_or_HEAD_binding_changed'):
        M.prior_failure_bindings(args, root)
    args.same_pod_head = FIXTURES / 'same-pod-first-object-head-run01.json'
    monkeypatch.setattr(M, 'ORIGINAL_SCRIPT_SHA', '0' * 64)
    with pytest.raises(ValueError, match='prior_failure_or_HEAD_binding_changed'):
        M.prior_failure_bindings(args, root)


def test_parent_requires_explicit_single_recovery_authorization_and_full_bindings(tmp_path):
    source, revision = source_metadata(), 'a' * 40
    data = parent_record(source, revision)
    path = tmp_path / 'parent.json'
    path.write_text(json.dumps(data))
    assert M.parent_review(path, revision, source, NOW)[0] == data
    for key, value in [('one_additional_bounded_attempt_authorized', False), ('same_pod_head_sha256', '0' * 64),
            ('prior_failure_archive_sha256', '0' * 64), ('prior_claim_sha256', '0' * 64),
            ('prior_journal_sha256', '0' * 64), ('prior_outer_sha256', '0' * 64), ('recovery_identity', 'another_attempt')]:
        bad = dict(data); bad[key] = value
        path.write_text(json.dumps(bad))
        with pytest.raises(ValueError, match='fixed_bindings'):
            M.parent_review(path, revision, source, NOW)
    bad = dict(data); bad.pop('one_additional_bounded_attempt_authorized')
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match='exact_schema'):
        M.parent_review(path, revision, source, NOW)


def test_coordinator_single_synthetic_http_failure_preserves_old_claim_and_blocks_retry(tmp_path, monkeypatch):
    real_load = M.load_module
    transport, continuity, gate = (real_load(name) for name in ('transport', 'continuity', 'priority'))
    monkeypatch.setattr(gate, '_clock', lambda current=None: NOW if current is None else current)
    monkeypatch.setattr(M.shutil, 'disk_usage', lambda _: SimpleNamespace(free=100 * M.GIB))
    payload = b'synthetic'
    rows = [dict(row, bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest()) for row in transport.frozen_plan()['files']]
    total = len(rows) * len(payload)
    monkeypatch.setattr(M, 'TOTAL_BYTES', total)
    restore, acceptance = tmp_path / 'source-json', tmp_path / 'acceptance-json'
    restore.mkdir(); acceptance.mkdir()
    bindings = {key: (value[0], 3, hashlib.sha256(b'{}\n').hexdigest()) for key, value in continuity.BINDINGS.items()}
    for key, (name, _, _) in bindings.items():
        ((restore if key in ('restore', 'completion', 'outer') else acceptance) / name).write_bytes(b'{}\n')
    source = {'metadata_sha256': {key: value[2] for key, value in bindings.items()}}
    report = {'status': 'SOURCE_RUNTIME_ACCEPTED_ORIGINAL_TASK_CONTINUITY_AND_TARGET_GATES_PENDING',
        'source_runtime': source, 'training_authorization': False,
        'old_task': {'state': 'OLD_WORK_ROOT_NOT_OBSERVED', 'counters': None}}
    continuity_path = tmp_path / 'continuity_review_run01.json'
    continuity_path.write_text(json.dumps(report))
    monkeypatch.setattr(M, 'CONTINUITY_SHA', M.digest(continuity_path))
    fake_continuity = SimpleNamespace(BINDINGS=bindings, source_review=lambda *_: source,
        load=continuity.load, OLD_JOB=continuity.OLD_JOB)
    called = []
    error, body = http_error(401, PUBLIC + '?token=synthetic-secret')
    def transfer(row, root, *, control_check, **kwargs):
        control_check()
        called.append(row['restore_relative_path'])
        raise error
    fake_transport = SimpleNamespace(FROZEN_SHA256=transport.FROZEN_SHA256, CHUNK=transport.CHUNK,
        frozen_plan=lambda: {'files': rows, 'file_count': 174, 'total_bytes': total, 'license': {'identifier': 'CC-BY-4.0'}},
        safe_path=transport.safe_path, digest_file=transport.digest_file, transport_one=transfer,
        verify_cached_manifest=lambda *_: pytest.fail('No complete byte receipt may follow first HTTP failure'))
    monkeypatch.setattr(M, 'load_module', lambda name: {'transport': fake_transport, 'continuity': fake_continuity, 'priority': gate}[name])
    revision = 'a' * 40
    review_path = tmp_path / 'parent.json'; review_path.write_text(json.dumps(parent_record(source, revision)))
    slot_path = tmp_path / 'slot.json'; slot_path.write_text(json.dumps(slot()))
    root = copy_prior_cache(tmp_path / 'target')
    monkeypatch.setattr(M, 'ROOT', root)
    args = args_prior(root)
    args.delivery_revision = revision
    args.source_restore_root, args.source_acceptance_root = restore, acceptance
    args.continuity_report, args.review_record, args.priority_receipt = continuity_path, review_path, slot_path
    before = {name: (root / name).read_bytes() for name in M.PRIOR_FILES}
    with pytest.raises(urllib.error.HTTPError):
        M.run(args)
    assert len(called) == 1 and body.reads == 0
    assert {name: (root / name).read_bytes() for name in M.PRIOR_FILES} == before
    claim = json.loads((root / M.CLAIM).read_text())
    assert claim['old_counters'] is None and claim['training_authorization'] is False
    assert claim['prior_failure_archive_sha256'] == M.FAILURE_ARCHIVE_SHA
    assert claim['automatic_retry'] is False
    journal = [json.loads(line) for line in (root / M.JOURNAL).read_text().splitlines()]
    assert journal[-1]['phase'] == 'failed_or_blocked_preserve_no_retry'
    assert journal[-1]['http_status'] == 401 and journal[-1]['public_location'] is None
    assert journal[-1]['unsafe_location_omitted'] is True
    assert not (root / M.BYTE_RECEIPT).exists() and not (root / M.SUMMARY).exists()
    assert 'synthetic-secret' not in (root / M.JOURNAL).read_text()
    with pytest.raises(ValueError, match='unknown_member_or_consumed_claim'):
        M.run(args)
    assert len(called) == 1
