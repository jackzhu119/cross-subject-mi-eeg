"""No real network writes: exercise publication, byte verification and secrets."""
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import warnings
from urllib.error import HTTPError, URLError

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/cloud_transport.py"
spec = importlib.util.spec_from_file_location("cloud_transport_tests_subject", SCRIPT)
t = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = t
spec.loader.exec_module(t)
BASE = "a" * 40
JOB = "20261013T120000Z-cloud-fixture"
TOKEN = "fixture-private-github-token-83915"


class GitFixture:
    def __init__(self):
        self.refs = {}
        self.blobs = {}
        self.trees = {"base-tree": {}}
        self.commits = {BASE: {"tree": {"sha": "base-tree"}}}
        self.calls = []
        self.serial = 0

    def sha(self):
        self.serial += 1
        return f"{self.serial:040x}"

    def request(self, method, endpoint, payload=None):
        self.calls.append((method, endpoint, payload))
        endpoint = endpoint.split("/repos/" + t.REPO)[1]
        if method == "GET" and endpoint.startswith("/git/ref/heads/"):
            branch = endpoint.split("/git/ref/heads/")[1]
            if branch not in self.refs:
                raise t.TransportError("github_http_404", http_status=404)
            return {"object": {"sha": self.refs[branch]}}
        if method == "POST" and endpoint == "/git/refs":
            self.refs[payload["ref"].removeprefix("refs/heads/")] = payload["sha"]
            return {"object": {"sha": payload["sha"]}}
        if method == "GET" and endpoint.startswith("/contents/"):
            path, ref = endpoint.removeprefix("/contents/").split("?ref=")
            tree = self.trees[self.commits[ref]["tree"]["sha"]]
            if path not in tree:
                raise t.TransportError("github_http_404", http_status=404)
            return {"content": base64.b64encode(self.blobs[tree[path]]).decode()}
        if method == "GET" and endpoint.startswith("/git/commits/"):
            return self.commits[endpoint.split("/git/commits/")[1]]
        if method == "POST" and endpoint == "/git/blobs":
            sha = self.sha()
            self.blobs[sha] = base64.b64decode(payload["content"])
            return {"sha": sha}
        if method == "POST" and endpoint == "/git/trees":
            sha = self.sha()
            tree = dict(self.trees[payload["base_tree"]])
            tree.update({entry["path"]: entry["sha"] for entry in payload["tree"]})
            self.trees[sha] = tree
            return {"sha": sha}
        if method == "POST" and endpoint == "/git/commits":
            sha = self.sha()
            self.commits[sha] = {"tree": {"sha": payload["tree"]}, "parents": payload["parents"]}
            return {"sha": sha}
        if method == "PATCH" and endpoint.startswith("/git/refs/heads/"):
            assert payload["force"] is False
            self.refs[endpoint.split("/git/refs/heads/")[1]] = payload["sha"]
            return {"object": {"sha": payload["sha"]}}
        raise AssertionError((method, endpoint))

    def public(self, url):
        from urllib.parse import unquote
        prefix = "https://raw.githubusercontent.com/" + t.REPO + "/"
        commit, path = url.removeprefix(prefix).split("/", 1)
        tree = self.trees[self.commits[commit]["tree"]["sha"]]
        return self.blobs[tree[unquote(path)]]


class R2Fixture:
    def __init__(self, wrong_size=False, corrupt=False):
        self.objects = {}
        self.wrong_size = wrong_size
        self.corrupt = corrupt

    def upload_file(self, filename, bucket, key, ExtraArgs):
        data = Path(filename).read_bytes()
        assert ExtraArgs["Metadata"]["sha256"] == hashlib.sha256(data).hexdigest()
        self.objects[(bucket, key)] = data

    def head_object(self, Bucket, Key):
        size = len(self.objects[(Bucket, Key)])
        return {"ContentLength": size + int(self.wrong_size)}

    def get_object(self, Bucket, Key):
        data = self.objects[(Bucket, Key)]
        if self.corrupt:
            data = data[:-1] + bytes([data[-1] ^ 1])
        return {"Body": io.BytesIO(data)}


def test_private_credentials_hidden_and_reused_without_workspace(tmp_path):
    directory = tmp_path / "private"
    prompts = []
    def hidden(prompt):
        prompts.append(prompt)
        return TOKEN
    result = t.secure_credentials(private_root=directory, environ={}, prompt=hidden)
    assert result == {"GH_TOKEN": TOKEN}
    assert len(prompts) == 1
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE((directory / "credentials.json").stat().st_mode) == 0o600
    assert t.secure_credentials(private_root=directory, environ={}, interactive=False) == result
    assert not any("RUNPOD" in name for name in result)


def test_private_credentials_env_and_reset(tmp_path):
    directory = tmp_path / "private"
    t.secure_credentials(private_root=directory, environ={"GH_TOKEN": TOKEN})
    result = t.secure_credentials(private_root=directory, environ={"GH_TOKEN": "second-token"}, reset=True)
    assert result == {"GH_TOKEN": "second-token"}


def test_credentials_input_empty_fails_without_saved_partial(tmp_path):
    calls = []
    with pytest.raises(t.TransportError, match="required_credential_not_provided:GH_TOKEN"):
        t.secure_credentials(private_root=tmp_path / "private", environ={}, prompt=lambda p: calls.append(p) or "")
    assert len(calls) == 3
    assert not (tmp_path / "private/credentials.json").exists()


@pytest.mark.parametrize("mode", [0o666, 0o644, 0o777])
def test_unsafe_existing_cache_never_accepted(tmp_path, mode):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    cache = directory / "credentials.json"
    cache.write_text(json.dumps({"GH_TOKEN": TOKEN}))
    cache.chmod(mode)
    with pytest.raises(t.TransportError, match="credential_cache_permissions_unsafe"):
        t.secure_credentials(private_root=directory, environ={}, interactive=False)


def test_directory_chmod_ignored_is_detected(tmp_path, monkeypatch):
    directory = tmp_path / "private"
    directory.mkdir()
    directory.chmod(0o777)
    monkeypatch.setattr(t.os, "chmod", lambda *a, **k: None)
    with pytest.raises(t.TransportError, match="credential_directory_permissions_unsafe"):
        t.private_credential_root(directory)


def test_network_volume_cache_forbidden():
    with pytest.raises(t.TransportError, match="network_volume_forbidden"):
        t.private_credential_root("/workspace/.q15-cloud")


def test_cache_symlink_forbidden(tmp_path):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"GH_TOKEN": TOKEN}))
    (directory / "credentials.json").symlink_to(other)
    with pytest.raises(t.TransportError, match="credential_cache_symlink_forbidden"):
        t.secure_credentials(private_root=directory, environ={}, interactive=False)


def test_local_directory_parent_symlink_forbidden(tmp_path):
    destination = tmp_path / "real"
    destination.mkdir()
    shortcut = tmp_path / "shortcut"
    shortcut.symlink_to(destination)
    with pytest.raises(t.TransportError, match="credential_directory_symlink_forbidden"):
        t.private_credential_root(shortcut / "private")


def test_r2_requires_all_four_and_valid_cloudflare_endpoint(tmp_path):
    environment = {"GH_TOKEN": TOKEN, "R2_BUCKET": "eeg-research", "R2_ENDPOINT": "https://example.r2.cloudflarestorage.com",
                   "R2_ACCESS_KEY_ID": "fixture-access", "R2_SECRET_ACCESS_KEY": "fixture-secret"}
    values = t.secure_credentials(private_root=tmp_path / "private", environ=environment, enable_r2=True)
    assert set(values) == {"GH_TOKEN", *t.R2_NAMES}
    environment["R2_ENDPOINT"] = "https://evil.example/?secret=bad"
    with pytest.raises(t.TransportError, match="r2_endpoint_format_invalid"):
        t.secure_credentials(private_root=tmp_path / "private", environ=environment, enable_r2=True)


def test_control_char_credential_rejected(tmp_path):
    with pytest.raises(t.TransportError, match="credential_format_invalid"):
        t.secure_credentials(private_root=tmp_path / "private", environ={"GH_TOKEN": "a\nb"})


def test_hidden_input_never_falls_back_to_echo(tmp_path):
    def unavailable(prompt):
        warnings.warn("terminal echo unavailable", t.getpass.GetPassWarning)
        pytest.fail("getpass warning should stop before echoed input")
    with pytest.raises(t.TransportError, match="hidden_credential_terminal_unavailable"):
        t.secure_credentials(private_root=tmp_path / "private", environ={}, prompt=unavailable)


def test_github_atomic_public_byte_verified_snapshot(tmp_path):
    (tmp_path / "runtime.json").write_text('{"gpu_verified":true}\n')
    (tmp_path / "scores.csv").write_text("person,score\nA01,0.5\n")
    fixture = GitFixture()
    publisher = t.GitHubPublisher(TOKEN, request=fixture.request, get_public=fixture.public)
    receipt = publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path,
                                         relative_paths=["runtime.json", "scores.csv"], message="Fixture runtime before fitting",
                                         immutable_paths=["runtime.json"])
    assert receipt["status"] == "VERIFIED_PUBLIC_GITHUB_SNAPSHOT"
    assert receipt["github_public_readback_verified"] is True
    assert receipt["checkpoint_backup_verified"] is False
    assert receipt["artifacts"]["runtime.json"]["immutable"] is True
    assert len([call for call in fixture.calls if call[0] == "PATCH"]) == 1
    assert TOKEN not in json.dumps(receipt)
    assert receipt["branch"] == "redesign/run-" + JOB
    manifest = json.loads(fixture.public(f"https://raw.githubusercontent.com/{t.REPO}/{receipt['commit']}/{t.JOB_PREFIX}/{JOB}/publication_manifest.json"))
    assert manifest["raw_eeg_in_github"] is False
    assert manifest["checkpoints_in_github"] is False


def test_github_frozen_artifact_cannot_be_replaced(tmp_path):
    file = tmp_path / "source_freeze.json"
    file.write_text('{"schedule":20}')
    fixture = GitFixture()
    publisher = t.GitHubPublisher(TOKEN, request=fixture.request, get_public=fixture.public)
    arguments = dict(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=[file.name], message="Freeze",
                     immutable_paths=[file.name])
    publisher.publish_snapshot(**arguments)
    file.write_text('{"schedule":30}')
    count = len(fixture.calls)
    with pytest.raises(t.TransportError, match="publication_frozen_artifact_changed"):
        publisher.publish_snapshot(**arguments)
    assert all(method == "GET" for method, _, _ in fixture.calls[count:])


def test_github_status_can_advance_preserving_immutable_inventory(tmp_path):
    freeze = tmp_path / "freeze.json"
    status_file = tmp_path / "job_status.json"
    freeze.write_text('{"frozen":true}')
    status_file.write_text('{"stage":"initial"}')
    fixture = GitFixture()
    publisher = t.GitHubPublisher(TOKEN, request=fixture.request, get_public=fixture.public)
    publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=[freeze.name, status_file.name],
                               immutable_paths=[freeze.name], message="Before fits")
    status_file.write_text('{"stage":"training"}')
    receipt = publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path,
                                         relative_paths=[status_file.name], message="Update status")
    inventory = json.loads(fixture.public(f"https://raw.githubusercontent.com/{t.REPO}/{receipt['commit']}/{t.JOB_PREFIX}/{JOB}/publication_manifest.json"))
    assert inventory["artifacts"][freeze.name]["immutable"] is True
    assert inventory["artifacts"][status_file.name]["sha256"] == hashlib.sha256(status_file.read_bytes()).hexdigest()


def test_public_readback_failure_retains_committed_receipt(tmp_path):
    (tmp_path / "runtime.json").write_text("{}")
    fixture = GitFixture()
    publisher = t.GitHubPublisher(TOKEN, request=fixture.request, get_public=lambda url: b"wrong")
    with pytest.raises(t.TransportError, match="github_public_readback_mismatch") as caught:
        publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=["runtime.json"], message="Freeze")
    partial = caught.value.partial_receipt
    assert partial["status"] == "COMMITTED_PUBLIC_READBACK_UNVERIFIED"
    assert partial["github_public_readback_verified"] is False
    assert fixture.refs[partial["branch"]] == partial["commit"]


@pytest.mark.parametrize("filename", ["credentials.json", ".env", "GH_TOKEN.txt", "raw.edf", "inputs.npz", "model.pt", "model.joblib", "archive.zip"])
def test_disallowed_artifacts_fail_before_remote_write(tmp_path, filename):
    (tmp_path / filename).write_bytes(b"private-or-raw")
    fixture = GitFixture()
    publisher = t.GitHubPublisher(TOKEN, request=fixture.request)
    with pytest.raises(t.TransportError):
        publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=[filename], message="Do not publish")
    assert not fixture.calls


@pytest.mark.parametrize("name", ["../outside.json", "/absolute.json", "a\\b.json", "a//b.json", "line\nbreak.json"])
def test_path_traversal_rejected(tmp_path, name):
    publisher = t.GitHubPublisher(TOKEN, request=lambda *a: pytest.fail("remote API called"))
    with pytest.raises(t.TransportError, match="artifact_path_invalid"):
        publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=[name], message="Fixture")


def test_secret_content_never_published(tmp_path):
    (tmp_path / "runtime.json").write_text(json.dumps({"mistaken_value": TOKEN}))
    publisher = t.GitHubPublisher(TOKEN, request=lambda *a: pytest.fail("remote API called"))
    with pytest.raises(t.TransportError, match="publication_secret_content_forbidden"):
        publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=["runtime.json"], message="Fixture")


def test_unknown_credential_assignment_never_published(tmp_path):
    (tmp_path / "supervisor.log").write_text("R2_SECRET_ACCESS_KEY=another-unexpected-secret-value")
    publisher = t.GitHubPublisher(TOKEN, request=lambda *a: pytest.fail("remote API called"))
    with pytest.raises(t.TransportError, match="publication_credential_pattern_forbidden"):
        publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=["supervisor.log"], message="Fixture")


def test_artifact_symlink_blocked(tmp_path):
    real = tmp_path / "real.json"
    real.write_text("{}")
    (tmp_path / "linked.json").symlink_to(real)
    publisher = t.GitHubPublisher(TOKEN, request=lambda *a: pytest.fail("remote API called"))
    with pytest.raises(t.TransportError, match="publication_artifact_missing_or_symlink"):
        publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=["linked.json"], message="Fixture")


def test_size_limit_before_upload(tmp_path, monkeypatch):
    (tmp_path / "scores.csv").write_bytes(b"123456")
    monkeypatch.setattr(t, "MAX_GITHUB_BYTES", 5)
    publisher = t.GitHubPublisher(TOKEN, request=lambda *a: pytest.fail("remote API called"))
    with pytest.raises(t.TransportError, match="publication_artifact_size_limit"):
        publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=["scores.csv"], message="Fixture")


def test_existing_branch_identity_collision_blocked(tmp_path):
    (tmp_path / "runtime.json").write_text("{}")
    fixture = GitFixture()
    fixture.commits["b" * 40] = {"tree": {"sha": "base-tree"}}
    fixture.refs["redesign/run-" + JOB] = "b" * 40
    publisher = t.GitHubPublisher(TOKEN, request=fixture.request)
    with pytest.raises(t.TransportError, match="publication_branch_identity_mismatch"):
        publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=["runtime.json"], message="Fixture")
    assert all(method == "GET" for method, _, _ in fixture.calls)


def test_github_auth_error_is_sanitized_failfast():
    calls = []
    def opener(request, **kwargs):
        calls.append(request)
        raise HTTPError("https://example?secret=" + TOKEN, 403, "private response " + TOKEN, {}, io.BytesIO(TOKEN.encode()))
    api = t.GitHubAPI(TOKEN, opener=opener, sleeper=lambda _: pytest.fail("403 retried"))
    with pytest.raises(t.TransportError) as caught:
        api("GET", "/repos/owner/repo/git/refs")
    assert str(caught.value) == "github_http_403"
    assert TOKEN not in str(caught.value)
    assert len(calls) == 1


def test_github_transient_error_retry_then_success():
    count = 0
    pauses = []
    def opener(request, **kwargs):
        nonlocal count
        count += 1
        if count < 3:
            raise HTTPError("url", 503, "unavailable", {}, io.BytesIO(b"private"))
        return io.BytesIO(b'{"sha":"ok"}')
    api = t.GitHubAPI(TOKEN, opener=opener, sleeper=pauses.append)
    assert api("GET", "/repos/owner/repo/git/refs") == {"sha": "ok"}
    assert count == 3
    assert pauses == [1, 2]


def test_github_network_error_does_not_expose_url():
    def opener(request, **kwargs):
        raise URLError("private URL " + TOKEN)
    api = t.GitHubAPI(TOKEN, opener=opener, sleeper=lambda _: None, attempts=2)
    with pytest.raises(t.TransportError, match="github_network_error") as caught:
        api("GET", "/repos/owner/repo/git/refs")
    assert TOKEN not in str(caught.value)


def test_public_reader_has_no_authorization_header():
    captured = []
    def opener(request, **kwargs):
        captured.append(request)
        return io.BytesIO(b"report")
    result = t.public_bytes(f"https://raw.githubusercontent.com/{t.REPO}/{BASE}/file.json", opener=opener)
    assert result == b"report"
    assert not captured[0].has_header("Authorization")


def test_r2_checkpoint_requires_complete_byte_readback(tmp_path):
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"fixture checkpoint bytes")
    credentials = dict(zip(t.R2_NAMES, ["fixture-bucket", "endpoint", "access", "secret"]))
    receipt = t.R2CheckpointBackup(credentials, client=R2Fixture()).upload_and_verify({"models/model.pt": checkpoint}, key_prefix="redesign/job")
    assert receipt["checkpoint_backup_verified"] is True
    assert receipt["objects"][0]["sha256"] == hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    assert receipt["objects"][0]["complete_byte_readback_verified"] is True
    assert "secret" not in json.dumps(receipt)


@pytest.mark.parametrize("wrong_size,corrupt,error", [(True, False, "r2_backup_size_mismatch"), (False, True, "r2_backup_byte_readback_mismatch")])
def test_r2_upload_acceptance_and_metadata_are_not_backup_proof(tmp_path, wrong_size, corrupt, error):
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    credentials = dict(zip(t.R2_NAMES, ["fixture-bucket", "endpoint", "access", "secret"]))
    with pytest.raises(t.TransportError, match=error):
        t.R2CheckpointBackup(credentials, client=R2Fixture(wrong_size, corrupt)).upload_and_verify({"model.pt": checkpoint}, key_prefix="redesign/job")


def test_r2_client_error_sanitized(tmp_path):
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"checkpoint")
    class Broken:
        def upload_file(self, *args, **kwargs):
            raise ValueError("SDK exception containing fixture-private-secret")
    credentials = dict(zip(t.R2_NAMES, ["fixture-bucket", "endpoint", "access", "fixture-private-secret"]))
    with pytest.raises(t.TransportError) as caught:
        t.R2CheckpointBackup(credentials, client=Broken()).upload_and_verify({"model.pt": checkpoint}, key_prefix="redesign/job")
    assert str(caught.value) == "r2_backup_request_failed"
    assert "fixture-private-secret" not in str(caught.value)


def test_r2_raw_eeg_not_implicitly_uploaded(tmp_path):
    raw = tmp_path / "person.edf"
    raw.write_bytes(b"raw")
    credentials = dict(zip(t.R2_NAMES, ["fixture-bucket", "endpoint", "access", "secret"]))
    with pytest.raises(t.TransportError, match="r2_backup_artifact_forbidden"):
        t.R2CheckpointBackup(credentials, client=R2Fixture()).upload_and_verify({"raw.edf": raw}, key_prefix="redesign/job")


def test_r2_result_log_containing_private_values_blocked(tmp_path):
    log = tmp_path / "supervisor.log"
    log.write_text("mistaken log value: fixture-r2-private-secret")
    credentials = dict(zip(t.R2_NAMES, ["fixture-bucket", "endpoint", "access-id-fixture", "fixture-r2-private-secret"]))
    with pytest.raises(t.TransportError, match="r2_backup_secret_content_forbidden"):
        t.R2CheckpointBackup(credentials, client=R2Fixture()).upload_and_verify({"supervisor.log": log}, key_prefix="redesign/job")


def completed_checkpoint(root, relative="source/final/BROAD_EEGNET/101/checkpoint.pt", status="completed"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture completed model weights without EEG")
    (path.parent / "fit_receipt.json").write_text(json.dumps({"status": status, "checkpoint_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
    return relative


@pytest.mark.parametrize("relative", ["source/final/BROAD_EEGNET/101/checkpoint.pt", "source/inner/SHARED_EEGNET/group01/checkpoint.pt"])
def test_completed_source_checkpoint_publicly_backed_up(tmp_path, relative):
    name = completed_checkpoint(tmp_path, relative)
    fixture = GitFixture()
    publisher = t.GitHubPublisher(TOKEN, request=fixture.request, get_public=fixture.public)
    receipt = publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path,
                                         relative_paths=[name], immutable_paths=[name], message="Freeze completed source checkpoint")
    assert receipt["checkpoint_backup_verified"] is True
    assert receipt["completed_checkpoint_count"] == 1
    inventory = json.loads(fixture.public(f"https://raw.githubusercontent.com/{t.REPO}/{receipt['commit']}/{t.JOB_PREFIX}/{JOB}/publication_manifest.json"))
    assert inventory["checkpoints_in_github"] is True
    assert inventory["raw_eeg_in_github"] is False


@pytest.mark.parametrize("status", ["running", "failed", "not_started", None])
def test_source_checkpoint_requires_completed_matching_fit_receipt(tmp_path, status):
    name = completed_checkpoint(tmp_path, status=status)
    fixture = GitFixture()
    publisher = t.GitHubPublisher(TOKEN, request=fixture.request)
    with pytest.raises(t.TransportError, match="publication_checkpoint_not_completed"):
        publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=[name], message="Fixture")
    assert not fixture.calls


def test_checkpoint_sha_mismatch_not_published(tmp_path):
    name = completed_checkpoint(tmp_path)
    (tmp_path / name).write_bytes(b"later changed checkpoint")
    fixture = GitFixture()
    publisher = t.GitHubPublisher(TOKEN, request=fixture.request)
    with pytest.raises(t.TransportError, match="publication_checkpoint_not_completed"):
        publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=[name], message="Fixture")
    assert not fixture.calls


@pytest.mark.parametrize("name", ["source/checkpoint.pt", "target/checkpoint.pt", "source/final/model/resume_state.pt", "source/final/model/update_intent.pt", "raw_cache/checkpoint.pt"])
def test_checkpoint_allowlist_rejects_resume_and_input_locations(tmp_path, name):
    path = tmp_path / name
    path.parent.mkdir(parents=True)
    path.write_bytes(b"state")
    fixture = GitFixture()
    publisher = t.GitHubPublisher(TOKEN, request=fixture.request)
    with pytest.raises(t.TransportError, match="publication_artifact_type_forbidden"):
        publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=[name], message="Fixture")
    assert not fixture.calls


def write_logits(root, name, *, raw=False, eeg_shape=False, object_ids=False):
    import numpy as np
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    values = np.zeros((2, 19, 320) if eeg_shape else (2, 2), dtype=np.float32)
    event_ids = np.asarray(["event-1", "event-2"], dtype=object if object_ids else str)
    np.savez(path, event_ids=event_ids, **({"BROAD_EEGNET__SOURCE_MINLOSS__101": values} if raw else {"logits": values}))
    return name


@pytest.mark.parametrize("name,raw", [("target/raw_logits.npz", True), ("target/cells/BROAD_EEGNET__SOURCE_MINLOSS__101.npz", False)])
def test_target_prediction_npz_only_is_publicly_verified(tmp_path, name, raw):
    write_logits(tmp_path, name, raw=raw)
    fixture = GitFixture()
    publisher = t.GitHubPublisher(TOKEN, request=fixture.request, get_public=fixture.public)
    receipt = publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=[name], message="Backup target model outputs")
    assert receipt["github_public_readback_verified"] is True
    assert receipt["checkpoint_backup_verified"] is False
    inventory = json.loads(fixture.public(f"https://raw.githubusercontent.com/{t.REPO}/{receipt['commit']}/{t.JOB_PREFIX}/{JOB}/publication_manifest.json"))
    assert inventory["prediction_only_npz_in_github"] is True


@pytest.mark.parametrize("name", ["input_cache/A01.npz", "target/input.npz", "source/inputs.npz", "target/cells/extra/nested.npz"])
def test_input_npz_paths_are_forbidden_even_with_logits_content(tmp_path, name):
    write_logits(tmp_path, name)
    fixture = GitFixture()
    publisher = t.GitHubPublisher(TOKEN, request=fixture.request)
    with pytest.raises(t.TransportError, match="publication_artifact_type_forbidden"):
        publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=[name], message="Fixture")
    assert not fixture.calls


@pytest.mark.parametrize("kwargs", [{"eeg_shape": True}, {"object_ids": True}])
def test_typed_prediction_path_does_not_authorize_eeg_arrays_or_pickle(tmp_path, kwargs):
    name = write_logits(tmp_path, "target/cells/cell.npz", **kwargs)
    fixture = GitFixture()
    publisher = t.GitHubPublisher(TOKEN, request=fixture.request)
    with pytest.raises(t.TransportError, match="publication_prediction_output_schema_invalid"):
        publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=[name], message="Fixture")
    assert not fixture.calls


def test_unchanged_blob_delta_preserves_frozen_bytes(tmp_path):
    (tmp_path / "freeze.json").write_text('{"frozen":true}')
    (tmp_path / "job_status.json").write_text('{"stage":"first"}')
    fixture = GitFixture()
    publisher = t.GitHubPublisher(TOKEN, request=fixture.request, get_public=fixture.public)
    first = publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path,
        relative_paths=["freeze.json", "job_status.json"], immutable_paths=["freeze.json"], message="Freeze")
    (tmp_path / "job_status.json").write_text('{"stage":"second"}')
    count = len(fixture.calls)
    second = publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path,
        relative_paths=["freeze.json", "job_status.json"], message="Update")
    uploads = [payload for method, endpoint, payload in fixture.calls[count:] if method == "POST" and endpoint.endswith("/git/blobs")]
    assert len(uploads) == 2  # Changed status and inventory, never frozen artifact.
    assert second["new_artifact_blob_count"] == 1
    assert second["artifacts"]["freeze.json"]["git_blob_sha"] == first["artifacts"]["freeze.json"]["git_blob_sha"]
    count = len(fixture.calls)
    third = publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path,
        relative_paths=["freeze.json", "job_status.json"], message="No-op identical snapshot")
    assert third["commit"] == second["commit"]
    assert all(method == "GET" for method, _, _ in fixture.calls[count:])


def test_aggregate_limit_counts_old_inventory_and_new_artifacts(tmp_path, monkeypatch):
    (tmp_path / "first.json").write_bytes(b"{}")
    fixture = GitFixture()
    publisher = t.GitHubPublisher(TOKEN, request=fixture.request, get_public=fixture.public)
    publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=["first.json"], message="First")
    (tmp_path / "second.json").write_bytes(b"{}")
    monkeypatch.setattr(t, "MAX_GITHUB_TOTAL_BYTES", 3)
    count = len(fixture.calls)
    with pytest.raises(t.TransportError, match="publication_aggregate_size_limit"):
        publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=["second.json"], message="Second")
    assert all(method == "GET" for method, _, _ in fixture.calls[count:])


def test_checkpoint_receipt_requires_public_bytes_even_on_status_only_update(tmp_path):
    checkpoint_name = completed_checkpoint(tmp_path)
    fixture = GitFixture()
    publisher = t.GitHubPublisher(TOKEN, request=fixture.request, get_public=fixture.public)
    publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=[checkpoint_name], message="Checkpoint backup")
    (tmp_path / "job_status.json").write_text('{"stage":"later"}')
    def corrupt_checkpoint(url):
        return b"corrupt" if url.endswith("/checkpoint.pt") else fixture.public(url)
    publisher._get_public = corrupt_checkpoint
    with pytest.raises(t.TransportError, match="github_public_checkpoint_readback_mismatch") as caught:
        publisher.publish_snapshot(job_id=JOB, base_commit=BASE, local_root=tmp_path, relative_paths=["job_status.json"], message="Status")
    assert caught.value.partial_receipt["checkpoint_backup_verified"] is False


def test_r2_reports_only_never_claim_checkpoint_backup(tmp_path):
    (tmp_path / "report.json").write_text('{"completed":true}')
    credentials = dict(zip(t.R2_NAMES, ["fixture-bucket", "endpoint", "access-id-fixture", "fixture-r2-private-secret"]))
    receipt = t.R2CheckpointBackup(credentials, client=R2Fixture()).backup(job_id=JOB, local_root=tmp_path, relative_paths=["report.json"])
    assert receipt["checkpoint_backup_verified"] is False
    assert receipt["objects"][0]["complete_byte_readback_verified"] is True


def test_r2_target_logits_backup_and_raw_cache_rejection(tmp_path):
    name = write_logits(tmp_path, "target/cells/cell.npz")
    credentials = dict(zip(t.R2_NAMES, ["fixture-bucket", "endpoint", "access-id-fixture", "fixture-r2-private-secret"]))
    backup = t.R2CheckpointBackup(credentials, client=R2Fixture())
    receipt = backup.backup(job_id=JOB, local_root=tmp_path, relative_paths=[name])
    assert receipt["checkpoint_backup_verified"] is False
    write_logits(tmp_path, "input_cache/A01.npz")
    with pytest.raises(t.TransportError, match="r2_backup_artifact_forbidden"):
        backup.backup(job_id=JOB, local_root=tmp_path, relative_paths=["input_cache/A01.npz"])
