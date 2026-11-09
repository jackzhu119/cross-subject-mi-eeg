"""Offline custody transport tests: no network, EEG runtime, fitting, or Pod API."""
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_q15_migration_bundle import _export, _git
from test_q15_migration_bundle import bundle as fixture_bundle

pytest_plugins = ("test_q15_migration_bundle",)


MODULE_PATH = Path(__file__).resolve().parents[1] / "research_runs/Q15-MIGRATION-20261004/q15_migration_transport.py"
SPEC = importlib.util.spec_from_file_location("q15_migration_transport_tests", MODULE_PATH)
transport = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(transport)


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


class RemoteError(RuntimeError):
    def __init__(self, code="AccessDenied", status=403):
        super().__init__("PRIVATE_ENDPOINT SECRET_ACCESS_KEY GH_TOKEN RUNPOD_API_KEY")
        self.response = {"Error": {"Code": code, "Message": str(self)},
                         "ResponseMetadata": {"HTTPStatusCode": status}}


class FakeS3:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})
        self.calls = []
        self.bodies = []
        self.parts = {}
        self.corrupt_get = False
        self.fail_part = False
        self.bad_range = False
        self.bad_etag = False
        self.deny_list = False

    def list_objects_v2(self, **args):
        self.calls.append(("list", args))
        if self.deny_list:
            raise RemoteError()
        return {"Contents": [{"Key": key} for key in self.objects if key.startswith(args["Prefix"])]}

    def put_object(self, **args):
        self.calls.append(("put", args))
        self.objects[args["Key"]] = args["Body"]
        return {}

    def delete_object(self, **args):
        self.calls.append(("delete", args))
        self.objects.pop(args["Key"], None)
        return {"ResponseMetadata": {"HTTPStatusCode": 204}}

    def head_object(self, **args):
        self.calls.append(("head", args))
        if args["Key"] not in self.objects:
            raise RemoteError("NoSuchKey", 404)
        payload = self.objects[args["Key"]]
        return {"ContentLength": len(payload), "ETag": '"' + sha(payload) + '"',
                "Metadata": {"sha256": sha(payload)}}

    def get_object(self, **args):
        self.calls.append(("get", args))
        payload = self.objects[args["Key"]]
        etag = '"' + sha(payload) + '"'
        if args.get("IfMatch", etag) != etag:
            raise RemoteError("PreconditionFailed", 412)
        offset = int(args["Range"].split("=")[1].split("-")[0]) if "Range" in args else 0
        chunk = payload[offset:]
        if self.corrupt_get and chunk:
            chunk = bytes([chunk[0] ^ 1]) + chunk[1:]
        body = io.BytesIO(chunk)
        self.bodies.append(body)
        response = {"ContentLength": len(chunk), "Body": body,
                    "ETag": '"changed"' if self.bad_etag else etag}
        if offset:
            response["ContentRange"] = ("bytes 0-1/2" if self.bad_range
                                        else f"bytes {offset}-{len(payload) - 1}/{len(payload)}")
        return response

    def create_multipart_upload(self, **args):
        self.calls.append(("create", args))
        self.parts["upload-1"] = {}
        return {"UploadId": "upload-1"}

    def upload_part(self, **args):
        self.calls.append(("part", {key: value for key, value in args.items() if key != "Body"}))
        if self.fail_part:
            raise RemoteError()
        self.parts[args["UploadId"]][args["PartNumber"]] = args["Body"]
        return {"ETag": '"part-' + str(args["PartNumber"]) + '"'}

    def complete_multipart_upload(self, **args):
        self.calls.append(("complete", args))
        self.objects[args["Key"]] = b"".join(self.parts[args["UploadId"]][row["PartNumber"]]
                                                for row in args["MultipartUpload"]["Parts"])
        return {}

    def abort_multipart_upload(self, **args):
        self.calls.append(("abort", args))
        self.parts.pop(args["UploadId"], None)
        return {}


def test_client_uses_only_explicit_r2_environment(monkeypatch):
    captured = {}

    def client(service, **kwargs):
        captured.update(kwargs)
        assert service == "s3"
        return "client"

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=client))
    monkeypatch.setitem(sys.modules, "botocore.config", SimpleNamespace(Config=lambda **kwargs: kwargs))
    environment = {"R2_BUCKET": "private-bucket", "R2_ENDPOINT": "https://private.example",
                   "R2_ACCESS_KEY_ID": "PRIVATE_ID", "R2_SECRET_ACCESS_KEY": "PRIVATE_SECRET",
                   "GH_TOKEN": "UNUSED", "RUNPOD_API_KEY": "UNUSED"}
    assert transport.make_s3(environment) == ("client", "private-bucket")
    assert captured["aws_access_key_id"] == "PRIVATE_ID"
    assert captured["aws_secret_access_key"] == "PRIVATE_SECRET"
    assert captured["region_name"] == "auto"
    assert captured["config"]["signature_version"] == "s3v4"
    assert captured["config"]["s3"] == {"addressing_style": "path"}
    # Preserve the SDK checksum defaults verified with the credential proxy.
    assert "request_checksum_calculation" not in captured["config"]
    assert "response_checksum_validation" not in captured["config"]
    assert "aws_session_token" not in captured


@pytest.mark.parametrize("endpoint", ["http://example.test", "https://user:secret@example.test",
                                      "https://example.test/?token=secret"])
def test_invalid_endpoint_refused_without_value(endpoint):
    env = {"R2_BUCKET": "bucket", "R2_ENDPOINT": endpoint,
           "R2_ACCESS_KEY_ID": "id", "R2_SECRET_ACCESS_KEY": "secret"}
    with pytest.raises(transport.MigrationError, match="r2_endpoint_invalid"):
        transport.make_s3(env)


@pytest.mark.parametrize("path", [".", "..", "a/../b", "/a", "a//b", "a/./b", "a/", "a\\b", "a\nb"])
def test_unsafe_relative_paths_rejected(path):
    with pytest.raises(transport.MigrationError, match="unsafe_relative_path"):
        transport.safe_relative(path)


def test_probe_lists_writes_fully_reads_and_deletes_only_random_own_key():
    client = FakeS3({"q15/raw/keep": b"keep"})
    assert all(transport.probe_r2(client, "private-bucket").values())
    assert [name for name, _ in client.calls] == ["list", "put", "get", "delete", "head"]
    own_key = client.calls[1][1]["Key"]
    assert own_key.startswith(client.calls[0][1]["Prefix"])
    assert own_key.startswith("q15/migrations/probes/")
    assert client.calls[-2][1]["Key"] == client.calls[-1][1]["Key"] == own_key
    assert client.objects == {"q15/raw/keep": b"keep"}
    assert client.bodies[0].closed


def test_probe_hash_failure_cleans_own_object_and_stops():
    client = FakeS3()
    client.corrupt_get = True
    with pytest.raises(transport.MigrationError, match="full_get_readback_hash_mismatch"):
        transport.probe_r2(client, "bucket")
    assert not client.objects
    assert client.calls[-2][0] == "delete"
    assert all(body.closed for body in client.bodies)


def test_probe_list_denial_has_no_mutations():
    client = FakeS3()
    client.deny_list = True
    with pytest.raises(RemoteError):
        transport.probe_r2(client, "bucket")
    assert [name for name, _ in client.calls] == ["list"]


def test_probe_delete_acknowledgement_alone_cannot_mark_deleted():
    class NoDeleteS3(FakeS3):
        def delete_object(self, **args):
            self.calls.append(("delete", args))
            return {"ResponseMetadata": {"HTTPStatusCode": 204}}

    client = NoDeleteS3()
    with pytest.raises(transport.MigrationError, match="probe_delete_not_verified"):
        transport.probe_r2(client, "bucket")
    assert client.calls[-1][0] == "head"


def test_probe_delete_denial_cannot_mark_ready():
    class DeniedDeleteS3(FakeS3):
        def delete_object(self, **args):
            self.calls.append(("delete", args))
            raise RemoteError()

    with pytest.raises(RemoteError):
        transport.probe_r2(DeniedDeleteS3(), "bucket")


def test_streaming_multipart_archive_requires_full_get(tmp_path):
    payload = b"a" * (5 * 1024 * 1024) + b"tail"
    archive = tmp_path / "source.tar"
    archive.write_bytes(payload)
    client = FakeS3()
    receipt = transport.upload_archive(client, "bucket", archive, "q15/migrations/job/source.tar",
                                       part_bytes=5 * 1024 * 1024)
    assert receipt["archive_sha256"] == sha(payload)
    assert receipt["bytes"] == len(payload)
    assert receipt["readback_verified"] is True
    assert [name for name, _ in client.calls].count("part") == 2
    assert next(args for name, args in client.calls if name == "complete")["IfNoneMatch"] == "*"
    assert client.calls[-1][0] == "get"
    assert "Range" not in client.calls[-1][1]
    assert all(body.closed for body in client.bodies)


def test_multipart_failure_aborts_only_own_upload(tmp_path):
    archive = tmp_path / "source.tar"
    archive.write_bytes(b"archive")
    client = FakeS3()
    client.fail_part = True
    with pytest.raises(RemoteError):
        transport.upload_archive(client, "bucket", archive, "q15/migrations/job/source.tar")
    assert client.calls[-1][0] == "abort"
    assert not any(name in {"complete", "get", "delete"} for name, _ in client.calls)


def test_readback_cannot_use_head_metadata_as_hash_proof(tmp_path):
    archive = tmp_path / "source.tar"
    archive.write_bytes(b"archive")
    client = FakeS3()
    client.corrupt_get = True
    with pytest.raises(transport.MigrationError, match="full_get_readback_hash_mismatch"):
        transport.upload_archive(client, "bucket", archive, "q15/migrations/job/source.tar")
    assert client.calls[-1][0] == "get"
    assert not any(name == "delete" for name, _ in client.calls)


def test_content_addressed_existing_object_is_read_back_without_overwrite(tmp_path):
    archive = tmp_path / "source.tar"
    archive.write_bytes(b"archive")
    client = FakeS3({"q15/migrations/job/source.tar": b"archive"})
    assert transport.upload_archive(client, "bucket", archive, "q15/migrations/job/source.tar")["reused"] is True
    assert [name for name, _ in client.calls] == ["head", "get"]
    client.objects["q15/migrations/job/source.tar"] = b"changed"
    with pytest.raises(transport.MigrationError, match="full_get_readback_hash_mismatch"):
        transport.upload_archive(client, "bucket", archive, "q15/migrations/job/source.tar")
    assert client.objects["q15/migrations/job/source.tar"] == b"changed"


def test_download_verifies_persisted_identity_and_reuses_only_exact(tmp_path):
    payload = b"raw original bytes"
    client = FakeS3({"q15/raw/Cho2017/file": payload})
    target = tmp_path / "raw.mat"
    proof = transport.download_verified(client, "bucket", "q15/raw/Cho2017/file", target,
                                       sha(payload), len(payload))
    assert proof["verified"] is True and target.read_bytes() == payload
    assert transport.download_verified(client, "bucket", "q15/raw/Cho2017/file", target,
                                       sha(payload), len(payload))["reused"] is True
    count = len(client.calls)
    target.write_bytes(b"changed final file")
    with pytest.raises(transport.MigrationError, match="existing_destination_changed"):
        transport.download_verified(client, "bucket", "q15/raw/Cho2017/file", target,
                                    sha(payload), len(payload))
    assert len(client.calls) == count
    assert target.read_bytes() == b"changed final file"


def test_corrupt_download_never_promotes_final(tmp_path):
    payload = b"raw original bytes"
    client = FakeS3({"q15/raw/Cho2017/file": payload})
    client.corrupt_get = True
    target = tmp_path / "raw.mat"
    with pytest.raises(transport.MigrationError, match="persisted_download_hash_mismatch"):
        transport.download_verified(client, "bucket", "q15/raw/Cho2017/file", target,
                                    sha(payload), len(payload))
    assert not target.exists()
    assert all(body.closed for body in client.bodies)


def resumed_download_fixture(tmp_path):
    payload, key = b"0123456789", "q15/raw/Cho2017/file"
    client = FakeS3({key: payload})
    target = tmp_path / "raw.mat"
    target.with_name(target.name + ".part").write_bytes(payload[:4])
    marker = target.with_name(target.name + ".part.json")
    marker.write_text(json.dumps({"object_key": key, "sha256": sha(payload),
                                  "size_bytes": len(payload), "etag": '"' + sha(payload) + '"'}))
    return client, target, payload, key


def test_resume_etag_range_and_full_persisted_hash(tmp_path):
    client, target, payload, key = resumed_download_fixture(tmp_path)
    assert transport.download_verified(client, "bucket", key, target, sha(payload), len(payload))["verified"] is True
    request = next(args for name, args in client.calls if name == "get")
    assert request["Range"] == "bytes=4-"
    assert request["IfMatch"] == '"' + sha(payload) + '"'
    assert target.read_bytes() == payload


@pytest.mark.parametrize("flag,error", [("bad_range", "get_content_range_mismatch"),
                                       ("bad_etag", "get_etag_mismatch")])
def test_resume_rejects_range_or_object_identity_change(tmp_path, flag, error):
    client, target, payload, key = resumed_download_fixture(tmp_path)
    setattr(client, flag, True)
    with pytest.raises(transport.MigrationError, match=error):
        transport.download_verified(client, "bucket", key, target, sha(payload), len(payload))
    assert not target.exists()
    assert all(body.closed for body in client.bodies)


def test_full_get_restore_uses_fresh_temp_and_can_retry(tmp_path):
    payload = b"source archive"
    target, key = tmp_path / "archive.tar", "q15/migrations/job/archive.tar"
    client = FakeS3({key: payload})
    client.corrupt_get = True
    with pytest.raises(transport.MigrationError, match="persisted_download_hash_mismatch"):
        transport.download_verified(client, "bucket", key, target, sha(payload),
                                    full_get_required=True, resume=False)
    assert not list(tmp_path.glob("*.part*"))
    client.corrupt_get = False
    assert transport.download_verified(client, "bucket", key, target, sha(payload),
                                       full_get_required=True, resume=False)["full_get_verified"] is True
    assert transport.download_verified(client, "bucket", key, target, sha(payload),
                                       full_get_required=True, resume=False)["full_get_verified"] is True
    assert all("Range" not in args for name, args in client.calls if name == "get")


def test_download_refuses_ancestor_symlink(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(transport.MigrationError, match="destination_symlink"):
        transport.download_verified(FakeS3(), "bucket", "q15/raw/file", link / "file.mat", sha(b"x"), 1)
    assert not list(actual.iterdir())


def inventory_fixture(tmp_path):
    repo, raw_root = tmp_path / "repo", tmp_path / "raw"
    inventory, receipts = [], {}
    for dataset in transport.RAW_PREFIXES:
        records = []
        for file_id in sorted(transport.expected_file_ids(dataset)):
            payload = (dataset + file_id).encode()
            row = {"dataset": dataset, "file_id": file_id, "sha256": sha(payload),
                   "md5": hashlib.md5(payload).hexdigest(), "size_bytes": len(payload)}
            inventory.append(row)
            records.append({**row, "path": str(raw_root / dataset / file_id)})
        receipt = {"dataset": dataset, "raw_hashes_verified": True,
                   "all_expected_files_hashed": True, "files": records}
        path = repo / transport.AUDIT_RECEIPTS[dataset]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt))
        receipts[dataset] = path
    path = repo / "research_runs/Q15-PREPARATION/transport_inventory.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "files": inventory}))
    return repo, raw_root, inventory, receipts


def test_inventory_cross_checks_all_160_audited_paths_hashes_sizes(tmp_path):
    repo, raw_root, _, _ = inventory_fixture(tmp_path)
    rows = transport.load_raw_inventory(repo, raw_root, require_committed=False)
    assert len(rows) == 160
    assert len({row["path"] for row in rows}) == 160
    for row in rows:
        assert row["r2_object_key"] == transport.RAW_PREFIXES[row["dataset"]] + row["file_id"]


def bnci_fixture(tmp_path):
    repo, raw_root = tmp_path / "repo", tmp_path / "raw"
    source, rows, objects = [], [], {}
    for subject in range(1, 10):
        for session in ("E", "T"):
            name = f"A{subject:02d}{session}.mat"
            payload = ("synthetic-source-" + name).encode()
            digest = sha(payload)
            source.append({"path": "/original/frozen/" + name, "bytes": len(payload), "sha256": digest})
            key = f"q15/source-originals/BNCI2014_001/{digest}/{name}"
            rows.append({"file_id": name, "sha256": digest, "size_bytes": len(payload),
                         "md5": hashlib.md5(payload).hexdigest(), "r2_object_key": key,
                         "persisted_readback_verified": True, "r2_full_readback_verified": True})
            objects[key] = payload
    source_path = repo / "research_runs/Q8-E001/results/source_files.json"
    receipt_path = repo / "research_runs/Q15-PREPARATION/BNCI_R2_SOURCE_RECEIPT_20261003.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(json.dumps(source))
    receipt_path.write_text(json.dumps({"files": rows, "n_files": 18, "r2_verified_files": 18,
                                        "r2_verified_size_bytes": sum(row["size_bytes"] for row in rows)}))
    return repo, raw_root, source_path, receipt_path, objects


def test_bnci_committed_receipt_matches_all18_frozen_source_hashes(tmp_path):
    repo, raw_root, _, _, _ = bnci_fixture(tmp_path)
    _git(repo, "init", "--quiet")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.test",
         "commit", "--quiet", "-m", "Synthetic source R2 custody")
    revision = _git(repo, "rev-parse", "HEAD")
    records = transport.load_bnci_inventory(repo, raw_root, revision=revision)
    assert len(records) == 18
    assert {row["file_id"] for row in records} == transport.expected_bnci_ids()
    assert all(row["path"] == str(raw_root / "BNCI2014_001" / row["file_id"]) for row in records)


@pytest.mark.parametrize("field,value", [("sha256", "0" * 64), ("size_bytes", True),
                                         ("persisted_readback_verified", False),
                                         ("r2_full_readback_verified", False),
                                         ("r2_object_key", "q15/source-originals/other/source.mat"),
                                         ("file_id", "A01E.mat/../../secret")])
def test_bnci_receipt_mutation_rejected(tmp_path, field, value):
    repo, raw_root, _, receipt_path, _ = bnci_fixture(tmp_path)
    receipt = json.loads(receipt_path.read_text())
    receipt["files"][0][field] = value
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(transport.MigrationError):
        transport.load_bnci_inventory(repo, raw_root, require_committed=False)


def test_bnci_duplicate_original_identity_rejected(tmp_path):
    repo, raw_root, _, receipt_path, _ = bnci_fixture(tmp_path)
    receipt = json.loads(receipt_path.read_text())
    receipt["files"][1] = receipt["files"][0]
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(transport.MigrationError, match="bnci_r2_receipt_identity_invalid"):
        transport.load_bnci_inventory(repo, raw_root, require_committed=False)


def test_bnci18_downloads_persisted_hashes_and_reuses_only_verified_outputs(tmp_path):
    repo, raw_root, _, _, objects = bnci_fixture(tmp_path)
    records = transport.load_bnci_inventory(repo, raw_root, require_committed=False)
    client = FakeS3(objects)
    evidence = transport.restore_source_originals(client, "private-bucket", records)
    assert len(evidence) == 18 and all(row["verified"] for row in evidence)
    assert all(Path(row["path"]).read_bytes() == objects[row["r2_object_key"]] for row in records)
    assert len([name for name, _ in client.calls if name == "get"]) == 18
    evidence = transport.restore_source_originals(client, "private-bucket", records)
    assert all(row["reused"] for row in evidence)
    assert len([name for name, _ in client.calls if name == "get"]) == 18
    with pytest.raises(transport.MigrationError, match="bnci_restore_record_cohort_invalid"):
        transport.restore_source_originals(client, "private-bucket", records[:-1])


def test_inventory_refuses_uncommitted_metadata(tmp_path):
    repo, raw_root, _, _ = inventory_fixture(tmp_path)
    with pytest.raises(transport.MigrationError, match="raw_inventory_or_receipt_not_committed_unchanged"):
        transport.load_raw_inventory(repo, raw_root)


@pytest.mark.parametrize("field,value", [("sha256", "0" * 64), ("size_bytes", True),
                                        ("path", "/outside/a.mat")])
def test_audit_drift_fails_closed(tmp_path, field, value):
    repo, raw_root, _, receipts = inventory_fixture(tmp_path)
    path = receipts["Cho2017"]
    receipt = json.loads(path.read_text())
    receipt["files"][0][field] = value
    path.write_text(json.dumps(receipt))
    with pytest.raises(transport.MigrationError):
        transport.load_raw_inventory(repo, raw_root, require_committed=False)


def test_key_map_duplicate_identity_is_ambiguous(tmp_path):
    repo, raw_root, inventory, _ = inventory_fixture(tmp_path)
    row = inventory[0]
    mapped = {"dataset": row["dataset"], "file_id": row["file_id"],
              "r2_object_key": transport.RAW_PREFIXES[row["dataset"]] + row["file_id"]}
    key_map = tmp_path / "keys.json"
    key_map.write_text(json.dumps({"schema_version": 1, "files": [mapped, mapped]}))
    with pytest.raises(transport.MigrationError, match="raw_key_map_ambiguous_identity"):
        transport.load_raw_inventory(repo, raw_root, key_map, require_committed=False)


def test_key_map_duplicate_object_is_ambiguous(tmp_path):
    repo, raw_root, inventory, _ = inventory_fixture(tmp_path)
    mapped = [{"dataset": row["dataset"], "file_id": row["file_id"],
               "r2_object_key": transport.RAW_PREFIXES[row["dataset"]] + row["file_id"]} for row in inventory]
    mapped[1]["r2_object_key"] = mapped[0]["r2_object_key"]
    key_map = tmp_path / "keys.json"
    key_map.write_text(json.dumps({"schema_version": 1, "files": mapped}))
    with pytest.raises(transport.MigrationError, match="raw_key_map_ambiguous_object_key"):
        transport.load_raw_inventory(repo, raw_root, key_map, require_committed=False)


def test_cli_sdk_failure_logs_no_secret_and_never_stops_pod(monkeypatch, capsys):
    client = FakeS3()
    client.deny_list = True
    monkeypatch.setattr(transport, "make_s3", lambda: (client, "PRIVATE_BUCKET"))
    assert transport.main(["probe"]) == 1
    output = capsys.readouterr()
    result = json.loads(output.err)
    assert result["error_code"] == "r2_access_denied"
    assert result["new_source_fits"] == 0 and result["target_fits"] == 0 and result["pod_stop_requested"] is False
    assert not any(value in output.err + output.out for value in
                   ("PRIVATE_BUCKET", "PRIVATE_ENDPOINT", "SECRET_ACCESS_KEY", "GH_TOKEN", "RUNPOD_API_KEY"))


def test_cli_argument_errors_do_not_echo_input(capsys):
    assert transport.main(["--PRIVATE_SECRET_ACCESS_KEY"]) == 1
    output = capsys.readouterr()
    assert "PRIVATE_SECRET_ACCESS_KEY" not in output.err + output.out
    assert json.loads(output.err)["error_code"] == "invalid_cli_arguments"


def bundle_manifest():
    return {"source_fit_count": 15, "files":
            [{"path": f"epochs/Cho2017/{i}.npz"} for i in range(106)] +
            [{"path": f"epochs/Cho2017/{i}.csv"} for i in range(106)] +
            [{"path": f"raw/BNCI2014_001/{i}.mat"} for i in range(18)]}


def test_backup_readback_failure_emits_no_success_receipt(tmp_path, monkeypatch):
    args = transport._parser().parse_args(["backup", "--archive", str(tmp_path / "archive.tar"),
                                          "--receipt", str(tmp_path / "backup.json"), "--origin-pod", "oldpod"])
    client = FakeS3()

    def export(*params):
        args.archive.write_bytes(b"source and epochs")
        client.corrupt_get = True  # permission probe has already passed
        return bundle_manifest()

    monkeypatch.setattr(transport, "load_raw_inventory", lambda *params, **kwargs: [])
    monkeypatch.setattr(transport, "check_raw_object_sizes", lambda *params: 160)
    with pytest.raises(transport.MigrationError, match="full_get_readback_hash_mismatch"):
        transport.run(args, client=client, bucket="bucket", bundle=SimpleNamespace(export_bundle=export))
    assert not args.receipt.exists()
    assert not any("stop" in name for name, _ in client.calls)


def test_backup_receipt_contains_verified_counts_only_after_full_readback(tmp_path, monkeypatch):
    args = transport._parser().parse_args(["backup", "--archive", str(tmp_path / "archive.tar"),
                                          "--receipt", str(tmp_path / "backup.json"), "--origin-pod", "oldpod"])

    def export(*params):
        args.archive.write_bytes(b"source and epochs")
        return bundle_manifest()

    monkeypatch.setattr(transport, "load_raw_inventory", lambda *params, **kwargs: [])
    monkeypatch.setattr(transport, "check_raw_object_sizes", lambda *params: 160)
    receipt = transport.run(args, client=FakeS3(), bucket="bucket", bundle=SimpleNamespace(export_bundle=export))
    assert json.loads(args.receipt.read_text()) == receipt
    assert receipt["readback_verified"] is True
    assert receipt["source_fit_count"] == 15
    assert receipt["external_epoch_npz_count"] == receipt["external_trial_csv_count"] == 106
    assert receipt["bnci_original_count"] == 18
    assert receipt["raw_originals_verified"] == 0
    assert receipt["raw_source_objects_size_checked"] == 160
    assert receipt["raw_source_backups"] == "existing_r2_objects_size_checked_not_rehashed"
    assert receipt["pod_stop_requested"] is False


def test_restore_raw_failure_leaves_receipt_not_ready(tmp_path, monkeypatch):
    payload, key = b"archive", "q15/migrations/job/archive.tar"
    args = transport._parser().parse_args(["restore", "--workspace", str(tmp_path / "workspace"),
                                          "--archive", str(tmp_path / "archive.tar"), "--object-key", key,
                                          "--archive-sha256", sha(payload), "--receipt", str(tmp_path / "restore.json")])
    bundle = SimpleNamespace(restore_bundle=lambda *params: {"paths_verified": True,
                             "paths": {"repo": str(args.workspace / "q15-execution/repo")}})

    def fail(*params):
        raise transport.MigrationError("persisted_download_hash_mismatch")

    monkeypatch.setattr(transport, "load_raw_inventory", lambda *params, **kwargs: [])
    monkeypatch.setattr(transport, "restore_originals", fail)
    with pytest.raises(transport.MigrationError, match="persisted_download_hash_mismatch"):
        transport.run(args, client=FakeS3({key: payload}), bucket="bucket", bundle=bundle)
    receipt = json.loads(args.receipt.read_text())
    assert receipt["ready_for_continuation"] is False
    assert receipt["raw_originals_verified"] == 0
    assert receipt["new_source_fits"] == 0 and receipt["target_fits"] == 0 and receipt["pod_stop_requested"] is False


def test_restore_cannot_mark_ready_without_all_160(tmp_path, monkeypatch):
    payload, key = b"archive", "q15/migrations/job/archive.tar"
    args = transport._parser().parse_args(["restore", "--workspace", str(tmp_path / "workspace"),
                                          "--archive", str(tmp_path / "archive.tar"), "--object-key", key,
                                          "--archive-sha256", sha(payload), "--receipt", str(tmp_path / "restore.json")])
    bundle = SimpleNamespace(restore_bundle=lambda *params: {"paths_verified": True,
                             "paths": {"repo": str(args.workspace / "q15-execution/repo")}})
    monkeypatch.setattr(transport, "load_raw_inventory", lambda *params, **kwargs: [])
    monkeypatch.setattr(transport, "restore_originals", lambda *params: [{}] * 159)
    with pytest.raises(transport.MigrationError, match="restored_original_count_invalid"):
        transport.run(args, client=FakeS3({key: payload}), bucket="bucket", bundle=bundle)
    assert json.loads(args.receipt.read_text())["ready_for_continuation"] is False


def test_real_bundle_transport_receipt_passes_continuation_guard(snapshot, monkeypatch):
    """Roundtrip an actual synthetic Git bundle plus all160 tiny raw originals."""
    workspace = snapshot["tmp"] / "new-workspace"
    raw_root = workspace / "q15-data/raw"
    temporary_repo, _, _inventory, receipts = inventory_fixture(snapshot["tmp"] / "raw-fixture")
    repo = snapshot["repo"]
    public = repo / "research_runs/Q15-PREPARATION/transport_inventory.json"
    public.parent.mkdir(parents=True, exist_ok=True)
    public.write_bytes((temporary_repo / "research_runs/Q15-PREPARATION/transport_inventory.json").read_bytes())
    objects = {}
    for dataset, path in receipts.items():
        receipt = json.loads(path.read_text())
        for row in receipt["files"]:
            row["path"] = str(raw_root / dataset / row["file_id"])
            objects[transport.RAW_PREFIXES[dataset] + row["file_id"]] = (dataset + row["file_id"]).encode()
        target = repo / transport.AUDIT_RECEIPTS[dataset]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt))
    _git(repo, "add", ".")
    _git(repo, "commit", "--quiet", "-m", "Synthetic raw custody receipts")
    snapshot["base"] = _git(repo, "rev-parse", "HEAD")
    monkeypatch.setattr(fixture_bundle, "BASE_COMMIT", snapshot["base"])
    monkeypatch.setattr(transport, "BASE_COMMIT", snapshot["base"])
    archive, _manifest = _export(snapshot)
    payload = archive.read_bytes()
    key = f"q15/migrations/{transport.ORIGIN_JOB}/{sha(payload)}/validated-source-and-epochs.tar"
    objects[key] = payload
    args = transport._parser().parse_args(["restore", "--workspace", str(workspace),
                                          "--raw-dir", str(raw_root), "--archive", str(snapshot["tmp"] / "download.tar"),
                                          "--object-key", key, "--archive-sha256", sha(payload),
                                          "--receipt", str(workspace / "q15-migration/restore_receipt.json")])
    proof = transport.run(args, client=FakeS3(objects), bucket="private-bucket", bundle=fixture_bundle)
    assert proof["ready_for_continuation"] is True and proof["raw_originals_verified"] == 160
    assert proof["kind"] == "q15_validated_source_and_epochs_restore"
    assert proof["code_base_commit"] == snapshot["base"]
    assert proof["origin_job_id"] == fixture_bundle.ORIGIN_JOB_ID
    assert proof["new_source_fits"] == proof["target_fits"] == 0
    assert proof["origin_source_fits"] == 15
    spec = importlib.util.spec_from_file_location("q15_continue_receipt_integration",
                                                  MODULE_PATH.with_name("q15_continue_validated.py"))
    continuation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(continuation)
    monkeypatch.setattr(continuation, "CODE_BASE_COMMIT", snapshot["base"])
    monkeypatch.setattr(continuation, "SCIENTIFIC_REVISION", snapshot["science"])
    guard_args = SimpleNamespace(workspace=str(workspace), repo=workspace / "q15-execution/repo",
                                 raw_dir=str(raw_root), bnci_dir=str(raw_root / "BNCI2014_001"),
                                 epoch_dir=str(workspace / "q15-data/epochs"), restore_receipt=args.receipt)
    assert continuation.validate_restore_receipt(guard_args) == proof
    # A second migration run must preserve identical restored science and safely
    # accept the transport extensions in the bundle's canonical receipt.
    second = transport.run(args, client=FakeS3(objects), bucket="private-bucket", bundle=fixture_bundle)
    assert second["ready_for_continuation"] is True
    assert all(row["reused"] for row in second["raw_originals"])
