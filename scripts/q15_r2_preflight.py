"""Fail-closed private R2 access check; never downloads EEG or starts fits."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

REQUIRED = ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT", "R2_BUCKET")
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "research_runs/Q15-DATA/r2_preflight.json"
BODY = b"Q15 private storage readiness probe\n"
KNOWN_CODES = {
    "AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch", "NoSuchBucket",
    "RequestTimeout", "SlowDown", "ExpiredToken", "InternalError",
}


def safe_error(exc: Exception) -> dict:
    """Exclude messages, request headers, endpoints and credential values."""
    response = getattr(exc, "response", {})
    code = response.get("Error", {}).get("Code") if isinstance(response, dict) else None
    return {"category": code if code in KNOWN_CODES else "operation_failed"}


def probe(client, bucket: str, key: str) -> dict:
    checks = dict.fromkeys(("bucket_access", "list", "write", "read_verify", "delete"), False)
    result = {"status": "blocked", "checks": checks, "probe_cleanup": "not_required"}
    attempted_write = False
    stage = "bucket_access"
    try:
        client.head_bucket(Bucket=bucket)
        checks[stage] = True
        stage = "list"
        listing = client.list_objects_v2(Bucket=bucket, Prefix="q15/", MaxKeys=1)
        if not isinstance(listing, dict) or "KeyCount" not in listing:
            raise ValueError("invalid_list_response")
        checks[stage] = True
        stage = "write"
        attempted_write = True
        client.put_object(
            Bucket=bucket, Key=key, Body=BODY, ContentType="text/plain",
            Metadata={"sha256": hashlib.sha256(BODY).hexdigest(), "purpose": "q15-preflight"},
        )
        checks[stage] = True
        stage = "read_verify"
        response = client.get_object(Bucket=bucket, Key=key)
        stream = response["Body"]
        try:
            actual = stream.read(len(BODY) + 1)
        finally:
            stream.close()
        if (actual != BODY or response.get("ContentLength") != len(BODY)
                or response.get("Metadata", {}).get("sha256") != hashlib.sha256(BODY).hexdigest()):
            raise ValueError("probe_integrity_mismatch")
        checks[stage] = True
    except Exception as exc:  # noqa: BLE001 -- redact arbitrary SDK error text
        result.update(failed_stage=stage, error=safe_error(exc))
    finally:
        if attempted_write:
            try:
                client.delete_object(Bucket=bucket, Key=key)
                # An accepted DELETE alone does not prove that this key is gone.
                page = client.list_objects_v2(Bucket=bucket, Prefix=key, MaxKeys=2)
                if (not isinstance(page, dict) or "KeyCount" not in page
                        or page.get("IsTruncated")
                        or any(item.get("Key") == key for item in page.get("Contents", []))):
                    raise ValueError("probe_delete_unverified")
                checks["delete"] = True
                result["probe_cleanup"] = "verified_absent"
            except Exception as exc:  # noqa: BLE001 -- retain sanitized cleanup failures
                result["cleanup_error"] = safe_error(exc)
                result["probe_cleanup"] = "unconfirmed"
                result["probe_key_requiring_cleanup"] = key
    if all(checks.values()):
        result["status"] = "passed"
    return result


def run_preflight() -> dict:
    result = {
        "schema_version": 1, "checked_at_utc": datetime.now(UTC).isoformat(),
        "environment_variables": {name: "present" if os.environ.get(name) else "missing"
                                  for name in REQUIRED},
        "status": "blocked_missing_environment", "fits_started": 0,
        "target_scores_computed": False, "large_download_started": False,
        "bucket_public_access_changed": False, "checks": {},
    }
    if "missing" in result["environment_variables"].values():
        return result
    endpoint = os.environ["R2_ENDPOINT"]
    parsed = urlsplit(endpoint)
    if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            or not re.fullmatch(r"[a-z0-9]+(?:\.(?:eu|fedramp))?\.r2\.cloudflarestorage\.com",
                                parsed.hostname or "")
            or os.environ["R2_BUCKET"] != "eeg-research"):
        result["status"] = "blocked_invalid_endpoint_or_bucket"
        return result
    for name in ("boto3", "botocore", "urllib3"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    try:
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "s3", endpoint_url=endpoint, region_name="auto",
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            config=Config(signature_version="s3v4", connect_timeout=15, read_timeout=30,
                          retries={"mode": "standard", "total_max_attempts": 3},
                          s3={"addressing_style": "path"}),
        )
        key = "q15/manifests/.preflight/" + uuid.uuid4().hex + ".txt"
        result.update(probe(client, "eeg-research", key))
    except Exception as exc:  # noqa: BLE001 -- client errors can contain credentials
        result.update(status="blocked_client_initialization", error=safe_error(exc))
    return result


def write_receipt(output: Path, receipt: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        archive = output.with_name(output.stem + "." + uuid.uuid4().hex + output.suffix)
        output.rename(archive)
    temporary = output.with_name(output.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        receipt = run_preflight()
    except Exception:  # noqa: BLE001 -- fail closed without printing configuration
        receipt = {"status": "blocked_configuration", "fits_started": 0,
                   "large_download_started": False, "target_scores_computed": False}
    write_receipt(args.output, receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0 if receipt["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
