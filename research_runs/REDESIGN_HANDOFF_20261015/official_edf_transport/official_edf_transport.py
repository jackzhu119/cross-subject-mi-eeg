#!/usr/bin/env python3
"""Offline frozen NEMAR EDF transport plan; never a training launcher.

The CLI deliberately exposes planning only. The one-object transport primitive
is supplied for independent synthetic review and future explicit integration;
it is not called by the CLI or any production worker in this amendment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import ssl
import stat
import urllib.error
import urllib.request
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[3]
EVIDENCE = REPO / "research_runs/REDESIGN_SOURCE_SELECTION_20261012/evidence/dataset_sources"
FROZEN_MANIFEST = EVIDENCE / "dreyer_nemar_acquisition_edf_manifest.json"
FROZEN_SHA256 = "2cfdf35aa7990df880826d1b84d1230e0bda3c9393c17d3ec6e27b7b311d2bf2"
PROVIDER_PROVENANCE = EVIDENCE / "dreyer_nemar_sourcedata_provenance.json"
PROVENANCE_SHA256 = "0d45bdd3394555e33d8dd153ad1ff15f9340f6f867a99e7bd13cf1e3b582b274"
PROVIDER_README = EVIDENCE / "dreyer_nemar_sourcedata_readme.txt"
README_SHA256 = "a86264010041a9980e425275b8e1cdba3d051ec9d0deb4f047b1cf646547c9db"
ORIGIN = "https://data.nemar.org"
PREFIX = ORIGIN + "/nm000250/v1.0.5/"
TREE_SHA = "f77f8859a84df42bd775920d288261260b2236db"
NFILES, NBYTES = 174, 2515343396
CHUNK = 1024 * 1024
GIB = 1024 ** 3
PATH_RE = re.compile(r"sourcedata/sub-(\d{2})/eeg/sub-\1_task-(R[12]acquisition)_eeg\.edf")
SHA_RE = re.compile(r"[0-9a-f]{64}")


def digest_file(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            result.update(block)
    return result.hexdigest()


def pinned_json(path, expected_sha256):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("frozen_metadata_sha256_mismatch")
    return json.loads(data)


def validate_row(row):
    expected_fields = {"provider_path", "restore_relative_path", "bytes", "sha256", "url"}
    if not isinstance(row, dict) or set(row) != expected_fields:
        raise ValueError("transport_row_schema")
    match = PATH_RE.fullmatch(row["provider_path"]) if isinstance(row["provider_path"], str) else None
    if match is None or not 1 <= int(match.group(1)) <= 87:
        raise ValueError("not_frozen_acquisition_edf_path")
    if row["restore_relative_path"] != "dreyer_acquisition/" + row["provider_path"]:
        raise ValueError("restore_layout_changed")
    if type(row["bytes"]) is not int or not 0 < row["bytes"] <= 16 * 1024 ** 2:
        raise ValueError("object_size_invalid")
    if not isinstance(row["sha256"], str) or not SHA_RE.fullmatch(row["sha256"]):
        raise ValueError("object_sha256_invalid")
    validate_url(row["url"], row["provider_path"])
    return row


def validate_url(url, provider_path):
    # Equality to the complete frozen URL rejects credentials, non-443 ports,
    # alternate hosts, escaped traversal, query/fragment and mirror substitution.
    if not isinstance(url, str) or url != PREFIX + provider_path:
        raise ValueError("url_not_exact_frozen_https_object")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != "data.nemar.org"
            or parsed.username or parsed.password or parsed.port is not None
            or parsed.query or parsed.fragment):
        raise ValueError("url_origin_invalid")
    return url


def frozen_plan():
    manifest = pinned_json(FROZEN_MANIFEST, FROZEN_SHA256)
    provenance = pinned_json(PROVIDER_PROVENANCE, PROVENANCE_SHA256)
    if digest_file(PROVIDER_README) != README_SHA256:
        raise ValueError("provider_readme_sha256_mismatch")
    if (manifest["dataset"] != "nm000250" or manifest["version"] != "v1.0.5"
            or manifest["tree_sha"] != TREE_SHA or provenance.get("license") != "CC-BY-4.0"):
        raise ValueError("frozen_provider_or_license_changed")
    source_index = {"sourcedata/" + entry["file"]: entry for entry in provenance["files"]}
    rows = []
    for entry in manifest["files"]:
        row = validate_row({"provider_path": entry["path"],
                            "restore_relative_path": "dreyer_acquisition/" + entry["path"],
                            "bytes": entry["size"], "sha256": entry["checksum"],
                            "url": entry["bytes_url"]})
        if entry["checksum_algorithm"] != "sha256" or entry["url"] != row["url"]:
            raise ValueError("manifest_checksum_or_url_changed")
        original = source_index.get(row["provider_path"])
        if original is None or original["bytes"] != row["bytes"] or original["sha256"] != row["sha256"]:
            raise ValueError("provider_provenance_identity_mismatch")
        rows.append(row)
    paths = {entry["provider_path"] for entry in rows}
    subjects = {}
    for entry in rows:
        match = PATH_RE.fullmatch(entry["provider_path"])
        subjects.setdefault(int(match.group(1)), set()).add(match.group(2))
    if (len(rows) != NFILES or len(paths) != NFILES or sum(row["bytes"] for row in rows) != NBYTES
            or set(subjects) != set(range(1, 88))
            or any(runs != {"R1acquisition", "R2acquisition"} for runs in subjects.values())):
        raise ValueError("frozen_cohort_mapping_incomplete")
    rows.sort(key=lambda row: row["provider_path"])
    return {
        "schema_version": 1,
        "status": "PROPOSED_OFFLINE_SAME_BYTE_EDF_TRANSPORT_PLAN_NOT_AUTHORIZATION",
        "frozen_manifest_sha256": FROZEN_SHA256,
        "provider_provenance_sha256": PROVENANCE_SHA256,
        "provider_tree_sha": TREE_SHA,
        "files": rows, "file_count": NFILES, "total_bytes": NBYTES,
        "license": {"identifier": "CC-BY-4.0", "url": "https://creativecommons.org/licenses/by/4.0/",
                    "attribution_sources": ["10.82901/nemar.nm000250", "10.5281/zenodo.8089820",
                                            "10.1038/s41597-023-02445-z"],
                    "provider_readme_sha256": README_SHA256,
                    "preserve_creator_attribution_and_indicate_processing_changes": True},
        "transport_policy": {"tls_certificate_and_hostname_verification": True,
                             "redirects": "reject_all", "http_status": 200,
                             "content_encoding": "identity", "content_length_required": True,
                             "full_object_sha256_required": True, "parallel_downloads": 1,
                             "automatic_retries": 0, "partial_range_resume": False,
                             "corrupt_or_partial_existing_object": "stop_preserve_evidence",
                             "publish_verified_object": "atomic_no_overwrite_hardlink_then_unlink_partial",
                             "maximum_new_data_bytes": NBYTES,
                             "minimum_free_bytes": 10 * GIB,
                             "additional_paper2_reserve_bytes": "must_be_real_fresh_dot_slot_value"},
        "scientific_boundary": {"target_role": "exploratory_external",
                                "prior_exposure": "unknown", "primary_participants": 85,
                                "primary_events": 6800, "provider_exclusions": [17, 41],
                                "science_manifest_or_input_hashes_changed": False,
                                "gdf_zip_or_bids_bdf_substitution_allowed": False},
        "current_observation": {"network_requests": 0, "target_bytes_read": 0,
                                "remote_availability_verified": False,
                                "remote_full_object_bytes_verified": False,
                                "r2_keys_inferred": False, "r2_retry_performed": False,
                                "packages_installed": False, "fits_started": 0},
        "gates": {"dot_parent_amendment_approval": False, "fresh_transport_slot": False,
                  "accounting_budget_checkpoint_reconciled": False, "actual_target_cache_accepted": False,
                  "actual_training_runtime_accepted": False, "training_authorization": False},
    }


class RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        raise urllib.error.HTTPError(request.full_url, code, "all_redirects_rejected", headers, fp)


def secure_opener():
    # Default trust (including the managed session's configured CA/proxy) stays
    # intact. No unverified context, custom CA bypass, alternate host or retry.
    context = ssl.create_default_context()
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise ValueError("tls_verification_required")
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), RejectRedirects())


def safe_path(root, relative):
    root = Path(root).absolute()
    parts = PurePosixPath(relative).parts
    if (not relative or "\\" in relative or relative.startswith("/")
            or any(part in ("", ".", "..") for part in relative.split("/"))):
        raise ValueError("unsafe_restore_relative_path")
    path = root.joinpath(*parts)
    for entry in (path, *path.parents):
        if entry.is_symlink():
            raise ValueError("restore_symlink_rejected")
    return path


def transport_one(row, root, *, control_check, min_free_bytes, paper2_reserve_bytes,
                  max_new_bytes, opener=None):
    """Future strict transport primitive; CLI never invokes this function.

    A future reviewed coordinator must bind row to frozen_plan(), validate a new
    dot transport slot, old accounting/backup gates and operation approval, and
    supply a live control_check rechecking those gates and the 174-object quota.
    No current metadata slot or this plan grants that authority.
    """
    validate_row(row)
    expected = {entry["provider_path"]: entry for entry in frozen_plan()["files"]}
    if expected.get(row["provider_path"]) != row:
        raise ValueError("transport_row_not_exact_frozen_manifest_identity")
    for name, value in (("min_free_bytes", min_free_bytes), ("paper2_reserve_bytes", paper2_reserve_bytes),
                        ("max_new_bytes", max_new_bytes)):
        if type(value) is not int or value < 0:
            raise ValueError("integer_resource_limit_required:" + name)
    if min_free_bytes < 10 * GIB or max_new_bytes > NBYTES or max_new_bytes < row["bytes"]:
        raise ValueError("transport_disk_or_byte_cap_invalid")
    control_check()
    target = safe_path(root, row["restore_relative_path"])
    if target.exists():
        if not stat.S_ISREG(target.stat().st_mode) or target.stat().st_size != row["bytes"] or digest_file(target) != row["sha256"]:
            raise ValueError("existing_object_corrupt_preserved")
        control_check()
        return {"path": row["restore_relative_path"], "bytes": row["bytes"], "sha256": row["sha256"],
                "status": "existing_exact_bytes_reused", "network_bytes": 0}
    temporary = target.with_name(target.name + ".partial")
    if temporary.exists() or temporary.is_symlink():
        raise ValueError("existing_partial_preserved_manual_review_required")
    ancestor = target.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    required = row["bytes"] + min_free_bytes + paper2_reserve_bytes
    if shutil.disk_usage(ancestor).free < required:
        raise ValueError("insufficient_disk_for_object_floor_and_paper2_reserve")
    target.parent.mkdir(parents=True, exist_ok=True)
    safe_path(root, row["restore_relative_path"])
    control_check()
    request = urllib.request.Request(row["url"], headers={"Accept-Encoding": "identity"}, method="GET")
    response_opener = opener if opener is not None else secure_opener()
    with response_opener.open(request, timeout=30) as response:
        if response.status != 200 or response.geturl() != row["url"]:
            raise ValueError("unexpected_http_status_or_response_url")
        content_length = response.headers.get("Content-Length")
        if not isinstance(content_length, str) or not content_length.isdecimal() or int(content_length) != row["bytes"]:
            raise ValueError("http_content_length_not_exact_frozen_size")
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise ValueError("http_content_encoding_not_identity")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(temporary, flags, 0o600)
        total, hashed = 0, hashlib.sha256()
        with os.fdopen(fd, "wb") as output:
            while True:
                control_check()
                if shutil.disk_usage(target.parent).free < min_free_bytes + paper2_reserve_bytes:
                    raise ValueError("paper2_reserved_free_space_reached_partial_preserved")
                block = response.read(min(CHUNK, row["bytes"] - total + 1))
                if not block:
                    break
                total += len(block)
                if total > row["bytes"] or total > max_new_bytes:
                    raise ValueError("http_body_exceeds_frozen_size_partial_preserved")
                control_check()
                if shutil.disk_usage(target.parent).free < min_free_bytes + paper2_reserve_bytes + len(block):
                    raise ValueError("paper2_reserved_free_space_before_write_partial_preserved")
                output.write(block)
                hashed.update(block)
            output.flush()
            os.fsync(output.fileno())
        if total != row["bytes"] or hashed.hexdigest() != row["sha256"]:
            raise ValueError("download_size_or_sha256_mismatch_partial_preserved")
        control_check()
        # link() is atomic and cannot overwrite an object appearing meanwhile.
        os.link(temporary, target, follow_symlinks=False)
        temporary.unlink()
        directory_fd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    return {"path": row["restore_relative_path"], "bytes": total, "sha256": hashed.hexdigest(),
            "status": "new_exact_bytes_atomic_publish", "network_bytes": total}


def verify_cached_manifest(root, *, control_check):
    """Future explicit byte-only cache acceptance; never called by this CLI.

    This hashes target raw bytes and therefore requires its own approved target
    read/transport scope. It is not header/QC/input-array or training acceptance.
    """
    plan = frozen_plan()
    if len(plan["files"]) != NFILES or sum(row["bytes"] for row in plan["files"]) != NBYTES:
        raise ValueError("complete_frozen_cohort_required")
    verified = []
    for row in plan["files"]:
        control_check()
        path = safe_path(root, row["restore_relative_path"])
        if (not path.is_file() or not stat.S_ISREG(path.stat().st_mode)
                or path.stat().st_size != row["bytes"] or digest_file(path) != row["sha256"]):
            raise ValueError("cached_frozen_edf_size_or_sha256_mismatch:" + row["provider_path"])
        verified.append({"path": row["restore_relative_path"], "bytes": row["bytes"], "sha256": row["sha256"]})
    control_check()
    return {"schema_version": 1, "status": "FROZEN_174_LOCAL_EDF_BYTES_VERIFIED_SCIENTIFIC_GATES_PENDING",
            "frozen_manifest_sha256": FROZEN_SHA256, "file_count": len(verified),
            "verified_bytes": sum(row["bytes"] for row in verified), "files": verified,
            "transport": "official_nemar_same_byte_edf_not_r2_key_receipt",
            "target_header_event_qc_and_input_hash_acceptance": False,
            "accounting_budget_checkpoint_acceptance": False,
            "source_and_actual_training_runtime_acceptance": False,
            "new_source_fits": 0, "target_fits": 0, "target_predictions": 0,
            "training_authorization": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional new plan JSON; never overwrite an existing file.")
    args = parser.parse_args()
    result = frozen_plan()
    data = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(data)
    print(data, end="")


if __name__ == "__main__":
    main()
