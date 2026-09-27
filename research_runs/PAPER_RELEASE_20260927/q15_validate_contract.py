"""Offline Q15 *plan* checks; never a raw-EEG or scientific validator.

This module deliberately cannot issue a scientific ``passed`` receipt. Its
optional metadata-receipt helper checks shape and fail-closed requirements,
but only an independent audit of the actual provider files can verify bytes,
cue timing, or electrode identity.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = Path(__file__).resolve().with_name("Q15_CONTRACT.json")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_contract(contract_path: Path = CONTRACT, root: Path = ROOT) -> dict:
    plan = _read(contract_path)
    q14 = _read(root / plan["historical_q14_config"])
    _require(plan["schema_version"] == 1, "Unknown Q15 contract schema")
    _require(plan["status"] == "prepared_metadata_and_source_freeze_pending", "Q15 plan status overclaims execution")
    concern = plan["source_of_channel_concern"]
    _require(concern["moabb_version"] == "v1.7.2", "Lee metadata source version drifted")
    _require(concern["raw_file_confirmation"] is False, "Catalogue evidence cannot assert raw confirmation")
    _require(concern["catalogue_missing_from_q14"] == ["FCz"], "Lee FCz concern changed")
    _require(set(concern["existing_22_channel_lee_arms"]) == {"Q15-E001", "Q15-E004"}, "Old Lee arms are not retained as blocked")
    _require(concern["disposition"] == "blocked_pending_raw_metadata_audit", "Old Lee arms must fail closed")
    q14_channels = q14["channels"]
    _require(q14_channels.count("FCz") == 1 and len(q14_channels) == 22, "Frozen Q14 channel contract changed")

    audits = plan["metadata_audits"]
    _require({item["id"] for item in audits} == {"Q15-V001", "Q15-V002"}, "Missing Q15 metadata audit")
    expected = {"Lee2019_MI": (54, 2), "Cho2017": (52, 1)}
    _require({item["dataset"] for item in audits} == set(expected), "Q15 dataset set changed")
    for audit in audits:
        _require((audit["expected_subjects"], audit["expected_sessions_per_subject"]) == expected[audit["dataset"]], "Unexpected documented cohort size")
        _require(audit["status"] == "not_executed", "Metadata audit overclaims execution")

    arm = plan["new_source_arm"]
    _require(arm["id"] == "Q15-E005" and arm["dataset"] == "BNCI2014_001", "Q15 source identity changed")
    _require(arm["implementation_status"] == "local_source_runner_synthetic_checks_only_real_raw_adapter_and_independent_source_validator_pending", "Q15 implementation overclaims readiness")
    _require(arm["channels"] == [channel for channel in q14_channels if channel != "FCz"], "Q15 21-channel order must be Q14 minus FCz only")
    _require(arm["channel_rule"] == "Q14_order_minus_FCz_only_before_training", "Channel rule changed")
    _require(arm["subject_ids"] == q14["source_subjects"], "Q15 source subjects changed")
    _require(arm["cue_window_s_half_open"] == [0.5, 2.5], "2-second cue window changed")
    _require(arm["common_sampling_rate_hz"] == q14["common_rate_hz"] == 160, "Common sampling rate changed")
    _require(arm["n_times"] == 320, "Expected exactly 320 samples")
    _require(arm["frequency_bands_hz"] == q14["bands_hz"], "Frequency bands changed")
    _require({key: arm["filter"][key] for key in ("order", "ftype", "phase")} == q14["filter"], "Frozen Q14 filter parameters changed")
    _require(arm["filter"]["scope"] == "run_local", "Filtering scope changed")
    for field in ("artifact_policy", "selection_seed", "final_seeds", "max_epochs", "batch_size", "learning_rate", "weight_decay", "source_only_epoch_rule"):
        _require(arm[field] == q14[field], f"Frozen Q14 {field} changed")
    _require(arm["source_only_inner_groups"] == q14["q14_e002_inner_groups"], "Source-only inner groups changed")
    _require(arm["neural_models"] == ["BROAD_EEGNET", "MU_BETA_SHARED"], "Neural arms changed")
    _require(arm["shallow_models"] == ["CSP4_LDA"], "Shallow arm changed")
    _require(arm["architecture_changes_from_q14"] == {"n_chans": 21, "n_times": 320}, "Architecture changes exceed required input dimensions")
    _require(arm["new_deep_fits"] == len(arm["neural_models"]) * (len(arm["source_only_inner_groups"]) + len(arm["final_seeds"])) , "Q15 deep fit arithmetic changed")
    _require(arm["new_shallow_fits"] == 1 and arm["external_target_fits"] == 0, "Q15 shallow/target fit arithmetic changed")
    _require(arm["status"] == "conditional_not_executed", "Q15 source arm overclaims execution")

    external = plan["external_arms"]
    _require({(item["id"], item["dataset"]) for item in external} == {("Q15-E006", "Cho2017"), ("Q15-E007", "Lee2019_MI")}, "External arms changed")
    for item in external:
        _require(item["source_arm"] == "Q15-E005" and item["new_model_fits"] == 0 and item["target_fits"] == 0, "External fit policy changed")
        _require(item["status"] == "conditional_not_executed", "External arm overclaims execution")
    _require(plan["readiness"] == "not_ready_for_external_prediction_until_real_raw_audits_source_fit_validation_and_checkpoint_freeze_pass", "Readiness overclaims execution")
    return {
        "status": "q15_contract_internally_consistent_not_scientific_validation",
        "metadata_audits_completed": 0,
        "new_source_deep_fits_planned": arm["new_deep_fits"],
        "new_source_shallow_fits_planned": arm["new_shallow_fits"],
        "external_target_fits_allowed": 0,
        "external_prediction_authorized": False,
    }


def validate_metadata_receipt(receipt: dict, cohort_spec: dict, required_channels: list[str]) -> dict:
    """Structural gate for a future metadata-only receipt, not raw-byte replay.

    The complete provider inventory and each raw hash must later be checked
    independently against the actual files. This helper never authorizes
    model inference, even when it returns normally.
    """
    _require(receipt.get("dataset") == cohort_spec["dataset"], "Dataset identity mismatch")
    _require(receipt.get("metadata_only") is True, "Receipt is not metadata-only")
    _require(receipt.get("predictions_computed") is False, "Target predictions already inspected")
    _require(receipt.get("model_predictions_computed") is False, "Target model predictions already inspected")
    _require(receipt.get("performance_metrics_computed") is False, "Target scores already inspected")
    _require(receipt.get("target_fits") == 0, "Target fitting is prohibited")
    for field in ("provider_version", "loader_version", "license", "provider_inventory_source"):
        _require(isinstance(receipt.get(field), str) and bool(receipt[field].strip()), f"Missing {field}")
    _require(receipt.get("all_expected_files_hashed") is True, "Expected files not all hashed")
    _require(receipt.get("failed_files") == [], "A missing or corrupt file blocks the cohort")
    expected_ids = receipt.get("expected_file_ids")
    files = receipt.get("files")
    _require(isinstance(expected_ids, list) and expected_ids and len(expected_ids) == len(set(expected_ids)), "Bad expected file inventory")
    _require(isinstance(files, list) and files, "No audited files")
    _require({item.get("file_id") for item in files} == set(expected_ids) and len(files) == len(expected_ids), "Observed files differ from provider inventory")
    subjects: dict[int, set[str]] = defaultdict(set)
    triple_ids: set[tuple[int, str, str]] = set()
    for item in files:
        _require(SHA256.fullmatch(str(item.get("sha256", ""))) is not None, "Missing raw SHA-256")
        subject = item.get("subject")
        _require(isinstance(subject, int) and not isinstance(subject, bool) and subject > 0, "Bad subject ID")
        session = str(item.get("session", ""))
        run = str(item.get("run", ""))
        _require(bool(session) and bool(run), "Missing session or run ID")
        triple = (subject, session, run)
        _require(triple not in triple_ids, "Duplicate subject/session/run")
        triple_ids.add(triple)
        subjects[subject].add(session)
        channels = item.get("channels")
        _require(isinstance(channels, list) and len(channels) == len(set(channels)), "Missing or duplicate channel metadata")
        _require(set(required_channels).issubset(channels), "Required source channels absent")
        _require(isinstance(item.get("sampling_rate_hz"), (int, float)) and item["sampling_rate_hz"] > 60, "Bad sample rate")
        _require(isinstance(item.get("native_physical_unit"), str) and bool(item["native_physical_unit"].strip()), "Native EEG unit undocumented")
        _require(item.get("loader_output_unit") == "V", "Loader must represent EEG in volts before frozen scaling")
        _require(isinstance(item.get("unit_conversion"), str) and bool(item["unit_conversion"].strip()), "Unit conversion undocumented")
        _require(isinstance(item.get("reference"), str) and bool(item["reference"].strip()), "EEG reference undocumented")
        _require(item.get("cue_origin") == "MI_cue_onset", "MI cue origin unproven")
        _require(item.get("task") == "left_right_motor_imagery" and item.get("labeled") is True, "Run is not labeled left/right MI")
        label_map = item.get("label_map")
        _require(isinstance(label_map, dict) and set(label_map) == {"left_hand", "right_hand"} and len(set(label_map.values())) == 2, "Invalid class mapping")
        available = item.get("available_cue_window_s")
        _require(isinstance(available, list) and len(available) == 2 and available[0] <= 0.5 and available[1] >= 2.5, "2-second MI window not covered")
    required_subjects = set(range(1, cohort_spec["expected_subjects"] + 1))
    _require(set(subjects) == required_subjects, "Subject inventory incomplete or changed")
    _require(all(len(sessions) == cohort_spec["expected_sessions_per_subject"] for sessions in subjects.values()), "Session inventory incomplete")
    return {"status": "metadata_receipt_structurally_valid_raw_replay_still_required", "subjects": len(subjects), "files": len(files), "external_prediction_authorized": False}


if __name__ == "__main__":
    print(json.dumps(validate_contract(), ensure_ascii=False, indent=2))
