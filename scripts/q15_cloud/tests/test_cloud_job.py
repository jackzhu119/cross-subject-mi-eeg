"""No-network integrity, extraction, scientific gate, and shutdown tests.

The fake object store contains only test bytes. These tests never read cloud
credentials, run a model, or send a real Pod stop request.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import q15_cloud_job as job
import q15_cloud_bootstrap as bootstrap


class MemoryObjectStore:
    """Small boto3-compatible store with independent full-byte readbacks."""

    def __init__(self, *, corrupt_readback: bool = False, fail_upload: bool = False):
        self.objects: dict[str, tuple[bytes, dict]] = {}
        self.events: list[tuple[str, str]] = []
        self.get_requests: list[dict] = []
        self.corrupt_readback = corrupt_readback
        self.fail_upload = fail_upload

    def head_object(self, *, Bucket, Key, **kwargs):
        self.events.append(("head", Key))
        payload, metadata = self.objects[Key]
        return {"ContentLength": len(payload), "Metadata": metadata,
                "ETag": '"' + hashlib.md5(payload).hexdigest() + '"'}

    def get_object(self, *, Bucket, Key, **kwargs):
        self.events.append(("get", Key))
        self.get_requests.append({"Key": Key, **kwargs})
        payload, metadata = self.objects[Key]
        if self.corrupt_readback:
            payload = payload[:-1] + bytes([payload[-1] ^ 1]) if payload else b"!"
        response = {"ContentLength": len(payload), "Metadata": metadata}
        if "Range" in kwargs:
            offset = int(kwargs["Range"].split("=")[1].split("-")[0])
            response["ContentRange"] = f"bytes {offset}-{len(payload)-1}/{len(payload)}"
            payload = payload[offset:]
            response["ContentLength"] = len(payload)
        response["Body"] = io.BytesIO(payload)
        return response

    def put_object(self, *, Bucket, Key, Body, Metadata=None, **kwargs):
        self.events.append(("put", Key))
        if self.fail_upload:
            raise OSError("simulated upload failure")
        if hasattr(Body, "read"):
            Body = Body.read()
        self.objects[Key] = (bytes(Body), Metadata or {})
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def upload_file(self, Filename, Bucket, Key, ExtraArgs=None, **kwargs):
        return self.put_object(Bucket=Bucket, Key=Key, Body=Path(Filename).read_bytes(),
                               Metadata=(ExtraArgs or {}).get("Metadata", {}))

    def download_file(self, Bucket, Key, Filename, **kwargs):
        Path(Filename).write_bytes(self.get_object(Bucket=Bucket, Key=Key)["Body"].read())


class CloudJobTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="q15-cloud-job-test-")
        self.root = Path(self.temporary.name)
        self.sleep_patch = patch.object(job.time, "sleep")
        self.sleep_patch.start()
        self.addCleanup(self.sleep_patch.stop)

    def tearDown(self):
        self.temporary.cleanup()

    def archive(self, entries):
        path = self.root / "code.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            for name, kind, payload in entries:
                info = tarfile.TarInfo(name)
                if kind == "file":
                    info.size = len(payload)
                    archive.addfile(info, io.BytesIO(payload))
                elif kind == "symlink":
                    info.type = tarfile.SYMTYPE
                    info.linkname = payload
                    archive.addfile(info)
                elif kind == "hardlink":
                    info.type = tarfile.LNKTYPE
                    info.linkname = payload
                    archive.addfile(info)
                else:
                    raise ValueError(kind)
        return path

    def test_valid_download_writes_only_verified_bytes(self):
        payload = b"raw EEG fixture, never training data"
        client = MemoryObjectStore()
        client.objects["raw/data.mat"] = (payload, {})
        destination = self.root / "data.mat"
        receipt = job.download_verified(
            client, "test-bucket", "raw/data.mat", destination,
            hashlib.sha256(payload).hexdigest(), hashlib.md5(payload).hexdigest(),
            len(payload), retries=1)
        self.assertEqual(destination.read_bytes(), payload)
        self.assertIs(receipt["verified"], True)
        self.assertEqual(receipt["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(receipt["md5"], hashlib.md5(payload).hexdigest())
        self.assertEqual(receipt["size_bytes"], len(payload))

    def test_sha_mismatch_never_promotes_download_to_destination(self):
        payload = b"content that does not match the expected digest"
        client = MemoryObjectStore()
        client.objects["raw/data.mat"] = (payload, {"sha256": "0" * 64})
        destination = self.root / "data.mat"
        with self.assertRaisesRegex(job.IntegrityError, "raw_content_hash_mismatch"):
            job.download_verified(client, "test-bucket", "raw/data.mat", destination,
                                  "0" * 64, hashlib.md5(payload).hexdigest(),
                                  len(payload), retries=1)
        self.assertFalse(destination.exists())

    def test_md5_mismatch_never_promotes_download(self):
        payload = b"another raw fixture"
        client = MemoryObjectStore()
        client.objects["raw/data.mat"] = (payload, {})
        destination = self.root / "data.mat"
        with self.assertRaisesRegex(job.IntegrityError, "raw_content_hash_mismatch"):
            job.download_verified(client, "test-bucket", "raw/data.mat", destination,
                                  hashlib.sha256(payload).hexdigest(), "0" * 32,
                                  len(payload), retries=1)
        self.assertFalse(destination.exists())

    def test_size_mismatch_never_promotes_download(self):
        payload = b"short data"
        client = MemoryObjectStore()
        client.objects["raw/data.mat"] = (payload, {})
        destination = self.root / "data.mat"
        with self.assertRaisesRegex(job.IntegrityError, "remote_size_mismatch"):
            job.download_verified(client, "test-bucket", "raw/data.mat", destination,
                                  hashlib.sha256(payload).hexdigest(),
                                  hashlib.md5(payload).hexdigest(), len(payload) + 1,
                                  retries=1)
        self.assertFalse(destination.exists())

    def test_matching_partial_resumes_using_etag_bound_range_and_full_hash(self):
        payload = b"fixture with a previously persisted prefix"
        key = "raw/data.mat"
        client = MemoryObjectStore()
        client.objects[key] = (payload, {})
        destination = self.root / "data.mat"
        destination.with_name("data.mat.part").write_bytes(payload[:7])
        destination.with_name("data.mat.part.json").write_text(json.dumps({
            "key": key, "sha256": hashlib.sha256(payload).hexdigest(),
            "md5": hashlib.md5(payload).hexdigest(), "size_bytes": len(payload),
            "etag": '"' + hashlib.md5(payload).hexdigest() + '"',
        }), encoding="utf-8")
        receipt = job.download_verified(
            client, "test-bucket", key, destination, hashlib.sha256(payload).hexdigest(),
            hashlib.md5(payload).hexdigest(), len(payload), retries=1)
        self.assertEqual(destination.read_bytes(), payload)
        self.assertIs(receipt["verified"], True)
        self.assertEqual(client.get_requests[0]["Range"], "bytes=7-")
        self.assertEqual(client.get_requests[0]["IfMatch"],
                         '"' + hashlib.md5(payload).hexdigest() + '"')
        self.assertFalse(destination.with_name("data.mat.part.json").exists())

    def test_partial_from_different_etag_is_discarded_before_new_download(self):
        payload = b"fixture of the current object version"
        key = "raw/data.mat"
        client = MemoryObjectStore()
        client.objects[key] = (payload, {})
        destination = self.root / "data.mat"
        destination.with_name("data.mat.part").write_bytes(b"old prefix")
        destination.with_name("data.mat.part.json").write_text(json.dumps({
            "key": key, "sha256": hashlib.sha256(payload).hexdigest(),
            "md5": hashlib.md5(payload).hexdigest(), "size_bytes": len(payload),
            "etag": '"old-etag"',
        }), encoding="utf-8")
        job.download_verified(client, "test-bucket", key, destination,
                              hashlib.sha256(payload).hexdigest(),
                              hashlib.md5(payload).hexdigest(), len(payload), retries=1)
        self.assertEqual(destination.read_bytes(), payload)
        self.assertNotIn("Range", client.get_requests[0])

    def test_existing_corrupt_prefix_is_never_marked_verified(self):
        payload = b"fixture with persisted prefix"
        key = "raw/data.mat"
        client = MemoryObjectStore()
        client.objects[key] = (payload, {})
        destination = self.root / "data.mat"
        destination.with_name("data.mat.part").write_bytes(b"bad data")
        destination.with_name("data.mat.part.json").write_text(json.dumps({
            "key": key, "sha256": hashlib.sha256(payload).hexdigest(),
            "md5": hashlib.md5(payload).hexdigest(), "size_bytes": len(payload),
            "etag": '"' + hashlib.md5(payload).hexdigest() + '"',
        }), encoding="utf-8")
        with self.assertRaisesRegex(job.IntegrityError, "raw_content_hash_mismatch"):
            job.download_verified(client, "test-bucket", key, destination,
                                  hashlib.sha256(payload).hexdigest(),
                                  hashlib.md5(payload).hexdigest(), len(payload), retries=1)
        self.assertFalse(destination.exists())
        self.assertFalse(destination.with_name("data.mat.part").exists())

    def test_persisted_byte_recheck_failure_never_promotes_stream_verified_file(self):
        payload = b"correct bytes delivered by the remote stream"
        client = MemoryObjectStore()
        client.objects["raw/data.mat"] = (payload, {})
        destination = self.root / "data.mat"
        inspected = []
        real_hashes = job.file_hashes

        def corrupt_persisted_hash(path):
            inspected.append(Path(path))
            if Path(path).name == "data.mat.part":
                return "0" * 64, hashlib.md5(payload).hexdigest(), len(payload)
            return real_hashes(path)

        with patch.object(job, "file_hashes", side_effect=corrupt_persisted_hash):
            with self.assertRaisesRegex(job.IntegrityError, "persisted_raw_file_hash_mismatch"):
                job.download_verified(
                    client, "test-bucket", "raw/data.mat", destination,
                    hashlib.sha256(payload).hexdigest(), hashlib.md5(payload).hexdigest(),
                    len(payload), retries=1)
        self.assertEqual(inspected, [destination.with_name("data.mat.part")])
        self.assertFalse(destination.exists())
        self.assertFalse(destination.with_name("data.mat.part").exists())

    def test_safe_tar_extracts_regular_files(self):
        archive = self.archive([("repo/README.txt", "file", b"fixture documentation")])
        destination = self.root / "unpacked"
        job.safe_extract(archive, destination)
        self.assertEqual((destination / "repo/README.txt").read_bytes(),
                         b"fixture documentation")

    def test_traversal_tar_rejected_before_any_member_is_extracted(self):
        archive = self.archive([("innocent.txt", "file", b"first member"),
                                ("../escaped.txt", "file", b"outside")])
        destination = self.root / "unpacked"
        with self.assertRaises(job.IntegrityError):
            job.safe_extract(archive, destination)
        self.assertFalse((self.root / "escaped.txt").exists())
        self.assertFalse((destination / "innocent.txt").exists())

    def test_absolute_path_tar_rejected(self):
        escaped = self.root / "absolute-escaped.txt"
        archive = self.archive([(str(escaped), "file", b"outside")])
        with self.assertRaises(job.IntegrityError):
            job.safe_extract(archive, self.root / "unpacked")
        self.assertFalse(escaped.exists())

    def test_symbolic_and_hard_links_rejected(self):
        for kind in ("symlink", "hardlink"):
            with self.subTest(kind=kind):
                archive = self.archive([("link", kind, "../escaped.txt")])
                destination = self.root / ("unpacked-" + kind)
                with self.assertRaisesRegex(job.IntegrityError, "unsupported_archive_member"):
                    job.safe_extract(archive, destination)
                self.assertFalse((destination / "link").is_symlink())
                self.assertFalse((self.root / "escaped.txt").exists())

    def test_tar_expansion_budget_is_enforced(self):
        archive = self.archive([("large.bin", "file", b"123456789")])
        destination = self.root / "unpacked"
        with self.assertRaisesRegex(job.IntegrityError, "archive_uncompressed_limit"):
            job.safe_extract(archive, destination, max_bytes=8)
        self.assertFalse((destination / "large.bin").exists())

    def test_missing_scientific_gates_cannot_call_training(self):
        gate = job.scientific_gate(self.root / "missing-repo")
        self.assertIs(gate["allowed"], False)
        runner = Mock()
        with self.assertRaises(job.GateBlocked):
            job.run_training_if_allowed(gate, runner)
        runner.assert_not_called()

    def test_arbitrary_positive_receipts_cannot_authorize_scientific_gate(self):
        repo = self.root / "repo"
        for rel in ("results/Q15-E005/pre_fit_freeze.json",
                    "results/Q15-V001/metadata_audit_receipt.json",
                    "results/Q15-V002/metadata_audit_receipt.json"):
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"allowed": True, "raw_audit_completed": True}),
                            encoding="utf-8")
        auditor = repo / "scripts/q15_metadata_audit.py"
        auditor.parent.mkdir(parents=True, exist_ok=True)
        auditor.write_text("# arbitrary non-auditor fixture\n", encoding="utf-8")
        gate = job.scientific_gate(repo)
        self.assertIs(gate["allowed"], False)
        runner = Mock()
        with self.assertRaises(job.GateBlocked):
            job.run_training_if_allowed(gate, runner)
        runner.assert_not_called()

    def test_allowed_scientific_gate_calls_runner_once(self):
        runner = Mock(return_value={"training": "synthetic completion"})
        job.run_training_if_allowed({"allowed": True}, runner)
        runner.assert_called_once_with()

    def test_backup_requires_complete_readback_not_only_matching_metadata(self):
        payload = b"training logs, synthetic only"
        client = MemoryObjectStore(corrupt_readback=True)
        with self.assertRaisesRegex(job.IntegrityError, "backup_readback_hash_mismatch"):
            job.verified_backup(client, "test-bucket", "backup/log.txt", payload)
        self.assertIn(("get", "backup/log.txt"), client.events)

    def test_valid_backup_reads_back_exact_upload(self):
        payload = b"finished synthetic result"
        client = MemoryObjectStore()
        receipt = job.verified_backup(client, "test-bucket", "backup/result.txt", payload)
        self.assertEqual(client.objects["backup/result.txt"][0], payload)
        self.assertIn(("get", "backup/result.txt"), client.events)
        self.assertIs(receipt["full_readback_verified"], True)
        self.assertEqual(receipt["sha256"], hashlib.sha256(payload).hexdigest())

    def finish(self, client, stopper, state):
        log = self.root / "job.log"
        log.write_text("synthetic durable log\n", encoding="utf-8")
        return job.finish_job(client, "test-bucket", "run/test", state, log, stopper)

    def test_finish_stops_only_after_all_uploaded_objects_have_readbacks(self):
        for status in ("raw_download_complete", "stopped_without_training", "failed_download"):
            with self.subTest(status=status):
                client = MemoryObjectStore()
                checkpoints = []
                self.finish(client, lambda: checkpoints.append(list(client.events)),
                            {"status": status, "fits_started": 0, "training_started": False})
                self.assertEqual(len(checkpoints), 1)
                uploaded = {key for operation, key in checkpoints[0] if operation == "put"}
                readback = {key for operation, key in checkpoints[0] if operation == "get"}
                self.assertTrue(uploaded, "No durable backup preceded stop")
                self.assertLessEqual(uploaded, readback)
                saved_state = json.loads(client.objects["run/test/final_job_status.json"][0])
                self.assertEqual(saved_state["status"], status)
                self.assertEqual(saved_state["fits_started"], 0)
                manifest = json.loads(client.objects["run/test/final_backup_manifest.json"][0])
                self.assertIs(manifest["stop_success_not_yet_confirmed"], True)
                for receipt in manifest["files"]:
                    self.assertEqual(receipt["sha256"],
                                     hashlib.sha256(client.objects[receipt["key"]][0]).hexdigest())

    def test_backup_upload_failure_never_stops_pod(self):
        client = MemoryObjectStore(fail_upload=True)
        stopper = Mock()
        with self.assertRaisesRegex(job.IntegrityError, "OSError"):
            self.finish(client, stopper, {"status": "raw_download_complete", "fits_started": 0})
        stopper.assert_not_called()

    def test_backup_corrupt_readback_never_stops_pod(self):
        client = MemoryObjectStore(corrupt_readback=True)
        stopper = Mock()
        with self.assertRaisesRegex(job.IntegrityError, "backup_readback_hash_mismatch"):
            self.finish(client, stopper, {"status": "raw_download_complete", "fits_started": 0})
        stopper.assert_not_called()
        self.assertTrue(any(operation == "get" for operation, _ in client.events))

    def test_last_manifest_backup_failure_prevents_stop_after_other_backups_succeed(self):
        class LastManifestFailure(MemoryObjectStore):
            def put_object(self, **kwargs):
                if kwargs["Key"].endswith("/final_backup_manifest.json"):
                    raise OSError("simulated manifest-only upload failure")
                return super().put_object(**kwargs)

        client = LastManifestFailure()
        stopper = Mock()
        with self.assertRaisesRegex(job.IntegrityError, "OSError"):
            self.finish(client, stopper, {"status": "raw_download_complete", "fits_started": 0})
        self.assertIn(("get", "run/test/final_job_status.json"), client.events)
        self.assertIn(("get", "run/test/job.log"), client.events)
        stopper.assert_not_called()

    def test_nonzero_fit_count_prevents_transport_only_finish(self):
        client = MemoryObjectStore()
        stopper = Mock()
        with self.assertRaisesRegex(job.IntegrityError, "unexpected_fit_count"):
            self.finish(client, stopper, {"status": "unexpected_training", "fits_started": 1})
        self.assertEqual(client.events, [])
        stopper.assert_not_called()

    def test_failed_pod_identity_check_never_sends_stop_request(self):
        # This config is a tempfile made of dummy test strings, never real credentials.
        config = self.root / "dummy-test-config.json"
        config.write_text(json.dumps({
            "R2_BUCKET": "test-bucket", "R2_ENDPOINT": "https://invalid.test",
            "R2_ACCESS_KEY_ID": "dummy-test-key", "R2_SECRET_ACCESS_KEY": "dummy-test-secret",
            "RUNPOD_API_KEY": "dummy-test-api", "pod_id": job.POD_ID,
            "raw_dir": str(self.root / "raw"),
        }), encoding="utf-8")
        config.chmod(0o600)
        client = MemoryObjectStore()
        boto = ModuleType("boto3")
        boto.client = Mock(return_value=client)
        core = ModuleType("botocore")
        core_config = ModuleType("botocore.config")
        core_config.Config = Mock()
        job_dir = self.root / "test-job"
        with patch.dict(sys.modules, {"boto3": boto, "botocore": core,
                                      "botocore.config": core_config}), \
                patch.object(sys, "argv", ["q15_cloud_job.py", "--config", str(config),
                                           "--job-dir", str(job_dir)]), \
                patch.dict(job.os.environ, {"RUNPOD_POD_ID": job.POD_ID}), \
                patch.object(job, "runpod_request", side_effect=job.IntegrityError(
                    "test_identity_check_failed")) as request, \
                patch.object(sys, "stdout", io.StringIO()):
            result = job.main()
        self.assertEqual(result, 2)
        request.assert_called_once_with("dummy-test-api", job.POD_ID)
        state = json.loads((job_dir / "job_status.json").read_text())
        self.assertEqual(state["shutdown_error_code"], "pod_identity_not_verified_stop_forbidden")
        self.assertEqual(state["fits_started"], 0)
        self.assertTrue(client.objects, "Identity failure should still preserve its durable error evidence")

    def test_bootstrap_rejects_non_terminal_before_prompting_for_secret(self):
        with patch.object(sys.stdin, "isatty", return_value=False), \
                patch.object(bootstrap.getpass, "getpass") as prompt:
            with self.assertRaisesRegex(bootstrap.BootstrapError, "run_in_jupyter_terminal"):
                bootstrap.main()
        prompt.assert_not_called()

    def test_hidden_prompt_rejects_echo_fallback_warning(self):
        with patch.dict(bootstrap.os.environ, {}, clear=True), \
                patch.object(sys.stdin, "isatty", return_value=True), \
                patch.object(bootstrap.getpass, "getpass", side_effect=
                             bootstrap.getpass.GetPassWarning("test cannot disable echo")):
            with self.assertRaisesRegex(bootstrap.BootstrapError, "no_plaintext_fallback"):
                bootstrap.read_hidden("Q15_UNIT_TEST_SECRET", {})

    def test_bootstrap_refuses_changed_companion_script_before_cloud_access(self):
        with patch.object(sys.stdin, "isatty", return_value=True), \
                patch.object(bootstrap, "EXPECTED_JOB_SHA256", "0" * 64), \
                patch.object(bootstrap, "read_hidden") as prompt:
            with self.assertRaisesRegex(bootstrap.BootstrapError, "companion_job_script_hash_mismatch"):
                bootstrap.main()
        prompt.assert_not_called()

    def test_bootstrap_pinned_sha_matches_current_job_script(self):
        self.assertEqual(bootstrap.EXPECTED_JOB_SHA256,
                         hashlib.sha256(Path(job.__file__).read_bytes()).hexdigest())

    def test_worker_lock_rejects_duplicate_and_releases_when_closed(self):
        lock_path = self.root / "active.lock"
        original = job.acquire_job_lock(lock_path)
        try:
            with self.assertRaisesRegex(job.IntegrityError, "another_cloud_supervisor_is_active"):
                job.acquire_job_lock(lock_path)
            self.assertFalse(original.closed)
        finally:
            original.close()
        replacement = job.acquire_job_lock(lock_path)
        replacement.close()

    def test_duplicate_main_never_reads_config_backs_up_or_stops_original_worker(self):
        original = job.acquire_job_lock(self.root / "active.lock")
        try:
            with patch.object(sys, "argv", ["q15_cloud_job.py", "--config",
                                             str(self.root / "unread-nonexistent-config.json"),
                                             "--job-dir", str(self.root / "duplicate-job")]), \
                    patch.object(job, "runpod_request") as request, \
                    patch.object(job, "verified_backup") as backup, \
                    patch.object(job, "finish_job") as finish:
                with self.assertRaisesRegex(job.IntegrityError, "another_cloud_supervisor_is_active"):
                    job.main()
            request.assert_not_called()
            backup.assert_not_called()
            finish.assert_not_called()
            self.assertFalse((self.root / "duplicate-job").exists())
        finally:
            original.close()

    def test_local_disk_full_still_verifies_final_remote_backups_before_stop(self):
        config = self.root / "dummy-enospc-config.json"
        config.write_text(json.dumps({
            "R2_BUCKET": "test-bucket", "R2_ENDPOINT": "https://invalid.test",
            "R2_ACCESS_KEY_ID": "dummy-test-key", "R2_SECRET_ACCESS_KEY": "dummy-test-secret",
            "RUNPOD_API_KEY": "dummy-test-api", "pod_id": job.POD_ID,
            "raw_dir": str(self.root / "raw"),
        }), encoding="utf-8")
        config.chmod(0o600)
        job_dir = self.root / "enospc-job"
        job_dir.mkdir()
        (job_dir / "job.log").write_text("prior durable log fixture\n", encoding="utf-8")
        client = MemoryObjectStore()
        boto = ModuleType("boto3")
        boto.client = Mock(return_value=client)
        core = ModuleType("botocore")
        core_config = ModuleType("botocore.config")
        core_config.Config = Mock()
        real_open = Path.open

        def disk_full_log_append(path, mode="r", *args, **kwargs):
            if path == job_dir / "job.log" and mode == "a":
                raise OSError(28, "test log volume full")
            return real_open(path, mode, *args, **kwargs)

        with patch.dict(sys.modules, {"boto3": boto, "botocore": core,
                                      "botocore.config": core_config}), \
                patch.object(sys, "argv", ["q15_cloud_job.py", "--config", str(config),
                                           "--job-dir", str(job_dir)]), \
                patch.dict(job.os.environ, {"RUNPOD_POD_ID": job.POD_ID}), \
                patch.object(job.shutil, "disk_usage", return_value=SimpleNamespace(free=200 * 1024**3)), \
                patch.object(job, "atomic_json", side_effect=OSError(28, "test JSON volume full")), \
                patch.object(Path, "open", new=disk_full_log_append), \
                patch.object(job, "print", create=True, side_effect=OSError(28, "test stdout volume full")), \
                patch.object(job, "download_verified", side_effect=job.IntegrityError(
                    "actual_volume_quota_or_disk_full")) as download, \
                patch.object(job, "runpod_request", return_value={"http_status": 200}) as request:
            result = job.main()
        self.assertEqual(result, 0)
        download.assert_called_once()
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args.args,
                         ("dummy-test-api", job.POD_ID, "POST", "/stop"))
        prefix = "q15/cloud-jobs/enospc-job"
        state = json.loads(client.objects[prefix + "/final_job_status.json"][0])
        self.assertEqual(state["error_code"], "actual_volume_quota_or_disk_full")
        self.assertEqual(state["fits_started"], 0)
        self.assertEqual({e["stage"] for e in state["local_persistence_errors"]},
                         {"local_json", "log_file", "log_stdout"})
        self.assertTrue(all(e["errno"] == 28 for e in state["local_persistence_errors"]))
        for name in ("final_job_status.json", "job.log", "final_backup_manifest.json"):
            self.assertIn(("get", prefix + "/" + name), client.events)


if __name__ == "__main__":
    unittest.main()
