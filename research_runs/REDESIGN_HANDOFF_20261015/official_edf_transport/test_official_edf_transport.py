"""Synthetic bytes and frozen public metadata only; no EEG or network requests."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import urllib.error

import pytest

SPEC = importlib.util.spec_from_file_location("official_edf_transport", Path(__file__).with_name("official_edf_transport.py"))
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def example(data=b"synthetic fixture: not EEG"):
    path = "sourcedata/sub-01/eeg/sub-01_task-R1acquisition_eeg.edf"
    return {"provider_path": path, "restore_relative_path": "dreyer_acquisition/" + path,
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "url": m.PREFIX + path}


class Response(io.BytesIO):
    def __init__(self, row, data, *, status=200, url=None, length=None, encoding=None):
        super().__init__(data)
        self.status = status
        self.url = row["url"] if url is None else url
        self.headers = {"Content-Length": str(row["bytes"]) if length is None else length}
        if encoding is not None:
            self.headers["Content-Encoding"] = encoding

    def geturl(self):
        return self.url


class Opener:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        return self.response


@pytest.fixture
def fixture(monkeypatch):
    data = b"synthetic fixture: not EEG"
    row = example(data)
    monkeypatch.setattr(m, "frozen_plan", lambda: {"files": [dict(row)]})
    monkeypatch.setattr(m.shutil, "disk_usage", lambda path: SimpleNamespace(free=100 * m.GIB))
    return row, data


def run(row, root, opener, **kwargs):
    defaults = dict(control_check=lambda: None, min_free_bytes=10 * m.GIB,
                    paper2_reserve_bytes=5 * m.GIB, max_new_bytes=m.NBYTES, opener=opener)
    defaults.update(kwargs)
    return m.transport_one(row, root, **defaults)


def test_plan_all_174_frozen_metadata_without_network(monkeypatch):
    # This one test reads only pinned JSON / provider README, never an EDF.
    monkeypatch.setattr(m.urllib.request, "build_opener", lambda *a, **k: pytest.fail("network"))
    plan = m.frozen_plan()
    assert len(plan["files"]) == 174
    assert plan["total_bytes"] == 2515343396
    assert plan["license"]["identifier"] == "CC-BY-4.0"
    assert not plan["gates"]["training_authorization"]
    assert not plan["current_observation"]["remote_full_object_bytes_verified"]
    assert len({row["provider_path"] for row in plan["files"]}) == 174


@pytest.mark.parametrize("replacement", ["http://data.nemar.org/nm000250/v1.0.5/", "https://evil.invalid/",
                                       "https://user@data.nemar.org/nm000250/v1.0.5/",
                                       "https://data.nemar.org:443/nm000250/v1.0.5/",
                                       "https://data.nemar.org/nm000250/v1.0.6/",
                                       "https://data.nemar.org/nm000250/v1.0.5/../"])
def test_nonexact_urls_rejected(replacement):
    row = example()
    row["url"] = replacement + row["provider_path"]
    with pytest.raises(ValueError):
        m.validate_row(row)


@pytest.mark.parametrize("suffix", ["?download=1", "#part", "%2e%2e", " "])
def test_query_fragment_and_escaped_mutations_rejected(suffix):
    row = example()
    row["url"] += suffix
    with pytest.raises(ValueError):
        m.validate_row(row)


@pytest.mark.parametrize("path", ["../data.edf", "/sourcedata/x.edf", "sourcedata/sub-01/eeg/sub-01_task-R3online_eeg.edf",
                                  "sourcedata/sub-88/eeg/sub-88_task-R1acquisition_eeg.edf",
                                  "sourcedata/sub-01/eeg/sub-01_task-R1acquisition_eeg.bdf"])
def test_wrong_cohort_or_format_paths_rejected(path):
    row = example()
    row["provider_path"] = path
    with pytest.raises(ValueError):
        m.validate_row(row)


def test_all_redirects_rejected_even_same_origin():
    request = m.urllib.request.Request(example()["url"])
    with pytest.raises(urllib.error.HTTPError, match="all_redirects_rejected"):
        m.RejectRedirects().redirect_request(request, None, 302, "Found", {}, example()["url"])


def test_default_tls_hostname_and_certificate_validation(monkeypatch):
    seen = []
    monkeypatch.setattr(m.urllib.request, "build_opener", lambda *handlers: seen.extend(handlers) or "synthetic opener")
    assert m.secure_opener() == "synthetic opener"
    handler = next(h for h in seen if isinstance(h, m.urllib.request.HTTPSHandler))
    assert handler._context.verify_mode == m.ssl.CERT_REQUIRED
    assert handler._context.check_hostname
    assert any(isinstance(h, m.RejectRedirects) for h in seen)


def test_insecure_context_cannot_be_used(monkeypatch):
    monkeypatch.setattr(m.ssl, "create_default_context", lambda: SimpleNamespace(verify_mode=m.ssl.CERT_NONE, check_hostname=False))
    with pytest.raises(ValueError, match="tls_verification_required"):
        m.secure_opener()


def test_strict_transfer_atomic_and_reuse(fixture, tmp_path):
    row, data = fixture
    opener = Opener(Response(row, data))
    result = run(row, tmp_path, opener)
    assert result["status"] == "new_exact_bytes_atomic_publish"
    target = tmp_path / row["restore_relative_path"]
    assert target.read_bytes() == data
    assert not target.with_name(target.name + ".partial").exists()
    assert len(opener.requests) == 1
    again = run(row, tmp_path, Opener(None))
    assert again["network_bytes"] == 0


@pytest.mark.parametrize("changes", [{"status": 206}, {"url": "https://evil.invalid/data.edf"},
                                    {"length": "999"}, {"length": ""}, {"encoding": "gzip"}])
def test_response_must_be_exact(fixture, tmp_path, changes):
    row, data = fixture
    with pytest.raises(ValueError):
        run(row, tmp_path, Opener(Response(row, data, **changes)))
    assert not (tmp_path / row["restore_relative_path"]).exists()


@pytest.mark.parametrize("kind", ["truncated", "oversized", "wronghash"])
def test_bad_body_preserved_as_partial_not_published(fixture, tmp_path, kind):
    row, data = fixture
    payload = {"truncated": data[:-1], "oversized": data + b"x", "wronghash": b"x" * len(data)}[kind]
    with pytest.raises(ValueError):
        run(row, tmp_path, Opener(Response(row, payload)))
    target = tmp_path / row["restore_relative_path"]
    assert not target.exists()
    assert target.with_name(target.name + ".partial").is_file()


def test_existing_corrupt_file_not_overwritten(fixture, tmp_path):
    row, _ = fixture
    target = tmp_path / row["restore_relative_path"]
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old failure evidence")
    opener = Opener(None)
    with pytest.raises(ValueError, match="corrupt_preserved"):
        run(row, tmp_path, opener)
    assert target.read_bytes() == b"old failure evidence"
    assert not opener.requests


def test_existing_partial_not_overwritten(fixture, tmp_path):
    row, _ = fixture
    partial = tmp_path / (row["restore_relative_path"] + ".partial")
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b"prior attempt")
    with pytest.raises(ValueError, match="existing_partial_preserved"):
        run(row, tmp_path, Opener(None))
    assert partial.read_bytes() == b"prior attempt"


def test_changed_hash_not_accepted_as_frozen(fixture, tmp_path):
    row, data = fixture
    forged = dict(row, sha256="0" * 64)
    with pytest.raises(ValueError, match="exact_frozen_manifest_identity"):
        run(forged, tmp_path, Opener(Response(forged, data)))


def test_symlink_root_rejected(fixture, tmp_path):
    row, _ = fixture
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        run(row, link, Opener(None))


def test_low_disk_rejects_before_network(fixture, tmp_path, monkeypatch):
    row, _ = fixture
    monkeypatch.setattr(m.shutil, "disk_usage", lambda path: SimpleNamespace(free=15 * m.GIB))
    opener = Opener(None)
    with pytest.raises(ValueError, match="insufficient_disk"):
        run(row, tmp_path, opener)
    assert not opener.requests


def test_write_cannot_knowingly_cross_reserved_floor(fixture, tmp_path, monkeypatch):
    row, data = fixture
    readings = iter([100 * m.GIB, 100 * m.GIB, 15 * m.GIB + len(data) - 1])
    monkeypatch.setattr(m.shutil, "disk_usage", lambda path: SimpleNamespace(free=next(readings)))
    with pytest.raises(ValueError, match="reserved_free_space_before_write"):
        run(row, tmp_path, Opener(Response(row, data)))
    target = tmp_path / row["restore_relative_path"]
    assert not target.exists()
    assert target.with_name(target.name + ".partial").read_bytes() == b""


@pytest.mark.parametrize("limits", [{"min_free_bytes": 9 * m.GIB}, {"max_new_bytes": m.NBYTES + 1},
                                    {"max_new_bytes": 1}, {"paper2_reserve_bytes": -1},
                                    {"paper2_reserve_bytes": True}])
def test_resource_limits_are_real_strict_integers(fixture, tmp_path, limits):
    row, _ = fixture
    with pytest.raises(ValueError):
        run(row, tmp_path, Opener(None), **limits)


def test_revocation_before_network(fixture, tmp_path):
    row, _ = fixture
    def revoke():
        raise ValueError("slot revoked")
    opener = Opener(None)
    with pytest.raises(ValueError, match="slot revoked"):
        run(row, tmp_path, opener, control_check=revoke)
    assert not opener.requests


def test_cli_is_plan_only(monkeypatch, capsys):
    monkeypatch.setattr(m, "transport_one", lambda *a, **k: pytest.fail("transport called"))
    monkeypatch.setattr(m, "frozen_plan", lambda: {"status": "offline plan"})
    monkeypatch.setattr("sys.argv", ["official_edf_transport.py"])
    m.main()
    assert json.loads(capsys.readouterr().out)["status"] == "offline plan"


def test_cached_receipt_verifies_only_synthetic_bytes_and_keeps_gates_false(fixture, tmp_path, monkeypatch):
    row, data = fixture
    monkeypatch.setattr(m, "NFILES", 1)
    monkeypatch.setattr(m, "NBYTES", len(data))
    target = tmp_path / row["restore_relative_path"]
    target.parent.mkdir(parents=True)
    target.write_bytes(data)
    receipt = m.verify_cached_manifest(tmp_path, control_check=lambda: None)
    assert receipt["verified_bytes"] == len(data)
    assert receipt["files"] == [{"path": row["restore_relative_path"], "bytes": len(data), "sha256": row["sha256"]}]
    assert not receipt["training_authorization"]
    assert not receipt["target_header_event_qc_and_input_hash_acceptance"]


def test_cached_receipt_requires_complete_manifest(fixture, tmp_path):
    with pytest.raises(ValueError, match="complete_frozen_cohort"):
        m.verify_cached_manifest(tmp_path, control_check=lambda: None)


def test_cached_receipt_preserves_corrupt_bytes(fixture, tmp_path, monkeypatch):
    row, data = fixture
    monkeypatch.setattr(m, "NFILES", 1)
    monkeypatch.setattr(m, "NBYTES", len(data))
    target = tmp_path / row["restore_relative_path"]
    target.parent.mkdir(parents=True)
    target.write_bytes(b"corrupt old bytes")
    with pytest.raises(ValueError, match="cached_frozen_edf_size_or_sha256_mismatch"):
        m.verify_cached_manifest(tmp_path, control_check=lambda: None)
    assert target.read_bytes() == b"corrupt old bytes"
