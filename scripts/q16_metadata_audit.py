"""Metadata-only Q16 BNCI gate. No power, model fits, or inference are computed."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from q16_common import (BASELINE_OFFSETS, CHANNELS, CLASS_MAP, PERFORMANCE, PERFORMANCE_VALIDATION, PRIOR_AUDIT, Q8_METADATA, Q15_RAW_RECEIPT, RAW_RECEIPT, ROOT, RUN_DIR, TASK_OFFSETS, binding, fixed_recipe, json_write, load_native_runs, now_utc, sha256_file, software, verify_raw_files)


def audit_metadata(data_dir: Path) -> dict:
    files, provenance = verify_raw_files(data_dir)
    prior = json.loads(PRIOR_AUDIT.read_text(encoding="utf-8"))
    if prior.get("raw_hashes_verified") is not True or prior.get("n_runs") != 108 or prior.get("n_all_four_class_trials") != 5184:
        raise ValueError("Prior Q15 full source audit is not the expected frozen inventory")
    prior_files = {row["file_id"]: row for row in prior["files"]}
    expected = pd.read_csv(Q8_METADATA).sort_values("sample_id").reset_index(drop=True)
    if len(expected) != 5184 or expected.sample_id.duplicated().any():
        raise ValueError("Frozen Q8 metadata inventory is not 5,184 unique four-class trials")
    trial_rows, all_gaps, enriched_files = [], [], []
    for record in files:
        path = Path(record["path"])
        runs = load_native_runs(path)
        summaries = []
        previous = prior_files[record["file_id"]]
        if previous["sha256"] != record["sha256"] or previous["subject"] != record["subject"] or previous["session"] != record["session"]:
            raise ValueError("Prior Q15 file identity/provenance differs")
        for run in runs:
            run_index = run["run"]
            old = previous["runs"][run_index]
            if old["run"] != run_index or old["n_native_samples"] != run["X"].shape[0] or old["trial_samples_matlab_one_based"] != run["trial"].tolist() or old["native_artifact_flags"] != run["artifacts"].tolist() or old["native_eeg_channel_names"] != list(CHANNELS):
                raise ValueError(f"Q15 frozen run metadata differs: {path.name}/run{run_index}")
            starts = run["trial"] - 1
            cues = starts + 500
            gaps = run["prior_nominal_imagery_gap_samples"]
            all_gaps.extend(gaps.tolist())
            for trial, (start, label, artifact) in enumerate(zip(starts, run["y"], run["artifacts"]), 1):
                trial_rows.append({"sample_id": f"s{record['subject']:02d}_{record['session']}_r{run_index}_t{trial:02d}", "subject": record["subject"], "session": record["session"], "run": run_index, "trial": trial, "label": int(label), "event_sample": int(start), "artifact_flagged": bool(artifact)})
            summaries.append({
                "run": run_index, "native_struct_index_zero_based": run["native_struct_index_zero_based"], "native_struct_index_matlab_one_based": run["native_struct_index_matlab_one_based"], "native_total_structs": run["native_total_structs"],
                "n_native_samples": run["X"].shape[0], "native_sampling_rate_hz": 250, "native_eeg_channel_names": list(CHANNELS), "native_channels_count": 25, "n_native_eeg_channels": 22, "n_native_eog_channels_skipped": 3,
                "native_class_names_in_code_order": run["classes"], "native_raw_class_names_in_code_order": run["raw_class_names"], "native_class_field_shape_after_scipy_simplify_cells": run["class_field_shape_after_scipy_simplify_cells"], "class_counts": {str(k): int(v) for k, v in sorted(Counter(run["y"].tolist()).items())}, "n_trials": 48,
                "trial_samples_matlab_one_based": run["trial"].tolist(), "trial_samples_zero_based": starts.tolist(), "cue_samples_zero_based": cues.tolist(), "native_class_codes": run["y"].tolist(), "native_artifact_flags": run["artifacts"].tolist(),
                "baseline_start_samples_zero_based": (starts + BASELINE_OFFSETS[0]).tolist(), "baseline_stop_samples_exclusive": (starts + BASELINE_OFFSETS[1]).tolist(), "task_start_samples_zero_based": (starts + TASK_OFFSETS[0]).tolist(), "task_stop_samples_exclusive": (starts + TASK_OFFSETS[1]).tolist(),
                "fixed_window_unavailable_trials": 0, "baseline_previous_nominal_imagery_overlap_trials": 0, "first_trial_has_no_previous_trial_in_run": True,
                "baseline_gap_after_previous_nominal_cue_plus_4s_samples": gaps.tolist(), "minimum_baseline_gap_after_previous_nominal_imagery_s": float(gaps.min() / 250),
            })
        enriched_files.append({**record, "runs": summaries})
        print(f"Metadata checked {path.name}: six labeled runs, no power computed", flush=True)
    actual = pd.DataFrame(trial_rows).sort_values("sample_id").reset_index(drop=True)
    pd.testing.assert_frame_equal(actual[expected.columns], expected, check_dtype=False)
    artifacts = int(actual.artifact_flagged.sum())
    binary_artifacts = int(actual.loc[actual.label.isin([1, 2]), "artifact_flagged"].sum())
    if len(actual) != 5184 or artifacts != 488 or binary_artifacts != 246 or len(all_gaps) != 5076:
        raise ValueError("Frozen full/binary/artifact/previous-trial count differs")
    return {
        "schema_version": 1, "analysis_id": "Q16-P001-BNCI-20261006", "created_at_utc": now_utc(), "status": "metadata_passed_before_raw_power", "dataset": "BNCI2014_001", "metadata_only": True,
        "raw_power_computed": False, "performance_metrics_computed": False, "model_predictions_computed": False, "new_decoder_fits": 0, "new_decoder_inference": 0,
        "raw_hashes_verified": True, "signal_amplitude_finiteness_audited_in_metadata_phase": False, "signal_finite_guard_scope_at_analysis": "all 22 EEG channels in each fixed baseline/task window; EOG excluded", "official_provider_inventory_independently_authenticated_by_this_script": False, "raw_hash_comparison_basis": "current persisted raw receipt matched to Q15 persisted original-file receipt; not a new provider checksum authentication",
        "n_files": 18, "n_labeled_runs": 108, "n_subjects": 9, "n_sessions": 18, "n_all_four_class_trials": 5184, "n_binary_trials": 2592,
        "class_counts": {CLASS_MAP[k]: int(v) for k, v in sorted(Counter(actual.label.tolist()).items())}, "n_artifact_flagged_all_classes": artifacts, "n_artifact_flagged_binary": binary_artifacts,
        "n_trial_with_fixed_windows_unavailable": 0, "n_baseline_previous_nominal_imagery_overlaps": 0, "n_previous_trial_checks": len(all_gaps), "n_first_trials_without_previous_in_run": 108, "minimum_gap_after_previous_nominal_imagery_samples": min(all_gaps), "minimum_gap_after_previous_nominal_imagery_s": min(all_gaps) / 250,
        "event_map_matches_frozen_Q8_metadata": True, "event_samples_match_frozen_Q8_metadata": True, "artifact_flags_match_frozen_Q8_metadata": True, "metadata_channel_mapping_basis": "provider fixed 22-EEG montage plus frozen Q8/Q15 channel map; native MAT lacks per-column names",
        "recipe": fixed_recipe(), "raw_receipt": provenance, "prior_Q15_raw_receipt": binding(Q15_RAW_RECEIPT), "prior_Q15_metadata_audit": binding(PRIOR_AUDIT), "frozen_Q8_trial_metadata": binding(Q8_METADATA), "files": enriched_files,
        "auditor_code_files": [binding(ROOT / "scripts/q16_common.py"), binding(Path(__file__))], "software": software(), "command": sys.argv,
    }


def prepare_freeze(output: Path, audit_path: Path, protocols: list[Path]) -> dict:
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("status") != "metadata_passed_before_raw_power" or audit.get("raw_power_computed") is not False:
        raise ValueError("Passed metadata-only receipt required to prepare freeze")
    manifest = {"schema_version": 1, "analysis_id": "Q16-P001-BNCI-20261006", "status": "frozen_before_raw_power", "created_at_utc": now_utc(), "recipe": fixed_recipe(),
                "code_files": [binding(ROOT / f"scripts/{name}") for name in ("q16_common.py", "q16_metadata_audit.py", "q16_bnci_analysis.py")],
                "input_files": [binding(p) for p in (RAW_RECEIPT, Q15_RAW_RECEIPT, PRIOR_AUDIT, Q8_METADATA, PERFORMANCE, PERFORMANCE_VALIDATION, audit_path)], "protocol_files": [binding(p) for p in protocols],
                "metadata_audit": binding(audit_path), "raw_files": [{k: r[k] for k in ("file_id", "sha256", "bytes")} for r in audit["files"]],
                "execution_gate": "Commit this manifest and all bound files, then pass that full commit SHA to --freeze-commit; raw power remains unauthorized until the parent explicitly runs --execute."}
    manifest.update({"protocol_sha256": manifest["protocol_files"][0]["sha256"], "code_sha256": {r["path"]: r["sha256"] for r in manifest["code_files"]}, "raw_receipt_sha256": sha256_file(RAW_RECEIPT), "metadata_audit_sha256": sha256_file(audit_path), "methodology": fixed_recipe(), "expected": {"raw_files": 18, "labeled_runs": 108, "all_four_class_trials": 5184, "binary_trials": 2592}, "new_decoder_fits": 0, "new_checkpoint_inference": 0})
    json_write(output, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--output", type=Path, default=RUN_DIR / "metadata_audit.json")
    parser.add_argument("--prepare-freeze", type=Path, help="Write freeze manifest after a passed metadata-only audit; computes no power")
    parser.add_argument("--protocol", type=Path, action="append", default=[], help="Written fixed protocol/amendment; repeat to bind multiple files")
    args = parser.parse_args()
    if args.prepare_freeze:
        if not args.protocol:
            parser.error("--prepare-freeze requires at least one --protocol")
        prepare_freeze(args.prepare_freeze, args.output, args.protocol)
        print(f"Prepared freeze manifest: {args.prepare_freeze.resolve()}; commit required before calculation")
        return
    if args.data_dir is None:
        parser.error("--data-dir is required for metadata-only raw audit")
    try:
        result = audit_metadata(args.data_dir)
    except Exception as exc:
        json_write(args.output, {"schema_version": 1, "analysis_id": "Q16-P001-BNCI-20261006", "status": "metadata_blocked_no_raw_power", "metadata_only": True, "raw_power_computed": False, "new_decoder_fits": 0, "new_decoder_inference": 0, "created_at_utc": now_utc(), "blocking_reason": f"{type(exc).__name__}: {exc}", "auditor_code_files": [binding(ROOT / "scripts/q16_common.py"), binding(Path(__file__))]})
        raise
    json_write(args.output, result)
    print(f"Passed metadata-only gate: {args.output.resolve()}")


if __name__ == "__main__":
    main()
