#!/usr/bin/env python3
"""Future paired analysis of immutable predictions; currently tested on fixtures only.

No fitting or inference occurs here. Real-data scoring requires a locked event
inventory and verified audit receipts; absence of a gate cannot be repaired by a
favourable p-value. See STATISTICAL_ANALYSIS_PLAN.md for the estimands.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import t


ARCHITECTURES = ("broad", "shared")
SELECTORS = ("fixed", "mean_loss", "mean_rank")
SEEDS = (20261013, 20261014, 20261015)
REQUIRED_GATES = ("raw_metadata_audit", "task_label_and_qc_audit",
                  "participant_independence_audit", "author_prior_exposure_attestation",
                  "prospective_protocol_freeze", "source_only_checkpoint_audit",
                  "independent_prediction_validation")
BOOTSTRAPS = 20000
BOOTSTRAP_SEED = 20261016
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class ValidationError(ValueError):
    pass


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValidationError(code)


def integer(value, field: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool)
            or isinstance(value, str) and re.fullmatch(r"-?[0-9]+", value) is not None,
            f"invalid_integer:{field}")
    return int(value)


def validate_contract(contract: dict, allow_synthetic: bool) -> tuple[list[str], dict]:
    require(isinstance(contract, dict), "contract_object_required")
    synthetic = contract.get("synthetic_fixture") is True
    require(not synthetic or allow_synthetic, "synthetic_fixture_requires_explicit_flag")
    people = contract.get("participants")
    require(isinstance(people, list) and len(people) >= 3, "expected_roster_missing_or_too_small")
    require(all(isinstance(p, str) and p for p in people), "invalid_participant_id")
    require(len(set(people)) == len(people), "duplicate_expected_participant")
    require(contract.get("seeds") == list(SEEDS), "seed_contract_mismatch")
    require(contract.get("architectures") == list(ARCHITECTURES), "architecture_contract_mismatch")
    require(contract.get("selectors") == list(SELECTORS), "selector_contract_mismatch")
    require(contract.get("label_map") == {"0": "left_hand_MI", "1": "right_hand_MI"},
            "label_map_contract_mismatch")
    if not synthetic:
        require(contract.get("cohort_id") == "Dreyer2023", "wrong_primary_cohort")
        require(len(people) <= 85, "eligibility_ceiling_exceeded")
        require(not {"A17", "A41"}.intersection(people), "known_electrode_order_exclusion_in_roster")
        require({"A17", "A41"}.issubset(set(contract.get("technical_exclusions", []))),
                "required_technical_exclusion_record_missing")
    events = {}
    fingerprints = set()
    classes = defaultdict(set)
    class_counts = defaultdict(lambda: {0: 0, 1: 0})
    require(isinstance(contract.get("events"), list), "expected_events_missing")
    for item in contract["events"]:
        require(isinstance(item, dict), "expected_event_object_required")
        person, event = item.get("subject_id"), item.get("event_id")
        require(person in people and isinstance(event, str) and event, "invalid_expected_event")
        key = (person, event)
        require(key not in events, "duplicate_expected_event")
        label = integer(item.get("ytrue"), "expected_ytrue")
        require(label in (0, 1), "nonbinary_expected_label")
        fingerprint = item.get("epoch_sha256")
        require(isinstance(fingerprint, str) and HASH_PATTERN.fullmatch(fingerprint) is not None,
                "expected_epoch_fingerprint_missing_or_invalid")
        require(fingerprint not in fingerprints, "duplicate_expected_eeg_window")
        fingerprints.add(fingerprint)
        classes[person].add(label)
        class_counts[person][label] += 1
        events[key] = (label, fingerprint)
    require(set(classes) == set(people), "expected_roster_event_coverage_mismatch")
    require(all(classes[p] == {0, 1} for p in people), "both_classes_required_for_ba")
    if not synthetic:
        require(all(class_counts[p][c] >= 20 for p in people for c in (0, 1)),
                "fewer_than_twenty_locked_trials_per_class")
    return people, events


def verify_gate_manifest(manifest: dict, base_dir: Path, contract_sha256: str,
                         predictions_sha256: str) -> dict:
    """Validate receipt identity, not reinterpret the scientific judgments in it."""
    require(isinstance(manifest, dict), "gate_manifest_object_required")
    require(isinstance(manifest.get("gates"), dict), "gate_receipts_object_required")
    require(isinstance(manifest.get("checkpoints"), list), "checkpoint_manifest_list_required")
    failures = []
    if manifest.get("locked_contract_sha256") != contract_sha256:
        failures.append("locked_contract_hash_mismatch")
    if manifest.get("predictions_sha256") != predictions_sha256:
        failures.append("prediction_artifact_hash_mismatch")
    for name in REQUIRED_GATES:
        gate = manifest.get("gates", {}).get(name, {})
        if not isinstance(gate, dict):
            failures.append(f"gate_receipt_invalid:{name}")
            continue
        if gate.get("passed") is not True:
            failures.append(f"gate_not_passed:{name}")
            continue
        path_value = gate.get("evidence_file")
        expected = gate.get("sha256")
        if not isinstance(path_value, str) or not isinstance(expected, str) or not HASH_PATTERN.fullmatch(expected):
            failures.append(f"gate_receipt_invalid:{name}")
            continue
        path = base_dir / path_value
        if not path.is_file() or digest(path) != expected:
            failures.append(f"gate_receipt_hash_mismatch:{name}")
            continue
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            failures.append(f"gate_receipt_unreadable:{name}")
            continue
        if (not isinstance(receipt, dict) or receipt.get("gate_name") != name
                or receipt.get("passed") is not True
                or receipt.get("locked_contract_sha256") != contract_sha256):
            failures.append(f"gate_receipt_judgment_or_identity_mismatch:{name}")
        if (name == "independent_prediction_validation"
                and receipt.get("predictions_sha256") != predictions_sha256):
            failures.append("independent_prediction_receipt_artifact_mismatch")
    manifests = manifest.get("checkpoints", [])
    expected_cells = {(a, r, s) for a in ARCHITECTURES for r in SELECTORS for s in SEEDS}
    seen = set()
    for item in manifests:
        if not isinstance(item, dict):
            failures.append("checkpoint_manifest_item_invalid")
            continue
        key = (item.get("model_arch"), item.get("selector"), item.get("seed"))
        if key not in expected_cells or key in seen:
            failures.append("checkpoint_coverage_duplicate_or_invalid")
        seen.add(key)
        if (item.get("source_only") is not True or type(item.get("target_fit_count")) is not int
                or item.get("target_fit_count") != 0):
            failures.append("checkpoint_source_only_policy_unverified")
        sha = item.get("checkpoint_sha256")
        if not isinstance(sha, str) or not HASH_PATTERN.fullmatch(sha):
            failures.append("checkpoint_identity_missing")
        path_value = item.get("checkpoint_file")
        if not isinstance(path_value, str) or not path_value:
            failures.append("checkpoint_file_missing")
        elif not (base_dir / path_value).is_file() or digest(base_dir / path_value) != sha:
            failures.append("checkpoint_file_hash_mismatch")
    if seen != expected_cells:
        failures.append("checkpoint_condition_seed_coverage_mismatch")
    return {"receipt_manifest_checked": True, "locked_contract_sha256": contract_sha256,
            "predictions_sha256": predictions_sha256,
            "checkpoint_identities": [{"model_arch": item.get("model_arch"),
                                       "selector": item.get("selector"), "seed": item.get("seed"),
                                       "checkpoint_sha256": item.get("checkpoint_sha256")}
                                      for item in manifests if isinstance(item, dict)],
            "independent_confirmation_ready": not failures, "failures": sorted(set(failures)),
            "basis": "locked input hashes, declared passed audit receipts and checkpoint identity coverage;"
                     " scientific judgments remain those of the cited audit authors"}


def validate_prediction_rows(rows: list[dict], people: list[str], events: dict,
                             checkpoint_identities: list[dict] | None = None) -> dict:
    expected_cells = {(p, a, r, s, e) for p, e in events for a in ARCHITECTURES
                      for r in SELECTORS for s in SEEDS}
    cells = {}
    condition_checkpoints = {}
    expected_checkpoints = {(item["model_arch"], item["selector"], item["seed"]): item["checkpoint_sha256"]
                            for item in checkpoint_identities or []}
    for row in rows:
        require(isinstance(row, dict), "prediction_row_object_required")
        person, event = row.get("subject_id"), row.get("event_id")
        arch, rule = row.get("model_arch"), row.get("selector")
        seed = integer(row.get("seed"), "seed")
        key = (person, arch, rule, seed, event)
        require(key in expected_cells, "unexpected_participant_condition_seed_or_event")
        require(key not in cells, "duplicate_prediction_cell")
        actual_label, prediction = integer(row.get("ytrue"), "ytrue"), integer(row.get("ypred"), "ypred")
        expected_label, expected_fingerprint = events[(person, event)]
        require(actual_label == expected_label, "ground_truth_mismatch_with_locked_inventory")
        require(row.get("epoch_sha256") == expected_fingerprint, "eeg_window_fingerprint_mismatch")
        require(prediction in (0, 1), "nonbinary_prediction")
        try:
            probabilities = np.asarray([float(row["p_left"]), float(row["p_right"])])
        except (KeyError, ValueError, TypeError):
            raise ValidationError("binary_probabilities_missing_or_invalid") from None
        require(np.isfinite(probabilities).all(), "nonfinite_probability")
        require(((probabilities >= 0) & (probabilities <= 1)).all(), "probability_out_of_range")
        require(abs(float(probabilities.sum()) - 1.0) <= 1e-6, "probabilities_not_normalized")
        require(prediction == int(np.argmax(probabilities)), "prediction_not_probability_argmax")
        checkpoint = row.get("checkpoint_sha256")
        require(isinstance(checkpoint, str) and HASH_PATTERN.fullmatch(checkpoint) is not None,
                "prediction_checkpoint_identity_missing")
        condition = (arch, rule, seed)
        require(condition not in condition_checkpoints or condition_checkpoints[condition] == checkpoint,
                "multiple_checkpoints_for_same_condition_seed")
        if checkpoint_identities is not None:
            require(expected_checkpoints.get(condition) == checkpoint,
                    "prediction_checkpoint_mismatch_with_manifest")
        condition_checkpoints[condition] = checkpoint
        cells[key] = (actual_label, prediction)
    require(set(cells) == expected_cells, "incomplete_prediction_coverage")
    return cells


def paired_stats(values: np.ndarray, bootstrap_indices: np.ndarray, alpha: float = 0.05) -> dict:
    values = np.asarray(values, dtype=float)
    require(values.ndim == 1, "paired_difference_vector_must_be_one_dimensional")
    n = len(values)
    require(n >= 3 and np.isfinite(values).all(), "invalid_participant_difference_vector")
    require(0 < alpha < 1, "invalid_interval_alpha")
    bootstrap_indices = np.asarray(bootstrap_indices)
    require(bootstrap_indices.ndim == 2 and bootstrap_indices.shape[0] > 0
            and bootstrap_indices.shape[1] == n and np.issubdtype(bootstrap_indices.dtype, np.integer)
            and (bootstrap_indices >= 0).all() and (bootstrap_indices < n).all(),
            "invalid_paired_participant_bootstrap_indices")
    mean, sd = float(values.mean()), float(values.std(ddof=1))
    bootstrap = values[bootstrap_indices].mean(axis=1)
    boot_interval = np.quantile(bootstrap, [0.025, 0.975]).tolist()
    common = {"participants_n": n, "mean_difference_pp": mean, "paired_sd_pp": sd,
              "median_difference_pp": float(np.median(values)), "minimum_pp": float(values.min()),
              "maximum_pp": float(values.max()), "participant_differences_pp": values.tolist(),
              "leave_one_participant_out_mean_pp": ((values.sum() - values) / (n - 1)).tolist(),
              "bootstrap_95_percentile_interval_pp": boot_interval}
    if np.ptp(values) == 0 or sd == 0:
        # A point bootstrap at zero empirical variance does not establish precise
        # population uncertainty or license an infinite t statistic with p=0.
        return common | {"test_status": "degenerate_zero_variance", "t_statistic": None,
                         "degrees_of_freedom": n - 1, "p_two_sided": None, "t_interval_pp": None,
                         "interval_alpha": alpha, "bootstrap_interval_degenerate": True}
    standard_error = sd / math.sqrt(n)
    statistic = mean / standard_error
    critical = float(t.ppf(1 - alpha / 2, n - 1))
    return common | {"test_status": "valid_under_paired_t_assumptions", "t_statistic": statistic,
                     "degrees_of_freedom": n - 1, "p_two_sided": float(2 * t.sf(abs(statistic), n - 1)),
                     "t_interval_pp": [mean - critical * standard_error, mean + critical * standard_error],
                     "interval_alpha": alpha, "bootstrap_interval_degenerate": False}


def holm_adjust(p_values: list[float | None]) -> list[float | None]:
    require(all(p is None or math.isfinite(p) and 0 <= p <= 1 for p in p_values), "invalid_p_value")
    m = len(p_values)
    working = [1.0 if p is None else p for p in p_values]
    order = sorted(range(m), key=lambda i: working[i])
    adjusted = [None] * m
    running_max = 0.0
    for rank, index in enumerate(order):
        running_max = max(running_max, (m - rank) * working[index])
        if p_values[index] is not None:
            adjusted[index] = min(1.0, running_max)
    return adjusted


def analyze_records(rows: list[dict], contract: dict, readiness: dict | None = None,
                    allow_synthetic: bool = False) -> dict:
    people, events = validate_contract(contract, allow_synthetic)
    synthetic = contract.get("synthetic_fixture") is True
    ready = (readiness is not None and readiness.get("receipt_manifest_checked") is True
             and readiness.get("independent_confirmation_ready") is True
             and readiness.get("failures") == [])
    require(synthetic or ready, "audit_gates_not_passed_no_real_data_scoring")
    cells = validate_prediction_rows(rows, people, events,
                                     readiness.get("checkpoint_identities") if ready else None)
    participant_scores = []
    by_condition = defaultdict(dict)
    for person in people:
        participant_events = [event for p, event in events if p == person]
        for arch in ARCHITECTURES:
            for rule in SELECTORS:
                seed_scores, seed_dominance, seed_dominant_classes, seed_class_recalls = [], [], [], []
                for seed in SEEDS:
                    selected = [cells[(person, arch, rule, seed, event)] for event in participant_events]
                    truth, predictions = np.asarray(selected).T
                    recalls = [float((predictions[truth == c] == c).mean()) for c in (0, 1)]
                    ba = 0.5 * sum(recalls)
                    class_counts = np.bincount(predictions, minlength=2)
                    seed_scores.append(100 * ba)
                    seed_class_recalls.append(recalls)
                    seed_dominance.append(float(class_counts.max() / len(predictions)))
                    seed_dominant_classes.append(int(class_counts.argmax()))
                row = {"subject_id": person, "model_arch": arch, "selector": rule,
                       "eligible_trials": len(participant_events), "seed_ba_pp": seed_scores,
                       "balanced_accuracy_pp": float(np.mean(seed_scores)),
                       "seed_class_recalls": seed_class_recalls,
                       "seed_prediction_dominance": seed_dominance,
                       "seed_dominant_class": seed_dominant_classes,
                       "mean_seed_prediction_dominance": float(np.mean(seed_dominance)),
                       "class_dominance_flag": float(np.mean(seed_dominance)) >= 0.95}
                participant_scores.append(row)
                by_condition[(arch, rule)][person] = row["balanced_accuracy_pp"]
    bootstrap_indices = np.random.default_rng(BOOTSTRAP_SEED).integers(0, len(people), (BOOTSTRAPS, len(people)))

    def differences(first: tuple, second: tuple) -> np.ndarray:
        return np.asarray([by_condition[first][p] - by_condition[second][p] for p in people])

    primary = paired_stats(differences(("broad", "mean_rank"), ("broad", "mean_loss")), bootstrap_indices)
    primary["contrast"] = "broad_mean_rank_minus_mean_loss"
    nominal_reject = primary["p_two_sided"] is not None and primary["p_two_sided"] < 0.05
    confirmatory_primary = ready and not synthetic and nominal_reject
    secondary_specs = (("broad_fixed_minus_mean_loss", ("broad", "fixed"), ("broad", "mean_loss")),
                       ("broad_fixed_minus_mean_rank", ("broad", "fixed"), ("broad", "mean_rank")),
                       ("shared_fixed_minus_broad_fixed", ("shared", "fixed"), ("broad", "fixed")))
    secondary = []
    for name, first, second in secondary_specs:
        delta = differences(first, second)
        stats = paired_stats(delta, bootstrap_indices)
        simultaneous = paired_stats(delta, bootstrap_indices, alpha=0.05 / 3)
        secondary.append(stats | {"contrast": name, "ordinary_95_interval_multiplicity_adjusted": False,
                                  "bonferroni_simultaneous_interval_pp": simultaneous["t_interval_pp"]})
    corrected = holm_adjust([r["p_two_sided"] for r in secondary])
    for stats, corrected_p in zip(secondary, corrected):
        stats["holm_adjusted_p"] = corrected_p
        stats["confirmatory_rejected"] = bool(confirmatory_primary and corrected_p is not None and corrected_p < 0.05)
    for stats in secondary:
        stats["nominal_threshold_passed"] = stats["p_two_sided"] is not None and stats["p_two_sided"] < 0.05
        stats["confirmation_role"] = "synthetic_only" if synthetic else (
            "prespecified_secondary_confirmation" if confirmatory_primary else "gate_closed_estimation_only")
    descriptive_conditions = []
    for arch in ARCHITECTURES:
        for rule in SELECTORS:
            selected = [row for row in participant_scores
                        if row["model_arch"] == arch and row["selector"] == rule]
            scores = np.asarray([row["balanced_accuracy_pp"] for row in selected])
            flags = sum(row["class_dominance_flag"] for row in selected)
            descriptive_conditions.append({"model_arch": arch, "selector": rule,
                                           "participants_n": len(people),
                                           "participant_mean_ba_pp": float(scores.mean()),
                                           "class_dominance_flag_count": flags,
                                           "class_dominance_flag_fraction": flags / len(people),
                                           "below_chance_ba_count": int((scores < 50).sum()),
                                           "minimum_participant_ba_pp": float(scores.min()),
                                           "tenth_percentile_participant_ba_pp": float(np.quantile(scores, 0.1)),
                                           "role": "descriptive_not_confirmatory"})
    return {"schema_version": 1, "results_role": "synthetic_planning_only" if synthetic else "independent_confirmatory_analysis",
            "cohort_id": contract.get("cohort_id"), "participants_n": len(people), "participant_order": people,
            "participant_seed_unit": "participant after equal mean over the three final seeds",
            "primary": primary | {"statistical_threshold_passed": nominal_reject,
                                   "confirmatory_rejected": bool(confirmatory_primary)},
            "secondary_confirmation_gate_open": bool(confirmatory_primary),
            "secondary_family": secondary, "participant_scores": participant_scores,
            "condition_descriptives": descriptive_conditions,
            "bootstrap_replicates": BOOTSTRAPS, "bootstrap_rng_seed": BOOTSTRAP_SEED,
            "equivalence_or_noninferiority_established": False, "model_fits_started_by_analysis": 0,
            "software_gate_status_is_not_scientific_independence_certification": True,
            "target_predictions_computed_by_analysis": False, "readiness": readiness,
            "limitations": ["Paired-t Gaussian/independent-participant assumptions apply.",
                            "Inference is conditional on the frozen source models.",
                            "Matched-duration architecture contrasts are complete pipelines.",
                            "Nonsignificance cannot establish equivalence."]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--gates", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-synthetic-fixture", action="store_true")
    args = parser.parse_args()
    try:
        contract = json.loads(args.contract.read_text(encoding="utf-8"))
        validate_contract(contract, args.allow_synthetic_fixture)
        readiness = None
        if args.gates:
            manifest = json.loads(args.gates.read_text(encoding="utf-8"))
            readiness = verify_gate_manifest(manifest, args.gates.parent, digest(args.contract), digest(args.predictions))
        require(contract.get("synthetic_fixture") is True
                or readiness is not None and readiness["independent_confirmation_ready"],
                "audit_gates_not_passed_no_real_data_scoring")
        with args.predictions.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        result = analyze_records(rows, contract, readiness, args.allow_synthetic_fixture)
        result["contract_sha256"] = digest(args.contract)
        result["predictions_sha256"] = digest(args.predictions)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({"status": "analysis_written", "results_role": result["results_role"],
                          "participants_n": result["participants_n"], "confirmation_gate_open": result["secondary_confirmation_gate_open"]}))
    except (ValidationError, KeyError, TypeError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "blocked_no_validated_analysis", "error_code": str(error),
                          "model_fits_started": 0, "target_predictions_computed": False}))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
