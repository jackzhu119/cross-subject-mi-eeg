"""Mocked requests and tiny synthetic bytes only; never HTTP, Pod or EEG."""
import ast
import hashlib
import importlib.util
import inspect
import io
import json
from pathlib import Path
from types import SimpleNamespace
import urllib.error

import pytest

PATH = Path(__file__).with_name('nemar_single_hop.py')
SPEC = importlib.util.spec_from_file_location('paper1_nemar_single_hop_tests_subject', PATH)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
PAYLOAD = b'tiny-safe'
SECRET = 'SYNTHETIC_SECRET_DO_NOT_LOG'


class Response:
    def __init__(self, url, body=PAYLOAD, status=200, length=None, encoding='identity'):
        self.status = status
        self.headers = {'Content-Length': str(len(body) if length is None else length), 'Content-Encoding': encoding}
        self.url, self.body, self.reads, self.closed = url, io.BytesIO(body), 0, False
    def geturl(self):
        return self.url
    def read(self, size=-1):
        self.reads += 1
        return self.body.read(size)
    def close(self):
        self.closed = True


def row():
    provider = 'sourcedata/sub-01/eeg/sub-01_task-R1acquisition_eeg.edf'
    return {'provider_path': provider, 'restore_relative_path': 'dreyer_acquisition/' + provider,
        'bytes': len(PAYLOAD), 'sha256': hashlib.sha256(PAYLOAD).hexdigest(), 'url': M.ORIGINAL.PREFIX + provider}


def storage_url(item, query='X-Amz-Signature=' + SECRET):
    return ('https://' + M.STORAGE_HOST + '/nm000250/objects/SHA256E-s' + str(item['bytes'])
        + '--' + item['sha256'] + '.edf' + ('?' + query if query else ''))


def http_error(url, code, location=None):
    response = Response(url, b'ERROR_BODY_MUST_NOT_BE_READ', code)
    headers = {'Location': location} if location is not None else {}
    return urllib.error.HTTPError(url, code, 'arbitrary-secret-reason-' + SECRET, headers, response), response


def setup(monkeypatch, outcomes, item=None):
    item = item or row()
    monkeypatch.setattr(M, 'frozen_plan', lambda: {'files': [item]})
    monkeypatch.setattr(M.shutil, 'disk_usage', lambda _: SimpleNamespace(free=100 * M.GIB))
    requests, openers = [], []
    class Opener:
        def open(self, request, timeout):
            requests.append((request, timeout))
            outcome = outcomes[len(requests) - 1]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
    def factory():
        instance = Opener()
        openers.append(instance)
        return instance
    monkeypatch.setattr(M, '_opener_factory', factory)
    return item, requests, openers


def transfer(item, root, check=lambda: None):
    return M.transport_one(item, root, control_check=check, min_free_bytes=10 * M.GIB,
        paper2_reserve_bytes=5 * M.GIB, max_new_bytes=M.NBYTES)


def test_valid_one_hop_full_sha_atomic_publish_and_no_secret_or_forwarded_headers(tmp_path, monkeypatch):
    item = row(); location = storage_url(item)
    redirect, redirect_body = http_error(item['url'], 302, location)
    response = Response(location)
    item, requests, openers = setup(monkeypatch, [redirect, response], item)
    result = transfer(item, tmp_path)
    target = tmp_path / item['restore_relative_path']
    assert target.read_bytes() == PAYLOAD and not target.with_name(target.name + '.partial').exists()
    assert result['sha256'] == item['sha256'] and result['network_bytes'] == len(PAYLOAD)
    assert result['http_route'] == {'http_status': 200, 'canonical_http_status': 302,
        'one_hop_host': M.STORAGE_HOST, 'query_present': True, 'fragment_present': False, 'redirects_followed': 1}
    assert len(requests) == 2 and len(openers) == 2 and openers[0] is not openers[1]
    assert [request.full_url for request, _ in requests] == [item['url'], location]
    for request, timeout in requests:
        assert request.get_method() == 'GET' and request.data is None and timeout == 30
        assert {key.lower(): value for key, value in request.header_items()} == {'accept-encoding': 'identity'}
    assert redirect_body.reads == 0 and redirect_body.closed and response.closed
    assert SECRET not in json.dumps(result) and '/objects/' not in json.dumps(result)
    assert 'opener' not in inspect.signature(M.transport_one).parameters


def test_direct_canonical200_retains_strict_original_behavior(tmp_path, monkeypatch):
    item = row(); response = Response(item['url'])
    item, requests, _ = setup(monkeypatch, [response], item)
    result = transfer(item, tmp_path)
    assert len(requests) == 1 and result['http_route']['redirects_followed'] == 0
    assert result['http_route']['one_hop_host'] is None
    assert (tmp_path / item['restore_relative_path']).read_bytes() == PAYLOAD


def invalid_locations(item):
    url = storage_url(item)
    return [url.replace(M.STORAGE_HOST, 'unknown.invalid'), url.replace(M.STORAGE_HOST, M.STORAGE_HOST + '.evil.invalid'),
        url.replace('https://', 'http://'), url.replace('https://', 'https://user:password@'),
        url.replace(M.STORAGE_HOST, M.STORAGE_HOST + ':443'), url.replace('/nm000250/', '/nm000251/'),
        url.replace('/objects/', '/objects%2f'), url.replace('SHA256E-s9--', 'SHA256E-s8--'),
        url.replace(item['sha256'], '0' * 64), url + '#fragment', url + '\ncontrol', url + '#',
        storage_url(item, 'x=' + 'a' * M.MAX_QUERY)]


@pytest.mark.parametrize('index', range(13))
def test_unapproved_location_stops_before_second_request_without_body_or_url_leak(tmp_path, monkeypatch, index):
    item = row(); location = invalid_locations(item)[index]
    redirect, body = http_error(item['url'], 302, location)
    item, requests, _ = setup(monkeypatch, [redirect], item)
    with pytest.raises(M.ControlledTransportError) as caught:
        transfer(item, tmp_path)
    assert caught.value.code == 'location_not_exact_derived_frozen_storage_object'
    assert len(requests) == 1 and body.reads == 0
    assert SECRET not in str(caught.value) and SECRET not in json.dumps(caught.value.safe_metadata)
    assert 'https://' not in json.dumps(caught.value.safe_metadata)
    assert caught.value.__context__ is None
    frames = []; current = caught.value.__traceback__
    while current is not None:
        frames.append(current.tb_frame.f_code.co_name)
        current = current.tb_next
    assert not {'_request', '_storage_url', 'open_frozen_object', '_strict_transport_one'} & set(frames)
    assert not list(tmp_path.rglob('*.partial'))


@pytest.mark.parametrize('status', [302, 401, 403])
def test_second_redirect_or_auth_error_is_not_followed_or_retried(tmp_path, monkeypatch, status):
    item = row(); location = storage_url(item)
    canonical, first_body = http_error(item['url'], 302, location)
    storage, second_body = http_error(location, status, 'https://private.invalid/path?token=' + SECRET)
    item, requests, _ = setup(monkeypatch, [canonical, storage], item)
    with pytest.raises(M.ControlledTransportError) as caught:
        transfer(item, tmp_path)
    assert caught.value.code == 'storage_http_status_rejected'
    assert caught.value.safe_metadata['http_status'] == status
    assert len(requests) == 2 and first_body.reads == second_body.reads == 0
    assert SECRET not in str(caught.value) and SECRET not in json.dumps(caught.value.safe_metadata)
    assert caught.value.__context__ is None


@pytest.mark.parametrize('status', [301, 401, 403, 307])
def test_canonical_non302_error_has_no_auth_retry(tmp_path, monkeypatch, status):
    item = row(); error, body = http_error(item['url'], status, storage_url(item))
    item, requests, _ = setup(monkeypatch, [error], item)
    with pytest.raises(M.ControlledTransportError) as caught:
        transfer(item, tmp_path)
    assert caught.value.code == 'canonical_http_status_rejected'
    assert caught.value.safe_metadata['http_status'] == status and len(requests) == 1
    assert body.reads == 0 and caught.value.__context__ is None
    assert SECRET not in json.dumps(caught.value.safe_metadata)


def test_actual_storage_response_url_is_checked_without_faking_geturl(tmp_path, monkeypatch):
    item = row(); location = storage_url(item)
    redirect, _ = http_error(item['url'], 302, location)
    response = Response(location + '&unapproved=1')
    item, requests, _ = setup(monkeypatch, [redirect, response], item)
    with pytest.raises(M.ControlledTransportError, match='actual_response_url_changed') as caught:
        transfer(item, tmp_path)
    assert response.url == location + '&unapproved=1' and response.reads == 0 and response.closed
    assert len(requests) == 2 and SECRET not in str(caught.value)


def test_slot_revocation_after_canonical302_blocks_storage_get(tmp_path, monkeypatch):
    item = row(); location = storage_url(item)
    redirect, body = http_error(item['url'], 302, location)
    item, requests, _ = setup(monkeypatch, [redirect], item)
    def check():
        if requests:
            raise ValueError('synthetic_slot_revoked_after_canonical_request')
    with pytest.raises(M.ControlledTransportError, match='controlled_transport_or_resource_failure_partial_preserved'):
        transfer(item, tmp_path, check)
    assert len(requests) == 1 and body.reads == 0
    assert not list(tmp_path.rglob('*.partial'))


def test_sha_mismatch_preserves_partial_and_second_call_cannot_retry(tmp_path, monkeypatch):
    item = row(); location = storage_url(item)
    redirect, _ = http_error(item['url'], 302, location)
    response = Response(location, b'x' * len(PAYLOAD))
    item, requests, _ = setup(monkeypatch, [redirect, response], item)
    with pytest.raises(M.ControlledTransportError, match='download_size_or_sha256_mismatch_partial_preserved'):
        transfer(item, tmp_path)
    target = tmp_path / item['restore_relative_path']; partial = target.with_name(target.name + '.partial')
    assert not target.exists() and partial.read_bytes() == b'x' * len(PAYLOAD)
    with pytest.raises(M.ControlledTransportError, match='existing_partial_preserved_manual_review_required'):
        transfer(item, tmp_path)
    assert len(requests) == 2 and partial.read_bytes() == b'x' * len(PAYLOAD)


@pytest.mark.parametrize('case', ['length', 'encoding', 'oversize', 'resource_floor'])
def test_original_length_encoding_size_and_reserved_disk_guards_remain(tmp_path, monkeypatch, case):
    item = row(); location = storage_url(item)
    redirect, _ = http_error(item['url'], 302, location)
    response = Response(location, PAYLOAD + b'x' if case == 'oversize' else PAYLOAD,
        length=len(PAYLOAD) - 1 if case == 'length' else len(PAYLOAD), encoding='gzip' if case == 'encoding' else 'identity')
    item, requests, _ = setup(monkeypatch, [redirect, response], item)
    if case == 'resource_floor':
        monkeypatch.setattr(M.shutil, 'disk_usage', lambda _: SimpleNamespace(free=15 * M.GIB))
    with pytest.raises(M.ControlledTransportError):
        transfer(item, tmp_path)
    target = tmp_path / item['restore_relative_path']
    assert not target.exists() and len(requests) <= 2
    if case == 'oversize':
        assert target.with_name(target.name + '.partial').exists()
    if case == 'resource_floor':
        assert len(requests) == 0


def test_unfrozen_row_and_existing_corrupt_cache_rejected_before_any_request(tmp_path, monkeypatch):
    item, requests, _ = setup(monkeypatch, [])
    changed = dict(item, bytes=item['bytes'] + 1)
    with pytest.raises(M.ControlledTransportError, match='exact_frozen_canonical_row_required'):
        transfer(changed, tmp_path)
    target = tmp_path / item['restore_relative_path']; target.parent.mkdir(parents=True)
    target.write_bytes(b'corrupt')
    with pytest.raises(M.ControlledTransportError, match='existing_object_corrupt_preserved'):
        transfer(item, tmp_path)
    assert target.read_bytes() == b'corrupt' and not requests


def test_original_hash_and_resource_body_loop_atomic_publish_are_unchanged():
    original_path = PATH.with_name('official_edf_transport.py')
    assert hashlib.sha256(original_path.read_bytes()).hexdigest() == M.ORIGINAL_SHA
    old = next(n for n in ast.parse(original_path.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'transport_one')
    new = next(n for n in ast.parse(PATH.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == '_strict_transport_one')
    old_loop = next(n for n in ast.walk(old) if isinstance(n, ast.While) and isinstance(n.test, ast.Constant) and n.test.value is True)
    new_loop = next(n for n in ast.walk(new) if isinstance(n, ast.While) and isinstance(n.test, ast.Constant) and n.test.value is True)
    class NormalizeErrorOnly(ast.NodeTransformer):
        def visit_Name(self, node):
            return ast.copy_location(ast.Name(id='ValueError', ctx=node.ctx), node) if node.id == 'ControlledTransportError' else node
    assert ast.dump(old_loop, include_attributes=False) == ast.dump(NormalizeErrorOnly().visit(new_loop), include_attributes=False)
    for name in ('link', 'fsync'):
        old_calls = [ast.dump(n, include_attributes=False) for n in ast.walk(old) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                     and isinstance(n.func.value, ast.Name) and n.func.value.id == 'os' and n.func.attr == name]
        new_calls = [ast.dump(n, include_attributes=False) for n in ast.walk(new) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                     and isinstance(n.func.value, ast.Name) and n.func.value.id == 'os' and n.func.attr == name]
        assert new_calls == old_calls
