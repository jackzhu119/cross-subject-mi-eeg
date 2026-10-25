"""Bounded R2 archive I/O. Never render credentials, endpoint URLs, or errors.

Requires boto3 only when constructing a real client. Tests inject an S3 client.
No listing, signal decoding, scientific processing, or local file deletion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time
from urllib.parse import urlsplit
import zlib

ENV_NAMES = ("R2_ENDPOINT", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
CHUNK = 8 * 1024 * 1024
PART_BYTES = 16 * 1024 * 1024
DEFAULT_PREFIX = "paper1-hpc-20261023/frozen-inputs-v1"


class ArchiveError(RuntimeError):
    def __init__(self, evidence):
        self.evidence = evidence
        super().__init__(evidence.get("status", "archive_failed"))


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def safe_error(error):
    """Return typed metadata only; exception strings can contain signed URLs."""
    row = {"error_class": type(error).__name__}
    response = getattr(error, "response", None)
    if isinstance(response, dict):
        metadata = response.get("ResponseMetadata", {})
        status = metadata.get("HTTPStatusCode")
        if isinstance(status, int):
            row["http_status"] = status
        code = response.get("Error", {}).get("Code")
        if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_\.\-]{1,60}", code):
            row["service_code"] = code
        headers = metadata.get("HTTPHeaders", {})
        if isinstance(headers, dict):
            headers = {str(key).lower(): value for key, value in headers.items()}
            server = headers.get("server", "")
            row["server_category"] = server if server in {"cloudflare", "envoy", "AmazonS3"} else "other_or_absent"
            kind = str(headers.get("content-type", "")).split(";", 1)[0].lower()
            row["content_type_category"] = kind if kind in {"application/xml", "application/json", "text/xml", "text/plain", "text/html"} else "other_or_absent"
            for header, name in (("cf-ray", "cf_ray_present"), ("x-amz-request-id", "x_amz_request_id_present"),
                                 ("x-amz-id-2", "x_amz_id_2_present"), ("via", "via_present"),
                                 ("www-authenticate", "www_authenticate_present")):
                row[name] = bool(headers.get(header))
    return row


def environment_client():
    bucket_name = "R2_BUCKET" if os.environ.get("R2_BUCKET") else "E2_BUCKET"
    missing = [name for name in ENV_NAMES if name != "R2_BUCKET" and not os.environ.get(name)]
    if not os.environ.get(bucket_name):
        missing.append("R2_BUCKET")
    if missing:
        raise ArchiveError({"status": "blocked_missing_r2_bindings", "missing_names": missing})
    parsed = urlsplit(os.environ["R2_ENDPOINT"])
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or parsed.path not in ("", "/") or parsed.port is not None):
        raise ArchiveError({"status": "blocked_invalid_r2_endpoint"})
    try:
        import boto3
        import botocore.session
        from botocore.config import Config
    except ImportError:
        raise ArchiveError({"status": "blocked_missing_boto3"}) from None
    # R2 uses the explicit existing R2 binding, independent of an inherited AWS
    # profile selector. Keep all inherited environment/auth/proxy state intact.
    # Session.set_config_variable('profile', None) alone still falls through
    # to AWS_PROFILE; config_store's documented override preserves explicit None.
    core_session = botocore.session.Session()
    core_session.set_config_variable("profile", None)
    core_session.get_component("config_store").set_config_variable("profile", None)
    session = boto3.Session(botocore_session=core_session)
    client = session.client(
        "s3", endpoint_url=os.environ["R2_ENDPOINT"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto", verify=os.environ.get("SSL_CERT_FILE") or True,
        config=Config(signature_version="s3v4", connect_timeout=15, read_timeout=90,
                      retries={"total_max_attempts": 1},
                      request_checksum_calculation="when_required",
                      response_checksum_validation="when_required",
                      s3={"addressing_style": "path"}),
    )
    return client, os.environ[bucket_name]


def _digest_stream(stream, *, progress=None):
    sha = hashlib.sha256()
    crc = size = 0
    while True:
        block = stream.read(CHUNK)
        if not block:
            break
        sha.update(block)
        crc = zlib.crc32(block, crc)
        size += len(block)
        if progress:
            progress(size)
    return {"bytes": size, "sha256": sha.hexdigest(), "crc32": f"{crc & 0xffffffff:08x}"}


def _remote_digest(client, bucket, key, *, progress=None):
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"]
    try:
        result = _digest_stream(body, progress=progress)
    finally:
        body.close()
    length = response.get("ContentLength")
    if length is not None and length != result["bytes"]:
        raise ArchiveError({"status": "remote_response_length_mismatch"})
    return result


def verify_remote(client, bucket, key, *, expected_size, expected_sha256, progress=None):
    """Fully read an existing object; HEAD size and ETag are never acceptance."""
    row = {"status": "remote_verifying", "key": key, "started_at_utc": utc_now(),
           "expected_bytes": expected_size, "expected_sha256": expected_sha256,
           "stream_readback_verified": False}
    try:
        digest = _remote_digest(client, bucket, key, progress=progress)
        row["remote"] = digest
        if digest["bytes"] != expected_size or digest["sha256"] != expected_sha256.lower():
            raise ArchiveError({"status": "remote_readback_mismatch"})
        row.update(status="remote_verified", stream_readback_verified=True)
    except Exception as error:
        row.update(status="remote_verification_failed", error=safe_error(error))
        if isinstance(error, ArchiveError):
            row["failure_detail"] = error.evidence
    row["completed_at_utc"] = utc_now()
    return row


def probe(client, bucket, *, prefix=DEFAULT_PREFIX):
    """PUT random self-owned bytes, stream GET+SHA256, DELETE, HEAD=>404."""
    key = prefix.rstrip("/") + "/_connectivity-probes/" + secrets.token_hex(16) + ".txt"
    payload = b"paper1 authorized archival connectivity probe\n" + secrets.token_bytes(24)
    expected = hashlib.sha256(payload).hexdigest()
    row = {"status": "probe_running", "started_at_utc": utc_now(), "probe_key": key,
           "bytes": len(payload), "sha256": expected, "operations": [],
           "stream_readback_verified": False, "cleanup_verified": False}
    uploaded = False
    stage = "PutObject"
    try:
        client.put_object(Bucket=bucket, Key=key, Body=payload, ContentLength=len(payload),
                          ContentType="application/octet-stream")
        uploaded = True
        row["operations"].append({"operation": stage, "status": "passed"})
        stage = "GetObject"
        digest = _remote_digest(client, bucket, key)
        if digest["bytes"] != len(payload) or digest["sha256"] != expected:
            raise ArchiveError({"status": "probe_readback_mismatch"})
        row["stream_readback_verified"] = True
        row["operations"].append({"operation": stage, "status": "passed", **digest})
    except Exception as error:
        row["status"] = "probe_failed"
        row["operations"].append({"operation": stage, "status": "failed", **safe_error(error)})
        if isinstance(error, ArchiveError):
            row["failure_category"] = error.evidence["status"]
    finally:
        if uploaded:
            try:
                client.delete_object(Bucket=bucket, Key=key)
                row["operations"].append({"operation": "DeleteObject", "status": "passed"})
                try:
                    client.head_object(Bucket=bucket, Key=key)
                except Exception as error:
                    detail = safe_error(error)
                    if detail.get("http_status") != 404:
                        raise
                    row["cleanup_verified"] = True
                    row["operations"].append({"operation": "HeadObject", "status": "confirmed_absent", **detail})
                else:
                    row["status"] = "probe_failed"
                    row["failure_category"] = "probe_cleanup_object_still_present"
            except Exception as error:
                row["status"] = "probe_failed"
                row["operations"].append({"operation": "cleanup", "status": "failed", **safe_error(error)})
        if row["stream_readback_verified"] and row["cleanup_verified"]:
            row["status"] = "probe_verified"
        row["completed_at_utc"] = utc_now()
    return row


def _upload_file(client, bucket, key, path, size, *, progress=None):
    if size <= PART_BYTES:
        with path.open("rb") as handle:
            client.put_object(Bucket=bucket, Key=key, Body=handle, ContentLength=size,
                              ContentType="application/octet-stream")
        if progress:
            progress(size)
        return
    upload_id = None
    completed = False
    try:
        response = client.create_multipart_upload(Bucket=bucket, Key=key,
                                                  ContentType="application/octet-stream")
        upload_id = response["UploadId"]
        parts = []
        sent = 0
        with path.open("rb") as handle:
            while True:
                block = handle.read(PART_BYTES)
                if not block:
                    break
                number = len(parts) + 1
                response = client.upload_part(Bucket=bucket, Key=key, UploadId=upload_id,
                                              PartNumber=number, Body=block, ContentLength=len(block))
                parts.append({"PartNumber": number, "ETag": response["ETag"]})
                sent += len(block)
                if progress:
                    progress(sent)
        if sent != size:
            raise ArchiveError({"status": "local_file_changed_during_upload"})
        client.complete_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id,
                                         MultipartUpload={"Parts": parts})
        completed = True
    except Exception as error:
        evidence = {"status": "upload_failed", **safe_error(error), "multipart_abort_attempted": False}
        if upload_id is not None and not completed:
            evidence["multipart_abort_attempted"] = True
            try:
                client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)
                evidence["multipart_abort_succeeded"] = True
            except Exception as abort_error:
                evidence["multipart_abort_succeeded"] = False
                evidence["abort_error"] = safe_error(abort_error)
        raise ArchiveError(evidence) from None


def archive_file(client, bucket, local_path, key, *, expected_size,
                 expected_sha256=None, expected_crc32=None, progress=None):
    """Verify local bytes, upload once, stream full GET+SHA256; never delete local.

    progress(stage, cumulative_stage_bytes) is optional. At least one frozen
    SHA256/CRC32 checksum is required. Caller may remove local_path only when
    returned `safe_to_remove_local` is True. A failed remote check retains local.
    """
    row = {"status": "archive_running", "key": key, "started_at_utc": utc_now(),
           "expected_bytes": expected_size, "expected_sha256": expected_sha256,
           "expected_crc32": expected_crc32, "safe_to_remove_local": False,
           "stream_readback_verified": False}
    stage = "local_verification"
    try:
        if expected_sha256 is None and expected_crc32 is None:
            raise ArchiveError({"status": "missing_original_checksum_basis"})
        path = Path(local_path)
        with path.open("rb") as handle:
            local = _digest_stream(handle, progress=(lambda n: progress(stage, n)) if progress else None)
        row["local"] = local
        if local["bytes"] != expected_size:
            raise ArchiveError({"status": "local_size_mismatch"})
        if expected_sha256 is not None and local["sha256"] != expected_sha256.lower():
            raise ArchiveError({"status": "local_sha256_mismatch"})
        if expected_crc32 is not None and local["crc32"] != expected_crc32.lower().zfill(8):
            raise ArchiveError({"status": "local_crc32_mismatch"})
        row["local_verified"] = True
        stage = "upload"
        _upload_file(client, bucket, key, path, expected_size,
                     progress=(lambda n: progress(stage, n)) if progress else None)
        row["upload_completed"] = True
        stage = "readback"
        remote = _remote_digest(client, bucket, key,
                                progress=(lambda n: progress(stage, n)) if progress else None)
        row["remote"] = remote
        if remote["bytes"] != local["bytes"] or remote["sha256"] != local["sha256"]:
            raise ArchiveError({"status": "remote_readback_mismatch"})
        row.update(status="archive_verified", stream_readback_verified=True, safe_to_remove_local=True)
    except Exception as error:
        row.update(status="archive_failed", failed_stage=stage, error=safe_error(error))
        if isinstance(error, ArchiveError):
            row["failure_detail"] = error.evidence
    row["completed_at_utc"] = utc_now()
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("probe",))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        client, bucket = environment_client()
        result = probe(client, bucket)
        result["bucket_variable_name"] = "R2_BUCKET" if os.environ.get("R2_BUCKET") else "E2_BUCKET"
    except Exception as error:
        result = error.evidence if isinstance(error, ArchiveError) else {"status": "probe_failed", **safe_error(error)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "probe_verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
