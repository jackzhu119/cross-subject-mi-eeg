#!/usr/bin/env python3
"""Cloud-only, detached Q15 raw transport; scientific gates remain fail-closed.

No model fit is implemented by this release. A completed transport is not a
scientific raw metadata audit or a frozen preprocessing contract.
"""
from __future__ import annotations

import argparse
import hashlib
import fcntl
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone
import urllib.error
import urllib.request
import uuid

REPO_COMMIT = "adb2d406b4300e2c8e4d5112969291c0331f3ed5"
ARCHIVE_KEY = "q15/provenance/20261001T093410835515Z-614d381fb70141d7b91a85ae4eb907a8/archive.tar.gz"
ARCHIVE_SHA = "332b878514894f7e6543c652e4138be13d8125ac8da20099ae9ca8641684fa0b"
ARCHIVE_BYTES = 4708471
INVENTORY_SHA256 = "6dc6728e3d8b84c405249845b3dd346d75ba74218e603d5ad8584b0ded93b62a"
RAW_BYTES = 75551469122
RAW_FILES = 160
RUNPOD_USER_AGENT = "q15-cloud-transport/20261003"
SAFETY = {"fits_started": 0, "source_fits": 0, "target_fits": 0,
          "raw_audit_completed": False, "scientific_raw_metadata_audit_complete": False,
          "preprocessing_contract_frozen": False, "source_training_authorized": False,
          "external_prediction_authorized": False, "preprocessing_applied": False,
          "predictions_computed": False, "model_predictions_computed": False,
          "performance_metrics_computed": False}

class IntegrityError(RuntimeError):
    def __init__(self, code):
        self.safe_code = code if isinstance(code, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_:.-]{0,159}", code) else "integrity_check_failed"
        super().__init__(self.safe_code)

class GateBlocked(RuntimeError):
    pass


def safe_error_code(exc):
    """Return an internal code or whitelisted status, never exception text."""
    if isinstance(exc, IntegrityError):
        return exc.safe_code
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = response.get("Error", {}).get("Code") if isinstance(response.get("Error"), dict) else None
        if code in {"AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch", "NoSuchBucket",
                    "NoSuchKey", "RequestTimeTooSkewed", "ExpiredToken", "InvalidToken",
                    "AuthorizationHeaderMalformed", "NotFound"}:
            return "s3_" + code
        meta = response.get("ResponseMetadata", {})
        status = meta.get("HTTPStatusCode") if isinstance(meta, dict) else None
        if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599:
            return "remote_http_" + str(status)
    if isinstance(exc, urllib.error.HTTPError):
        return "http_" + str(exc.code)
    name = type(exc).__name__
    return name if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name) else "unexpected_error"


def acquire_job_lock(lock_path):
    """Hold the returned file for the worker's lifetime; duplicate cannot stop Pod."""
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    stream = os.fdopen(fd, "a+")
    try:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        stream.close()
        raise IntegrityError("another_cloud_supervisor_is_active") from None
    return stream


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".new")
    with part.open("wb") as f:
        f.write(encoded(value))
        f.flush()
        os.fsync(f.fileno())
    os.replace(part, path)


def safe_relative(name):
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise IntegrityError("unsafe_relative_path")
    p = PurePosixPath(name)
    if p.is_absolute() or any(x in ("", ".", "..") for x in p.parts):
        raise IntegrityError("unsafe_relative_path")
    return p


def safe_extract(archive, dest, max_bytes=128 * 1024 * 1024):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        total = 0
        targets = set()
        for m in members:
            rel = safe_relative(m.name)
            target = root.joinpath(*rel.parts)
            if not target.resolve().is_relative_to(root) or str(rel) in targets:
                raise IntegrityError("unsafe_or_duplicate_archive_path")
            targets.add(str(rel))
            if not (m.isfile() or m.isdir()) or m.size < 0:
                raise IntegrityError("unsupported_archive_member")
            total += m.size
            if total > max_bytes:
                raise IntegrityError("archive_uncompressed_limit")
        # Validate every member before writing any file. Never use extractall.
        for m in members:
            target = root.joinpath(*safe_relative(m.name).parts)
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and not target.is_file():
                raise IntegrityError("archive_target_not_regular_file")
            source = tar.extractfile(m)
            if source is None:
                raise IntegrityError("archive_file_body_missing")
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
    return dest


def file_hashes(path):
    sha, md5, count = hashlib.sha256(), hashlib.md5(), 0
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            sha.update(block)
            md5.update(block)
            count += len(block)
    return sha.hexdigest(), md5.hexdigest(), count


def raw_disk_requirements(raw_dir, files=None):
    """Budget allocation; cached bytes still need full integrity verification."""
    root = Path(raw_dir).resolve()
    credited = 0
    if files is not None:
        for item in files:
            target = root / item["dataset"] / Path(*safe_relative(item["file_id"]).parts)
            if not target.resolve().is_relative_to(root):
                raise IntegrityError("raw_destination_outside_root")
            occupied = 0
            for path in (target, target.with_name(target.name + ".part")):
                if path.is_symlink():
                    raise IntegrityError("raw_disk_preflight_symlink")
                if path.is_file():
                    info = path.stat()
                    if info.st_nlink == 1:
                        occupied += min(info.st_size, getattr(info, "st_blocks", 0) * 512)
            credited += min(item["size_bytes"], occupied)
    return {"expected_raw_bytes": RAW_BYTES, "credited_existing_allocation_bytes": credited,
            "remaining_allocation_bytes": max(0, RAW_BYTES - credited),
            "headroom_bytes": 20 * 1024 ** 3,
            "required_free_bytes": max(0, RAW_BYTES - credited) + 20 * 1024 ** 3,
            "cached_content_integrity_verified_by_space_check": False}


def download_verified(s3, bucket, key, dest, expected_sha256, expected_md5,
                      expected_size, retries=3, on_progress=None):
    dest = Path(dest)
    if re.fullmatch(r"[0-9a-f]{64}", str(expected_sha256)) is None:
        raise IntegrityError("expected_sha256_invalid")
    if expected_md5 is not None and re.fullmatch(r"[0-9a-f]{32}", str(expected_md5)) is None:
        raise IntegrityError("expected_md5_invalid")
    if not isinstance(expected_size, int) or expected_size <= 0:
        raise IntegrityError("expected_size_invalid")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink():
        raise IntegrityError("download_target_symlink")
    if dest.exists():
        sha, md5, size = file_hashes(dest)
        if sha == expected_sha256 and size == expected_size and (not expected_md5 or md5 == expected_md5):
            return {"verified": True, "sha256": sha, "md5": md5, "size_bytes": size, "reused": True}
        dest.unlink()
    part = dest.with_name(dest.name + ".part")
    marker = dest.with_name(dest.name + ".part.json")
    if part.is_symlink() or marker.is_symlink():
        raise IntegrityError("download_partial_symlink")
    identity = {"key": key, "sha256": expected_sha256, "md5": expected_md5, "size_bytes": expected_size}
    last_code = "download_failed"
    for attempt in range(retries):
        body = None
        try:
            head = s3.head_object(Bucket=bucket, Key=key)
            if head.get("ContentLength") != expected_size:
                raise IntegrityError("remote_size_mismatch")
            # Range resumes are bound to the same remote ETag and expected full hashes.
            bound = {**identity, "etag": head.get("ETag")}
            previous = json.loads(marker.read_text()) if marker.exists() else None
            if previous != bound or (part.exists() and part.stat().st_size > expected_size):
                part.unlink(missing_ok=True)
                marker.unlink(missing_ok=True)
            atomic_json(marker, bound)
            offset = part.stat().st_size if part.exists() else 0
            sha, md5 = hashlib.sha256(), hashlib.md5()
            if offset:
                with part.open("rb") as f:
                    for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
                        sha.update(block)
                        md5.update(block)
            if offset < expected_size:
                args = {"Bucket": bucket, "Key": key}
                if head.get("ETag"):
                    args["IfMatch"] = head["ETag"]
                if offset:
                    args["Range"] = f"bytes={offset}-"
                response = s3.get_object(**args)
                if offset and not str(response.get("ContentRange", "")).startswith(f"bytes {offset}-"):
                    raise IntegrityError("range_response_mismatch")
                body = response["Body"]
                with part.open("ab") as f:
                    while True:
                        block = body.read(8 * 1024 * 1024)
                        if not block:
                            break
                        offset += len(block)
                        if offset > expected_size:
                            raise IntegrityError("remote_body_overflow")
                        sha.update(block)
                        md5.update(block)
                        f.write(block)
                        if on_progress:
                            on_progress(offset, expected_size)
                    f.flush()
                    os.fsync(f.fileno())
            if offset != expected_size:
                raise IntegrityError("remote_body_truncated")
            if sha.hexdigest() != expected_sha256 or (expected_md5 and md5.hexdigest() != expected_md5):
                part.unlink(missing_ok=True)
                marker.unlink(missing_ok=True)
                raise IntegrityError("raw_content_hash_mismatch")
            # Verify actual persisted bytes, independently of the network-stream hash.
            disk_sha, disk_md5, disk_size = file_hashes(part)
            if disk_sha != expected_sha256 or disk_size != expected_size or (expected_md5 and disk_md5 != expected_md5):
                part.unlink(missing_ok=True)
                marker.unlink(missing_ok=True)
                raise IntegrityError("persisted_raw_file_hash_mismatch")
            os.replace(part, dest)
            marker.unlink(missing_ok=True)
            return {"verified": True, "sha256": sha.hexdigest(), "md5": md5.hexdigest(),
                    "size_bytes": offset, "reused": False}
        except OSError as exc:
            # Real allocation errors override misleading shared df capacity.
            if exc.errno == 28:
                raise IntegrityError("actual_volume_quota_or_disk_full") from None
            last_code = safe_error_code(exc)
        except Exception as exc:
            last_code = safe_error_code(exc)
        finally:
            if body is not None:
                body.close()
        if attempt + 1 < retries:
            time.sleep(min(2 ** attempt, 8))
    raise IntegrityError(last_code)


def verified_backup(s3, bucket, key, body):
    expected = hashlib.sha256(body).hexdigest()
    last_code = "backup_failed"
    for attempt in range(3):
        stream = None
        try:
            s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/octet-stream",
                          Metadata={"sha256": expected})
            response = s3.get_object(Bucket=bucket, Key=key)
            stream = response["Body"]
            digest, size = hashlib.sha256(), 0
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
                size += len(block)
            if size != len(body) or digest.hexdigest() != expected:
                raise IntegrityError("backup_readback_hash_mismatch")
            return {"key": key, "sha256": expected, "size_bytes": size, "full_readback_verified": True}
        except Exception as exc:
            last_code = safe_error_code(exc)
        finally:
            if stream is not None:
                stream.close()
        if attempt < 2:
            time.sleep(2 ** attempt)
    raise IntegrityError(last_code)


def scientific_gate(repo):
    repo = Path(repo)
    auditor = repo / "scripts/q15_metadata_audit.py"
    adapter_unsupported = True
    if auditor.is_file():
        text = auditor.read_text(encoding="utf-8")
        adapter_unsupported = 'adapter != "synthetic_json_v1"' in text and "raw_adapter_unverified" in text
    freeze = repo / "results/Q15-E005/pre_fit_freeze.json"
    receipts = [repo / "results" / q / "metadata_audit_receipt.json" for q in ("Q15-V001", "Q15-V002")]
    blocks = []
    if not auditor.is_file() or adapter_unsupported:
        blocks.append("real_mat_metadata_adapter_unverified")
    if not freeze.is_file():
        blocks.append("committed_pre_fit_freeze_missing")
    if not all(p.is_file() for p in receipts):
        blocks.append("authenticated_real_metadata_audit_receipts_missing")
    blocks.append("BNCI2014_001_18_source_files_not_downloaded_or_audited")
    # This release deliberately has no scientific audit implementation or training executor.
    # Even arbitrary positive JSON flags cannot authorize a source fit.
    blocks.append("this_release_supports_raw_transport_only")
    return {"allowed": False, "status": "blocked_scientific_audit_and_freeze",
            "blocking_reasons": blocks, **SAFETY}


def run_training_if_allowed(gate, runner):
    if gate.get("allowed") is not True:
        raise GateBlocked("scientific_audit_and_freeze_pending")
    # Future release must first implement and verify real metadata and committed freeze.
    return runner()


def validate_pod_id(pod_id):
    if not isinstance(pod_id, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", pod_id) is None:
        raise IntegrityError("runpod_pod_id_invalid")
    return pod_id


def current_pod_id():
    pod_id = os.environ.get("RUNPOD_POD_ID")
    if not pod_id:
        raise IntegrityError("runpod_pod_id_environment_missing")
    return validate_pod_id(pod_id)


def runpod_request(api_key, pod_id, method="GET", action=""):
    pod_id = validate_pod_id(pod_id)
    if (method, action) not in (("GET", ""), ("POST", "/stop")):
        raise IntegrityError("runpod_api_operation_invalid")
    url = f"https://rest.runpod.io/v1/pods/{pod_id}" + action
    if method == "GET":
        url += "?includeNetworkVolume=true"
    req = urllib.request.Request(url, method=method,
                                  headers={"Authorization": "Bearer " + api_key, "Accept": "application/json",
                                           "User-Agent": RUNPOD_USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=40) as response:
            raw = response.read(1024 * 1024)
            status = response.status
    except urllib.error.HTTPError as exc:
        # Classify an edge denial without printing arbitrary response text. An
        # edge 403 must not trigger repeated secret entry as if it were auth.
        edge_denied = False
        if exc.code == 403:
            try:
                body = exc.read(65536).lower()
                headers = exc.headers or {}
                edge_denied = (b"error code: 1010" in body or b'"error_code":1010' in body.replace(b" ", b"")
                               or b"browser_signature_banned" in body
                               or headers.get("cf-mitigated", "").lower() == "challenge")
            except Exception:
                pass
        if edge_denied:
            raise IntegrityError("runpod_api_edge_policy_denied_http_403") from None
        raise IntegrityError(f"runpod_api_http_{exc.code}") from None
    except Exception as exc:
        raise IntegrityError("runpod_api_" + type(exc).__name__) from None
    if not isinstance(status, int) or not 200 <= status <= 299:
        raise IntegrityError("runpod_api_http_" + str(status) if isinstance(status, int) else "runpod_api_status_invalid")
    metadata = {}
    if method == "GET":
        try:
            result = json.loads(raw)
        except ValueError:
            raise IntegrityError("runpod_api_invalid_json") from None
        if not isinstance(result, dict) or result.get("id") != pod_id:
            raise IntegrityError("runpod_api_pod_identity_mismatch")
        if result.get("locked") is True:
            raise IntegrityError("runpod_pod_locked_stop_forbidden")
        # The API response may contain secrets in env. Return only these fields.
        mounted = result.get("volumeMountPath") == "/workspace"
        volume = result.get("networkVolume")
        capacity = volume.get("size") if isinstance(volume, dict) else None
        capacity_source = "networkVolume.size"
        if not isinstance(capacity, (int, float)) or isinstance(capacity, bool) or not math.isfinite(capacity) or capacity <= 0:
            capacity = result.get("volumeInGb")
            capacity_source = "volumeInGb"
        if not mounted or not isinstance(capacity, (int, float)) or isinstance(capacity, bool) or not math.isfinite(capacity) or capacity <= 0:
            capacity, capacity_source = None, "unknown"
        metadata = {"disk_capacity_gb": capacity, "disk_capacity_source": capacity_source,
                    "workspace_volume_mount_verified": mounted, "pod_locked": False,
                    "stop_permission_verified": False}
    return {"http_status": status, "pod_id": pod_id, "action": "stop" if action else "inspect", **metadata}


def finish_job(s3, bucket, prefix, state, log_path, stopper):
    # Stop is conditional on full read-back of every final status/log backup.
    if state.get("fits_started") != 0:
        raise IntegrityError("unexpected_fit_count_in_transport_only_release")
    state = {**state, "updated_at_utc": now(), "shutdown_status": "pending_verified_backup_then_stop"}
    try:
        log = Path(log_path).read_bytes() if Path(log_path).exists() else b""
    except OSError as exc:
        state["local_log_read_error"] = {"error_type": type(exc).__name__, "errno": exc.errno}
        log = encoded({"event": "local_log_unavailable", "error_type": type(exc).__name__, "errno": exc.errno})
    receipts = [verified_backup(s3, bucket, prefix + "/final_job_status.json", encoded(state)),
                verified_backup(s3, bucket, prefix + "/job.log", log)]
    manifest = {"files": receipts, "fits_started": 0, "generated_at_utc": now(),
                "stop_request": "will_be_requested_after_this_manifest_readback",
                "stop_success_not_yet_confirmed": True}
    receipts.append(verified_backup(s3, bucket, prefix + "/final_backup_manifest.json", encoded(manifest)))
    result = stopper()
    # The Pod can disappear immediately after stop. The durable manifest truthfully
    # records intent; only this local response confirms API acceptance (not power-off).
    return {"backup_receipts": receipts, "stop_response": result,
            "shutdown_status": "stop_api_accepted", "physical_shutdown_confirmed": False}


def load_inventory(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    files = data.get("files")
    if not isinstance(files, list) or len(files) != RAW_FILES:
        raise IntegrityError("original_inventory_count_mismatch")
    if sum(x.get("size_bytes", 0) for x in files) != RAW_BYTES:
        raise IntegrityError("original_inventory_bytes_mismatch")
    identities = set()
    counts = {"Cho2017": 0, "Lee2019_MI": 0}
    for item in files:
        dataset = item.get("dataset")
        if dataset not in counts:
            raise IntegrityError("unexpected_dataset")
        safe_relative(item.get("file_id"))
        safe_relative(item.get("r2_object_key"))
        identity = (dataset, item["file_id"])
        if identity in identities:
            raise IntegrityError("duplicate_original_file")
        identities.add(identity)
        counts[dataset] += 1
    if counts != {"Cho2017": 52, "Lee2019_MI": 108}:
        raise IntegrityError("dataset_inventory_count_mismatch")
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--job-dir", type=Path, required=True)
    parser.add_argument("--control-dir", type=Path, help="shared non-secret lock/state root; supplied by the bootstrap")
    args = parser.parse_args()
    control_root = args.control_dir if args.control_dir is not None else args.config.parent
    if any(path.is_symlink() for path in (control_root, *control_root.parents)):
        raise IntegrityError("shared_control_directory_symlink")
    # Acquire outside the backup/stop handler: duplicate workers must never stop
    # the original worker's Pod. Keep this handle alive until main returns.
    with acquire_job_lock(control_root / "active.lock") as active_lock:
        # No traceback or arbitrary API exception strings are written to public output.
        import boto3
        from botocore.config import Config
        if any(path.is_symlink() for path in (args.config, *args.config.parents)):
            raise IntegrityError("credential_file_permissions_unsafe")
        info = args.config.stat()
        parent = args.config.parent.stat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 64 * 1024
            or not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid()
            or stat.S_IMODE(parent.st_mode) != 0o700):
            raise IntegrityError("credential_file_permissions_unsafe")
        credentials = json.loads(args.config.read_text())
        if args.control_dir is not None and credentials.get("shared_control_dir") != str(control_root):
            raise IntegrityError("shared_control_directory_mismatch")
        job = args.job_dir.resolve()
        job.mkdir(parents=True, exist_ok=True)
        os.chmod(job, 0o700)
        log_path = job / "job.log"
        bucket = credentials["R2_BUCKET"]
        s3 = boto3.client("s3", endpoint_url=credentials["R2_ENDPOINT"],
                          aws_access_key_id=credentials["R2_ACCESS_KEY_ID"],
                          aws_secret_access_key=credentials["R2_SECRET_ACCESS_KEY"], region_name="auto",
                          config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3, "mode": "standard"},
                                        connect_timeout=30, read_timeout=90,
                                        request_checksum_calculation="when_required",
                                        response_checksum_validation="when_required"))
        job_id = job.name
        prefix = "q15/cloud-jobs/" + job_id
        state = {"schema_version": 1, "job_id": job_id, "pod_id": credentials["pod_id"],
                 "status": "starting", "expected_raw_files": RAW_FILES, "expected_raw_bytes": RAW_BYTES,
                 "verified_files": [], "verified_size_bytes": 0, "full_readback_files": 0,
                 "R2_status_prefix": prefix, "started_at_utc": now(),
                 "workspace_df_is_shared_storage_not_verified_purchased_quota": True, **SAFETY}
        def local_error(stage, exc):
            state.setdefault("local_persistence_errors", []).append(
                {"stage": stage, "error_type": type(exc).__name__, "errno": exc.errno})
        def local_json(path, value):
            try:
                atomic_json(path, value)
            except OSError as exc:
                local_error("local_json", exc)
        def log(code, **details):
            line = encoded({"at_utc": now(), "event": code, **details}).decode().strip()
            try:
                with log_path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError as exc:
                local_error("log_file", exc)
            try:
                print(line, flush=True)
            except OSError as exc:
                local_error("log_stdout", exc)
        def checkpoint(remote=True):
            state["updated_at_utc"] = now()
            local_json(job / "job_status.json", state)
            if remote:
                verified_backup(s3, bucket, prefix + "/progress.json", encoded(state))
                verified_backup(s3, bucket, prefix + "/job.log", log_path.read_bytes())
        identity_verified = False
        def stop():
            if not identity_verified:
                raise IntegrityError("pod_identity_not_verified_stop_forbidden")
            if current_pod_id() != credentials["pod_id"]:
                raise IntegrityError("running_pod_environment_identity_mismatch")
            return runpod_request(credentials["RUNPOD_API_KEY"], credentials["pod_id"], "POST", "/stop")
        try:
            if current_pod_id() != validate_pod_id(credentials["pod_id"]):
                raise IntegrityError("running_pod_environment_identity_mismatch")
            pod_metadata = runpod_request(credentials["RUNPOD_API_KEY"], credentials["pod_id"])
            state["pod_preflight"] = pod_metadata
            identity_verified = True
            capacity = pod_metadata.get("disk_capacity_gb")
            if capacity is None and credentials.get("declared_volume_pod_id") == credentials["pod_id"]:
                candidate = credentials.get("declared_volume_gb")
                if isinstance(candidate, (int, float)) and not isinstance(candidate, bool) and math.isfinite(candidate) and candidate > 0:
                    capacity = candidate
                    state["pod_preflight"]["disk_capacity_source"] = "user_reported_for_current_pod"
            if capacity is None:
                raise IntegrityError("configured_workspace_volume_quota_unknown")
            if capacity * 1_000_000_000 < 95 * 1024 ** 3:
                raise IntegrityError("configured_workspace_volume_capacity_insufficient")
            log("runpod_identity_verified")
            raw = Path(credentials["raw_dir"]).resolve()
            raw.mkdir(parents=True, exist_ok=True)
            free = shutil.disk_usage(raw).free
            if free < 20 * 1024 ** 3:
                raise IntegrityError("requires_20_gib_working_headroom")
            log("disk_capacity_and_headroom_passed", reported_free_bytes=free)
            state["status"] = "preflight_verified_downloading_provenance"
            state["pod_identity_verified"] = True
            checkpoint()
            archive = job / "provenance_archive.tar.gz"
            download_verified(s3, bucket, ARCHIVE_KEY, archive, ARCHIVE_SHA, None, ARCHIVE_BYTES)
            safe_extract(archive, job / "provenance")
            inventory_path = job / "provenance/research_runs/Q15-DATA/r2_source_storage_verification.json"
            inventory_bytes = inventory_path.read_bytes()
            if hashlib.sha256(inventory_bytes).hexdigest() != INVENTORY_SHA256:
                raise IntegrityError("transport_inventory_hash_mismatch")
            files = load_inventory(inventory_path)
            verified_backup(s3, bucket, prefix + "/inventory.json", inventory_bytes)
            # Cache only the exact authenticated inventory bytes for restart space
            # planning. Allocation credits never replace per-file SHA/MD5 checks.
            inventory_cache = control_root / "transport_inventory.json"
            cache_temp = inventory_cache.with_name(".transport_inventory-" + uuid.uuid4().hex)
            try:
                if inventory_cache.is_symlink():
                    raise IntegrityError("transport_inventory_cache_symlink")
                fd = os.open(cache_temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
                with os.fdopen(fd, "wb") as output:
                    output.write(inventory_bytes)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(cache_temp, inventory_cache)
            except OSError as exc:
                local_error("transport_inventory_cache", exc)
            finally:
                try:
                    cache_temp.unlink(missing_ok=True)
                except OSError as exc:
                    local_error("transport_inventory_temp_cleanup", exc)
            disk_plan = raw_disk_requirements(raw, files)
            state["raw_disk_requirements"] = disk_plan
            if shutil.disk_usage(raw).free < disk_plan["required_free_bytes"]:
                raise IntegrityError("insufficient_free_space_for_remaining_raw_data")
            state["status"] = "downloading_original_raw_files"
            checkpoint()
            last_checkpoint = [0.0]
            for number, item in enumerate(files, 1):
                dataset, file_id = item["dataset"], item["file_id"]
                dest = raw / dataset / Path(*safe_relative(file_id).parts)
                if not dest.resolve().is_relative_to(raw):
                    raise IntegrityError("raw_destination_outside_root")
                state["current_file"] = {"dataset": dataset, "file_id": file_id, "number": number}
                log("download_started", dataset=dataset, file_id=file_id, number=number)
                def progress(done, size):
                    state["current_file"].update({"downloaded_bytes": done, "expected_bytes": size})
                    if time.monotonic() - last_checkpoint[0] >= 60:
                        checkpoint()
                        last_checkpoint[0] = time.monotonic()
                receipt = download_verified(s3, bucket, item["r2_object_key"], dest,
                                            item["sha256"], item.get("md5"), item["size_bytes"],
                                            on_progress=progress)
                entry = {"dataset": dataset, "file_id": file_id, "r2_object_key": item["r2_object_key"],
                         "local_relative_path": str(dest.relative_to(raw)), **receipt, **SAFETY,
                         "proof": "full_local_byte_read_sha256_and_official_md5_when_available"}
                state["verified_files"].append(entry)
                state["verified_size_bytes"] += receipt["size_bytes"]
                state["full_readback_files"] = len(state["verified_files"])
                log("raw_file_verified", dataset=dataset, file_id=file_id, number=number)
                file_receipt_key = prefix + f"/files/{number:03d}.json"
                verified_backup(s3, bucket, file_receipt_key, encoded(entry))
                checkpoint()
            if len(state["verified_files"]) != RAW_FILES or state["verified_size_bytes"] != RAW_BYTES:
                raise IntegrityError("final_raw_inventory_mismatch")
            state["status"] = "raw_transport_complete_non_authorizing"
            state["transport_integrity_verified"] = True
            log("raw_transport_complete_non_authorizing", files=RAW_FILES, bytes=RAW_BYTES)
            checkpoint()
            # Provenance is already cryptographically pinned and includes gate evidence.
            # Do not clone historical raw/artifact blobs simply to rediscover known blockers.
            repo = job / "provenance"
            state["reference_repository_commit"] = REPO_COMMIT
            state["repository_checkout_performed"] = False
            gate = scientific_gate(repo)
            state["scientific_gate"] = gate
            state["status"] = gate["status"]
            state["training_status"] = "not_started_scientific_gate_blocked"
            state["completion_kind"] = "downloaded_and_verified_without_training"
            local_json(job / "scientific_gate.json", gate)
            verified_backup(s3, bucket, prefix + "/scientific_gate.json", encoded(gate))
            log("scientific_gate_blocked_no_training", reasons=gate["blocking_reasons"])
        except Exception as exc:
            state["status"] = "failed_without_training"
            state["training_status"] = "not_started"
            state["error_code"] = safe_error_code(exc)
            log("job_failed_without_training", error_code=state["error_code"])
        # An idle/blocked/failed Pod is stopped only after its final evidence is durable.
        local_json(job / "job_status.json", state)
        try:
            log("final_backup_before_stop", scientific_status=state["status"])
            result = finish_job(s3, bucket, prefix, state, log_path, stop)
            local_json(job / "stop_api_receipt.json", result)
            log("stop_api_accepted_physical_shutdown_unconfirmed")
        except Exception as exc:
            code = safe_error_code(exc)
            state["shutdown_status"] = "not_confirmed_backup_or_stop_failed"
            state["shutdown_error_code"] = code
            local_json(job / "job_status.json", state)
            log("stop_not_confirmed_manual_attention_required", error_code=code)
            return 2
        return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({"status": "bootstrap_or_config_failed", "stage": "worker_initialization", "error_code": safe_error_code(exc),
                          "fits_started": 0}), flush=True)
        sys.exit(2)
