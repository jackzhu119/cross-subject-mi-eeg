"""Q15 custody transport. Uses only the four explicit R2 environment variables.

This module imports no scientific runtime and performs no fitting or inference.
SDK exception messages and credential values never enter its receipts or logs.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
from functools import wraps
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

BASE_COMMIT = "782d2d0070a50c37d13c8e9f1cab3b3b81bac4fc"
SCIENTIFIC_REVISION = "271af288a2f3863430ab80e3145c2dee9bd5571d"
ORIGIN_JOB = "20261004T005335Z-9b3bce30277a"
RAW_ROOT = Path("/workspace/q15-data/raw")
STREAM_BYTES = 8 * 1024 * 1024
PART_BYTES = 64 * 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}")
RAW_PREFIXES = {
    "Cho2017": "q15/raw/Cho2017/provider-100295/mat_data/",
    "Lee2019_MI": "q15/raw/Lee2019_MI/provider-100542/",
}
AUDIT_RECEIPTS = {
    "Lee2019_MI": "results/Q15-V001/metadata_audit_receipt.json",
    "Cho2017": "results/Q15-V002/metadata_audit_receipt.json",
}


class MigrationError(RuntimeError):
    def __init__(self, code):
        self.safe_code = code if isinstance(code, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,95}", code) else "migration_failed"
        super().__init__(self.safe_code)


def safe_error_code(exc):
    """Classify errors without serializing SDK responses or exception text."""
    if isinstance(exc, MigrationError):
        return exc.safe_code
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        error = response.get("Error")
        code = error.get("Code") if isinstance(error, dict) else None
        if code in {"AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch", "NoSuchBucket",
                    "NoSuchKey", "ExpiredToken", "InvalidToken", "PreconditionFailed"}:
            return "r2_" + re.sub(r"(?<!^)(?=[A-Z])", "_", code).lower()
        metadata = response.get("ResponseMetadata")
        status = metadata.get("HTTPStatusCode") if isinstance(metadata, dict) else None
        if type(status) is int and 100 <= status <= 599:
            return "r2_http_" + str(status)
    if isinstance(exc, OSError) and exc.errno == 28:
        return "workspace_disk_or_quota_full"
    if isinstance(exc, KeyboardInterrupt):
        return "interrupted"
    return "migration_operation_failed"


def _missing_object(exc):
    response = getattr(exc, "response", {})
    if not isinstance(response, dict):
        return False
    error, metadata = response.get("Error", {}), response.get("ResponseMetadata", {})
    return (isinstance(error, dict) and error.get("Code") in {"NoSuchKey", "NotFound", "404"}
            or isinstance(metadata, dict) and metadata.get("HTTPStatusCode") == 404)


def safe_relative(value):
    if (not isinstance(value, str) or not value or "\\" in value
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise MigrationError("unsafe_relative_path")
    path = PurePosixPath(value)
    if not path.parts or path.is_absolute() or any(part in {".", ".."} for part in path.parts) or path.as_posix() != value:
        raise MigrationError("unsafe_relative_path")
    return path


def safe_path(path):
    """Reject symlinks in every existing component, including the final path."""
    path = Path(os.path.abspath(path))
    for component in (path, *path.parents):
        if component.is_symlink():
            raise MigrationError("destination_symlink")
    return path


def file_identity(path):
    path = safe_path(path)
    if not path.is_file():
        raise MigrationError("expected_regular_file_missing")
    sha, md5, count = hashlib.sha256(), hashlib.md5(), 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(STREAM_BYTES), b""):
            sha.update(block)
            md5.update(block)
            count += len(block)
    return {"sha256": sha.hexdigest(), "md5": md5.hexdigest(), "size_bytes": count}


def atomic_json(path, value):
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="." + path.name + ".", delete=False) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        safe_path(path)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def make_s3(environment=None):
    """Explicit keys bypass all SDK shared-credential/profile discovery."""
    environment = os.environ if environment is None else environment
    values = {}
    for name in ("R2_BUCKET", "R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        value = environment.get(name)
        if not isinstance(value, str) or not value or any(char.isspace() for char in value):
            raise MigrationError("required_r2_environment_missing_or_invalid")
        values[name] = value
    endpoint = urlsplit(values["R2_ENDPOINT"])
    if (endpoint.scheme != "https" or not endpoint.hostname or endpoint.username is not None
            or endpoint.password is not None or endpoint.query or endpoint.fragment
            or endpoint.path not in {"", "/"}):
        raise MigrationError("r2_endpoint_invalid")
    import boto3
    from botocore.config import Config
    client = boto3.client(
        "s3", endpoint_url=values["R2_ENDPOINT"], region_name="auto",
        aws_access_key_id=values["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=values["R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                      retries={"mode": "standard", "max_attempts": 3},
                      connect_timeout=30, read_timeout=120),
    )
    return client, values["R2_BUCKET"]


def _read_exact_body(body, expected_size, sink):
    """Stop at declared length; probing proxy-backed EOF can block indefinitely."""
    count = 0
    while count < expected_size:
        requested = min(STREAM_BYTES, expected_size - count)
        block = body.read(requested)
        if not block:
            raise MigrationError("remote_body_truncated")
        if len(block) > requested:
            raise MigrationError("remote_body_overflow")
        sink(block)
        count += len(block)
    return count


def full_readback(s3, bucket, key, expected_sha256, expected_size):
    """A full GET body hash, never a HEAD or user-supplied metadata hash."""
    safe_relative(key)
    if SHA256.fullmatch(str(expected_sha256)) is None or type(expected_size) is not int or expected_size < 0:
        raise MigrationError("readback_expected_identity_invalid")
    body = None
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        body = response["Body"]
        if response.get("ContentRange") is not None or response.get("ContentLength") != expected_size:
            raise MigrationError("full_get_response_length_mismatch")
        digest = hashlib.sha256()
        count = _read_exact_body(body, expected_size, digest.update)
        if count != expected_size or digest.hexdigest() != expected_sha256:
            raise MigrationError("full_get_readback_hash_mismatch")
        return {"object_key": key, "archive_sha256": expected_sha256,
                "bytes": count, "readback_verified": True}
    finally:
        if body is not None:
            body.close()


def probe_r2(s3, bucket):
    """List/write/full-read/delete one unpredictable key before large transfer."""
    prefix = "q15/migrations/probes/" + secrets.token_hex(24) + "/"
    key = prefix + "permission-probe.bin"
    payload = secrets.token_bytes(32768)
    wrote = False
    try:
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1)
        if not isinstance(response, dict) or response.get("Contents"):
            raise MigrationError("probe_prefix_not_empty")
        # Mark the random key ours before the call: a failed response may still
        # have persisted the object. Cleanup never touches a different key.
        wrote = True
        s3.put_object(Bucket=bucket, Key=key, Body=payload,
                      ContentType="application/octet-stream")
        full_readback(s3, bucket, key, hashlib.sha256(payload).hexdigest(), len(payload))
    finally:
        if wrote:
            response = s3.delete_object(Bucket=bucket, Key=key)
            metadata = response.get("ResponseMetadata", {}) if isinstance(response, dict) else {}
            if metadata.get("HTTPStatusCode", 204) not in {200, 204}:
                raise MigrationError("probe_delete_failed")
            try:
                s3.head_object(Bucket=bucket, Key=key)
            except Exception as exc:
                if not _missing_object(exc):
                    raise
            else:
                raise MigrationError("probe_delete_not_verified")
    return {"list_verified": True, "write_verified": True,
            "full_readback_verified": True, "delete_verified": True}


def upload_archive(s3, bucket, archive, key, *, part_bytes=PART_BYTES):
    archive, key = safe_path(archive), str(safe_relative(key))
    if type(part_bytes) is not int or part_bytes < 5 * 1024 * 1024:
        raise MigrationError("multipart_part_size_invalid")
    expected = file_identity(archive)
    if expected["size_bytes"] <= 0 or expected["size_bytes"] > part_bytes * 10000:
        raise MigrationError("archive_multipart_size_invalid")
    # Content-addressed objects can be reused only after full GET verification.
    try:
        head = s3.head_object(Bucket=bucket, Key=key)
    except Exception as exc:
        if not _missing_object(exc):
            raise
    else:
        if head.get("ContentLength") != expected["size_bytes"]:
            raise MigrationError("existing_archive_object_changed")
        receipt = full_readback(s3, bucket, key, expected["sha256"], expected["size_bytes"])
        return {**receipt, "reused": True}
    upload_id = None
    completed = False
    try:
        response = s3.create_multipart_upload(Bucket=bucket, Key=key,
                                              ContentType="application/x-tar",
                                              Metadata={"sha256": expected["sha256"]})
        upload_id = response["UploadId"]
        digest, count, parts = hashlib.sha256(), 0, []
        with archive.open("rb") as stream:
            for part_number in range(1, 10001):
                block = stream.read(part_bytes)
                if not block:
                    break
                count += len(block)
                digest.update(block)
                response = s3.upload_part(Bucket=bucket, Key=key, UploadId=upload_id,
                                          PartNumber=part_number, Body=block)
                etag = response.get("ETag")
                if not isinstance(etag, str) or not etag:
                    raise MigrationError("multipart_etag_missing")
                parts.append({"PartNumber": part_number, "ETag": etag})
        if count != expected["size_bytes"] or digest.hexdigest() != expected["sha256"]:
            raise MigrationError("archive_changed_during_upload")
        s3.complete_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id,
                                     MultipartUpload={"Parts": parts}, IfNoneMatch="*")
        completed = True
        receipt = full_readback(s3, bucket, key, expected["sha256"], expected["size_bytes"])
        return {**receipt, "reused": False}
    finally:
        if upload_id is not None and not completed:
            try:
                s3.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)
            except Exception as abort_error:  # noqa: BLE001 -- SDK errors may contain credentials.
                print(json.dumps({"cleanup_error_code": safe_error_code(abort_error),
                                  "pod_stop_requested": False}), file=sys.stderr)


def _unique_json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise MigrationError("json_duplicate_key")
        result[key] = value
    return result


def _decode_json(payload):
    value = json.loads(payload, object_pairs_hook=_unique_json_pairs)
    if not isinstance(value, dict):
        raise MigrationError("expected_json_object")
    return value


def _read_json(path):
    return _decode_json(safe_path(path).read_text(encoding="utf-8"))


def _committed_value(repo, relative, revision="HEAD"):
    safe_relative(relative)
    path = safe_path(Path(repo) / relative)
    if revision != "HEAD" and re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise MigrationError("raw_provenance_revision_invalid")
    result = subprocess.run(["git", "show", revision + ":" + relative], cwd=repo,
                            capture_output=True, check=False)
    if result.returncode or not path.is_file() or path.read_bytes() != result.stdout:
        raise MigrationError("raw_inventory_or_receipt_not_committed_unchanged")
    return json.loads(result.stdout, object_pairs_hook=_unique_json_pairs)


def _committed_json(repo, relative, revision="HEAD"):
    value = _committed_value(repo, relative, revision)
    if not isinstance(value, dict):
        raise MigrationError("expected_json_object")
    return value


def expected_bnci_ids():
    return {f"A{subject:02d}{session}.mat" for subject in range(1, 10) for session in ("E", "T")}


def load_bnci_inventory(repo, raw_root=RAW_ROOT, *, require_committed=True, revision=BASE_COMMIT):
    """Match all18 source originals to the frozen Q8 hashes and R2 readback receipt."""
    repo, raw_root = safe_path(repo), safe_path(raw_root)
    source_name = "research_runs/Q8-E001/results/source_files.json"
    receipt_name = "research_runs/Q15-PREPARATION/BNCI_R2_SOURCE_RECEIPT_20261003.json"
    if require_committed:
        source = _committed_value(repo, source_name, revision)
        receipt = _committed_json(repo, receipt_name, revision)
    else:
        source = json.loads(safe_path(repo / source_name).read_text(), object_pairs_hook=_unique_json_pairs)
        receipt = _read_json(repo / receipt_name)
    expected_ids = expected_bnci_ids()
    if not isinstance(source, list) or len(source) != 18:
        raise MigrationError("bnci_frozen_inventory_incomplete")
    frozen = {}
    for row in source:
        if not isinstance(row, dict) or set(row) != {"path", "bytes", "sha256"}:
            raise MigrationError("bnci_frozen_inventory_record_invalid")
        path = row.get("path")
        if (not isinstance(path, str) or "\\" in path or any(ord(char) < 32 for char in path)
                or not PurePosixPath(path).is_absolute()
                or any(part in {".", ".."} for part in PurePosixPath(path).parts)
                or PurePosixPath(path).as_posix() != path):
            raise MigrationError("bnci_frozen_inventory_path_invalid")
        name = PurePosixPath(path).name
        if (name not in expected_ids or name in frozen or SHA256.fullmatch(str(row.get("sha256"))) is None
                or type(row.get("bytes")) is not int or row["bytes"] <= 0):
            raise MigrationError("bnci_frozen_inventory_identity_invalid")
        frozen[name] = row
    rows = receipt.get("files")
    if (not isinstance(rows, list) or len(rows) != 18
            or type(receipt.get("n_files")) is not int or receipt["n_files"] != 18
            or type(receipt.get("r2_verified_files")) is not int or receipt["r2_verified_files"] != 18):
        raise MigrationError("bnci_r2_receipt_incomplete")
    records, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise MigrationError("bnci_r2_receipt_record_invalid")
        name = row.get("file_id")
        if name not in frozen or name in seen:
            raise MigrationError("bnci_r2_receipt_identity_invalid")
        seen.add(name)
        if (row.get("sha256") != frozen[name]["sha256"]
                or type(row.get("size_bytes")) is not int or row["size_bytes"] != frozen[name]["bytes"]
                or re.fullmatch(r"[0-9a-f]{32}", str(row.get("md5"))) is None
                or row.get("persisted_readback_verified") is not True
                or row.get("r2_full_readback_verified") is not True):
            raise MigrationError("bnci_r2_receipt_hash_or_readback_mismatch")
        key = f"q15/source-originals/BNCI2014_001/{row['sha256']}/{name}"
        if row.get("r2_object_key") != key:
            raise MigrationError("bnci_r2_receipt_object_key_mismatch")
        target = safe_path(raw_root / "BNCI2014_001" / name)
        records.append({"dataset": "BNCI2014_001", "file_id": name, "path": str(target),
                        "r2_object_key": key, "sha256": row["sha256"], "md5": row["md5"],
                        "size_bytes": row["size_bytes"]})
    if seen != expected_ids or set(frozen) != expected_ids:
        raise MigrationError("bnci_r2_receipt_cohort_incomplete")
    if (type(receipt.get("r2_verified_size_bytes")) is not int
            or receipt["r2_verified_size_bytes"] != sum(row["size_bytes"] for row in records)):
        raise MigrationError("bnci_r2_receipt_total_size_mismatch")
    return sorted(records, key=lambda row: row["file_id"])


def expected_file_ids(dataset):
    if dataset == "Cho2017":
        return {f"s{subject:02d}.mat" for subject in range(1, 53)}
    if dataset == "Lee2019_MI":
        return {f"session{session}/s{subject}/sess{session:02d}_subj{subject:02d}_EEG_MI.mat"
                for session in (1, 2) for subject in range(1, 55)}
    raise MigrationError("raw_dataset_unknown")


def load_raw_inventory(repo, raw_root=RAW_ROOT, raw_key_map=None, *, require_committed=True, revision="HEAD"):
    """Tie every object to a committed raw audit and authenticated inventory."""
    repo, raw_root = safe_path(repo), safe_path(raw_root)
    read = (lambda relative: _committed_json(repo, relative, revision)) if require_committed else (lambda relative: _read_json(repo / relative))
    inventory = read("research_runs/Q15-PREPARATION/transport_inventory.json")
    rows = inventory.get("files")
    if inventory.get("schema_version") != 1 or not isinstance(rows, list) or len(rows) != 160:
        raise MigrationError("raw_inventory_count_or_schema_invalid")
    identities = {}
    for row in rows:
        if not isinstance(row, dict):
            raise MigrationError("raw_inventory_record_invalid")
        dataset, file_id = row.get("dataset"), row.get("file_id")
        safe_relative(file_id)
        if dataset not in RAW_PREFIXES or file_id not in expected_file_ids(dataset):
            raise MigrationError("raw_inventory_identity_invalid")
        identity = (dataset, file_id)
        if identity in identities:
            raise MigrationError("raw_inventory_duplicate_identity")
        if (SHA256.fullmatch(str(row.get("sha256"))) is None
                or type(row.get("size_bytes")) is not int or row["size_bytes"] <= 0
                or re.fullmatch(r"[0-9a-f]{32}", str(row.get("md5"))) is None):
            raise MigrationError("raw_inventory_hash_or_size_invalid")
        identities[identity] = row
    for dataset in RAW_PREFIXES:
        if {file_id for ds, file_id in identities if ds == dataset} != expected_file_ids(dataset):
            raise MigrationError("raw_inventory_cohort_incomplete")
    mapping = {identity: RAW_PREFIXES[identity[0]] + identity[1] for identity in identities}
    if raw_key_map is not None:
        key_map = _read_json(raw_key_map)
        mapped = key_map.get("files")
        if key_map.get("schema_version") != 1 or not isinstance(mapped, list):
            raise MigrationError("raw_key_map_schema_invalid")
        mapping = {}
        for row in mapped:
            if not isinstance(row, dict):
                raise MigrationError("raw_key_map_record_invalid")
            identity = (row.get("dataset"), row.get("file_id"))
            if "r2_object_key" in row and "r2_key" in row and row["r2_object_key"] != row["r2_key"]:
                raise MigrationError("raw_key_map_conflicting_aliases")
            key = row.get("r2_object_key", row.get("r2_key"))
            safe_relative(key)
            if identity in mapping:
                raise MigrationError("raw_key_map_ambiguous_identity")
            if identity not in identities or not key.startswith("q15/raw/" + identity[0] + "/"):
                raise MigrationError("raw_key_map_identity_or_prefix_invalid")
            mapping[identity] = key
        if set(mapping) != set(identities):
            raise MigrationError("raw_key_map_incomplete")
    if len(set(mapping.values())) != len(mapping):
        raise MigrationError("raw_key_map_ambiguous_object_key")
    records = []
    for dataset, relative in AUDIT_RECEIPTS.items():
        receipt = read(relative)
        files = receipt.get("files")
        if (receipt.get("dataset") != dataset or receipt.get("raw_hashes_verified") is not True
                or receipt.get("all_expected_files_hashed") is not True
                or not isinstance(files, list) or len(files) != len(expected_file_ids(dataset))):
            raise MigrationError("committed_raw_audit_incomplete")
        seen = set()
        for row in files:
            if not isinstance(row, dict):
                raise MigrationError("committed_raw_audit_record_invalid")
            file_id = row.get("file_id")
            identity = (dataset, file_id)
            if identity not in identities or file_id in seen:
                raise MigrationError("committed_raw_audit_identity_mismatch")
            seen.add(file_id)
            expected = identities[identity]
            if any(row.get(field) != expected[field] for field in ("sha256", "md5", "size_bytes")):
                raise MigrationError("committed_raw_audit_transport_mismatch")
            canonical = raw_root / dataset / file_id
            path_string = row.get("path")
            if not isinstance(path_string, str) or path_string != canonical.as_posix():
                raise MigrationError("committed_raw_audit_path_mismatch")
            target = safe_path(path_string)
            if not target.is_relative_to(raw_root):
                raise MigrationError("raw_destination_outside_root")
            records.append({**expected, "path": str(target), "r2_object_key": mapping[identity]})
    if len({row["path"] for row in records}) != 160:
        raise MigrationError("raw_destinations_ambiguous")
    return sorted(records, key=lambda row: (row["dataset"], row["file_id"]))


def check_raw_object_sizes(s3, bucket, records):
    """Existing raw R2 backup availability; this is explicitly not a body hash."""
    for row in records:
        response = s3.head_object(Bucket=bucket, Key=row["r2_object_key"])
        if type(response.get("ContentLength")) is not int or response["ContentLength"] != row["size_bytes"]:
            raise MigrationError("existing_r2_raw_object_size_mismatch")
    return len(records)


def _download_lock(function):
    @wraps(function)
    def locked(s3, bucket, key, destination, *args, **kwargs):
        destination = safe_path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        lock_path = safe_path(destination.with_name(destination.name + ".migration.lock"))
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "a+") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise MigrationError("another_download_is_active") from None
            return function(s3, bucket, key, destination, *args, **kwargs)
    return locked


@_download_lock
def download_verified(s3, bucket, key, destination, expected_sha256, expected_size=None,
                      *, expected_md5=None, resume=True, full_get_required=False):
    """Hash persisted bytes, bind resumes to ETag, refuse changed final outputs."""
    safe_relative(key)
    if SHA256.fullmatch(str(expected_sha256)) is None:
        raise MigrationError("download_expected_sha256_invalid")
    if expected_size is not None and (type(expected_size) is not int or expected_size <= 0):
        raise MigrationError("download_expected_size_invalid")
    if expected_md5 is not None and re.fullmatch(r"[0-9a-f]{32}", str(expected_md5)) is None:
        raise MigrationError("download_expected_md5_invalid")
    destination = safe_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        actual = file_identity(destination)
        if (actual["sha256"] != expected_sha256 or expected_size is not None and actual["size_bytes"] != expected_size
                or expected_md5 is not None and actual["md5"] != expected_md5):
            raise MigrationError("existing_destination_changed")
        if not full_get_required:
            return {"sha256": expected_sha256, "size_bytes": actual["size_bytes"], "verified": True, "reused": True}
    head = s3.head_object(Bucket=bucket, Key=key)
    size = head.get("ContentLength")
    if type(size) is not int or size <= 0 or expected_size is not None and size != expected_size:
        raise MigrationError("remote_size_mismatch")
    etag = head.get("ETag")
    if not isinstance(etag, str) or not etag:
        raise MigrationError("remote_etag_missing_or_invalid")
    partial_suffix = ".part." + secrets.token_hex(16) if full_get_required else ".part"
    part = safe_path(destination.with_name(destination.name + partial_suffix))
    marker = safe_path(part.with_name(part.name + ".json"))
    bound = {"object_key": key, "sha256": expected_sha256, "size_bytes": size, "etag": etag}
    offset = part.stat().st_size if part.is_file() else 0
    if part.exists() and not part.is_file():
        raise MigrationError("partial_destination_not_file")
    if offset:
        if not resume or full_get_required:
            raise MigrationError("full_get_requires_clean_partial_destination")
        if not etag or not marker.exists() or _read_json(marker) != bound or offset > size:
            raise MigrationError("partial_identity_or_etag_mismatch")
    elif marker.exists() and _read_json(marker) != bound:
        raise MigrationError("partial_identity_or_etag_mismatch")
    atomic_json(marker, bound)
    body = None
    did_full_get = False
    try:
        if offset < size:
            args = {"Bucket": bucket, "Key": key}
            if etag:
                args["IfMatch"] = etag
            if offset:
                args["Range"] = f"bytes={offset}-"
            response = s3.get_object(**args)
            body = response["Body"]
            did_full_get = not bool(args.get("Range"))
            if response.get("ContentLength") != size - offset:
                raise MigrationError("get_content_length_mismatch")
            if etag and response.get("ETag") != etag:
                raise MigrationError("get_etag_mismatch")
            if offset:
                if response.get("ContentRange") != f"bytes {offset}-{size - 1}/{size}":
                    raise MigrationError("get_content_range_mismatch")
            elif response.get("ContentRange") is not None:
                raise MigrationError("full_get_unexpected_content_range")
            with part.open("ab" if offset else "wb") as stream:
                offset += _read_exact_body(body, size - offset, stream.write)
                stream.flush()
                os.fsync(stream.fileno())
            if offset != size:
                raise MigrationError("download_body_truncated")
        actual = file_identity(part)
        if (actual["sha256"] != expected_sha256 or actual["size_bytes"] != size
                or expected_md5 is not None and actual["md5"] != expected_md5):
            raise MigrationError("persisted_download_hash_mismatch")
        safe_path(destination)
        if destination.exists():
            existing = file_identity(destination)
            if existing != actual:
                raise MigrationError("existing_destination_changed")
        else:
            # link() atomically refuses a destination that appeared concurrently.
            os.link(part, destination)
        part.unlink()
        marker.unlink()
        return {"sha256": expected_sha256, "size_bytes": size, "verified": True,
                "reused": False, "full_get_verified": did_full_get}
    finally:
        if body is not None:
            body.close()
        if full_get_required:
            part.unlink(missing_ok=True)
            marker.unlink(missing_ok=True)


def restore_originals(s3, bucket, records):
    verified = []
    for row in records:
        result = download_verified(s3, bucket, row["r2_object_key"], row["path"],
                                   row["sha256"], row["size_bytes"], expected_md5=row["md5"])
        verified.append({"dataset": row["dataset"], "file_id": row["file_id"],
                         "path": row["path"], "sha256": result["sha256"],
                         "size_bytes": result["size_bytes"], "verified": True,
                         "reused": result["reused"]})
    return verified


def restore_source_originals(s3, bucket, records):
    """Restore18 frozen source bytes; this function never trains or preprocesses."""
    expected_ids = expected_bnci_ids()
    if (len(records) != 18 or {row.get("file_id") for row in records} != expected_ids
            or any(row.get("dataset") != "BNCI2014_001" for row in records)):
        raise MigrationError("bnci_restore_record_cohort_invalid")
    return restore_originals(s3, bucket, records)


def _bundle_module():
    path = Path(__file__).with_name("q15_migration_bundle.py")
    spec = importlib.util.spec_from_file_location("q15_migration_bundle", path)
    if spec is None or spec.loader is None:
        raise MigrationError("bundle_helper_unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise MigrationError("invalid_cli_arguments")


def _parser():
    parser = SafeArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    probe = actions.add_parser("probe")
    probe.add_argument("--receipt", type=Path)
    backup = actions.add_parser("backup")
    backup.add_argument("--repo", type=Path, default=Path("/workspace/q15-execution/repo"))
    backup.add_argument("--epoch-dir", type=Path, default=Path("/workspace/q15-data/epochs"))
    backup.add_argument("--bnci-dir", type=Path, default=RAW_ROOT / "BNCI2014_001")
    backup.add_argument("--raw-dir", type=Path, default=RAW_ROOT)
    backup.add_argument("--raw-key-map", type=Path)
    backup.add_argument("--archive", type=Path, required=True)
    backup.add_argument("--receipt", type=Path, required=True)
    backup.add_argument("--base-commit", default=BASE_COMMIT)
    backup.add_argument("--origin-job", default=ORIGIN_JOB)
    backup.add_argument("--origin-pod", required=True)
    restore = actions.add_parser("restore")
    restore.add_argument("--workspace", type=Path, default=Path("/workspace"))
    restore.add_argument("--raw-dir", type=Path, default=RAW_ROOT)
    restore.add_argument("--raw-key-map", type=Path)
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--object-key", required=True)
    restore.add_argument("--archive-sha256", required=True)
    restore.add_argument("--receipt", type=Path, required=True)
    return parser


def _validate_output_paths(args):
    receipt = safe_path(args.receipt) if args.receipt is not None else None
    if receipt is not None and receipt.exists():
        allowed = {"r2_permissions_verified", "backup_full_get_verified", "bundle_restored_raw_pending",
                   "migration_restored_verified"}
        if not receipt.is_file() or _read_json(receipt).get("status") not in allowed:
            raise MigrationError("existing_receipt_destination_changed")
    if args.action == "probe":
        return
    archive = safe_path(args.archive)
    if (receipt == archive or receipt.exists() and archive.exists()
            and os.path.samefile(receipt, archive)):
        raise MigrationError("archive_and_receipt_paths_collide")
    if args.action == "backup":
        protected = [safe_path(path) for path in (args.repo, args.raw_dir, args.epoch_dir, args.bnci_dir)]
    else:
        workspace = safe_path(args.workspace)
        protected = [workspace / "q15-execution", workspace / "q15-data", safe_path(args.raw_dir)]
        if receipt == workspace / "q15-migration/migration_manifest.json":
            raise MigrationError("receipt_collides_with_bundle_manifest")
    if any(receipt.is_relative_to(root) or archive.is_relative_to(root) for root in protected):
        raise MigrationError("transport_output_inside_scientific_artifact_tree")


def run(args, *, client=None, bucket=None, bundle=None):
    if args.action == "backup":
        if (re.fullmatch(r"[0-9a-f]{40}", args.base_commit) is None
                or re.fullmatch(r"[A-Za-z0-9_-]{1,80}", args.origin_job) is None
                or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.origin_pod) is None):
            raise MigrationError("backup_provenance_invalid")
    elif args.action == "restore":
        safe_relative(args.object_key)
        if SHA256.fullmatch(args.archive_sha256) is None or not args.object_key.startswith("q15/migrations/"):
            raise MigrationError("restore_archive_identity_invalid")
    _validate_output_paths(args)
    if client is None:
        client, bucket = make_s3()
    probe_receipt = probe_r2(client, bucket)
    if args.action == "probe":
        receipt = {"status": "r2_permissions_verified", "probe": probe_receipt,
                   "new_source_fits": 0, "target_fits": 0, "pod_stop_requested": False}
        if args.receipt:
            atomic_json(args.receipt, receipt)
        return receipt
    bundle = _bundle_module() if bundle is None else bundle
    if args.action == "backup":
        originals = load_raw_inventory(args.repo, args.raw_dir, args.raw_key_map, revision=args.base_commit)
        raw_count = check_raw_object_sizes(client, bucket, originals)
        if raw_count != 160:
            raise MigrationError("existing_r2_raw_object_count_invalid")
        manifest = bundle.export_bundle(args.repo, args.epoch_dir, args.bnci_dir, args.archive,
                                        args.base_commit, args.origin_job, args.origin_pod)
        paths = [row.get("path") for row in manifest.get("files", []) if isinstance(row, dict)]
        counts = {"source_fit_count": manifest.get("source_fit_count"),
                  "external_epoch_npz_count": sum(isinstance(path, str) and path.startswith("epochs/") and path.endswith(".npz") for path in paths),
                  "external_trial_csv_count": sum(isinstance(path, str) and path.startswith("epochs/") and path.endswith(".csv") for path in paths),
                  "bnci_original_count": sum(isinstance(path, str) and path.startswith("raw/BNCI2014_001/") and path.endswith(".mat") for path in paths)}
        if counts != {"source_fit_count": 15, "external_epoch_npz_count": 106,
                      "external_trial_csv_count": 106, "bnci_original_count": 18}:
            raise MigrationError("exported_bundle_counts_invalid")
        identity = file_identity(args.archive)
        key = f"q15/migrations/{args.origin_job}/{identity['sha256']}/validated-source-and-epochs.tar"
        proof = upload_archive(client, bucket, args.archive, key)
        receipt = {"schema_version": 1, "status": "backup_full_get_verified", **proof,
                   "origin_job": args.origin_job, "origin_pod": args.origin_pod,
                   "base_commit": args.base_commit, "scientific_revision": SCIENTIFIC_REVISION,
                   "probe": probe_receipt, "bundle_manifest": manifest,
                   **counts,
                   "raw_originals_verified": 0, "raw_source_objects_size_checked": raw_count,
                   "raw_source_backups": "existing_r2_objects_size_checked_not_rehashed",
                   "new_source_fits": 0, "origin_source_fits": 15, "target_fits": 0,
                   "pod_stop_requested": False, "ready_to_stop_origin_after_user_review": raw_count == 160}
        atomic_json(args.receipt, receipt)
        return receipt
    download = download_verified(client, bucket, args.object_key, args.archive, args.archive_sha256,
                                  resume=False, full_get_required=True)
    restored = bundle.restore_bundle(args.archive, args.workspace, args.archive_sha256)
    if restored.get("paths_verified") is not True:
        raise MigrationError("restored_bundle_paths_unverified")
    receipt = {**restored, "schema_version": 1, "status": "bundle_restored_raw_pending",
               "object_key": args.object_key, "archive_sha256": args.archive_sha256,
               "bytes": download["size_bytes"], "full_get_verified": True,
               "probe": probe_receipt,
               "raw_originals_verified": 0, "ready_for_continuation": False,
               "new_source_fits": 0, "origin_source_fits": 15, "target_fits": 0,
               "pod_stop_requested": False}
    atomic_json(args.receipt, receipt)
    repo = Path(args.workspace) / "q15-execution/repo"
    if restored.get("paths", {}).get("repo") != str(repo):
        raise MigrationError("restored_bundle_repo_path_mismatch")
    originals = load_raw_inventory(repo, args.raw_dir, args.raw_key_map, revision=BASE_COMMIT)
    evidence = restore_originals(client, bucket, originals)
    if len(evidence) != 160:
        raise MigrationError("restored_original_count_invalid")
    receipt.update({"status": "migration_restored_verified", "raw_originals_verified": len(evidence),
                    "raw_originals": evidence, "ready_for_continuation": True})
    atomic_json(args.receipt, receipt)
    return receipt


def main(argv=None):
    try:
        receipt = run(_parser().parse_args(argv))
        # Full receipts are private files. Console output contains only safe codes,
        # public archive identity and counts, never environment/SDK objects.
        public = {key: receipt[key] for key in ("status", "object_key", "archive_sha256", "bytes",
                                               "readback_verified", "raw_originals_verified",
                                               "ready_for_continuation", "new_source_fits", "origin_source_fits",
                                               "target_fits", "pod_stop_requested")
                  if key in receipt}
        print(json.dumps(public, sort_keys=True))
        return 0
    except (Exception, KeyboardInterrupt) as exc:  # noqa: BLE001 -- Never expose SDK error messages.
        print(json.dumps({"status": "failed_stopped", "error_code": safe_error_code(exc),
                          "ready_for_continuation": False, "new_source_fits": 0, "target_fits": 0,
                          "pod_stop_requested": False}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
