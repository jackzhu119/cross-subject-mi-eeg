#!/usr/bin/env python3
"""Bounded transport/header audit. Does not fit, select, infer or score a decoder.

The optional download is fixed to two acquisition EDFs from one person and the
corresponding first BDF conversion (< 100 MB). Original Zenodo GDF bytes are
not acquired or certified by this check. Raw files are kept outside git.
"""
from __future__ import annotations

import argparse
import base64
import collections
import csv
import hashlib
import io
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "evidence/dataset_sources"
DEFAULT_CACHE = Path("/workspace/mi-eeg-redesign-data/dreyer_subset")
COMMON19 = ["Fz", "FC3", "FC1", "FCz", "FC2", "FC4", "C5", "C3", "C1", "Cz",
            "C2", "C4", "C6", "CP3", "CP1", "CPz", "CP2", "CP4", "Pz"]
FIXED_RAW = [
    "sourcedata/sub-01/eeg/sub-01_task-R1acquisition_eeg.edf",
    "sourcedata/sub-01/eeg/sub-01_task-R2acquisition_eeg.edf",
    "sub-1/ses-0/eeg/sub-1_ses-0_task-imagery_acq-R1acquisition_run-0_eeg.bdf",
]
FIXED_METADATA = {
    "sourcedata/README.md": "dreyer_nemar_sourcedata_readme.txt",
    "sourcedata/sourcedata_provenance.json": "dreyer_nemar_sourcedata_provenance.json",
    "participants.tsv": "dreyer_nemar_participants.tsv",
    ".nemar/availability-report.json": "dreyer_nemar_availability_report.json",
    "sub-1/ses-0/eeg/sub-1_ses-0_task-imagery_acq-R1acquisition_run-0_eeg.json":
        "dreyer_nemar_sub-1_ses-0_task-imagery_acq-R1acquisition_run-0_eeg.json",
    "sub-1/ses-0/eeg/sub-1_ses-0_task-imagery_acq-R1acquisition_run-0_channels.tsv":
        "dreyer_nemar_sub-1_ses-0_task-imagery_acq-R1acquisition_run-0_channels.tsv",
    "sub-1/ses-0/eeg/sub-1_ses-0_task-imagery_acq-R1acquisition_run-0_events.tsv":
        "dreyer_nemar_sub-1_ses-0_task-imagery_acq-R1acquisition_run-0_events.tsv",
}


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def read_url(url, limit):
    request = urllib.request.Request(url, headers={"User-Agent": "EEG metadata audit"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError("bounded_metadata_limit_exceeded")
        return data, response.status


def metadata_row(row, filename, online):
    path = SOURCES / filename
    if online:
        data, status = read_url(row["bytes_url"], max(int(row["size"]), 1024))
    else:
        data, status = path.read_bytes(), "cached_not_network_rechecked"
    actual = git_blob_sha(data)
    if row["checksum_algorithm"] != "git" or actual != row["checksum"]:
        raise ValueError(f"metadata_blob_checksum_mismatch:{row['path']}")
    if online:
        path.write_bytes(data)
    return {"path": row["path"], "url": row["bytes_url"], "status": status,
            "git_blob_sha1": actual, "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data), "checksum_verified": True}


def annex_pointer(row, tree_by_path, online):
    entry = tree_by_path[row["path"]]
    if not online:
        return {"verified": False, "reason": "network_check_not_requested"}
    raw, status = read_url(entry["url"], 8192)
    result = json.loads(raw)
    data = base64.b64decode(result["content"])
    if git_blob_sha(data) != entry["sha"]:
        raise ValueError("git_annex_pointer_blob_sha_mismatch")
    text = data.decode("ascii").strip()
    expected_key = f"SHA256E-s{row['size']}--{row['checksum']}"
    if expected_key not in text:
        raise ValueError("git_annex_content_key_mismatch")
    return {"verified": True, "api_status": status, "blob_sha1": entry["sha"],
            "pointer": text, "sha256_key_matches_provider_manifest": True}


def download_one(row, cache, online):
    path = cache / row["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size == row["size"] and sha256(path) == row["checksum"]:
        status = "verified_cache_reused"
    elif online:
        temporary = path.with_suffix(path.suffix + ".partial")
        request = urllib.request.Request(row["bytes_url"], headers={"User-Agent": "Bounded EEG parser preflight"})
        downloaded = 0
        with urllib.request.urlopen(request, timeout=30) as response, temporary.open("wb") as handle:
            for block in iter(lambda: response.read(1024 * 1024), b""):
                downloaded += len(block)
                if downloaded > row["size"]:
                    raise ValueError("raw_download_exceeds_manifest_size")
                handle.write(block)
            status = response.status
        if temporary.stat().st_size != row["size"] or sha256(temporary) != row["checksum"]:
            raise ValueError(f"raw_sha256_or_size_mismatch:{row['path']}")
        temporary.replace(path)
    else:
        return {"path": row["path"], "available": False, "reason": "subset_not_downloaded"}
    return {"path": row["path"], "url": row["bytes_url"], "cache_path": str(path),
            "bytes": path.stat().st_size, "sha256": sha256(path), "checksum_verified": True,
            "status": status, "available": True}


def parse_header(path):
    with path.open("rb") as stream:
        fixed = stream.read(256)
        ns = int(fixed[252:256])
        header_bytes = int(fixed[184:192])
        signal_headers = stream.read(header_bytes - 256)
    widths = [16, 80, 8, 8, 8, 8, 8, 80, 8, 32]
    names = ["label", "transducer", "unit", "physical_min", "physical_max", "digital_min",
             "digital_max", "prefilter", "samples_per_record", "reserved"]
    fields = {}
    offset = 0
    for name, width in zip(names, widths):
        fields[name] = [signal_headers[offset + width * index:offset + width * (index + 1)].decode("ascii").strip()
                        for index in range(ns)]
        offset += width * ns
    channels = []
    record_duration = float(fixed[244:252])
    for index in range(ns):
        item = {name: values[index] for name, values in fields.items()}
        for name in ["physical_min", "physical_max", "digital_min", "digital_max"]:
            item[name] = float(item[name])
        item["samples_per_record"] = int(item["samples_per_record"])
        item["sampling_frequency_hz"] = item["samples_per_record"] / record_duration
        channels.append(item)
    width = 3 if path.suffix == ".bdf" else 2
    records = int(fixed[236:244])
    expected_bytes = header_bytes + records * sum(c["samples_per_record"] for c in channels) * width
    if expected_bytes != path.stat().st_size:
        raise ValueError("record_shape_does_not_match_file_bytes")
    return {"format": "BDF" if width == 3 else "EDF", "header_bytes": header_bytes,
            "sample_bytes": width, "n_signals": ns, "records": records,
            "record_duration_seconds": record_duration,
            "duration_seconds": records * record_duration, "expected_file_bytes": expected_bytes,
            "record_shape_verified": True, "channels": channels}


def annotation_and_prefix(path, header):
    """Read event annotations, and only the first 1-second precue EEG prefix.

    Continuous records are traversed solely to extract the annotation channel;
    no task EEG features, class statistics, predictions or accuracy are computed.
    """
    import numpy as np
    channels = header["channels"]
    offsets, position = [], 0
    for channel in channels:
        offsets.append(position)
        position += channel["samples_per_record"] * header["sample_bytes"]
    ann_idx = next(i for i, c in enumerate(channels) if "Annotations" in c["label"])
    annotations, prefix = [], {}
    with path.open("rb") as stream:
        stream.seek(header["header_bytes"])
        for record in range(header["records"]):
            block = stream.read(position)
            start = offsets[ann_idx]
            count = channels[ann_idx]["samples_per_record"] * header["sample_bytes"]
            ann = block[start:start + count]
            for tal in ann.split(b"\x00"):
                if b"\x14" not in tal:
                    continue
                parts = tal.decode("ascii").split("\x14")
                onset_duration = parts[0].split("\x15")
                for description in parts[1:]:
                    if description:
                        annotations.append({"onset": float(onset_duration[0]), "description": description})
            if record == 0:
                for index, channel in enumerate(channels):
                    if channel["label"] not in COMMON19:
                        continue
                    data = block[offsets[index]:offsets[index] + channel["samples_per_record"] * header["sample_bytes"]]
                    if header["sample_bytes"] == 2:
                        digital = np.frombuffer(data, dtype="<i2").astype(np.int64)
                    else:
                        octets = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3).astype(np.int64)
                        digital = octets[:, 0] | (octets[:, 1] << 8) | (octets[:, 2] << 16)
                        digital = np.where(digital & 0x800000, digital - 0x1000000, digital)
                    scale = (channel["physical_max"] - channel["physical_min"]) / (channel["digital_max"] - channel["digital_min"])
                    physical = (digital - channel["digital_min"]) * scale + channel["physical_min"]
                    if channel["unit"] not in ("uV", "µV") or not np.isfinite(physical).all():
                        raise ValueError("unexpected_units_or_nonfinite_precue_prefix")
                    prefix[channel["label"]] = physical * 1e-6
    return annotations, prefix


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-subset", action="store_true", help="Fetch only the fixed <100 MB raw subset.")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--receipt", type=Path, default=ROOT / "evidence/dreyer_access_metadata_receipt.json")
    args = parser.parse_args()
    manifest_path = SOURCES / "dreyer_nemar_manifest.txt"
    manifest = json.loads(manifest_path.read_text())
    by_path = {row["path"]: row for row in manifest}
    tree = json.loads((SOURCES / "dreyer_nemar_gittree.txt").read_text())
    tree_by_path = {row["path"]: row for row in tree["tree"]}
    assert tree["truncated"] is False
    assert len(by_path) == len(manifest)
    raw_rows = [by_path[name] for name in FIXED_RAW]
    subset_bytes = sum(row["size"] for row in raw_rows)
    if subset_bytes > 100_000_000:
        raise ValueError("fixed_subset_budget_exceeded")
    runs = collections.defaultdict(set)
    for row in manifest:
        if row["path"].startswith("sourcedata/sub-") and row["path"].endswith(".edf"):
            person = row["path"].split("/")[1]
            runs[person].add(row["path"].split("_task-")[1].split("_")[0])
    all_runs = {"R1acquisition", "R2acquisition", "R3online", "R4online", "R5online", "R6online"}
    missing = {person: sorted(all_runs - tasks) for person, tasks in runs.items() if all_runs - tasks}
    acquisition_complete = all({"R1acquisition", "R2acquisition"} <= tasks for tasks in runs.values())
    receipt = {
        "schema_version": 1, "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "bounded_transport_header_annotation_and_precue_parser_preflight_only",
        "dataset": "Dreyer2023", "provider": "NEMAR nm000250", "provider_version": "v1.0.5",
        "tree_sha": tree["sha"], "manifest_sha256": sha256(manifest_path),
        "source_fits": 0, "target_fits": 0, "target_predictions": 0, "target_decoder_scores": 0,
        "common19": COMMON19, "declared_source_edf_count": sum(len(tasks) for tasks in runs.values()),
        "declared_participants": len(runs), "expected_all_runs_count": len(runs) * 6,
        "missing_run_resolution": missing, "acquisition_manifest_complete": acquisition_complete,
        "acquisition_manifest_count": sum(len(tasks & {"R1acquisition", "R2acquisition"}) for tasks in runs.values()),
        "fixed_subset_budget_bytes": subset_bytes,
        "acquisition_manifest_total_bytes": sum(row["size"] for row in manifest
                                                 if row["path"].startswith("sourcedata/sub-")
                                                 and "acquisition_eeg.edf" in row["path"]),
        "original_gdf_or_zenodo_zip_verified": False,
        "original_acquisition_physical_calibration_verified": False,
        "full_cohort_signals_qc_complete": False,
        "author_prior_use_confirmed": False,
        "confirmatory_target_evaluation_authorized_by_this_receipt": False,
        "metadata": [], "files": [],
    }
    for original, local in FIXED_METADATA.items():
        receipt["metadata"].append(metadata_row(by_path[original], local, args.download_subset))
    for row in raw_rows:
        row["annex_pointer_receipt"] = annex_pointer(row, tree_by_path, args.download_subset)
    with ThreadPoolExecutor(max_workers=3) as pool:
        downloaded = list(pool.map(lambda row: download_one(row, args.cache_dir, args.download_subset), raw_rows))
    prefixes, annotation_records = {}, {}
    for row, result in zip(raw_rows, downloaded):
        result["annex_pointer_receipt"] = row["annex_pointer_receipt"]
        if result["available"]:
            path = Path(result["cache_path"])
            header = parse_header(path)
            annotations, prefix = annotation_and_prefix(path, header)
            labels = [channel["label"] for channel in header["channels"]]
            if len(set(labels)) != len(labels) or not all(name in labels for name in COMMON19):
                raise ValueError("missing_or_duplicate_common19_label")
            eeg = [c for c in header["channels"] if c["label"] not in {"EOG1", "EOG2", "EOG3", "EMGg", "EMGd", "EDF Annotations", "BDF Annotations"}]
            if len(eeg) != 27 or any(c["sampling_frequency_hz"] != 512 for c in eeg):
                raise ValueError("unexpected_eeg_count_or_sampling_frequency")
            counts = collections.Counter(event["description"] for event in annotations)
            cue_codes = ("769", "770") if path.suffix == ".edf" else ("left_hand", "right_hand")
            if counts[cue_codes[0]] != 20 or counts[cue_codes[1]] != 20:
                raise ValueError("first_run_class_event_count_mismatch")
            result.update({"header": header, "annotation_counts": dict(counts),
                           "cue_event_mapping": {cue_codes[0]: "left_hand", cue_codes[1]: "right_hand"},
                           "expected_class_events_verified": True, "common19_label_order_verified": True,
                           "prefix_seconds_read_for_unit_roundtrip_only": 1,
                           "prefix_finite_and_scalable_to_si_volts": True})
            first_cue = min(event["onset"] for event in annotations if event["description"] in cue_codes)
            if first_cue <= 1:
                raise ValueError("unit_roundtrip_prefix_is_not_entirely_precue")
            result["first_cue_onset_seconds"] = first_cue
            result["unit_roundtrip_prefix_before_all_class_cues_verified"] = True
            prefixes[row["path"]] = prefix
            annotation_records[row["path"]] = annotations
        receipt["files"].append(result)
    if all(result["available"] for result in downloaded):
        import numpy as np
        source_events = [event for event in annotation_records[FIXED_RAW[0]] if event["description"] in ("769", "770")]
        bdf_events = [event for event in annotation_records[FIXED_RAW[2]] if event["description"] in ("left_hand", "right_hand")]
        tsv = list(csv.DictReader(io.StringIO((SOURCES / FIXED_METADATA[
            "sub-1/ses-0/eeg/sub-1_ses-0_task-imagery_acq-R1acquisition_run-0_events.tsv"]).read_text(encoding="utf-8-sig")), delimiter="\t"))
        event_check = len(source_events) == len(bdf_events) == len(tsv) == 40
        deviations = []
        for source, converted, sidecar in zip(source_events, bdf_events, tsv):
            mapped = "left_hand" if source["description"] == "769" else "right_hand"
            sidecar_value = "1" if mapped == "left_hand" else "2"
            event_check &= mapped == converted["description"] == sidecar["trial_type"]
            event_check &= sidecar_value == sidecar["value"]
            deviations.extend([abs(source["onset"] - converted["onset"]), abs(source["onset"] - float(sidecar["onset"]))])
        # EDF annotation decimal encoding can round within half a source sample.
        event_check &= max(deviations) <= 0.5 / 512 + 1e-9
        per_channel = {}
        unit_roundtrip = True
        for label in COMMON19:
            a, b = prefixes[FIXED_RAW[0]][label], prefixes[FIXED_RAW[2]][label]
            delta = float(np.max(np.abs(a - b)))
            bh = next(c for c in receipt["files"][2]["header"]["channels"] if c["label"] == label)
            quantum = (bh["physical_max"] - bh["physical_min"]) / (bh["digital_max"] - bh["digital_min"]) * 1e-6
            tolerance = quantum + 1e-12
            unit_roundtrip &= delta <= tolerance
            per_channel[label] = {"max_absolute_conversion_difference_volts": delta,
                                  "one_bdf_quantization_step_volts": quantum,
                                  "within_one_step": delta <= tolerance}
        receipt["first_run_conversion_checks"] = {
            "matching_cue_counts_labels_and_onsets_verified": bool(event_check),
            "max_event_onset_difference_seconds": max(deviations),
            "event_tolerance_seconds": 0.5 / 512,
            "precue_common19_physical_scale_roundtrip_verified": bool(unit_roundtrip),
            "precue_prefix_seconds": 1, "per_channel_unit_check": per_channel,
            "physical_device_calibration_not_established": True,
            "no_task_signal_feature_or_decoder_performance_computed": True,
        }
    receipt["limitations"] = [
        "Only one person's two acquisition runs and one BDF counterpart are hash-checked here; the full 87-person signal cohort is not audited.",
        "Provider claims NEMAR sourcedata EDF bytes mirror MOABB/OSF upstream bytes. These are not authenticated original Zenodo GDF bytes.",
        "All 174 acquisition EDFs are declared; the two absent R5/R6 online EDFs belong to sub-59 and do not affect the proposed first-two-run manifest.",
        "The provider's BDF sidecar records HardwareFilters 5-35 Hz while the descriptor says raw recordings have no hardware filters and describes online processing separately; keep this metadata conflict unresolved.",
        "EDF/BDF headers use uV; the BIDS channels.tsv uses V, consistent with an SI reader convention but not an independent instrument-calibration certificate.",
        "The EDF mirror retains EOG/EMG; BDF conversion retains only EEG. Both have annotations but different cue-code conventions.",
        "Two initial runs include side-specific sham visual feedback; they are not feedback-free physiological recordings.",
        "A17/A41 documented channel-order errors still require prior objective exclusion; a nominal label list cannot repair a physically mislabeled order.",
        "The NEMAR participants.tsv assigns the same aggregate mean age 29 to all individuals; do not use those rows as verified person-level ages.",
        "No target performance, target-fitted preprocessing, model selection, model inference, or confirmatory experiment is performed.",
    ]
    receipt["bounded_subset_transport_and_parser_verified"] = bool(
        all(r["available"] for r in downloaded)
        and receipt.get("first_run_conversion_checks", {}).get("matching_cue_counts_labels_and_onsets_verified", False)
        and receipt.get("first_run_conversion_checks", {}).get("precue_common19_physical_scale_roundtrip_verified", False)
    )
    receipt["status"] = "PARTIAL_SOURCE_ROUTE_VERIFIED_NO_TARGET_PERFORMANCE" if receipt["bounded_subset_transport_and_parser_verified"] else "METADATA_ONLY_OR_CONVERSION_CHECK_BLOCKED_NO_TARGET_PERFORMANCE"
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "receipt": str(args.receipt),
                      "acquisition_manifest_files": receipt["acquisition_manifest_count"],
                      "subset_bytes": subset_bytes, "source_fits": 0, "target_fits": 0,
                      "target_predictions": 0, "target_decoder_scores": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
