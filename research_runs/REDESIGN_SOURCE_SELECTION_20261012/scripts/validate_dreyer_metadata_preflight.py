#!/usr/bin/env python3
"""Replay bounded metadata/byte checks without downloading, fitting or scoring."""
import argparse
import importlib.util
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=root / "evidence/dreyer_access_metadata_receipt.json")
    parser.add_argument("--output", type=Path, default=root / "evidence/dreyer_metadata_replay_validation.json")
    args = parser.parse_args()
    specification = importlib.util.spec_from_file_location("dreyer_metadata_audit", root / "scripts/check_dreyer_metadata.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    receipt = json.loads(args.receipt.read_text())
    checks = []

    def check(name, condition):
        checks.append({"check": name, "passed": bool(condition)})

    manifest = json.loads((module.SOURCES / "dreyer_nemar_manifest.txt").read_text())
    by_path = {row["path"]: row for row in manifest}
    for file in receipt["files"]:
        path = Path(file["cache_path"])
        expected = by_path[file["path"]]
        check("full_subset_content_hash_replay:" + file["path"],
              path.stat().st_size == expected["size"] and module.sha256(path) == expected["checksum"] == file["sha256"])
    check("all_three_provider_git_annex_pointers_verified_online",
          len(receipt["files"]) == 3 and all(file["annex_pointer_receipt"]["verified"] for file in receipt["files"]))
    metadata_verified = len(receipt["metadata"]) == 7
    for original, local in module.FIXED_METADATA.items():
        metadata_verified &= module.git_blob_sha((module.SOURCES / local).read_bytes()) == by_path[original]["checksum"]
    check("seven_metadata_blob_hashes_replayed", metadata_verified)
    check("520_declared_edf_resolved_without_missing_acquisition",
          receipt["declared_source_edf_count"] == 520
          and receipt["missing_run_resolution"] == {"sub-59": ["R5online", "R6online"]}
          and receipt["acquisition_manifest_count"] == 174 and receipt["acquisition_manifest_complete"])
    actual_prefixes, actual_annotations = {}, {}
    header_checks = True
    for file in receipt["files"]:
        path = Path(file["cache_path"])
        header = module.parse_header(path)
        events, prefix = module.annotation_and_prefix(path, header)
        actual_prefixes[file["path"]] = prefix
        actual_annotations[file["path"]] = events
        labels = {channel["label"] for channel in header["channels"]}
        header_checks &= all(label in labels for label in module.COMMON19)
        header_checks &= header["record_shape_verified"]
        class_events = [event for event in events if event["description"] in file["cue_event_mapping"]]
        header_checks &= len(class_events) == 40 and min(event["onset"] for event in class_events) > 1
    check("reparsed_raw_record_shape_common19_and_entire_precue_prefix", header_checks)
    import numpy as np
    a, b = actual_prefixes[module.FIXED_RAW[0]], actual_prefixes[module.FIXED_RAW[2]]
    physical_roundtrip = True
    for label in module.COMMON19:
        maximum = float(np.max(np.abs(a[label] - b[label])))
        expected = receipt["first_run_conversion_checks"]["per_channel_unit_check"][label]
        physical_roundtrip &= maximum <= expected["one_bdf_quantization_step_volts"] + 1e-12
        physical_roundtrip &= abs(maximum - expected["max_absolute_conversion_difference_volts"]) < 1e-18
    check("all19_recomputed_precue_scales_within_one_bdf_quantum", physical_roundtrip)
    raw_events = [event for event in actual_annotations[module.FIXED_RAW[0]] if event["description"] in ("769", "770")]
    converted_events = actual_annotations[module.FIXED_RAW[2]]
    onset_checks = len(raw_events) == len(converted_events) == 40
    for raw, converted in zip(raw_events, converted_events):
        onset_checks &= converted["description"] == ("left_hand" if raw["description"] == "769" else "right_hand")
        onset_checks &= abs(raw["onset"] - converted["onset"]) <= 0.5 / 512 + 1e-9
    check("reparsed_cue_mapping_and_onsets_within_half_source_sample", onset_checks)
    check("raw_and_confirmatory_limits_fail_closed",
          not receipt["original_gdf_or_zenodo_zip_verified"]
          and not receipt["full_cohort_signals_qc_complete"]
          and not receipt["author_prior_use_confirmed"]
          and not receipt["confirmatory_target_evaluation_authorized_by_this_receipt"])
    check("no_fits_predictions_or_decoder_scores",
          all(receipt[name] == 0 for name in ["source_fits", "target_fits", "target_predictions", "target_decoder_scores"]))
    with tempfile.TemporaryDirectory() as temporary:
        broken = Path(temporary) / "truncated.edf"
        raw_file = Path(receipt["files"][0]["cache_path"])
        with raw_file.open("rb") as source:
            broken.write_bytes(source.read(receipt["files"][0]["header"]["header_bytes"]))
        try:
            module.parse_header(broken)
        except ValueError:
            rejected = True
        else:
            rejected = False
        check("truncated_record_file_is_rejected", rejected)
    result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "saved_subset_offline_hash_and_parser_preflight_replay",
              "checks": checks, "passed": sum(check["passed"] for check in checks),
              "failed": sum(not check["passed"] for check in checks),
              "task_eeg_features_computed": False, "decoder_predictions_computed": False}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "failed": result["failed"], "report": str(args.output)}))
    if result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
