"""Full bootstrap flows with real companion imports and no external side effects.

The fake SDK is injected at the dependency boundary. RunPod requests still pass
through the real worker's urllib request/error handling, and the real preflight
performs its list/HEAD/write/full-byte readback/delete sequence. Fixtures contain
only synthetic credentials and object bytes. No worker process, GPU operation,
real network request, or stop request is executed.
"""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import q15_cloud_bootstrap as bootstrap
import q15_cloud_job as job
from test_cloud_job import MemoryObjectStore


class ClientError(Exception):
    """SDK-compatible response fixture; deliberately unsafe exception text."""

    def __init__(self, code, status=403):
        self.response = {"Error": {"Code": code, "Message": "SENTINEL_SECRET_HTTP_BODY"},
                         "ResponseMetadata": {"HTTPStatusCode": status}}
        super().__init__("SENTINEL_SECRET_HTTP_BODY credential=SENTINEL_SECRET_API")


class PreflightStore(MemoryObjectStore):
    def __init__(self):
        super().__init__()
        self.fail_list = None
        self.keep_deleted = False
        self.deletion_confirmed = False

    def list_objects_v2(self, *, Bucket, Prefix, MaxKeys):
        self.events.append(("list", Prefix))
        if self.fail_list:
            raise self.fail_list
        return {"KeyCount": 0}

    def head_object(self, *, Bucket, Key, **kwargs):
        if Key == job.ARCHIVE_KEY:
            self.events.append(("head", Key))
            return {"ContentLength": job.ARCHIVE_BYTES}
        if Key not in self.objects:
            self.events.append(("head", Key))
            self.deletion_confirmed = True
            raise ClientError("404", status=404)
        return super().head_object(Bucket=Bucket, Key=Key, **kwargs)

    def delete_object(self, *, Bucket, Key):
        self.events.append(("delete", Key))
        if not self.keep_deleted:
            self.objects.pop(Key, None)
        return {"ResponseMetadata": {"HTTPStatusCode": 204}}


class Response(io.BytesIO):
    status = 200


class BootstrapFlowTest(unittest.TestCase):
    POD = "fixture-new-current-pod"
    CREDS = {
        "R2_BUCKET": "fixture-test-bucket",
        "R2_ENDPOINT": "https://fixture-account.r2.cloudflarestorage.com",
        "R2_ACCESS_KEY_ID": "SENTINEL_SECRET_ACCESS_ID",
        "R2_SECRET_ACCESS_KEY": "SENTINEL_SECRET_ACCESS_KEY",
        "RUNPOD_API_KEY": "SENTINEL_SECRET_API",
    }

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="q15-bootstrap-flow-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.private = self.root / "private"
        self.state = self.root / "shared-control"
        self.legacy = self.root / "legacy-private"
        self.raw = self.root / "raw"
        self.store = PreflightStore()
        self.api_requests = []
        self.api_errors = []
        self.api_payload = {"id": self.POD, "volumeMountPath": "/workspace", "volumeInGb": 200,
                            "env": {"SENTINEL": "SENTINEL_SECRET_HTTP_BODY"}}
        self.children = []
        self.child_mode = "verified"
        self.stdout = io.StringIO()
        self.prompts = Mock(side_effect=AssertionError("Unexpected hidden credential prompt"))

        boto = ModuleType("boto3")
        boto.client = Mock(return_value=self.store)
        self.boto = boto
        core = ModuleType("botocore")
        config = ModuleType("botocore.config")
        config.Config = Mock()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(sys.modules, {"boto3": boto, "botocore": core,
                                                         "botocore.config": config}))
        self.stack.enter_context(patch.dict(bootstrap.os.environ, {**self.CREDS,
                                               "RUNPOD_POD_ID": self.POD}, clear=True))
        self.stack.enter_context(patch.object(bootstrap, "PRIVATE_ROOT", self.private))
        self.stack.enter_context(patch.object(bootstrap, "STATE_ROOT", self.state))
        self.stack.enter_context(patch.object(bootstrap, "LEGACY_PRIVATE_ROOT", self.legacy))
        self.stack.enter_context(patch.object(bootstrap, "RAW_ROOT", self.raw))
        # Exercise the pin check and real dynamic import while other agents may
        # change the worker. The committed pin is checked separately in release.
        source = Path(job.__file__)
        self.stack.enter_context(patch.object(bootstrap, "EXPECTED_JOB_SHA256",
                                             hashlib.sha256(source.read_bytes()).hexdigest()))
        self.stack.enter_context(patch.object(urllib.request, "urlopen", side_effect=self.api_call))
        self.stack.enter_context(patch.object(bootstrap.shutil, "disk_usage",
                                             return_value=SimpleNamespace(free=200 * 1024 ** 3)))
        # Archive restoration has its own real-reader tests below. Other full
        # flows isolate this dependency so public CI needs no private archive.
        self.real_restore_inventory = bootstrap.restore_transport_inventory
        self.restore_inventory = self.stack.enter_context(
            patch.object(bootstrap, "restore_transport_inventory", return_value=None))
        self.popen = self.stack.enter_context(patch.object(bootstrap.subprocess, "Popen",
                                                          side_effect=self.spawn))
        self.stack.enter_context(patch.object(bootstrap.getpass, "getpass", self.prompts))
        self.stack.enter_context(patch.object(sys.stdin, "isatty", return_value=False))
        self.stack.enter_context(patch.object(bootstrap.time, "sleep"))
        self.stack.enter_context(patch.object(sys, "stdout", self.stdout))

    def api_call(self, request, **kwargs):
        self.api_requests.append(request)
        if request.get_method() != "GET":
            raise AssertionError("Bootstrap must never issue a stop or mutation request")
        if self.api_errors:
            error = self.api_errors.pop(0)
            if error is not None:
                raise error
        return Response(json.dumps(self.api_payload).encode())

    def spawn(self, argv, **kwargs):
        job_dir = Path(argv[argv.index("--job-dir") + 1])
        status = {"status": "downloading_raw", "pod_identity_verified": True, "fits_started": 0}
        child = SimpleNamespace(pid=54321, poll=Mock(return_value=None))
        if self.child_mode == "failed_log_only":
            # Real __main__ configuration/API errors can precede job_status.
            # Deliberately embed unsafe details to prove the bootstrap selects
            # only the safe code from the private child log.
            entry = {"status": "bootstrap_or_config_failed", "error_code": "runpod_api_http_403",
                     "message": "SENTINEL_SECRET_HTTP_BODY",
                     "request_url": "https://rest.runpod.io/?token=SENTINEL_SECRET_API"}
            kwargs["stdout"].write((json.dumps(entry) + "\n").encode())
            child.poll.return_value = 2
            self.children.append(child)
            return child
        if self.child_mode == "failed":
            status.update({"status": "failed_without_training", "pod_identity_verified": False,
                           "error_code": "archive_hash_mismatch"})
            child.poll.return_value = 2
        elif self.child_mode == "exited_after_status":
            child.poll.return_value = 2
        elif self.child_mode == "pending":
            status = {"status": "worker_initializing", "fits_started": 0}
        bootstrap.atomic_state_json(job_dir / "job_status.json", status)
        self.children.append(child)
        return child

    def invoke(self, *args):
        self.stdout.seek(0)
        self.stdout.truncate(0)
        result = bootstrap.cli(list(args))
        report_path = self.state / "last_bootstrap_report.json"
        report = json.loads(report_path.read_text()) if report_path.exists() else {}
        self.assert_safe_output(report)
        return result, report

    def assert_safe_output(self, report):
        text = self.stdout.getvalue() + json.dumps(report)
        for path in self.state.glob("jobs/*/launch_receipt.json") if self.state.exists() else []:
            text += path.read_text()
        for value in ("SENTINEL_SECRET_HTTP_BODY", "SENTINEL_SECRET_API",
                      "SENTINEL_SECRET_ACCESS_ID", "SENTINEL_SECRET_ACCESS_KEY"):
            self.assertNotIn(value, text)
        self.assertEqual(report.get("fits_started", 0), 0)

    def cache(self, *, omit=(), **extra):
        bootstrap.safe_private_root(self.private)
        values = {name: value for name, value in self.CREDS.items() if name not in omit}
        bootstrap.atomic_private_json(self.private / "credentials.json", {**values, **extra})

    def read_cache(self):
        return json.loads((self.private / "credentials.json").read_text())

    def cache_actual_pinned_inventory(self):
        """Use private source evidence if locally available; never publish it.

        This integration fixture is optional outside the research workspace.
        The remaining tests keep the portable failure paths covered without
        checking the private 200 KB R2 inventory into the public repository.
        """
        repo = Path(__file__).resolve().parents[3]
        archive_relative = (Path("research_runs/Q15-DATA/provenance_archive") /
                            "20261001T093410835515Z-614d381fb70141d7b91a85ae4eb907a8/archive.tar.gz")
        candidates = (repo / archive_relative,
                      repo.parent / "cross-subject-mi-eeg" / archive_relative)
        archive = next((path for path in candidates if path.is_file()), None)
        if archive is None:
            self.skipTest("Private pinned provenance archive is unavailable in this checkout")
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), job.ARCHIVE_SHA)
        with tarfile.open(archive, "r:gz") as source:
            member = source.extractfile("research_runs/Q15-DATA/r2_source_storage_verification.json")
            self.assertIsNotNone(member)
            data = member.read()
        self.assertEqual(hashlib.sha256(data).hexdigest(), job.INVENTORY_SHA256)
        bootstrap.safe_private_root(self.state)
        inventory = self.state / "transport_inventory.json"
        inventory.write_bytes(data)
        inventory.chmod(0o600)
        files = job.load_inventory(inventory)
        self.assertEqual(len(files), job.RAW_FILES)
        self.assertEqual(sum(item["size_bytes"] for item in files), job.RAW_BYTES)
        return files

    def simulated_raw_allocation(self, allocations):
        """Mock filesystem allocation for tiny files; do not create real EEG.

        Disk preflight must account for occupied blocks but never treat the
        planning result as content-hash or scientific-audit verification.
        """
        original_stat = Path.stat
        for path in allocations:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture-allocation-only")

        def allocation_stat(path, *args, **kwargs):
            result = original_stat(path, *args, **kwargs)
            allocated_bytes = allocations.get(path)
            if allocated_bytes is None:
                return result
            return SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_nlink=1,
                                   st_size=allocated_bytes,
                                   st_blocks=math.ceil(allocated_bytes / 512))

        return patch.object(Path, "stat", allocation_stat)

    def assert_not_started(self, report, stage, code):
        self.assertEqual(report["status"], "NOT_STARTED")
        self.assertEqual(report["stage"], stage)
        self.assertEqual(report["error_code"], code)
        self.popen.assert_not_called()

    def test_check_only_runs_real_api_and_complete_r2_probe_without_worker_or_stop(self):
        result, report = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 0)
        self.assertEqual(report["status"], "PREFLIGHT_PASSED_WORKER_NOT_STARTED")
        self.assertEqual([event[0] for event in self.store.events],
                         ["list", "head", "put", "get", "delete", "head"])
        self.assertTrue(self.store.deletion_confirmed)
        self.assertEqual(len(self.api_requests), 1)
        self.assertEqual(self.api_requests[0].full_url,
                         f"https://rest.runpod.io/v1/pods/{self.POD}?includeNetworkVolume=true")
        self.popen.assert_not_called()
        self.prompts.assert_not_called()
        cached = self.read_cache()
        self.assertTrue(cached["_validation"]["runpod"]["verified"])
        self.assertTrue(cached["_validation"]["r2"]["verified"])
        self.assertEqual((self.private / "credentials.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.private.stat().st_mode & 0o777, 0o700)

    def test_cached_manual_api_key_wins_over_invalid_injected_key(self):
        self.cache()
        bootstrap.os.environ["RUNPOD_API_KEY"] = "INVALID_INJECTED_API_KEY"
        result, _ = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 0)
        self.assertEqual(self.api_requests[0].get_header("Authorization"),
                         "Bearer " + self.CREDS["RUNPOD_API_KEY"])
        self.prompts.assert_not_called()

    def test_current_pod_environment_replaces_historical_cached_identity(self):
        self.cache(pod_id="historical-pod-id")
        result, _ = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 0)
        self.assertEqual(self.read_cache()["pod_id"], self.POD)
        self.assertIn(self.POD, self.api_requests[0].full_url)
        self.assertNotIn("historical-pod-id", self.api_requests[0].full_url)

    def test_non_tty_missing_field_fails_before_plaintext_prompt(self):
        bootstrap.os.environ.pop("R2_BUCKET")
        result, report = self.invoke()
        self.assertEqual(result, 2)
        self.assert_not_started(report, "credential_cache", "interactive_terminal_required_no_plaintext_fallback")
        self.prompts.assert_not_called()
        self.assertFalse(self.api_requests)

    def test_non_interactive_missing_field_names_variable_without_values(self):
        bootstrap.os.environ.pop("R2_BUCKET")
        result, report = self.invoke("--non-interactive")
        self.assertEqual(result, 2)
        self.assert_not_started(report, "credential_cache", "credential_missing_non_interactive:R2_BUCKET")
        self.prompts.assert_not_called()

    def test_cached_complete_credentials_work_without_tty_or_injected_r2_fields(self):
        self.cache()
        for name in bootstrap.REQUIRED:
            bootstrap.os.environ.pop(name, None)
        result, _ = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 0)
        self.prompts.assert_not_called()

    def test_network_edge_403_does_not_reprompt_for_credentials_or_launch_worker(self):
        self.api_errors.append(urllib.error.HTTPError(
            "https://rest.runpod.io/private-SENTINEL_SECRET_API", 403,
            "SENTINEL_SECRET_HTTP_BODY", {"cf-mitigated": "challenge"},
            io.BytesIO(b'{"error_code":1010,"detail":"SENTINEL_SECRET_HTTP_BODY"}')))
        result, report = self.invoke("--check-only")
        self.assertEqual(result, 2)
        self.assert_not_started(report, "runpod_api", "runpod_api_edge_policy_denied_http_403")
        self.assertEqual(len(self.api_requests), 1)
        self.prompts.assert_not_called()
        self.popen.assert_not_called()
        self.assertNotIn("SENTINEL_SECRET_HTTP_BODY", self.stdout.getvalue())
        self.assertIn("Do not keep re-entering credentials", self.stdout.getvalue())

    def test_real_401_and_403_http_errors_are_safe_and_persist_credentials_for_retry(self):
        for status in (401, 403):
            with self.subTest(status=status):
                self.api_errors = [urllib.error.HTTPError(
                    "https://rest.runpod.io/?token=SENTINEL_SECRET_API", status,
                    "SENTINEL_SECRET_HTTP_BODY", {}, io.BytesIO(b"SENTINEL_SECRET_HTTP_BODY"))]
                result, report = self.invoke("--check-only", "--non-interactive")
                self.assertEqual(result, 2)
                self.assert_not_started(report, "runpod_api", f"runpod_api_http_{status}")
                self.assertEqual({name: self.read_cache()[name] for name in bootstrap.REQUIRED}, self.CREDS)
                self.assertFalse(self.store.events)
        result, report = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 0)
        self.prompts.assert_not_called()

    def test_api_auth_retry_prompts_only_api_key_and_preserves_four_r2_fields(self):
        self.cache()
        self.api_errors = [urllib.error.HTTPError("https://rest.runpod.io/", 401,
                                                  "SENTINEL_SECRET_HTTP_BODY", {}, None), None]
        self.prompts.side_effect = ["SENTINEL_REENTERED_API"]
        with patch.object(sys.stdin, "isatty", return_value=True):
            result, _ = self.invoke("--check-only")
        self.assertEqual(result, 0)
        self.assertEqual(self.prompts.call_args_list[0].args, ("RUNPOD_API_KEY (hidden input): ",))
        self.assertEqual(self.prompts.call_count, 1)
        self.assertEqual(len(self.api_requests), 2)
        self.assertEqual(self.api_requests[-1].get_header("Authorization"), "Bearer SENTINEL_REENTERED_API")
        cached = self.read_cache()
        self.assertEqual({name: cached[name] for name in bootstrap.REQUIRED[:-1]},
                         {name: self.CREDS[name] for name in bootstrap.REQUIRED[:-1]})
        self.assertEqual(len([event for event in self.store.events if event[0] == "list"]), 1)
        self.assertNotIn("SENTINEL_REENTERED_API", self.stdout.getvalue())

    def test_partial_r2_cache_survives_api_failure_then_reuses_every_field(self):
        self.cache(omit=("RUNPOD_API_KEY",))
        for name in bootstrap.REQUIRED[:-1]:
            bootstrap.os.environ.pop(name, None)
        self.api_errors = [urllib.error.HTTPError("https://rest.runpod.io/", 403, "unsafe", {}, None)]
        result, report = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 2)
        self.assertEqual(report["stage"], "runpod_api")
        result, _ = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 0)
        self.prompts.assert_not_called()
        self.assertEqual({name: self.read_cache()[name] for name in bootstrap.REQUIRED}, self.CREDS)

    def test_reset_one_field_hidden_reentry_keeps_other_cached_values(self):
        self.cache()
        self.prompts.side_effect = ["SENTINEL_REENTERED_ACCESS_KEY"]
        with patch.object(sys.stdin, "isatty", return_value=True):
            # Saved start.sh uses --non-interactive; --interactive must allow
            # replacing a single rejected field without rebuilding the cache.
            result, _ = self.invoke("--non-interactive", "--interactive", "--check-only",
                                    "--reset-credential", "R2_SECRET_ACCESS_KEY")
        self.assertEqual(result, 0)
        self.prompts.assert_called_once_with("R2_SECRET_ACCESS_KEY (hidden input): ")
        cached = self.read_cache()
        self.assertEqual(cached["R2_SECRET_ACCESS_KEY"], "SENTINEL_REENTERED_ACCESS_KEY")
        for name in bootstrap.REQUIRED:
            if name != "R2_SECRET_ACCESS_KEY":
                self.assertEqual(cached[name], self.CREDS[name])
        self.assertNotIn("SENTINEL_REENTERED_ACCESS_KEY", self.stdout.getvalue())

    def test_known_allocated_quota_insufficient_blocks_before_sdk_or_popen(self):
        self.api_payload["volumeInGb"] = 30
        result, report = self.invoke("--non-interactive")
        self.assertEqual(result, 2)
        self.assert_not_started(report, "disk", "allocated_volume_quota_below_95_gib_requirement")
        self.boto.client.assert_not_called()
        self.assertFalse(self.store.events)

    def test_shared_df_capacity_cannot_replace_unknown_purchased_quota(self):
        self.api_payload.pop("volumeInGb")
        result, report = self.invoke("--non-interactive")
        self.assertEqual(result, 2)
        self.assert_not_started(report, "disk", "configured_workspace_volume_quota_unknown")
        self.boto.client.assert_not_called()

    def test_explicit_quota_fallback_persists_only_for_same_current_pod(self):
        self.api_payload.pop("volumeInGb")
        result, report = self.invoke("--check-only", "--non-interactive", "--volume-gb", "120")
        self.assertEqual(result, 0)
        self.assertFalse(report["disk_preflight"]["api_allocated_quota_verified"])
        self.assertEqual(report["disk_preflight"]["capacity_source"], "user_reported_for_current_pod")
        self.assertEqual(self.read_cache()["declared_volume_pod_id"], self.POD)
        result, _ = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 0)
        bootstrap.os.environ["RUNPOD_POD_ID"] = "fixture-second-pod"
        self.api_payload["id"] = "fixture-second-pod"
        result, report = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 2)
        self.assert_not_started(report, "disk", "configured_workspace_volume_quota_unknown")
        self.assertNotIn("declared_volume_gb", self.read_cache())
        self.assertNotIn("declared_volume_pod_id", self.read_cache())
        self.assertEqual(self.read_cache()["pod_id"], "fixture-second-pod")
        self.assertIn("fixture-second-pod", self.api_requests[-1].full_url)
        self.assertTrue(all(request.get_method() == "GET" for request in self.api_requests))

    def test_migration_rejects_old_pod_response_without_any_stop_or_old_pod_request(self):
        old_pod = "fixture-obsolete-pod"
        self.cache(pod_id=old_pod, declared_volume_gb=200, declared_volume_pod_id=old_pod)
        self.api_payload["id"] = old_pod
        result, report = self.invoke("--non-interactive")
        self.assertEqual(result, 2)
        self.assert_not_started(report, "runpod_api", "runpod_api_pod_identity_mismatch")
        self.assertEqual(len(self.api_requests), 1)
        self.assertEqual(self.api_requests[0].get_method(), "GET")
        self.assertIn(self.POD, self.api_requests[0].full_url)
        self.assertNotIn(old_pod, self.api_requests[0].full_url)
        self.assertNotIn("/stop", self.api_requests[0].full_url)
        self.assertNotIn("declared_volume_gb", self.read_cache())
        self.assertFalse(self.store.events)
        self.boto.client.assert_not_called()

    def test_cold_disk_budget_requires_all_raw_bytes_plus_reserve_before_detach(self):
        free = job.RAW_BYTES + 20 * 1024 ** 3 - 1
        with patch.object(bootstrap.shutil, "disk_usage", return_value=SimpleNamespace(free=free)):
            result, report = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 2)
        self.assert_not_started(report, "disk_remaining_space", "insufficient_free_disk_for_remaining_raw_and_reserve")
        self.restore_inventory.assert_called_once()

    def test_unpinned_existing_raw_files_cannot_bypass_cold_disk_budget(self):
        target = self.raw / "Cho2017" / "untrusted-fixture.mat"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"fixture-existing-untrusted-data")
        with patch.object(bootstrap.shutil, "disk_usage",
                          return_value=SimpleNamespace(free=20 * 1024 ** 3)):
            result, report = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 2)
        self.assert_not_started(report, "disk_remaining_space", "insufficient_free_disk_for_remaining_raw_and_reserve")
        self.restore_inventory.assert_called_once()

    def test_wrong_cached_inventory_hash_blocks_before_space_credit_or_r2_access(self):
        bootstrap.safe_private_root(self.state)
        inventory = self.state / "transport_inventory.json"
        inventory.write_bytes(b'{"files": [], "fixture": "not-trusted"}')
        inventory.chmod(0o600)
        result, report = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 2)
        self.assert_not_started(report, "disk", "cached_transport_inventory_hash_mismatch")
        self.boto.client.assert_not_called()
        self.assertFalse(self.store.events)

    def test_actual_pinned_inventory_full_cache_can_restart_with_only_reserve_free(self):
        files = self.cache_actual_pinned_inventory()
        allocations = {self.raw / item["dataset"] / item["file_id"]: item["size_bytes"]
                       for item in files}
        with self.simulated_raw_allocation(allocations), \
                patch.object(bootstrap.shutil, "disk_usage",
                             return_value=SimpleNamespace(free=20 * 1024 ** 3)):
            result, report = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 0)
        disk = report["disk_preflight"]
        self.assertTrue(disk["cached_transport_inventory_verified"])
        self.assertEqual(disk["credited_existing_allocation_bytes"], job.RAW_BYTES)
        self.assertEqual(disk["remaining_allocation_bytes"], 0)
        self.assertEqual(disk["required_free_bytes"], 20 * 1024 ** 3)
        self.assertFalse(disk["cached_content_integrity_verified_by_space_check"])
        self.popen.assert_not_called()

    def test_actual_pinned_partial_cache_uses_remaining_bytes_and_preserves_reserve(self):
        files = self.cache_actual_pinned_inventory()
        first, second = files[:2]
        partial = (self.raw / first["dataset"] / first["file_id"])
        partial = partial.with_name(partial.name + ".part")
        complete = self.raw / second["dataset"] / second["file_id"]
        allocations = {partial: first["size_bytes"] // 2, complete: second["size_bytes"]}
        credit = sum(allocations.values())
        free_needed = job.RAW_BYTES - credit + 20 * 1024 ** 3
        with self.simulated_raw_allocation(allocations):
            with patch.object(bootstrap.shutil, "disk_usage", return_value=SimpleNamespace(free=free_needed)):
                result, report = self.invoke("--check-only", "--non-interactive")
            self.assertEqual(result, 0)
            disk = report["disk_preflight"]
            self.assertEqual(disk["credited_existing_allocation_bytes"], credit)
            self.assertEqual(disk["required_free_bytes"], free_needed)
            self.assertFalse(disk["cached_content_integrity_verified_by_space_check"])
            prior_sdk_calls = self.boto.client.call_count
            with patch.object(bootstrap.shutil, "disk_usage", return_value=SimpleNamespace(free=free_needed - 1)):
                result, report = self.invoke("--check-only", "--non-interactive")
            self.assertEqual(result, 2)
            self.assert_not_started(report, "disk", "insufficient_free_disk_for_remaining_raw_and_reserve")
            self.assertEqual(self.boto.client.call_count, prior_sdk_calls)

    def test_known_small_api_quota_cannot_be_overridden_with_larger_user_report(self):
        self.api_payload["volumeInGb"] = 30
        result, report = self.invoke("--non-interactive", "--volume-gb", "200")
        self.assertEqual(result, 2)
        self.assert_not_started(report, "disk", "allocated_volume_quota_below_95_gib_requirement")
        self.boto.client.assert_not_called()

    def test_locked_pod_blocks_before_download_or_detach(self):
        self.api_payload["locked"] = True
        result, report = self.invoke("--non-interactive")
        self.assertEqual(result, 2)
        self.assert_not_started(report, "runpod_api", "runpod_pod_locked_stop_forbidden")
        self.boto.client.assert_not_called()

    def test_sdk_access_errors_have_precise_safe_codes_and_unchanged_stage(self):
        cases = {"AccessDenied": "s3_AccessDenied", "SignatureDoesNotMatch": "s3_SignatureDoesNotMatch",
                 "NoSuchBucket": "s3_NoSuchBucket"}
        for remote, safe in cases.items():
            with self.subTest(remote=remote):
                self.store.fail_list = ClientError(remote)
                result, report = self.invoke("--non-interactive")
                self.assertEqual(result, 2)
                self.assert_not_started(report, "r2_list_write_readback_delete", safe)
                self.assertEqual(report["fits_started"], 0)

    def test_probe_readback_mismatch_is_specific_and_no_worker_is_started(self):
        self.store.corrupt_readback = True
        result, report = self.invoke("--non-interactive")
        self.assertEqual(result, 2)
        self.assert_not_started(report, "r2_list_write_readback_delete", "backup_readback_hash_mismatch")
        self.assertEqual(len([event for event in self.store.events if event[0] == "get"]), 3)

    def test_probe_delete_must_be_confirmed_not_merely_accepted(self):
        self.store.keep_deleted = True
        result, report = self.invoke("--non-interactive")
        self.assertEqual(result, 2)
        self.assert_not_started(report, "r2_list_write_readback_delete", "preflight_delete_not_confirmed")

    def test_dependency_install_failure_keeps_private_cache_for_next_start(self):
        with patch.dict(sys.modules, {"boto3": None}), \
                patch.object(bootstrap.subprocess, "run", return_value=SimpleNamespace(returncode=1)) as install:
            result, report = self.invoke("--non-interactive")
        self.assertEqual(result, 2)
        self.assert_not_started(report, "s3_dependency_and_client", "boto3_install_failed")
        self.assertEqual({name: self.read_cache()[name] for name in bootstrap.REQUIRED}, self.CREDS)
        self.assertEqual(install.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(install.call_args.kwargs["stdout"], subprocess.DEVNULL)
        self.assertEqual(install.call_args.kwargs["stderr"], subprocess.DEVNULL)
        result, _ = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 0)
        self.prompts.assert_not_called()

    def test_dependency_timeout_does_not_print_unsafe_command_or_drop_cache(self):
        unsafe = subprocess.TimeoutExpired(["SENTINEL_SECRET_API"], 300,
                                            output=b"SENTINEL_SECRET_HTTP_BODY")
        with patch.dict(sys.modules, {"boto3": None}), \
                patch.object(bootstrap.subprocess, "run", side_effect=unsafe):
            result, report = self.invoke("--non-interactive")
        self.assertEqual(result, 2)
        self.assert_not_started(report, "s3_dependency_and_client", "dependency_install_timeout")
        self.assertEqual({name: self.read_cache()[name] for name in bootstrap.REQUIRED}, self.CREDS)

    def test_unsafe_cached_credential_permissions_fail_before_loading_or_cloud_access(self):
        self.cache()
        (self.private / "credentials.json").chmod(0o644)
        result, report = self.invoke("--non-interactive")
        self.assertEqual(result, 2)
        self.assert_not_started(report, "credential_storage", "existing_credential_file_permissions_unsafe")
        self.assertFalse(self.api_requests)
        self.prompts.assert_not_called()

    def test_verified_detached_start_requires_handshake_and_does_not_inherit_credentials(self):
        result, report = self.invoke("--non-interactive")
        self.assertEqual(result, 0)
        self.assertEqual(report["status"], "detached_download_supervisor_started_training_not_started")
        self.assertEqual(report["pid"], 54321)
        self.popen.assert_called_once()
        kwargs = self.popen.call_args.kwargs
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertTrue(kwargs["start_new_session"])
        self.assertTrue(kwargs["close_fds"])
        self.assertEqual(kwargs["env"]["RUNPOD_POD_ID"], self.POD)
        for name in bootstrap.REQUIRED:
            self.assertNotIn(name, kwargs["env"])
        self.assertIsNone(self.children[0].poll())
        start = self.private / "start.sh"
        self.assertEqual(start.stat().st_mode & 0o777, 0o700)
        self.assertIn("--non-interactive", start.read_text())
        for value in self.CREDS.values():
            self.assertNotIn(value, start.read_text())
        runtime = self.private / "runtime"
        manifest = json.loads((runtime / "runtime_manifest.json").read_text())
        for name, expected_sha in manifest["files"].items():
            self.assertEqual(hashlib.sha256((runtime / name).read_bytes()).hexdigest(), expected_sha)
        self.assertEqual(len(self.api_requests), 1)

    def test_verified_status_from_already_exited_child_cannot_claim_started(self):
        self.child_mode = "exited_after_status"
        result, report = self.invoke("--non-interactive")
        self.assertEqual(result, 2)
        self.assertEqual(report["status"], "WORKER_STARTUP_NOT_CONFIRMED")
        self.assertEqual(report["stage"], "verified_worker_startup")
        self.assertEqual(report["error_code"], "detached_worker_exited_before_verified_startup")
        self.assertNotIn("Verified detached startup succeeded", self.stdout.getvalue())

    def test_startup_timeout_is_pending_not_a_false_not_started_retry(self):
        self.child_mode = "pending"
        with patch.object(bootstrap.time, "monotonic", side_effect=[0, 0, 2]):
            result, report = self.invoke("--non-interactive", "--startup-timeout", "1")
        self.assertEqual(result, 2)
        self.assertEqual(report["status"], "LAUNCH_PENDING_NOT_CONFIRMED")
        self.assertEqual(report["pid"], 54321)
        self.popen.assert_called_once()
        self.assertNotIn('"status": "NOT_STARTED"', self.stdout.getvalue())
        pointer = json.loads((self.state / "active_job.json").read_text())
        self.assertEqual(pointer["pid"], 54321)

    def test_detached_worker_failure_carries_safe_specific_error_and_retains_pid(self):
        self.child_mode = "failed"
        result, report = self.invoke("--non-interactive")
        self.assertEqual(result, 2)
        self.assertEqual(report["status"], "WORKER_STARTUP_NOT_CONFIRMED")
        self.assertEqual(report["error_code"], "archive_hash_mismatch")
        self.assertEqual(report["pid"], 54321)

    def test_child_config_failure_without_status_extracts_only_safe_code_from_private_log(self):
        self.child_mode = "failed_log_only"
        result, report = self.invoke("--non-interactive")
        self.assertEqual(result, 2)
        self.assertEqual(report["status"], "WORKER_STARTUP_NOT_CONFIRMED")
        self.assertEqual(report["stage"], "verified_worker_startup")
        self.assertEqual(report["error_code"], "runpod_api_http_403")
        self.assertEqual(report["pid"], 54321)
        pointer = json.loads((self.state / "active_job.json").read_text())
        job_dir = self.state / "jobs" / pointer["job_id"]
        self.assertFalse((job_dir / "job_status.json").exists())
        self.assertEqual((job_dir / "supervisor.log").stat().st_mode & 0o777, 0o600)
        self.assertNotIn("request_url", json.dumps(report))
        self.assertNotIn("SENTINEL_SECRET_HTTP_BODY", self.stdout.getvalue())
        self.assertNotIn("SENTINEL_SECRET_API", self.stdout.getvalue())

    def test_existing_active_worker_reused_without_credentials_api_or_second_popen(self):
        bootstrap.safe_private_root(self.state)
        active = job.acquire_job_lock(self.state / "active.lock")
        self.addCleanup(active.close)
        stamp = "20261002T130000Z-abcdef123456"
        job_dir = self.state / "jobs" / stamp
        job_dir.mkdir(parents=True)
        bootstrap.atomic_state_json(self.state / "active_job.json",
                                      {"job_id": stamp, "pid": 54321, "pod_id": self.POD})
        bootstrap.atomic_state_json(job_dir / "job_status.json",
                                      {"status": "downloading_raw", "fits_started": 0,
                                       "pod_identity_verified": True})
        for name in bootstrap.REQUIRED:
            bootstrap.os.environ.pop(name, None)
        result, report = self.invoke("--non-interactive")
        self.assertEqual(result, 0)
        self.assertEqual(report["status"], "EXISTING_WORKER_ACTIVE")
        self.assertFalse(self.api_requests)
        self.popen.assert_not_called()
        self.prompts.assert_not_called()
        self.boto.client.assert_not_called()

    def test_active_shared_volume_worker_on_old_pod_is_not_reused_or_stopped(self):
        bootstrap.safe_private_root(self.state)
        active = job.acquire_job_lock(self.state / "active.lock")
        self.addCleanup(active.close)
        stamp = "20261002T130000Z-abcdef123456"
        job_dir = self.state / "jobs" / stamp
        job_dir.mkdir(parents=True)
        bootstrap.atomic_state_json(self.state / "active_job.json",
                                      {"job_id": stamp, "pid": 54321, "pod_id": "fixture-old-still-active-pod"})
        bootstrap.atomic_state_json(job_dir / "job_status.json",
                                      {"status": "downloading_raw", "fits_started": 0,
                                       "pod_identity_verified": True})
        result, report = self.invoke("--non-interactive")
        self.assertEqual(result, 2)
        self.assert_not_started(report, "current_pod_identity", "shared_volume_worker_belongs_to_different_pod")
        self.assertFalse(self.api_requests)
        self.prompts.assert_not_called()
        self.boto.client.assert_not_called()

    def test_rejected_cached_old_pod_api_key_retries_current_environment_without_prompt(self):
        self.cache(pod_id="fixture-old-pod", RUNPOD_API_KEY="SENTINEL_OLD_POD_SCOPED_KEY")
        self.api_errors = [urllib.error.HTTPError("https://rest.runpod.io/", 403, "unsafe", {}, None), None]
        result, report = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 0)
        self.assertEqual(len(self.api_requests), 2)
        self.assertEqual(self.api_requests[0].get_header("Authorization"), "Bearer SENTINEL_OLD_POD_SCOPED_KEY")
        self.assertEqual(self.api_requests[1].get_header("Authorization"), "Bearer " + self.CREDS["RUNPOD_API_KEY"])
        self.assertTrue(all(self.POD in request.full_url for request in self.api_requests))
        self.assertTrue(all(request.get_method() == "GET" for request in self.api_requests))
        self.assertEqual(report["credential_sources"]["RUNPOD_API_KEY"], "current_environment_auth_retry")
        self.prompts.assert_not_called()
        self.assertEqual(self.read_cache()["RUNPOD_API_KEY"], self.CREDS["RUNPOD_API_KEY"])
        self.assertNotIn("SENTINEL_OLD_POD_SCOPED_KEY", self.stdout.getvalue())

    def fixture_inventory_archive(self, *, member_kind="file", duplicate=False, wrong_schema=False):
        """Small public-CI fixture; hashes and byte totals are fixture pins only."""
        files = [{"dataset": dataset, "file_id": f"fixture-{index:03d}.mat",
                  "r2_object_key": f"fixture-only/{dataset}/{index:03d}.mat", "size_bytes": 1}
                 for dataset, count in (("Cho2017", 52), ("Lee2019_MI", 108))
                 for index in range(count)]
        inventory = json.dumps({"files": [] if wrong_schema else files}).encode()
        stream = io.BytesIO()
        member_name = "research_runs/Q15-DATA/r2_source_storage_verification.json"
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            for _ in range(2 if duplicate else 1):
                member = tarfile.TarInfo(member_name)
                if member_kind == "file":
                    member.size = len(inventory)
                    archive.addfile(member, io.BytesIO(inventory))
                else:
                    member.type = tarfile.SYMTYPE
                    member.linkname = "../../fixture-must-not-be-written"
                    archive.addfile(member)
            # The implementation reads only the pinned regular inventory
            # member. No other archive path is extracted, even if hostile.
            unrelated = tarfile.TarInfo("../../fixture-must-not-be-written")
            unrelated.size = 1
            archive.addfile(unrelated, io.BytesIO(b"!"))
        archive_body = stream.getvalue()
        self.store.objects[job.ARCHIVE_KEY] = (archive_body, {})
        bootstrap.safe_private_root(self.state)
        patches = ExitStack()
        self.addCleanup(patches.close)
        patches.enter_context(patch.object(job, "ARCHIVE_SHA", hashlib.sha256(archive_body).hexdigest()))
        patches.enter_context(patch.object(job, "ARCHIVE_BYTES", len(archive_body)))
        patches.enter_context(patch.object(job, "INVENTORY_SHA256", hashlib.sha256(inventory).hexdigest()))
        patches.enter_context(patch.object(job, "RAW_BYTES", len(files)))
        return inventory

    def test_restored_fixture_inventory_is_pinned_private_and_reused_without_archive_get(self):
        inventory = self.fixture_inventory_archive()
        target = self.real_restore_inventory(self.store, self.CREDS, job, self.state)
        self.assertEqual(target.read_bytes(), inventory)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(len(job.load_inventory(target)), 160)
        self.assertEqual([event[0] for event in self.store.events], ["head", "get"])
        self.assertFalse((self.root.parent / "fixture-must-not-be-written").exists())
        self.assertFalse(self.raw.exists())
        requests_before = list(self.store.events)
        self.assertEqual(self.real_restore_inventory(self.store, self.CREDS, job, self.state), target)
        self.assertEqual(self.store.events, requests_before)
        self.assertEqual(list(self.state.iterdir()), [target])

    def test_restored_archive_with_wrong_full_hash_never_creates_final_inventory(self):
        self.fixture_inventory_archive()
        with patch.object(job, "ARCHIVE_SHA", "0" * 64):
            with self.assertRaises(job.IntegrityError):
                self.real_restore_inventory(self.store, self.CREDS, job, self.state)
        self.assertFalse((self.state / "transport_inventory.json").exists())
        self.assertEqual(sum(event[0] == "get" for event in self.store.events), 3)

    def test_restored_inventory_with_wrong_member_hash_is_rejected_before_cache(self):
        self.fixture_inventory_archive()
        with patch.object(job, "INVENTORY_SHA256", "0" * 64):
            with self.assertRaisesRegex(bootstrap.BootstrapError, "authenticated_transport_inventory_hash_mismatch"):
                self.real_restore_inventory(self.store, self.CREDS, job, self.state)
        self.assertFalse((self.state / "transport_inventory.json").exists())

    def test_duplicate_inventory_members_are_rejected_without_extracting_archive_paths(self):
        self.fixture_inventory_archive(duplicate=True)
        with self.assertRaisesRegex(bootstrap.BootstrapError, "authenticated_transport_inventory_member_invalid"):
            self.real_restore_inventory(self.store, self.CREDS, job, self.state)
        self.assertFalse((self.state / "transport_inventory.json").exists())

    def test_symlink_inventory_member_is_rejected_without_extracting_archive_paths(self):
        self.fixture_inventory_archive(member_kind="symlink")
        with self.assertRaisesRegex(bootstrap.BootstrapError, "authenticated_transport_inventory_member_invalid"):
            self.real_restore_inventory(self.store, self.CREDS, job, self.state)
        self.assertFalse((self.state / "transport_inventory.json").exists())

    def test_correctly_pinned_but_invalid_inventory_schema_does_not_leave_final_cache(self):
        self.fixture_inventory_archive(wrong_schema=True)
        with self.assertRaisesRegex(job.IntegrityError, "original_inventory_count_mismatch"):
            self.real_restore_inventory(self.store, self.CREDS, job, self.state)
        self.assertFalse((self.state / "transport_inventory.json").exists())

    def test_raw_only_migration_restores_authenticated_metadata_before_full_space_budget(self):
        inventory = self.fixture_inventory_archive()
        files = json.loads(inventory)["files"]
        for item in files:
            path = self.raw / item["dataset"] / item["file_id"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"!")
        self.assertFalse((self.state / "transport_inventory.json").exists())
        original_loader = bootstrap.load_job_module

        def fixture_loader(source):
            # The loader still validates the real worker source pin. Only the
            # imported module's dataset byte/hash constants become small
            # synthetic fixtures, leaving the actual restore flow intact.
            module = original_loader(source)
            for name in ("ARCHIVE_SHA", "ARCHIVE_BYTES", "INVENTORY_SHA256", "RAW_BYTES"):
                setattr(module, name, getattr(job, name))
            return module

        self.restore_inventory.side_effect = self.real_restore_inventory
        with patch.object(bootstrap, "load_job_module", side_effect=fixture_loader), \
                patch.object(bootstrap.shutil, "disk_usage",
                             return_value=SimpleNamespace(free=20 * 1024 ** 3)):
            result, report = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 0)
        self.assertEqual(report["status"], "PREFLIGHT_PASSED_WORKER_NOT_STARTED")
        disk = report["disk_preflight"]
        self.assertTrue(disk["complete_remaining_space_budget_verified"])
        self.assertTrue(disk["cached_transport_inventory_verified"])
        self.assertEqual(disk["remaining_allocation_bytes"], 0)
        self.assertEqual(disk["required_free_bytes"], 20 * 1024 ** 3)
        self.assertFalse(disk["cached_content_integrity_verified_by_space_check"])
        self.assertEqual((self.state / "transport_inventory.json").read_bytes(), inventory)
        # Probe readback completes first, then the archive GET authenticates
        # metadata. No raw EEG is downloaded or accepted as hash-verified here.
        self.assertEqual([event[0] for event in self.store.events],
                         ["list", "head", "put", "get", "delete", "head", "head", "get"])
        self.popen.assert_not_called()

    def assert_shared_state_has_no_credentials(self):
        for path in self.state.rglob("*"):
            if path.is_file():
                body = path.read_bytes()
                for value in self.CREDS.values():
                    self.assertNotIn(value.encode(), body, str(path))
        self.assertFalse((self.state / "credentials.json").exists())

    def make_wide_legacy_cache(self, **extra):
        self.legacy.mkdir(mode=0o777)
        self.legacy.chmod(0o777)
        legacy = self.legacy / "credentials.json"
        legacy.write_text(json.dumps({**self.CREDS, **extra}))
        legacy.chmod(0o666)
        return legacy

    def test_wide_legacy_credentials_migrate_to_strict_private_storage_without_leak(self):
        legacy = self.make_wide_legacy_cache(
            pod_id="fixture-old-pod", raw_dir="/fixture-untrusted-path",
            attacker_extra="SENTINEL_EXTRA_MUST_NOT_MIGRATE",
            _validation={"runpod": {"verified": True, "pod_id": "fixture-old-pod"}})
        for name in bootstrap.REQUIRED:
            bootstrap.os.environ.pop(name, None)
        result, report = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 0)
        self.assertEqual(report["status"], "PREFLIGHT_PASSED_WORKER_NOT_STARTED")
        cached = self.read_cache()
        self.assertEqual({name: cached[name] for name in bootstrap.REQUIRED}, self.CREDS)
        self.assertEqual(cached["pod_id"], self.POD)
        self.assertEqual(cached["raw_dir"], str(self.raw))
        self.assertNotIn("attacker_extra", cached)
        self.assertNotIn("SENTINEL_EXTRA_MUST_NOT_MIGRATE", self.stdout.getvalue())
        self.assertEqual(self.private.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.private / "credentials.json").stat().st_mode & 0o777, 0o600)
        self.assertFalse(legacy.exists())
        self.prompts.assert_not_called()
        self.assert_shared_state_has_no_credentials()

    def test_existing_private_cache_wins_and_legacy_wide_secret_copy_is_removed(self):
        self.cache()
        legacy = self.make_wide_legacy_cache(RUNPOD_API_KEY="SENTINEL_LEGACY_API_MUST_NOT_REPLACE")
        result, report = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 0)
        self.assertEqual(self.read_cache()["RUNPOD_API_KEY"], self.CREDS["RUNPOD_API_KEY"])
        self.assertEqual(self.api_requests[0].get_header("Authorization"),
                         "Bearer " + self.CREDS["RUNPOD_API_KEY"])
        self.assertFalse(legacy.exists())
        self.assertNotIn("SENTINEL_LEGACY_API_MUST_NOT_REPLACE", self.stdout.getvalue())
        self.assert_shared_state_has_no_credentials()

    def test_partial_private_cache_recovers_missing_fields_before_legacy_removal(self):
        self.cache(omit=("R2_SECRET_ACCESS_KEY", "RUNPOD_API_KEY"))
        legacy = self.make_wide_legacy_cache()
        for name in bootstrap.REQUIRED:
            bootstrap.os.environ.pop(name, None)
        result, report = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 0)
        self.assertEqual({name: self.read_cache()[name] for name in bootstrap.REQUIRED}, self.CREDS)
        self.assertFalse(legacy.exists())
        self.prompts.assert_not_called()
        self.assert_shared_state_has_no_credentials()

    def test_legacy_symlink_cannot_be_loaded_migrated_or_deleted(self):
        outside = self.root / "outside-credentials.json"
        outside.write_text(json.dumps(self.CREDS))
        self.legacy.mkdir()
        legacy = self.legacy / "credentials.json"
        legacy.symlink_to(outside)
        result, report = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 2)
        self.assertTrue(legacy.is_symlink())
        self.assertTrue(outside.exists())
        self.assertFalse((self.private / "credentials.json").exists())
        self.assertFalse(self.api_requests)
        self.popen.assert_not_called()
        self.prompts.assert_not_called()

    def test_legacy_hardlink_cannot_duplicate_secret_into_private_storage(self):
        outside = self.root / "outside-credentials.json"
        outside.write_text(json.dumps(self.CREDS))
        self.legacy.mkdir()
        legacy = self.legacy / "credentials.json"
        os.link(outside, legacy)
        result, report = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 2)
        self.assertTrue(legacy.exists())
        self.assertTrue(outside.exists())
        self.assertFalse((self.private / "credentials.json").exists())
        self.assertFalse(self.api_requests)
        self.popen.assert_not_called()

    def test_private_filesystem_that_ignores_chmod_fails_before_secret_loading(self):
        self.private.mkdir(mode=0o777)
        self.private.chmod(0o777)
        with patch.object(bootstrap.os, "chmod", return_value=None):
            result, report = self.invoke("--check-only", "--non-interactive")
        self.assertEqual(result, 2)
        self.assertFalse((self.private / "credentials.json").exists())
        self.assertFalse(self.api_requests)
        self.popen.assert_not_called()
        self.prompts.assert_not_called()
        self.assertNotIn("SENTINEL", self.stdout.getvalue())

    def test_private_atomic_write_rejects_broad_mode_before_secret_installation(self):
        bootstrap.safe_private_root(self.private)
        destination = self.private / "credentials.json"
        original_open = bootstrap.os.open

        def broad_create(path, flags, mode=0o777, *args, **kwargs):
            fd = original_open(path, flags, mode, *args, **kwargs)
            if flags & os.O_CREAT and Path(path).parent == self.private:
                # Model a filesystem's returned modes independently of the
                # bootstrap's protective umask and requested create mode.
                os.fchmod(fd, 0o666)
            return fd

        with patch.object(bootstrap.os, "chmod", return_value=None), \
                patch.object(bootstrap.os, "open", side_effect=broad_create):
            with self.assertRaises(bootstrap.BootstrapError):
                bootstrap.atomic_private_json(destination, self.CREDS)
        self.assertFalse(destination.exists())
        self.assertEqual(list(self.private.glob("credentials.json.new-*")), [])
        self.assertFalse(self.api_requests)

    def test_shared_fuse_modes_are_supported_without_any_persistent_credentials(self):
        self.state.mkdir(mode=0o777)
        self.state.chmod(0o777)
        original_chmod = bootstrap.os.chmod
        original_stat = Path.stat

        def shared_chmod(path, mode, *args, **kwargs):
            if Path(path).is_relative_to(self.state):
                return None
            return original_chmod(path, mode, *args, **kwargs)

        def shared_stat(path, *args, **kwargs):
            result = original_stat(path, *args, **kwargs)
            if path.is_relative_to(self.state):
                values = list(result)
                values[0] = stat.S_IFMT(result.st_mode) | (0o777 if stat.S_ISDIR(result.st_mode) else 0o666)
                return os.stat_result(values)
            return result

        with patch.object(bootstrap.os, "chmod", side_effect=shared_chmod), \
                patch.object(Path, "stat", shared_stat):
            result, report = self.invoke("--non-interactive")
        self.assertEqual(result, 0)
        self.assertEqual(report["status"], "detached_download_supervisor_started_training_not_started")
        self.assertEqual(self.read_cache()["shared_control_dir"], str(self.state))
        self.assertEqual(self.private.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.private / "credentials.json").stat().st_mode & 0o777, 0o600)
        self.assert_shared_state_has_no_credentials()
        config_arg = self.popen.call_args.args[0]
        self.assertEqual(config_arg[config_arg.index("--config") + 1], str(self.private / "credentials.json"))
        self.assertEqual(config_arg[config_arg.index("--control-dir") + 1], str(self.state))
        self.assertTrue(Path(config_arg[1]).is_relative_to(self.private / "workers"))

    def test_concurrent_bootstrap_lock_failure_has_no_external_effects(self):
        bootstrap.safe_private_root(self.state)
        with bootstrap.launch_lock(self.state / "launch.lock"):
            result, report = self.invoke("--non-interactive")
        self.assertEqual(result, 2)
        # Before this invocation owns launch.lock it cannot replace an earlier
        # launch report. The safe stdout still gives an actionable reason.
        self.assertIn('"error_code": "another_bootstrap_is_active"', self.stdout.getvalue())
        self.assertFalse(self.api_requests)
        self.popen.assert_not_called()
        self.prompts.assert_not_called()


if __name__ == "__main__":
    unittest.main()
