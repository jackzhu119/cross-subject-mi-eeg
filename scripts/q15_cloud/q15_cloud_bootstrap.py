#!/usr/bin/env python3
"""Launch a private detached RunPod R2 download and fail-closed supervisor.
Run this in the RunPod Jupyter Terminal (interactive TTY), never a notebook cell.
Secret values are read with getpass and are never included in argv or job logs.
"""
from __future__ import annotations
import getpass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import time
import subprocess
import sys
from datetime import datetime, timezone
import urllib.parse
import uuid
import warnings

EXPECTED_JOB_SHA256 = "528047be63a1040355a9cbc679d991fd329e1aa764e89b34bd76c3affe80df96"
EXPECTED_POD_ID = "i9fw4mnl9zh558"
REQUIRED = ("R2_BUCKET", "R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "RUNPOD_API_KEY")

class BootstrapError(RuntimeError):
    pass


def read_hidden(name, previous):
    value = os.environ.get(name) or previous.get(name)
    if value:
        return str(value).strip()
    if not sys.stdin.isatty():
        raise BootstrapError("interactive_terminal_required_no_plaintext_fallback")
    for _ in range(3):
        # getpass writes the variable name only; it suppresses secret input echo.
        try:
            with warnings.catch_warnings():
                # getpass normally falls back to echoed input if terminal echo
                # cannot be disabled. Convert that warning into a hard failure.
                warnings.simplefilter("error", getpass.GetPassWarning)
                value = getpass.getpass(name + " (hidden input): ").strip()
        except getpass.GetPassWarning:
            raise BootstrapError("hidden_terminal_input_unavailable_no_plaintext_fallback") from None
        if value:
            return value
    raise BootstrapError("required_credential_not_provided:" + name)


def main():
    if not sys.stdin.isatty():
        raise BootstrapError("run_in_jupyter_terminal_not_notebook_or_pipe")
    launch = Path(__file__).resolve().parent
    source = launch / "q15_cloud_job.py"
    if not source.is_file() or source.is_symlink():
        raise BootstrapError("companion_job_script_missing_or_symlink")
    if hashlib.sha256(source.read_bytes()).hexdigest() != EXPECTED_JOB_SHA256:
        raise BootstrapError("companion_job_script_hash_mismatch")
    spec = importlib.util.spec_from_file_location("q15_launch_job", source)
    job_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(job_module)
    private = Path("/workspace/.q15-cloud")
    if any((parent / ".git").exists() for parent in (private, *private.parents)):
        raise BootstrapError("private_credential_directory_inside_git_worktree")
    if private.is_symlink():
        raise BootstrapError("private_credential_directory_symlink")
    private.mkdir(parents=True, exist_ok=True)
    os.chmod(private, 0o700)
    active_check = job_module.acquire_job_lock(private / "active.lock")
    active_check.close()
    config_path = private / "credentials.json"
    previous = {}
    if config_path.exists():
        if config_path.is_symlink() or config_path.stat().st_mode & 0o077:
            raise BootstrapError("existing_credential_file_permissions_unsafe")
        previous = json.loads(config_path.read_text())
    print("Q15 raw download supervisor: fits_started = 0.", flush=True)
    print("This release downloads and verifies data, backs up evidence, then stops the Pod.", flush=True)
    print("Training remains blocked until real raw metadata audits and a committed preprocessing freeze are complete.", flush=True)
    credentials = {name: read_hidden(name, previous) for name in REQUIRED}
    endpoint = urllib.parse.urlsplit(credentials["R2_ENDPOINT"])
    if (endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or endpoint.password
        or endpoint.query or endpoint.fragment or endpoint.path not in ("", "/")
        or not endpoint.hostname.endswith(".r2.cloudflarestorage.com")):
        raise BootstrapError("expected_https_cloudflare_r2_account_endpoint")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", credentials["R2_BUCKET"]):
        raise BootstrapError("bucket_name_invalid")
    pod_id = os.environ.get("RUNPOD_POD_ID") or previous.get("pod_id") or EXPECTED_POD_ID
    if pod_id != EXPECTED_POD_ID:
        raise BootstrapError("pod_id_does_not_match_current_user_pod")
    credentials.update({"pod_id": pod_id, "raw_dir": "/workspace/q15-data/raw"})
    # Install only on the RunPod where this script is invoked. Suppress pip output,
    # which can otherwise include credential-bearing package-index URLs.
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
        import boto3
        from botocore.config import Config
    # Validate the API key and Pod identity without stopping at startup.
    job_module.runpod_request(credentials["RUNPOD_API_KEY"], pod_id)
    print("RunPod API key and current Pod identity verified.", flush=True)
    raw_dir = Path(credentials["raw_dir"])
    raw_dir.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(raw_dir).free < 95 * 1024 ** 3:
        raise BootstrapError("requires_at_least_95_GiB_free_disk")
    print("Shared-filesystem free-space precheck passed; purchased Volume Disk quota must still be sufficient.", flush=True)
    s3 = boto3.client("s3", endpoint_url=credentials["R2_ENDPOINT"],
                      aws_access_key_id=credentials["R2_ACCESS_KEY_ID"],
                      aws_secret_access_key=credentials["R2_SECRET_ACCESS_KEY"], region_name="auto",
                      config=Config(s3={"addressing_style": "path"}, connect_timeout=30, read_timeout=60,
                                    retries={"max_attempts": 3, "mode": "standard"},
                                    request_checksum_calculation="when_required",
                                    response_checksum_validation="when_required"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
    prefix = "q15/cloud-jobs/" + stamp
    s3.list_objects_v2(Bucket=credentials["R2_BUCKET"], Prefix="q15/", MaxKeys=1)
    head = s3.head_object(Bucket=credentials["R2_BUCKET"], Key=job_module.ARCHIVE_KEY)
    if head.get("ContentLength") != job_module.ARCHIVE_BYTES:
        raise BootstrapError("provenance_archive_size_mismatch")
    probe_key = prefix + "/preflight-probe.bin"
    probe = os.urandom(64)
    job_module.verified_backup(s3, credentials["R2_BUCKET"], probe_key, probe)
    s3.delete_object(Bucket=credentials["R2_BUCKET"], Key=probe_key)
    try:
        s3.head_object(Bucket=credentials["R2_BUCKET"], Key=probe_key)
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        status = getattr(exc, "response", {}).get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code not in ("404", "NoSuchKey", "NotFound") and status != 404:
            raise BootstrapError("preflight_delete_not_confirmed") from None
    else:
        raise BootstrapError("preflight_delete_not_confirmed")
    print("R2 list/write/full-readback/delete preflight passed; credential values were not printed.", flush=True)
    # Persist a 0600 file; its path, not secret values, is placed in argv.
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(config_path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(credentials, f)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.chmod(config_path, 0o600)
    job_dir = private / "jobs" / stamp
    job_dir.mkdir(parents=True, mode=0o700)
    destination = job_dir / "q15_cloud_job.py"
    shutil.copyfile(source, destination)
    os.chmod(destination, 0o700)
    # Do not inherit secret environment variables into the detached subprocess.
    child_env = dict(os.environ)
    for name in REQUIRED:
        child_env.pop(name, None)
    with (job_dir / "supervisor.log").open("ab", buffering=0) as output:
        child = subprocess.Popen([sys.executable, str(destination), "--config", str(config_path),
                                  "--job-dir", str(job_dir)], stdin=subprocess.DEVNULL,
                                 stdout=output, stderr=output, start_new_session=True,
                                 close_fds=True, env=child_env)
    status_path = job_dir / "job_status.json"
    deadline = time.monotonic() + 20
    started = False
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise BootstrapError("detached_worker_exited_before_verified_startup_check_private_log")
        if status_path.exists():
            startup = json.loads(status_path.read_text())
            if startup.get("status") in ("failed_without_training", "bootstrap_or_config_failed"):
                raise BootstrapError("detached_worker_failed_check_private_log")
            if startup.get("pod_identity_verified") is True:
                started = True
                break
        time.sleep(0.5)
    if not started:
        print(json.dumps({"status": "LAUNCH_PENDING_NOT_CONFIRMED", "pid": child.pid,
                          "local_log": str(job_dir / "supervisor.log"), "fits_started": 0}), flush=True)
        print("Worker launch is pending; inspect the private log before closing the computer.", flush=True)
        return 2
    launch_receipt = {"status": "detached_download_supervisor_started_training_not_started",
                      "pid": child.pid, "pod_id": pod_id, "job_id": stamp,
                      "job_script_sha256": EXPECTED_JOB_SHA256, "fits_started": 0,
                      "R2_status_prefix": prefix,
                      "local_status": str(job_dir / "job_status.json"),
                      "local_log": str(job_dir / "supervisor.log"),
                      "scientific_contract_frozen": False,
                      "automatic_stop_policy": "only_after_final_status_and_logs_full_r2_readback"}
    job_module.atomic_json(job_dir / "launch_receipt.json", launch_receipt)
    print(json.dumps(launch_receipt, indent=2), flush=True)
    print("Only after the detached supervisor STARTED receipt above may you close the local browser/computer.", flush=True)
    print("If final backup or RunPod stop fails, automatic shutdown is not confirmed; inspect the Pod.", flush=True)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        code = str(exc) if isinstance(exc, BootstrapError) else type(exc).__name__
        print(json.dumps({"status": "NOT_STARTED", "error_code": code, "fits_started": 0}), flush=True)
        sys.exit(2)
