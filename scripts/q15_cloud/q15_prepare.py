#!/usr/bin/env python3
"""Cloud-only migration preparation; observations never release the fit gate.

Fetch and verify the 18 BNCI source originals; inspect every retained Lee/Cho
MAT container; publish only bounded metadata JSON, never raw EEG or secrets.
This is deliberately not a training launcher or a replacement scientific audit.
"""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
BNCI_BASE = "https://bnci-horizon-2020.eu/database/data-sets/001-2014/"
REPOSITORY = "jackzhu119/cross-subject-mi-eeg"
SAFETY = {"fits_started": 0, "predictions_computed": False,
          "preprocessing_contract_frozen": False, "scientific_audit_passed": False}


def now():
    return datetime.now(timezone.utc).isoformat()


def digests(path):
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            sha.update(block)
            md5.update(block)
    return {"sha256": sha.hexdigest(), "md5": md5.hexdigest(),
            "size_bytes": Path(path).stat().st_size}


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".receipt-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def safe_relative(value):
    parts = PurePosixPath(value)
    if parts.is_absolute() or any(x in ("", ".", "..") for x in parts.parts) or "\\" in value:
        raise ValueError("unsafe_file_identity")
    return parts


def fetch_bnci(record, directory, opener=urllib.request.urlopen):
    filename = Path(record["path"]).name
    if not re.fullmatch(r"A0[1-9][TE]\.mat", filename):
        raise ValueError("unexpected_bnci_identity")
    target = Path(directory) / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise ValueError("bnci_symlink_rejected")
    reused = False
    if target.is_file():
        previous = digests(target)
        reused = previous["size_bytes"] == record["bytes"] and previous["sha256"] == record["sha256"]
    if not reused:
        descriptor, temporary = tempfile.mkstemp(prefix="." + filename + "-", dir=target.parent)
        try:
            request = urllib.request.Request(BNCI_BASE + filename,
                                            headers={"User-Agent": "q15-cloud-preparation/20261003"})
            with os.fdopen(descriptor, "wb") as output, opener(request, timeout=120) as response:
                total = 0
                for block in iter(lambda: response.read(8 * 1024**2), b""):
                    total += len(block)
                    if total > record["bytes"]:
                        raise ValueError("bnci_download_exceeds_expected_size")
                    output.write(block)
            actual = digests(temporary)
            if actual["sha256"] != record["sha256"] or actual["size_bytes"] != record["bytes"]:
                raise ValueError("bnci_original_hash_mismatch")
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
    # Independent reread of the persisted original, including resumed files.
    actual = digests(target)
    if actual["sha256"] != record["sha256"] or actual["size_bytes"] != record["bytes"]:
        raise ValueError("bnci_persisted_readback_mismatch")
    return {"file_id": filename, "official_url": BNCI_BASE + filename,
            **actual, "persisted_readback_verified": True, "reused_verified_file": reused}


def observe_mat(path, dataset):
    import numpy as np
    from scipy.io import loadmat
    if dataset == "Lee2019_MI":
        data = loadmat(path, variable_names=["EEG_MI_train"], mat_dtype=True)
        train = data["EEG_MI_train"][0, 0]
        x = train["x"]
        t, y = train["t"].ravel(), train["y_dec"].ravel()
        rate = float(train["fs"].item())
        channels = [str(np.asarray(cell).squeeze().item()) for cell in train["chan"].ravel()]
        codes, counts = np.unique(y, return_counts=True)
        if x.ndim != 2 or len(channels) != x.shape[1] or len(set(channels)) != len(channels):
            raise ValueError("lee_channel_signal_schema_mismatch")
        if len(t) != len(y) or not len(t) or np.any(np.diff(t) <= 0):
            raise ValueError("lee_event_label_schema_mismatch")
        return {"run_field_observed": "EEG_MI_train", "other_fields_not_authorized": True,
                "sampling_rate_hz": rate, "continuous_shape": list(x.shape),
                "signal_dtype": str(x.dtype), "channel_names_as_stored": channels,
                "cue_count": int(len(t)), "cue_min_as_stored": int(t.min()),
                "cue_max_as_stored": int(t.max()),
                "label_counts_as_stored": {str(int(c)): int(n) for c, n in zip(codes, counts)},
                "unit_field_present": any(re.search("unit|scal|gain", n, re.I) for n in train.dtype.names),
                "reference_field_present": any(re.search("ref|ground", n, re.I) for n in train.dtype.names),
                "event_index_conversion_frozen": False}
    if dataset != "Cho2017":
        raise ValueError("unknown_dataset")
    eeg = loadmat(path, variable_names=["eeg"], simplify_cells=True)["eeg"]
    left, right = eeg["imagery_left"], eeg["imagery_right"]
    events = np.asarray(eeg["imagery_event"]).ravel()
    markers = np.flatnonzero(events)
    trials, rate = int(eeg["n_imagery_trials"]), float(eeg["srate"])
    if trials <= 0 or left.ndim != 2 or left.shape != right.shape:
        raise ValueError("cho_class_signal_schema_mismatch")
    if left.shape[1] != len(events) or len(markers) != trials or left.shape[1] % trials:
        raise ValueError("cho_marker_signal_schema_mismatch")
    width = left.shape[1] // trials
    if not np.array_equal(markers, markers[0] + width * np.arange(trials)):
        raise ValueError("cho_irregular_retained_trial_markers")
    return {"run_fields_observed": ["imagery_left", "imagery_right"],
            "sampling_rate_hz": rate, "class_array_shape": list(left.shape),
            "signal_dtype": str(left.dtype), "trials_per_class_as_stored": trials,
            "retained_samples_per_class_trial": int(width),
            "first_marker_zero_based": int(markers[0]),
            "marker_codes_as_stored": np.unique(events).tolist(),
            "frame_as_stored": np.asarray(eeg["frame"]).ravel().tolist(),
            "in_file_channel_name_field_present": any(re.search("chan|label", n, re.I) for n in eeg),
            "unit_field_present": any(re.search("unit|scal|gain", n, re.I) for n in eeg),
            "reference_field_present": any(re.search("ref|ground", n, re.I) for n in eeg),
            "artificial_concatenation_boundaries_present": True,
            "run_mapping_verified": False, "event_index_conversion_frozen": False}


def github_request(token, method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request("https://api.github.com/" + path, data=data, method=method,
                                     headers={"Authorization": "Bearer " + token,
                                              "User-Agent": "q15-cloud-preparation/20261003",
                                              "Accept": "application/vnd.github+json",
                                              "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def publish_reports(token, job_id, reports, api=github_request):
    """Create a new branch and a single atomic commit containing only allowlisted JSON."""
    allowed = {"preparation_status.json", "bnci_source_receipt.json", "external_observations.json"}
    if set(reports) != allowed:
        raise ValueError("unapproved_publication_file_set")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", job_id):
        raise ValueError("unsafe_job_id")
    prefix = "repos/" + REPOSITORY + "/"
    head = api(token, "GET", prefix + "git/ref/heads/q15/cloud-bootstrap-20261002")["object"]["sha"]
    tree = api(token, "GET", prefix + "git/commits/" + head)["tree"]["sha"]
    branch = "q15/preparation-" + job_id
    entries = []
    for name, data in sorted(reports.items()):
        content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        if len(content.encode()) > 1024**2 or token in content:
            raise ValueError("publication_content_rejected")
        entries.append({"path": "research_runs/Q15-PREPARATION/" + job_id + "/" + name,
                        "mode": "100644", "type": "blob", "content": content})
    new_tree = api(token, "POST", prefix + "git/trees", {"base_tree": tree, "tree": entries})["sha"]
    commit = api(token, "POST", prefix + "git/commits", {
        "message": "Record Q15 cloud preparation without training: " + job_id,
        "tree": new_tree, "parents": [head]})["sha"]
    api(token, "POST", prefix + "git/refs", {"ref": "refs/heads/" + branch, "sha": commit})
    # Read back all three exact JSON payloads from this immutable commit.
    for name, data in reports.items():
        result = api(token, "GET", prefix + "contents/research_runs/Q15-PREPARATION/" + job_id + "/" + name + "?ref=" + commit)
        if json.loads(base64.b64decode(result["content"])) != data:
            raise ValueError("github_report_readback_mismatch")
    return {"branch": branch, "commit": commit,
            "url": "https://github.com/" + REPOSITORY + "/commit/" + commit,
            "readback_verified": True}


def run(args):
    job = Path(args.output).resolve()
    status = {"schema_version": 1, "job_id": job.name, "updated_at_utc": now(),
              "status": "preparing_not_training", **SAFETY}
    atomic_json(job / "preparation_status.json", status)
    originals = json.loads((ROOT / "research_runs/Q8-E001/results/source_files.json").read_text())
    if len(originals) != 18 or {Path(x["path"]).name for x in originals} != {
            f"A0{s}{split}.mat" for s in range(1, 10) for split in "TE"}:
        raise ValueError("bnci_expected_inventory_invalid")
    with ThreadPoolExecutor(max_workers=3) as pool:
        source_files = list(pool.map(lambda row: fetch_bnci(row, args.bnci_dir), originals))
    bnci = {"schema_version": 1, "status": "18_originals_verified_no_training", **SAFETY,
            "files": source_files, "n_files": len(source_files),
            "q8_provenance_sha256": digests(ROOT / "research_runs/Q8-E001/results/source_files.json")["sha256"]}
    atomic_json(job / "bnci_source_receipt.json", bnci)
    inventory = json.loads((ROOT / "research_runs/Q15-PREPARATION/transport_inventory.json").read_text())
    observations = {"schema_version": 1, "status": "observations_not_scientific_clearance", **SAFETY,
                    "files": [], "failures": [], "expected_files": 160}
    raw_root = Path(args.raw_dir).resolve()
    for record in inventory["files"]:
        identity = {"dataset": record["dataset"], "file_id": record["file_id"]}
        path = raw_root / record["dataset"] / Path(*safe_relative(record["file_id"]).parts)
        if not path.resolve().is_relative_to(raw_root) or path.is_symlink():
            raise ValueError("raw_path_outside_declared_root")
        try:
            actual = digests(path)
            if any(actual[k] != record[k] for k in ("sha256", "md5", "size_bytes")):
                raise ValueError("external_original_integrity_mismatch")
            metadata = observe_mat(path, record["dataset"])
            observations["files"].append({**identity, **actual, "metadata_observation": metadata})
        except Exception as exc:
            # Do not expose exception text, local paths, arbitrary MAT strings, or credentials.
            observations["failures"].append({**identity, "error_type": type(exc).__name__})
        status.update({"external_files_checked": len(observations["files"]) + len(observations["failures"]),
                       "external_observations_successful": len(observations["files"]), "updated_at_utc": now()})
        atomic_json(job / "external_observations.json", observations)
        atomic_json(job / "preparation_status.json", status)
    atomic_json(job / "external_observations.json", observations)
    status.update({"status": "blocked_scientific_audit_and_freeze", "bnci_originals_verified": 18,
                   "blocking_reasons": ["real_authorizing_metadata_adapter_not_implemented",
                                        "unit_event_boundary_run_contract_not_frozen",
                                        "independent_source_output_validator_missing"],
                   "training_status": "not_started", "updated_at_utc": now()})
    if observations["failures"]:
        status["blocking_reasons"].append("external_raw_files_missing_corrupt_or_schema_failed")
    atomic_json(job / "preparation_status.json", status)
    token = os.environ.get("GH_TOKEN", "")
    if token:
        receipt = publish_reports(token, job.name, {"preparation_status.json": status,
                                  "bnci_source_receipt.json": bnci, "external_observations.json": observations})
        atomic_json(job / "github_publication_receipt.json", receipt)
        print(json.dumps(receipt), flush=True)
    else:
        print(json.dumps({"github_publication": "not_configured", "fits_started": 0}), flush=True)
    print(json.dumps({"status": status["status"], "bnci_originals_verified": 18,
                      "external_files_checked": status["external_files_checked"], **SAFETY}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bnci-dir", default="/workspace/q15-data/raw/BNCI2014_001")
    parser.add_argument("--raw-dir", default="/workspace/q15-data/raw")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        control = Path("/workspace/.q15-cloud")
        control.mkdir(parents=True, exist_ok=True)
        with (control / "active.lock").open("a+") as lock:
            # Same migration-wide lock as the raw-download supervisor. No fit
            # or stop request is attempted on another running job's failure.
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            run(args)
    except Exception as exc:
        report = {"status": "preparation_failed_no_training", "error_type": type(exc).__name__,
                  "updated_at_utc": now(), **SAFETY}
        atomic_json(Path(args.output) / "failure.json", report)
        print(json.dumps(report), flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
