#!/usr/bin/env python3
"""Independently recompute stored CSP scores/partitions; do not load any model.

Scientific PASS requires a new read of all original source MAT labels, trial
identities and artifact flags. This validator never fits or invokes inference.
Model/epoch hashes authenticate the execution record, not the absence of every
possible implementation error.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

from cpu_csp_source_audit import (
    ROOT, STUDY, SUBJECTS, PARAMETERS, RAW_PROVENANCE,
    EXECUTION_CONTRACT, ORIGINAL_PROTOCOL,
    array_hash, canonical_hash, now, original_replay_policy, rel,
    runtime_versions, sha, verify_preanalysis, write_json,
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    require(Path(path).is_file() and not Path(path).is_symlink(), f"Required non-symlink file absent: {path}")
    return json.loads(Path(path).read_text())


def read_predictions(path):
    require(Path(path).is_file(), f"Predictions missing: {path}")
    with Path(path).open(newline="") as stream:
        reader = csv.DictReader(stream)
        expected = {"sample_id", "subject", "session", "run", "trial", "label", "artifact_flagged", "prediction", "p_left", "p_right"}
        require(set(reader.fieldnames or ()) == expected, "Stored prediction columns differ")
        rows = list(reader)
    require(bool(rows), "Predictions cannot be empty")
    for row in rows:
        for field in ("subject", "run", "trial", "label", "prediction"):
            row[field] = int(row[field])
        require(row["artifact_flagged"] in {"True", "False"}, "Native artifact indicator changed")
        row["artifact_flagged"] = row["artifact_flagged"] == "True"
        row["p_left"], row["p_right"] = float(row["p_left"]), float(row["p_right"])
        require(row["subject"] in SUBJECTS and row["label"] in (1, 2) and row["prediction"] in (1, 2), "Invalid source label or participant")
        require(all(math.isfinite(row[field]) and 0 <= row[field] <= 1 for field in ("p_left", "p_right")), "Invalid prediction probability")
        require(abs(row["p_left"] + row["p_right"] - 1) <= 1e-10, "Stored class probabilities do not sum to one")
        require(row["prediction"] == (1 if row["p_left"] >= row["p_right"] else 2), "Stored label differs from the binary probability decision")
    require(len({row["sample_id"] for row in rows}) == len(rows), "Duplicate prediction identity")
    return rows


def participant_metrics(rows):
    """Integer confusion counts; no library estimator or trial pseudoreplication."""
    grouped = {}
    for row in rows:
        grouped.setdefault(row["subject"], []).append(row)
    output = []
    for person, selected in sorted(grouped.items()):
        counts = Counter((row["label"], row["prediction"]) for row in selected)
        n_left = counts[1, 1] + counts[1, 2]
        n_right = counts[2, 1] + counts[2, 2]
        require(n_left > 0 and n_right > 0, "Participant lacks one ground-truth hand class")
        recall_left = counts[1, 1] / n_left
        recall_right = counts[2, 2] / n_right
        output.append({"subject": person, "n_trials": len(selected), "n_left": n_left, "n_right": n_right,
                       "left_true_left_pred": counts[1, 1], "left_true_right_pred": counts[1, 2],
                       "right_true_left_pred": counts[2, 1], "right_true_right_pred": counts[2, 2],
                       "recall_left": recall_left, "recall_right": recall_right,
                       "balanced_accuracy_percent": 50 * (recall_left + recall_right),
                       "predicted_left_percent": 100 * sum(row["prediction"] == 1 for row in selected) / len(selected),
                       "median_p_left": statistics.median(row["p_left"] for row in selected)})
    return output


def identity_rows(rows):
    fields = ("sample_id", "subject", "session", "run", "trial", "label", "artifact_flagged")
    return [{field: row[field] for field in fields} for row in rows]


def validate_partition(partition, predictions, held_out, source_records):
    train = partition.get("train_records", [])
    evaluation = partition.get("evaluation_records", [])
    require(partition.get("held_out_subject") == held_out, "Partition held-out identity changed")
    require(bool(train) and bool(evaluation), "Source partitions must be nonempty")
    expected_train = source_records if held_out is None else [row for row in source_records if row["subject"] != held_out]
    expected_eval = source_records if held_out is None else [row for row in source_records if row["subject"] == held_out]
    require(train == expected_train and evaluation == expected_eval, "Partition differs from source identities or label/artifact evidence")
    require(identity_rows(predictions) == identity_rows(evaluation), "Stored prediction identities/labels differ from the evaluation partition")
    train_ids = {row["sample_id"] for row in train}
    eval_ids = {row["sample_id"] for row in evaluation}
    require(len(train_ids) == len(train) and len(eval_ids) == len(evaluation), "Duplicate source partition identities")
    if held_out is not None:
        require(not (train_ids & eval_ids), "Held-out source sample leaked into training")
        require(held_out not in {row["subject"] for row in train}, "Held-out source participant leaked into training")
        require({row["subject"] for row in evaluation} == {held_out}, "Evaluation includes a different source participant")
    return train, evaluation


def native_source_records(data_dir):
    """Read native labels only; no filtering, model loading, fitting or prediction."""
    sys.path.insert(0, str(ROOT / "src"))
    from mi_eeg.data.q15_context import verify_bnci_originals, _validated_bnci_runs
    originals = verify_bnci_originals(Path(data_dir), RAW_PROVENANCE)
    records = []
    for person in SUBJECTS:
        for suffix, session in (("T", "0train"), ("E", "1test")):
            for run_index, run in enumerate(_validated_bnci_runs(originals[f"A{person:02d}{suffix}.mat"])):
                for trial_index, (trial, label, artifact) in enumerate(zip(run["trial"], run["y"], run["artifacts"]), 1):
                    if int(label) in (1, 2):
                        records.append({"sample_id": f"s{person:02d}_{session}_r{run_index}_t{trial_index:02d}",
                                        "subject": person, "session": session, "run": run_index,
                                        "trial": trial_index, "label": int(label),
                                        "event_sample": int(trial) - 1, "artifact_flagged": bool(artifact)})
    require(len(records) == 2592 and len({row["sample_id"] for row in records}) == 2592, "Native binary source trial count differs")
    return records


def validate(output, data_dir):
    output = Path(output).resolve()
    require(output.is_relative_to(STUDY / "results"), "Validation output must belong to the new study")
    config, freeze = verify_preanalysis()
    manifest = read_json(output / "run_manifest.json")
    status = read_json(output / "execution_status.json")
    runtime = read_json(output / "runtime_provenance.json")
    raw = read_json(output / "raw_metadata_audit.json")
    require(manifest.get("status") == "completed_pending_independent_validation", "Only actually completed runs can be validated")
    require(manifest.get("new_source_fits") == 10 and manifest.get("target_fits") == 0 and manifest.get("new_neural_fits") == 0, "Declared fit budget differs")
    require(status.get("status") == "completed_pending_independent_validation" and status.get("new_source_fits_started") == 10 and status.get("new_source_fits_completed") == 10, "Execution counter lacks ten completed fits")
    require(status.get("target_fits") == 0 and status.get("new_neural_fits") == 0 and status.get("target_predictions_computed") is False, "Target activity declared")
    require(manifest.get("parameters") == PARAMETERS and runtime.get("config_sha256") == sha(STUDY / "config/cpu_csp_diagnostic.json"), "Source model configuration changed")
    require(runtime.get("protocol_commit") == freeze["protocol_commit"] and runtime.get("source_provenance_sha256") == sha(RAW_PROVENANCE), "Execution source provenance changed")
    for field, path in {
        "executor_sha256": STUDY / "scripts/cpu_csp_source_audit.py",
        "label_identity_validator_sha256": Path(__file__),
        "eeg_preprocessing_module_sha256": ROOT / "src/mi_eeg/data/q15_context.py",
        "fixed_basis_module_sha256": ROOT / "src/mi_eeg/models/q15_csp.py",
        "execution_contract_sha256": EXECUTION_CONTRACT,
        "original_protocol_sha256": ORIGINAL_PROTOCOL,
    }.items():
        require(runtime.get(field) == sha(path), f"Execution implementation/contract provenance differs: {field}")
    require(runtime.get("versions") == runtime_versions(), "Validator scientific runtime differs from execution; numerical replay cannot be certified")
    require(runtime.get("source_epoch_dtype") == "float32" and runtime.get("estimator_input_dtype") == "float64",
            "Source preprocessing or estimator input dtype changed")
    require(raw.get("raw_hashes_verified") is True and raw.get("n_files") == 18 and raw.get("n_runs") == 108 and raw.get("n_binary_trials") == 2592, "Original source audit is incomplete")
    originals = json.loads(RAW_PROVENANCE.read_text())
    source_hashes = {Path(row["path"]).name: (row["bytes"], row["sha256"]) for row in originals}
    require({row["file_id"]: (row["bytes"], row["sha256"]) for row in raw["files"]} == source_hashes, "Raw audit differs from frozen 18-file provenance")
    source_records = native_source_records(data_dir)
    with (output / "source_metadata.csv").open(newline="") as stream:
        source_csv = list(csv.DictReader(stream))
    for row in source_csv:
        for key in ("subject", "run", "trial", "label", "event_sample"):
            row[key] = int(row[key])
        require(row["artifact_flagged"] in {"True", "False"}, "Source artifact metadata changed")
        row["artifact_flagged"] = row["artifact_flagged"] == "True"
    require(source_csv == source_records, "Source metadata differs from independent original MATLAB labels, flags or trial order")
    require(runtime.get("source_sample_ids_sha256") == canonical_hash([row["sample_id"] for row in source_records]), "Execution source sample hash changed")
    # Numerical input replay only: this invokes the immutable preprocessing
    # helper, never a trained model. It is a reproducibility check of that same
    # implementation, not an independently designed alternative transform.
    import numpy as np
    from threadpoolctl import threadpool_limits
    from mi_eeg.data.q15_context import load_bnci_source
    with threadpool_limits(limits=1):
        replayed_arrays, replayed_metadata, _ = load_bnci_source(Path(data_dir), SUBJECTS, RAW_PROVENANCE)
    replayed_X = replayed_arrays["broad"]
    del replayed_arrays
    replayed_y = np.array([row["label"] for row in source_records], dtype=np.int64)
    require(replayed_metadata.to_dict(orient="records") == source_records, "Input replay source labels/identities differ")
    require(array_hash(replayed_X) == runtime.get("source_epochs_sha256") and
            array_hash(replayed_y) == runtime.get("source_labels_sha256"), "Replayed numerical source inputs differ from fit inputs")
    folds = [*(f"loso_s{person:02d}" for person in SUBJECTS), "all_source_resubstitution"]
    require(manifest.get("folds") == folds, "Missing or unexpected source folds")
    loso_predictions, fit_receipts = [], []
    all_source_metrics = None
    for ordinal, fold in enumerate(folds, 1):
        held_out = ordinal if ordinal <= 9 else None
        folder = output / "folds" / fold
        receipt = read_json(folder / "fit_receipt.json")
        require(receipt.get("status") == "completed" and receipt.get("fit_ordinal") == ordinal and receipt.get("new_source_fit") is True,
                "Completed fit receipt missing or duplicated")
        require(receipt.get("target_fit") is False and receipt.get("fit_method") == "sklearn.pipeline.Pipeline.fit", "Unexpected fit declaration")
        require(receipt.get("parameters") == PARAMETERS and receipt.get("held_out_subject") == held_out, "Fold fit configuration changed")
        require(receipt.get("actual_estimator_input_dtype") == "float64" and receipt.get("preprocessing_epoch_dtype") == "float32",
                "Fold fit dtype receipt differs from actual frozen conversion")
        require(receipt.get("partition_file_sha256") == sha(folder / "partition.json") and receipt.get("predictions_sha256") == sha(folder / "predictions.csv"), "Fold artifact hash mismatch")
        partition = read_json(folder / "partition.json")
        predictions = read_predictions(folder / "predictions.csv")
        train, evaluation = validate_partition(partition, predictions, held_out, source_records)
        require(receipt.get("n_training_trials") == len(train) and receipt.get("n_evaluation_trials") == len(evaluation), "Fit receipt partition counts differ")
        require(receipt.get("training_subjects") == sorted({row["subject"] for row in train}), "Fit receipt source subject boundary differs")
        require(receipt.get("training_sample_ids_sha256") == canonical_hash([row["sample_id"] for row in train]) and
                receipt.get("evaluation_sample_ids_sha256") == canonical_hash([row["sample_id"] for row in evaluation]), "Fit receipt sample hash differs")
        require(receipt.get("scaler_n_samples_seen") == len(train) and receipt.get("lda_classes") == [1, 2] and receipt.get("csp_fitted_filters_shape") == [20, 20], "Fitted-state dimensions or fitting counts differ")
        for field in ("training_epochs_sha256", "training_labels_sha256", "evaluation_epochs_sha256", "evaluation_labels_sha256"):
            require(isinstance(receipt.get(field), str) and len(receipt[field]) == 64, "Numerical source partition hash missing")
        train_indices = [index for index, row in enumerate(source_records) if held_out is None or row["subject"] != held_out]
        eval_indices = list(range(len(source_records))) if held_out is None else [
            index for index, row in enumerate(source_records) if row["subject"] == held_out]
        require(receipt["training_epochs_sha256"] == array_hash(np.ascontiguousarray(replayed_X[train_indices], dtype=np.float64)) and
                receipt["training_labels_sha256"] == array_hash(replayed_y[train_indices]) and
                receipt["evaluation_epochs_sha256"] == array_hash(np.ascontiguousarray(replayed_X[eval_indices], dtype=np.float64)) and
                receipt["evaluation_labels_sha256"] == array_hash(replayed_y[eval_indices]),
                "Source fold numerical input hash differs from the original-label-bound replay")
        model = (ROOT / receipt.get("model_path", "")).resolve()
        require(model.is_relative_to(STUDY / "models") and model.is_file() and not model.is_symlink() and
                model.stat().st_size > 0 and sha(model) == receipt.get("model_sha256"), "Source model artifact missing or untrusted")
        metrics = participant_metrics(predictions)
        fit_receipts.append({"fold": fold, "fit_receipt_sha256": sha(folder / "fit_receipt.json"),
                             "model_sha256": sha(model), "n_source_trials": len(train)})
        if held_out is None:
            all_source_metrics = metrics
        else:
            require(len(metrics) == 1 and metrics[0]["subject"] == held_out and metrics[0]["n_trials"] == 288,
                    "Held-out participant evaluation coverage changed")
            loso_predictions.extend(predictions)
    require(len(loso_predictions) == 2592 and len({row["sample_id"] for row in loso_predictions}) == 2592,
            "LOSO predictions omit or duplicate source trials")
    loso_metrics = participant_metrics(loso_predictions)
    require(len(loso_metrics) == 9 and len(all_source_metrics) == 9, "Participant-level summary coverage changed")
    old = read_json(output / "original_model_replay_receipt.json")
    require(old.get("status") in {"SKIP", "REPLAYED"}, "Original-model replay status is ambiguous")
    original_metrics = None
    if old["status"] == "REPLAYED":
        policy = original_replay_policy(config, runtime["versions"])
        require(policy.get("status") == "ELIGIBLE" and old.get("sha256") == policy.get("sha256") and
                old.get("path") == policy.get("path"), "Original replay lacks trusted hash and matching historical runtime")
        require(old.get("model_deserialized") is True and old.get("predictions_sha256") == sha(output / "original_model_source_resubstitution.csv"), "Original replay evidence missing")
        old_rows = read_predictions(output / "original_model_source_resubstitution.csv")
        require(identity_rows(old_rows) == identity_rows(source_records), "Original source resubstitution labels differ")
        original_metrics = participant_metrics(old_rows)
    else:
        require(old.get("model_deserialized") is False, "Skipped original model was unexpectedly deserialized")
    summary = {"schema_version": 1, "status": "PASS_STORED_SCORES_PARTITIONS_RAW_LABELS_VERIFIED",
               "validated_at_utc": now(), "run_id": manifest["run_id"], "new_source_fits": len(fit_receipts),
               "target_fits": 0, "new_neural_fits": 0,
               "all_18_original_raw_hashes_and_labels_verified": True,
               "all_ten_fit_input_numeric_hashes_replayed": True,
               "fresh_loso_mean_participant_ba_percent": statistics.mean(row["balanced_accuracy_percent"] for row in loso_metrics),
               "fresh_all_source_resubstitution_mean_participant_ba_percent": statistics.mean(row["balanced_accuracy_percent"] for row in all_source_metrics),
               "loso_participant_confusion": loso_metrics, "all_source_resubstitution_participant_confusion": all_source_metrics,
               "original_model_replay_status": old["status"], "original_model_source_resubstitution_participant_confusion": original_metrics,
               "fits_evidence": fit_receipts, "raw_provenance_sha256": sha(RAW_PROVENANCE),
               "new_result_is_independent_confirmatory_evidence": False,
               "historical_report_numeric_claims_retroactively_verified": False,
               "limits": ["New source-only refits on previously observed BNCI participants are retrospective diagnostics",
                          "Training-set resubstitution is not independent validation",
                          "No target model inference or target centering was performed",
                          "Independent stored-output and raw-label checks do not prove every implementation error is absent",
                          "Input numerical replay reuses the frozen preprocessing helper, not an independently designed alternate transform",
                          "Original report train/LOSO numbers lack archived run identity; numerical agreement cannot restore provenance"]}
    write_json(output / "independent_validation.json", summary)
    table = [{"evaluation": "new_source_loso", **row} for row in loso_metrics] + [
        {"evaluation": "new_all_source_resubstitution", **row} for row in all_source_metrics]
    with (output / "participant_confusion_and_metrics.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)
    summary_path = output / "independent_validation.json"
    write_json(output / "independent_validation_receipt.json", {"status": "PASS", "validator_sha256": sha(__file__),
                                                                "summary_sha256": sha(summary_path),
                                                                "confusion_csv_sha256": sha(output / "participant_confusion_and_metrics.csv"),
                                                                "model_deserialization": False, "model_fits": 0, "model_inference": False})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    report = validate(args.run_dir, args.data_dir)
    print(json.dumps({key: report[key] for key in ("status", "new_source_fits", "target_fits",
                                                  "fresh_loso_mean_participant_ba_percent",
                                                  "fresh_all_source_resubstitution_mean_participant_ba_percent")}, indent=2))


if __name__ == "__main__":
    main()
