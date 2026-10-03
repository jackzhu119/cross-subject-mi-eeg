#!/usr/bin/env python3
"""Private, resumable RunPod bootstrap for Q15 raw transport only.

Credentials never enter command arguments, reports, or logs. All network checks
run on the Pod where this script is invoked; no model training is implemented.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import getpass
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
import uuid
import warnings

EXPECTED_JOB_SHA256 = "f4b9526b7a04d1f8d55bddac9b405f8d842e8a99ab800bfec1df34997604f8a2"
PRIVATE_ROOT = Path("/workspace/.q15-cloud")
RAW_ROOT = Path("/workspace/q15-data/raw")
REQUIRED = ("R2_BUCKET", "R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "RUNPOD_API_KEY")
SAFE_CODE_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,159}(?::(?:R2_BUCKET|R2_ENDPOINT|R2_ACCESS_KEY_ID|R2_SECRET_ACCESS_KEY|RUNPOD_API_KEY))?")
MIN_FREE_BYTES = 95 * 1024 ** 3


class BootstrapError(RuntimeError):
    def __init__(self, safe_code):
        self.safe_code = safe_code if isinstance(safe_code, str) and SAFE_CODE_PATTERN.fullmatch(safe_code) else "bootstrap_failure"
        super().__init__(self.safe_code)


def safe_error_code(exc, job_module=None):
    """Never stringify arbitrary exceptions or server responses."""
    code = getattr(exc, "safe_code", None)
    if isinstance(code, str) and SAFE_CODE_PATTERN.fullmatch(code):
        return code
    if isinstance(exc, subprocess.TimeoutExpired):
        return "dependency_install_timeout"
    if isinstance(exc, OSError):
        if exc.errno in (28, 122):
            return "actual_volume_quota_or_disk_full"
        if exc.errno in (13, 1):
            return "filesystem_permission_denied"
        return "filesystem_operation_failed"
    if isinstance(exc, KeyboardInterrupt):
        return "bootstrap_interrupted"
    if job_module is not None and hasattr(job_module, "safe_error_code"):
        code = job_module.safe_error_code(exc)
        if isinstance(code, str) and SAFE_CODE_PATTERN.fullmatch(code):
            return code
    return "bootstrap_unexpected_failure"


def now():
    return datetime.now(timezone.utc).isoformat()


def safe_private_root(root):
    root = Path(root).absolute()
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise BootstrapError("private_directory_or_ancestor_symlink")
    if any((path / ".git").exists() for path in (root, *root.parents)):
        raise BootstrapError("private_credential_directory_inside_git_worktree")
    root.mkdir(parents=True, exist_ok=True)
    if not root.is_dir() or root.stat().st_uid != os.getuid():
        raise BootstrapError("private_directory_owner_or_type_unsafe")
    os.chmod(root, 0o700)
    return root


def check_regular_file(path, secret=False):
    if path.is_symlink():
        raise BootstrapError("private_file_symlink")
    mode = path.stat()
    if not stat.S_ISREG(mode.st_mode) or mode.st_uid != os.getuid():
        raise BootstrapError("private_file_owner_or_type_unsafe")
    if secret and mode.st_mode & 0o077:
        raise BootstrapError("existing_credential_file_permissions_unsafe")


def atomic_private_bytes(path, body, mode=0o600):
    path = Path(path)
    if path.is_symlink():
        raise BootstrapError("private_file_symlink")
    if path.exists():
        check_regular_file(path)
    temp = path.with_name(path.name + ".new-" + uuid.uuid4().hex)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(temp, flags, mode)
        with os.fdopen(fd, "wb") as output:
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def atomic_private_json(path, value):
    atomic_private_bytes(path, (json.dumps(value, sort_keys=True, indent=2) + "\n").encode())


def read_private_json(path, secret=False):
    path = Path(path)
    if path.is_symlink():
        raise BootstrapError("private_file_symlink")
    if not path.exists():
        return {}
    check_regular_file(path, secret=secret)
    try:
        value = json.loads(path.read_bytes())
    except (ValueError, UnicodeError):
        raise BootstrapError("private_json_invalid") from None
    if not isinstance(value, dict):
        raise BootstrapError("private_json_invalid")
    return value


@contextmanager
def launch_lock(path):
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "a+") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise BootstrapError("bootstrap_lock_file_type_unsafe")
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BootstrapError("another_bootstrap_is_active") from None
        yield


class StageReport:
    def __init__(self):
        self.path = None
        self.job_module = None
        self.data = {"schema_version": 1, "status": "NOT_STARTED", "stage": "initialization",
                     "fits_started": 0, "scientific_contract_frozen": False,
                     "started_at_utc": now(), "stages": []}

    def save(self):
        self.data["updated_at_utc"] = now()
        if self.path is not None:
            atomic_private_json(self.path, self.data)

    def stage(self, name, status="running", **safe_details):
        self.data["stage"] = name
        self.data["stages"].append({"stage": name, "status": status, "at_utc": now(), **safe_details})
        self.save()
        print(json.dumps({"stage": name, "status": status, **safe_details}), flush=True)


def read_hidden(name, previous, non_interactive=False, force_prompt=False):
    # User-entered, protected cached values take precedence over possibly stale
    # injected environment values. They are revalidated remotely every launch.
    if not force_prompt:
        value = previous.get(name) or os.environ.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if non_interactive:
        raise BootstrapError("credential_missing_non_interactive:" + name)
    if not sys.stdin.isatty():
        raise BootstrapError("interactive_terminal_required_no_plaintext_fallback")
    for _ in range(3):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                value = getpass.getpass(name + " (hidden input): ").strip()
        except getpass.GetPassWarning:
            raise BootstrapError("hidden_terminal_input_unavailable_no_plaintext_fallback") from None
        except EOFError:
            raise BootstrapError("hidden_terminal_input_ended") from None
        if value:
            return value
    raise BootstrapError("required_credential_not_provided:" + name)


def validate_credential_shape(credentials):
    endpoint = urllib.parse.urlsplit(credentials["R2_ENDPOINT"])
    if (endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or endpoint.password
        or endpoint.query or endpoint.fragment or endpoint.path not in ("", "/")
        or not endpoint.hostname.endswith(".r2.cloudflarestorage.com")):
        raise BootstrapError("expected_https_cloudflare_r2_account_endpoint")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", credentials["R2_BUCKET"]):
        raise BootstrapError("bucket_name_invalid")
    for name in REQUIRED:
        value = credentials[name]
        if not isinstance(value, str) or not value or len(value) > 4096 or any(ord(ch) < 32 for ch in value):
            raise BootstrapError("credential_format_invalid:" + name)


def load_job_module(source):
    if source.is_symlink() or not source.is_file():
        raise BootstrapError("companion_job_script_missing_or_symlink")
    if hashlib.sha256(source.read_bytes()).hexdigest() != EXPECTED_JOB_SHA256:
        raise BootstrapError("companion_job_script_hash_mismatch")
    spec = importlib.util.spec_from_file_location("q15_launch_job", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def install_runtime(private, bootstrap, source):
    runtime = private / "runtime"
    if runtime.is_symlink():
        raise BootstrapError("private_runtime_directory_symlink")
    runtime.mkdir(mode=0o700, exist_ok=True)
    os.chmod(runtime, 0o700)
    files = {"q15_cloud_bootstrap.py": Path(bootstrap).read_bytes(), "q15_cloud_job.py": source.read_bytes()}
    for name, body in files.items():
        atomic_private_bytes(runtime / name, body, 0o700)
    atomic_private_json(runtime / "runtime_manifest.json",
                        {"files": {name: hashlib.sha256(body).hexdigest() for name, body in files.items()}, "fits_started": 0})
    command = shlex.quote(sys.executable) + " " + shlex.quote(str(runtime / "q15_cloud_bootstrap.py"))
    body = '#!/usr/bin/env bash\nset -euo pipefail\nexec ' + command + ' --non-interactive "$@"\n'
    atomic_private_bytes(private / "start.sh", body.encode(), 0o700)


def make_s3_client(credentials):
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        print("Installing the cloud S3 client...", flush=True)
        result = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                                 "--quiet", "boto3>=1.36,<2"], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
        if result.returncode:
            raise BootstrapError("boto3_install_failed")
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise BootstrapError("boto3_unavailable_after_install") from None
    return boto3.client("s3", endpoint_url=credentials["R2_ENDPOINT"],
                        aws_access_key_id=credentials["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=credentials["R2_SECRET_ACCESS_KEY"], region_name="auto",
                        config=Config(s3={"addressing_style": "path"}, connect_timeout=30, read_timeout=60,
                                      retries={"max_attempts": 3, "mode": "standard"},
                                      request_checksum_calculation="when_required",
                                      response_checksum_validation="when_required"))


def verify_runpod(job_module, credentials, config_path, report, non_interactive):
    environment_candidate = os.environ.get("RUNPOD_API_KEY")
    environment_candidate_tried = environment_candidate == credentials["RUNPOD_API_KEY"]
    for attempt in range(3):
        try:
            result = job_module.runpod_request(credentials["RUNPOD_API_KEY"], credentials["pod_id"])
            credentials.setdefault("_validation", {})["runpod"] = {"verified": True, "pod_id": credentials["pod_id"]}
            atomic_private_json(config_path, credentials)
            return result
        except Exception as exc:
            code = safe_error_code(exc, job_module)
            credentials.setdefault("_validation", {})["runpod"] = {"verified": False, "error_code": code}
            atomic_private_json(config_path, credentials)
            if code not in ("runpod_api_http_401", "runpod_api_http_403") or attempt == 2:
                raise
            if (not environment_candidate_tried and isinstance(environment_candidate, str)
                and environment_candidate.strip() and len(environment_candidate) <= 4096
                and not any(ord(ch) < 32 for ch in environment_candidate)):
                environment_candidate_tried = True
                credentials["RUNPOD_API_KEY"] = environment_candidate.strip()
                report.data.setdefault("credential_sources", {})["RUNPOD_API_KEY"] = "current_environment_auth_retry"
                report.stage("runpod_api", "current_environment_auth_retry", error_code=code, retry=attempt + 1)
                atomic_private_json(config_path, credentials)
                continue
            if non_interactive:
                raise
            report.stage("runpod_api", "credential_rejected", error_code=code, retry=attempt + 1)
            print("Re-enter RUNPOD_API_KEY; the four protected R2 values remain cached.", flush=True)
            credentials["RUNPOD_API_KEY"] = read_hidden("RUNPOD_API_KEY", {}, force_prompt=True)
            report.data.setdefault("credential_sources", {})["RUNPOD_API_KEY"] = "hidden_prompt"
            report.save()
            atomic_private_json(config_path, credentials)
    raise BootstrapError("runpod_api_verification_failed")


def verify_disk(raw, api_result, report, declared_volume_gb=None, inventory_pending=False):
    raw = Path(raw).absolute()
    if any(path.is_symlink() for path in (raw, *raw.parents)):
        raise BootstrapError("raw_directory_or_ancestor_symlink")
    raw.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(raw).free
    capacity = api_result.get("disk_capacity_gb")
    quota_verified = (api_result.get("workspace_volume_mount_verified") is True
                      and isinstance(capacity, (float, int)) and not isinstance(capacity, bool)
                      and math.isfinite(capacity) and capacity > 0)
    if not quota_verified:
        capacity = declared_volume_gb
        if (not isinstance(capacity, (float, int)) or isinstance(capacity, bool)
            or not math.isfinite(capacity) or capacity <= 0):
            raise BootstrapError("configured_workspace_volume_quota_unknown")
    if capacity * 1000 ** 3 < MIN_FREE_BYTES:
        raise BootstrapError("allocated_volume_quota_below_95_gib_requirement")
    job_module = report.job_module
    inventory_path = Path(PRIVATE_ROOT) / "transport_inventory.json"
    files = None
    if inventory_path.is_symlink():
        raise BootstrapError("cached_transport_inventory_symlink")
    if inventory_path.exists():
        check_regular_file(inventory_path)
        if inventory_path.stat().st_size > 4 * 1024 ** 2:
            raise BootstrapError("cached_transport_inventory_size_invalid")
        if hashlib.sha256(inventory_path.read_bytes()).hexdigest() != job_module.INVENTORY_SHA256:
            raise BootstrapError("cached_transport_inventory_hash_mismatch")
        files = job_module.load_inventory(inventory_path)
    requirements = job_module.raw_disk_requirements(raw, files)
    required_free = requirements["headroom_bytes"] if inventory_pending and files is None else requirements["required_free_bytes"]
    if free < required_free:
        raise BootstrapError("insufficient_free_disk_for_remaining_raw_and_reserve")
    report.data["disk_preflight"] = {"reported_free_bytes": free, "api_allocated_quota_verified": quota_verified,
                                     "workspace_df_is_shared_storage": True,
                                     "cached_transport_inventory_verified": files is not None,
                                     "complete_remaining_space_budget_verified": not inventory_pending or files is not None,
                                     **requirements}
    report.data["disk_preflight"]["allocated_capacity_gb"] = capacity
    report.data["disk_preflight"]["capacity_source"] = "runpod_api" if quota_verified else "user_reported_for_current_pod"
    report.stage("disk", "passed" if not inventory_pending or files is not None else "inventory_budget_pending",
                 allocated_quota_verified=quota_verified)


def restore_transport_inventory(s3, credentials, job_module, private):
    """Restore only authenticated transport metadata; never derive training permission."""
    target = Path(private) / "transport_inventory.json"
    if target.is_symlink():
        raise BootstrapError("cached_transport_inventory_symlink")
    if target.exists():
        check_regular_file(target)
        if target.stat().st_size > 4 * 1024 ** 2:
            raise BootstrapError("cached_transport_inventory_size_invalid")
        if hashlib.sha256(target.read_bytes()).hexdigest() != job_module.INVENTORY_SHA256:
            raise BootstrapError("cached_transport_inventory_hash_mismatch")
        job_module.load_inventory(target)
        return target
    # A small pinned archive avoids a cold space budget when raw data survived
    # migration but the private supervisor cache did not. No archive paths are
    # extracted here; only a named regular member is read into memory.
    with tempfile.TemporaryDirectory(prefix="inventory-", dir=private) as temporary:
        archive = Path(temporary) / "archive.tar.gz"
        job_module.download_verified(s3, credentials["R2_BUCKET"], job_module.ARCHIVE_KEY, archive,
                                     job_module.ARCHIVE_SHA, None, job_module.ARCHIVE_BYTES)
        name = "research_runs/Q15-DATA/r2_source_storage_verification.json"
        with tarfile.open(archive, "r:gz") as source:
            candidates = [member for member in source.getmembers() if member.name == name]
            if len(candidates) != 1 or not candidates[0].isfile() or candidates[0].size > 4 * 1024 ** 2:
                raise BootstrapError("authenticated_transport_inventory_member_invalid")
            stream = source.extractfile(candidates[0])
            if stream is None:
                raise BootstrapError("authenticated_transport_inventory_member_missing")
            with stream:
                body = stream.read(4 * 1024 ** 2 + 1)
        if hashlib.sha256(body).hexdigest() != job_module.INVENTORY_SHA256:
            raise BootstrapError("authenticated_transport_inventory_hash_mismatch")
        candidate = Path(temporary) / "inventory.json"
        atomic_private_bytes(candidate, body)
        job_module.load_inventory(candidate)
        atomic_private_bytes(target, body)
    return target


def verify_r2(s3, credentials, job_module, prefix):
    bucket = credentials["R2_BUCKET"]
    s3.list_objects_v2(Bucket=bucket, Prefix="q15/", MaxKeys=1)
    head = s3.head_object(Bucket=bucket, Key=job_module.ARCHIVE_KEY)
    if head.get("ContentLength") != job_module.ARCHIVE_BYTES:
        raise BootstrapError("provenance_archive_size_mismatch")
    probe_key = prefix + "/preflight-probe.bin"
    try:
        job_module.verified_backup(s3, bucket, probe_key, os.urandom(64))
    except Exception:
        # Best-effort removal does not hide the original failed readback code.
        try:
            s3.delete_object(Bucket=bucket, Key=probe_key)
        except Exception:
            pass
        raise
    s3.delete_object(Bucket=bucket, Key=probe_key)
    try:
        s3.head_object(Bucket=bucket, Key=probe_key)
    except Exception as exc:
        response = getattr(exc, "response", {})
        if not isinstance(response, dict):
            raise BootstrapError("preflight_delete_not_confirmed") from None
        code = response.get("Error", {}).get("Code")
        status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code not in ("404", "NoSuchKey", "NotFound") and status != 404:
            raise BootstrapError("preflight_delete_not_confirmed") from None
    else:
        raise BootstrapError("preflight_delete_not_confirmed")


def worker_snapshot(private):
    pointer = read_private_json(private / "active_job.json")
    if not pointer:
        return {}
    job_id = pointer.get("job_id")
    if not isinstance(job_id, str) or not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}", job_id):
        raise BootstrapError("active_job_pointer_invalid")
    job = private / "jobs" / job_id
    if job.is_symlink() or job.parent.is_symlink():
        raise BootstrapError("private_job_directory_symlink")
    status = read_private_json(job / "job_status.json")
    snapshot = {"job_id": job_id}
    pod_id = pointer.get("pod_id")
    if isinstance(pod_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", pod_id):
        snapshot["pod_id"] = pod_id
    pid = pointer.get("pid")
    if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0:
        snapshot["pid"] = pid
    for key in ("status", "error_code", "error_stage"):
        value = status.get(key)
        if isinstance(value, str) and re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,159}", value):
            snapshot[key] = value
    for key in ("verified_size_bytes", "full_readback_files", "expected_raw_files", "expected_raw_bytes"):
        value = status.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            snapshot[key] = value
    snapshot["fits_started"] = 0
    snapshot["pod_identity_verified"] = status.get("pod_identity_verified") is True
    return snapshot


def existing_worker(private, job_module):
    try:
        check = job_module.acquire_job_lock(private / "active.lock")
    except Exception as exc:
        if safe_error_code(exc, job_module) != "another_cloud_supervisor_is_active":
            raise
        snapshot = worker_snapshot(private)
        if snapshot.get("pod_id") != job_module.current_pod_id():
            raise BootstrapError("shared_volume_worker_belongs_to_different_pod")
        return {"status": "EXISTING_WORKER_ACTIVE", "worker": snapshot,
                **({"pid": snapshot["pid"]} if snapshot.get("pid") else {})}
    check.close()
    # A just-detached child can exist before it takes active.lock. Check only the
    # recorded worker command, so a recycled PID never blocks an unrelated job.
    snapshot = worker_snapshot(private)
    if snapshot.get("pid"):
        command = Path("/proc") / str(snapshot["pid"]) / "cmdline"
        try:
            raw_command = command.read_bytes()
        except OSError:
            raw_command = b""
        worker_path = str(private / "jobs" / snapshot["job_id"] / "q15_cloud_job.py").encode()
        if worker_path in raw_command.split(b"\0"):
            if snapshot.get("pod_id") != job_module.current_pod_id():
                raise BootstrapError("shared_volume_worker_belongs_to_different_pod")
            return {"status": "EXISTING_WORKER_STARTUP_PENDING", "worker": snapshot, "pid": snapshot["pid"]}
    return None


def show_status(private):
    previous = read_private_json(private / "last_bootstrap_report.json")
    # Reports are generated locally and contain safe fields, but status output
    # intentionally selects fields rather than printing arbitrary cached JSON.
    result = {"status": "STATUS_ONLY", "fits_started": 0, "worker": worker_snapshot(private)}
    result["bootstrap"] = {key: previous[key] for key in ("status", "stage", "error_code", "pid", "job_id", "updated_at_utc")
                           if key in previous and isinstance(previous[key], (str, int))}
    print(json.dumps(result, indent=2), flush=True)
    return 0


def detach_worker(source, config_path, job_dir):
    destination = job_dir / "q15_cloud_job.py"
    atomic_private_bytes(destination, source.read_bytes(), 0o700)
    child_env = dict(os.environ)
    for name in REQUIRED:
        child_env.pop(name, None)
    log_path = job_dir / "supervisor.log"
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "ab", buffering=0) as output:
        return subprocess.Popen([sys.executable, str(destination), "--config", str(config_path),
                                 "--job-dir", str(job_dir)], stdin=subprocess.DEVNULL,
                                stdout=output, stderr=output, start_new_session=True,
                                close_fds=True, env=child_env)


def child_failure_code(job_dir):
    # The worker can fail before it creates job_status.json. Read only a small
    # private log tail, parse JSON, and select an internal safe error code; never
    # print the log text, exception message, server body, or request URL.
    log_path = Path(job_dir) / "supervisor.log"
    if log_path.is_symlink() or not log_path.exists():
        return None
    check_regular_file(log_path)
    with log_path.open("rb") as stream:
        stream.seek(max(0, log_path.stat().st_size - 65536))
        lines = stream.read(65536).splitlines()
    for line in reversed(lines[-64:]):
        try:
            entry = json.loads(line)
        except (ValueError, UnicodeError):
            continue
        if not isinstance(entry, dict):
            continue
        if (entry.get("status") not in ("bootstrap_or_config_failed", "failed_without_training")
            and entry.get("event") not in ("job_failed_without_training", "stop_not_confirmed_manual_attention_required")):
            continue
        code = entry.get("error_code")
        if isinstance(code, str) and SAFE_CODE_PATTERN.fullmatch(code):
            return code
    return None


def wait_for_startup(child, job_dir, timeout, job_module):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = read_private_json(job_dir / "job_status.json")
        if status.get("status") in ("failed_without_training", "bootstrap_or_config_failed"):
            code = status.get("error_code")
            if isinstance(code, str) and SAFE_CODE_PATTERN.fullmatch(code):
                raise BootstrapError(code)
            raise BootstrapError("detached_worker_failed_before_verified_startup")
        if child.poll() is not None:
            code = child_failure_code(job_dir)
            raise BootstrapError(code or "detached_worker_exited_before_verified_startup")
        if status.get("pod_identity_verified") is True:
            return True
        time.sleep(0.5)
    return False


def run(args, report):
    private = safe_private_root(PRIVATE_ROOT)
    if args.status:
        return show_status(private)
    with launch_lock(private / "launch.lock"):
        report.path = private / "last_bootstrap_report.json"
        report.stage("scripts")
        launch = Path(__file__).resolve().parent
        source = launch / "q15_cloud_job.py"
        job_module = load_job_module(source)
        report.job_module = job_module
        report.stage("current_pod_identity")
        pod_id = job_module.current_pod_id()
        active = existing_worker(private, job_module)
        if active:
            report.data.update({"status": "EXISTING_WORKER_ACTIVE", "worker": active})
            report.stage("existing_worker", "reused")
            print(json.dumps(active, indent=2), flush=True)
            return 0
        report.stage("persistent_runtime")
        install_runtime(private, Path(__file__), source)
        print("Q15 raw download supervisor: fits_started = 0.", flush=True)
        print("Downloads and verifies data, backs up evidence, then stops the current Pod.", flush=True)
        print("Training stays blocked until raw audits and a committed preprocessing freeze are complete.", flush=True)
        config_path = private / "credentials.json"
        previous = read_private_json(config_path, secret=True)
        credentials = {name: previous[name] for name in REQUIRED if isinstance(previous.get(name), str)}
        credentials["_validation"] = previous.get("_validation", {}) if isinstance(previous.get("_validation"), dict) else {}
        credentials.update({"pod_id": pod_id, "raw_dir": str(RAW_ROOT)})
        if args.volume_gb is not None:
            credentials.update({"declared_volume_gb": args.volume_gb, "declared_volume_pod_id": pod_id})
        elif previous.get("declared_volume_pod_id") == pod_id:
            saved_capacity = previous.get("declared_volume_gb")
            if isinstance(saved_capacity, (int, float)) and not isinstance(saved_capacity, bool) and math.isfinite(saved_capacity) and saved_capacity > 0:
                credentials.update({"declared_volume_gb": saved_capacity, "declared_volume_pod_id": pod_id})
        report.stage("credential_cache")
        for name in args.reset_credential:
            credentials.pop(name, None)
            credentials["_validation"].pop("runpod" if name == "RUNPOD_API_KEY" else "r2", None)
        # Persist each successful field before dependency or API checks. A later
        # failure never forces retyping the four R2 values on the next attempt.
        for name in REQUIRED:
            if name in args.reset_credential:
                value_source = "hidden_prompt"
            elif credentials.get(name):
                validation = credentials["_validation"].get("runpod" if name == "RUNPOD_API_KEY" else "r2", {})
                was_verified = isinstance(validation, dict) and validation.get("verified") is True
                if name == "RUNPOD_API_KEY":
                    was_verified = was_verified and validation.get("pod_id") == pod_id
                value_source = "verified_private_cache" if was_verified else "private_cache_not_yet_verified"
            elif os.environ.get(name):
                value_source = "environment_not_yet_verified"
            else:
                value_source = "hidden_prompt"
            credentials[name] = read_hidden(name, credentials, args.non_interactive,
                                            force_prompt=name in args.reset_credential)
            atomic_private_json(config_path, credentials)
            report.data.setdefault("credential_sources", {})[name] = value_source
            report.save()
        validate_credential_shape(credentials)
        report.stage("credential_cache", "saved_private")
        report.stage("runpod_api")
        api_result = verify_runpod(job_module, credentials, config_path, report, args.non_interactive)
        report.stage("runpod_api", "passed")
        report.stage("disk")
        verify_disk(RAW_ROOT, api_result, report, credentials.get("declared_volume_gb"), inventory_pending=True)
        report.stage("s3_dependency_and_client")
        s3 = make_s3_client(credentials)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
        prefix = "q15/cloud-jobs/" + stamp
        report.stage("r2_list_write_readback_delete")
        verify_r2(s3, credentials, job_module, prefix)
        credentials["_validation"]["r2"] = {"verified": True, "at_utc": now()}
        atomic_private_json(config_path, credentials)
        report.stage("r2_list_write_readback_delete", "passed")
        report.stage("authenticated_transport_inventory")
        restore_transport_inventory(s3, credentials, job_module, private)
        report.stage("authenticated_transport_inventory", "passed")
        report.stage("disk_remaining_space")
        verify_disk(RAW_ROOT, api_result, report, credentials.get("declared_volume_gb"))
        if args.check_only:
            report.data["status"] = "PREFLIGHT_PASSED_WORKER_NOT_STARTED"
            report.stage("check_only", "complete")
            print(json.dumps({"status": report.data["status"], "fits_started": 0,
                              "next_start_command": str(private / "start.sh")}), flush=True)
            return 0
        report.stage("detached_worker")
        job_dir = private / "jobs" / stamp
        if job_dir.parent.is_symlink():
            raise BootstrapError("private_jobs_directory_symlink")
        job_dir.mkdir(parents=True, mode=0o700)
        os.chmod(job_dir, 0o700)
        child = detach_worker(source, config_path, job_dir)
        atomic_private_json(private / "active_job.json", {"job_id": stamp, "pid": child.pid, "pod_id": pod_id})
        report.data.update({"pid": child.pid, "job_id": stamp})
        report.stage("verified_worker_startup")
        if not wait_for_startup(child, job_dir, args.startup_timeout, job_module):
            report.data["status"] = "LAUNCH_PENDING_NOT_CONFIRMED"
            report.stage("verified_worker_startup", "pending")
            print(json.dumps({"status": report.data["status"], "pid": child.pid, "fits_started": 0,
                              "status_command": str(private / "start.sh") + " --status"}), flush=True)
            return 2
        receipt = {"status": "detached_download_supervisor_started_training_not_started", "pid": child.pid,
                   "pod_id": pod_id, "job_id": stamp, "job_script_sha256": EXPECTED_JOB_SHA256,
                   "fits_started": 0, "R2_status_prefix": prefix,
                   "local_status": str(job_dir / "job_status.json"), "local_log": str(job_dir / "supervisor.log"),
                   "scientific_contract_frozen": False,
                   "automatic_stop_policy": "only_after_final_status_and_logs_full_r2_readback"}
        atomic_private_json(job_dir / "launch_receipt.json", receipt)
        report.data["status"] = receipt["status"]
        report.stage("verified_worker_startup", "passed")
        print(json.dumps(receipt, indent=2), flush=True)
        print("Verified detached startup succeeded. You may close the local browser/computer.", flush=True)
        print("A stop API response confirms acceptance, not physical power-off.", flush=True)
        return 0


def cli(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="verify API/R2/disk only; do not detach or stop")
    parser.add_argument("--non-interactive", action="store_true", help="use private cache/environment without reading stdin")
    parser.add_argument("--interactive", action="store_true", help="allow hidden prompts, overriding the saved start command's non-interactive default")
    parser.add_argument("--reset-credential", action="append", choices=REQUIRED, default=[], metavar="NAME",
                        help="replace only this field using hidden input, never a value in argv")
    parser.add_argument("--status", action="store_true", help="show safe last bootstrap and worker status")
    parser.add_argument("--startup-timeout", type=float, default=60, help="seconds to wait for verified detached startup")
    parser.add_argument("--volume-gb", type=float, help="actual purchased workspace quota in GB, used only if the API does not expose it")
    args = parser.parse_args(argv)
    report = StageReport()
    try:
        if args.interactive:
            args.non_interactive = False
        if not 1 <= args.startup_timeout <= 600:
            raise BootstrapError("startup_timeout_must_be_1_to_600_seconds")
        if args.volume_gb is not None and (not math.isfinite(args.volume_gb) or args.volume_gb <= 0):
            raise BootstrapError("declared_volume_gb_must_be_positive_finite")
        if args.non_interactive and args.reset_credential:
            raise BootstrapError("credential_reset_requires_interactive_hidden_input")
        return run(args, report)
    except (Exception, KeyboardInterrupt) as exc:
        code = safe_error_code(exc, report.job_module)
        status = "WORKER_STARTUP_NOT_CONFIRMED" if report.data.get("pid") else "NOT_STARTED"
        report.data.update({"status": status, "error_code": code})
        report.data["stages"].append({"stage": report.data["stage"], "status": "failed", "error_code": code, "at_utc": now()})
        try:
            report.save()
        except Exception:
            pass
        output = {"status": status, "stage": report.data["stage"], "error_code": code, "fits_started": 0}
        if report.data.get("pid"):
            output["pid"] = report.data["pid"]
        if code == "configured_workspace_volume_quota_unknown":
            output["next_step"] = "Read the purchased Volume Disk GB from RunPod and rerun with --volume-gb N. Cached R2 values are retained."
        elif code == "shared_volume_worker_belongs_to_different_pod":
            output["next_step"] = "The shared volume has a supervisor for another Pod. Verify and stop that old worker/Pod before launching here."
        elif code in ("runpod_api_http_401", "runpod_api_http_403"):
            output["next_step"] = "Rerun with --interactive --reset-credential RUNPOD_API_KEY. Cached R2 values are retained."
        print(json.dumps(output), flush=True)
        return 2


def main(argv=None):
    return cli(argv)


if __name__ == "__main__":
    sys.exit(cli())
