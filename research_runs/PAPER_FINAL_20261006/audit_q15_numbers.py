"""Reconstruct Q15 paper numbers from immutable, saved prediction CSVs.

No raw EEG is loaded, no estimator is fitted, no checkpoint is deserialized,
and no model inference or network operation is performed. Git blob reads are
used so later working-tree changes cannot silently change this paper audit.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

RESULT_HEAD = "7af1a137e2676a018e1e880ab076de6cae4ce30b"
RESULT_COMMIT = "bc48b257eb44f412ad069f50d0f1a72a33c3c520"
SCIENTIFIC_CODE = "271af288a2f3863430ab80e3145c2dee9bd5571d"
PRE_FIT_COMMIT = "fc0e7d54006076bec7701064e1045034c02d06a4"
INFERENCE_FREEZE_COMMIT = "2ad479f5bccb4f92cd6c77bc78a8ba9b620604c1"
JOB = "20261005T050511Z-migration-from-r2-b82ad79b"
JOB_ROOT = f"research_runs/Q15-MIGRATION-20261004/jobs/{JOB}"
EXTERNAL_ROOT = "results/Q15-EXTERNAL"
MODELS = ("BROAD_EEGNET", "MU_BETA_SHARED", "CSP4_LDA")
SEEDS = ("20260924", "20260925", "20260926")
COHORTS = {
    "Cho2017": ("Q15-E006", 52, (1,), "Q15-V002"),
    "Lee2019_MI": ("Q15-E007", 54, (1, 2), "Q15-V001"),
}
META = (
    "sample_id", "subject", "session", "run", "label", "file_id",
    "raw_sha256", "cue_sample_native", "dataset", "experiment_id",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class Snapshot:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.input_sha256: dict[str, str] = {}

    def blob(self, path: str, revision: str = RESULT_HEAD) -> bytes:
        require(not path.startswith("/") and ".." not in Path(path).parts,
                "Unsafe repository-relative artifact path")
        value = subprocess.check_output(
            ["git", "show", f"{revision}:{path}"], cwd=self.root,
        )
        self.input_sha256[f"{revision}:{path}"] = hashlib.sha256(value).hexdigest()
        return value

    def document(self, path: str, revision: str = RESULT_HEAD) -> dict:
        return json.loads(self.blob(path, revision))

    def verify_map(self, expected: dict[str, str], revision: str) -> int:
        for path, digest in expected.items():
            require(hashlib.sha256(self.blob(path, revision)).hexdigest() == digest,
                    f"Artifact digest differs: {path} at {revision}")
        return len(expected)

    def committed_at(self, revision: str) -> datetime:
        value = subprocess.check_output(
            ["git", "show", "-s", "--format=%cI", revision], cwd=self.root, text=True,
        ).strip()
        return datetime.fromisoformat(value)

    def require_ancestor(self, earlier: str, later: str) -> None:
        result = subprocess.run(["git", "merge-base", "--is-ancestor", earlier, later],
                                cwd=self.root, check=False, capture_output=True)
        require(result.returncode == 0, "Frozen commit is not an ancestor of results")


def score(frame: pd.DataFrame) -> dict:
    matrix = np.zeros((2, 2), dtype=np.int64)
    actual = frame["label"].to_numpy(dtype=np.int64)
    predicted = frame["predicted_label"].to_numpy(dtype=np.int64)
    require(set(actual) == {1, 2} and set(predicted).issubset({1, 2}),
            "Both canonical classes are required")
    np.add.at(matrix, (actual - 1, predicted - 1), 1)
    recalls = matrix.diagonal() / matrix.sum(axis=1)
    return {
        "n_trials": len(frame), "n_left": int(matrix[0].sum()),
        "n_right": int(matrix[1].sum()), "left_recall": float(recalls[0]),
        "right_recall": float(recalls[1]),
        "balanced_accuracy": float(recalls.mean()),
        "confusion_matrix": matrix.tolist(),
    }


def paired_statistics(effects: np.ndarray) -> dict:
    """Frozen person-level Monte Carlo sequence, reconstructed independently."""
    require(effects.ndim == 1 and np.isfinite(effects).all(), "Invalid paired effects")
    bootstrap_rng = np.random.default_rng(20260924)
    draw_indices = bootstrap_rng.integers(0, len(effects), (20000, len(effects)))
    bootstrapped_means = np.take(effects, draw_indices).mean(axis=1)
    sign_rng = np.random.default_rng(20261003)
    signs = sign_rng.integers(0, 2, (20000, len(effects))) * 2 - 1
    observed = float(effects.mean())
    simulated = np.abs(np.sum(signs * effects, axis=1) / len(effects))
    extreme = int(np.count_nonzero(simulated >= abs(observed) - 1e-15))
    return {
        "mean_delta": observed,
        "ci_low": float(np.quantile(bootstrapped_means, 0.025)),
        "ci_high": float(np.quantile(bootstrapped_means, 0.975)),
        "raw_p": (extreme + 1) / 20001,
        "sign_flip_extreme_count": extreme,
        "n_persons": len(effects),
        "positive_effect_persons": int(np.count_nonzero(effects > 1e-15)),
        "negative_effect_persons": int(np.count_nonzero(effects < -1e-15)),
        "tied_effect_persons_at_1e_minus_15": int(np.count_nonzero(np.abs(effects) <= 1e-15)),
    }


def same_number(observed: float, expected: float, label: str) -> None:
    require(np.isclose(observed, expected, rtol=0, atol=1e-12),
            f"Archived number differs from reconstruction: {label}")


def audit_cohort(snapshot: Snapshot, dataset: str) -> tuple[dict, list, list, list]:
    experiment, n_persons, sessions, audit_id = COHORTS[dataset]
    csv_path = f"{EXTERNAL_ROOT}/{experiment}/predictions.csv"
    frame = pd.read_csv(io.BytesIO(snapshot.blob(csv_path)), dtype={"seed": str})
    require(set(frame["dataset"]) == {dataset}, "Dataset tags differ")
    require(set(frame["experiment_id"]) == {experiment}, "Experiment tags differ")
    require(set(frame["subject"]) == set(range(1, n_persons + 1)), "Person coverage differs")
    require(not frame.duplicated(["sample_id", "model", "seed"]).any(), "Duplicate prediction key")
    require(not frame.isna().any().any(), "Missing prediction value")
    probabilities = frame[["p_left", "p_right"]].to_numpy(dtype=float)
    require(np.isfinite(probabilities).all(), "Nonfinite probability")
    require(((probabilities >= 0) & (probabilities <= 1)).all(), "Probability outside unit interval")
    require(np.allclose(probabilities.sum(axis=1), 1, rtol=0, atol=1e-6), "Probability sum differs")
    require(np.array_equal(probabilities.argmax(axis=1) + 1, frame["predicted_label"]),
            "Saved labels differ from frozen left-first argmax")
    variants = {(model, seed) for model in MODELS
                for seed in (SEEDS if model != "CSP4_LDA" else ("deterministic",))}
    require(set(zip(frame["model"], frame["seed"])) == variants, "Model/seed coverage differs")
    reference = None
    for _, rows in frame.groupby(["model", "seed"], sort=True):
        metadata = rows.loc[:, list(META)].sort_values("sample_id").reset_index(drop=True)
        if reference is None:
            reference = metadata
        require(reference.equals(metadata), "Trial metadata differs across variants")
    require(reference is not None, "Missing unique trial table")
    require(len(frame) == len(reference) * 7, "Expected exactly seven predictions per trial")

    metadata_audit = snapshot.document(f"results/{audit_id}/metadata_audit_receipt.json")
    require(metadata_audit["dataset"] == dataset and metadata_audit["blocking_reasons"] == [],
            "Raw metadata audit is blocked")
    require(metadata_audit["raw_hashes_verified"] and metadata_audit["all_expected_files_hashed"],
            "Raw file hash audit is incomplete")
    require(metadata_audit["n_labeled_trials"] == len(reference), "Raw retained trial count differs")
    raw_keys = {}
    for file in metadata_audit["files"]:
        for event in file["events"]:
            key = event["sample_id"]
            require(key not in raw_keys, "Duplicate raw event sample ID")
            raw_keys[key] = (file["subject"], file["session"], file["file_id"],
                             file["sha256"], event["canonical_label"], event["onset_sample"])
    require(set(reference["sample_id"]) == set(raw_keys), "Prediction/raw event identity differs")
    for row in reference.to_dict("records"):
        require((row["subject"], row["session"], row["file_id"], row["raw_sha256"],
                 row["label"], row["cue_sample_native"]) == raw_keys[row["sample_id"]],
                "Prediction metadata does not match audited raw event")

    archived = snapshot.document(f"{EXTERNAL_ROOT}/{experiment}/statistics.json")
    archived_persons = {row["subject"]: row for row in archived["persons"]}
    person_rows, seed_rows, model_rows = [], [], []
    for subject in range(1, n_persons + 1):
        person = frame.loc[frame["subject"] == subject]
        require(tuple(sorted(person["session"].unique())) == sessions, "Session coverage differs")
        unique = reference.loc[reference["subject"] == subject]
        row = {"dataset": dataset, "experiment_id": experiment, "subject": subject,
               "n_sessions": len(sessions), "n_trials": len(unique),
               "n_left": int((unique["label"] == 1).sum()),
               "n_right": int((unique["label"] == 2).sum())}
        for model in MODELS:
            seeds = SEEDS if model != "CSP4_LDA" else ("deterministic",)
            values = []
            for seed in seeds:
                part = person.loc[(person["model"] == model) & (person["seed"] == seed)]
                metrics = score(part)
                values.append(metrics["balanced_accuracy"])
                saved = archived_persons[subject]["models"][model]["per_seed"][seed]
                for key in ("balanced_accuracy", "left_recall", "right_recall", "n_trials"):
                    same_number(metrics[key], saved[key], f"{dataset}/{subject}/{model}/{seed}/{key}")
                require(metrics["confusion_matrix"] == saved["confusion_matrix_rows_actual_left_right"],
                        "Archived confusion matrix differs")
                seed_rows.append({"dataset": dataset, "experiment_id": experiment, "subject": subject,
                                  "model": model, "seed": seed, "n_sessions": len(sessions),
                                  **{k: v for k, v in metrics.items() if k != "confusion_matrix"}})
            row[model] = float(np.mean(values))
            if model != "CSP4_LDA":
                row[f"{model}_seed_sd"] = float(np.std(values, ddof=1))
            same_number(row[model], archived_persons[subject]["models"][model][
                "within_person_seed_mean_balanced_accuracy"], "Archived person mean")
        row["primary_delta"] = row["MU_BETA_SHARED"] - row["BROAD_EEGNET"]
        same_number(row["primary_delta"], archived_persons[subject]["primary_paired_difference"],
                    "Archived person primary delta")
        person_rows.append(row)

    effects = np.array([row["primary_delta"] for row in person_rows], dtype=np.float64)
    primary = paired_statistics(effects)
    saved_primary = archived["primary_contrast"]
    same_number(primary["mean_delta"], saved_primary["mean_paired_balanced_accuracy_difference"], "Primary mean")
    same_number(primary["ci_low"], saved_primary["paired_person_bootstrap_percentile_95_ci"][0], "Primary CI low")
    same_number(primary["ci_high"], saved_primary["paired_person_bootstrap_percentile_95_ci"][1], "Primary CI high")
    same_number(primary["raw_p"], saved_primary["two_sided_person_sign_flip_p_value"], "Primary p")
    for model in MODELS:
        values = np.array([row[model] for row in person_rows])
        metrics = [row for row in seed_rows if row["model"] == model]
        model_row = {
            "dataset": dataset, "experiment_id": experiment, "model": model,
            "n_persons": n_persons, "n_sessions": n_persons * len(sessions),
            "n_trials": len(reference), "n_seeds": 3 if model != "CSP4_LDA" else 1,
            "mean_balanced_accuracy": float(values.mean()), "person_sample_sd": float(values.std(ddof=1)),
            "mean_seed_sd": float(np.mean([row[f"{model}_seed_sd"] for row in person_rows]))
            if model != "CSP4_LDA" else None,
            "mean_left_recall": float(np.mean([row["left_recall"] for row in metrics])),
            "mean_right_recall": float(np.mean([row["right_recall"] for row in metrics])),
        }
        same_number(model_row["mean_balanced_accuracy"], archived[
            "cohort_equal_person_mean_balanced_accuracy"][model], "Archived cohort mean")
        model_rows.append(model_row)
    special = {str(row["subject"]): row["n_trials"] for row in person_rows if row["n_trials"] != 200}
    cohort = {
        "experiment_id": experiment, "n_persons": n_persons,
        "n_sessions": n_persons * len(sessions), "n_unique_trials": len(reference),
        "n_prediction_rows": len(frame), "n_raw_files": metadata_audit["n_files"],
        "trials_per_person_min": min(row["n_trials"] for row in person_rows),
        "trials_per_person_max": max(row["n_trials"] for row in person_rows),
        "persons_with_other_than_200_trials": special,
        "n_probability_ties": int((probabilities[:, 0] == probabilities[:, 1]).sum()),
        "balanced_accuracy": {row["model"]: row["mean_balanced_accuracy"] for row in model_rows},
        "primary": primary, "saved_statistics_reproduced": True,
        "audited_raw_event_labels_and_ids_match": True,
        "canonical_label_map": {"left_hand": 1, "right_hand": 2},
        "native_label_map": metadata_audit["files"][0]["native_label_map"],
        "native_sampling_rate_hz": metadata_audit["files"][0]["sampling_rate_hz"],
        "included_raw_run_roles": sorted({file["run_role"] for file in metadata_audit["files"]}),
    }
    return cohort, person_rows, seed_rows, model_rows


def run(root: Path, output: Path) -> dict:
    snapshot = Snapshot(root)
    status = snapshot.document(f"{JOB_ROOT}/job_status.json")
    publication = snapshot.document(f"{JOB_ROOT}/publication_evidence.json")
    validator = snapshot.document(f"{EXTERNAL_ROOT}/validation_report.json")
    freeze = snapshot.document(f"{EXTERNAL_ROOT}/inference_freeze.json")
    source = snapshot.document("results/Q15-E005/source_validation.json")
    pre_fit = snapshot.document("results/Q15-E005/pre_fit_freeze.json")
    source_complete = snapshot.document("results/Q15-E005/source/source_stage_complete.json")
    completion = snapshot.document(f"{EXTERNAL_ROOT}/completion_receipt.json")
    require(status["job_id"] == JOB and publication["job_id"] == JOB, "Current job binding differs")
    require(publication["verified_commit"] == RESULT_COMMIT and publication["readback_verified"],
            "Results publication is not verified")
    require(status["scientific_validation_passed"] and status["github_results_backup_verified"],
            "Final job is not scientifically validated and backed up")
    require(validator["passed"] and validator["scientific_validation_passed"] and
            validator["statistics_independently_reconstructed"], "Final scientific validator is incomplete")
    require(status["original_source_fits"] == 15 and source["deep_fit_count"] == 14 and
            source["shallow_fit_count"] == 1 and source["passed"], "Source fit counts differ")
    require(status["new_source_fits"] == 0 and status["target_fits"] == 0 and
            validator["new_model_fits"] == 0 and validator["target_fits"] == 0 and
            freeze["new_model_fits"] == 0 and freeze["target_fits"] == 0,
            "Unexpected new or target fit")
    require(not freeze["target_outcomes_inspected"] and
            freeze["statistics"]["primary_contrast"] == "MU_BETA_SHARED_minus_BROAD_EEGNET",
            "Frozen inference/statistical contrast differs")
    publication_verified = snapshot.verify_map(publication["artifact_sha256"], RESULT_COMMIT)
    validator_verified = snapshot.verify_map(validator["artifact_sha256"], RESULT_HEAD)
    source_verified = snapshot.verify_map(source["artifact_sha256"], RESULT_HEAD)
    frozen_models_verified = snapshot.verify_map(freeze["source_checkpoints"], RESULT_HEAD)
    require(hashlib.sha256(snapshot.blob("results/Q15-E005/source_validation.json")).hexdigest() ==
            freeze["source_validation_sha256"], "Source validation binding differs")
    require(hashlib.sha256(snapshot.blob("results/Q15-E005/pre_fit_freeze.json")).hexdigest() ==
            source["pre_fit_freeze_sha256"], "Source pre-fit freeze binding differs")
    for dataset, (_, _, _, audit_id) in COHORTS.items():
        audit_path = f"results/{audit_id}/metadata_audit_receipt.json"
        digest = hashlib.sha256(snapshot.blob(audit_path)).hexdigest()
        require(digest == pre_fit["metadata_receipt_sha256"][dataset] ==
                freeze["metadata_receipts"][dataset], "Raw audit freeze binding differs")
        manifest_path = f"{EXTERNAL_ROOT}/manifests/{dataset}.json"
        manifest = snapshot.document(manifest_path)
        require(hashlib.sha256(snapshot.blob(manifest_path)).hexdigest() ==
                freeze["epoch_manifests"][dataset]["sha256"], "Epoch manifest freeze binding differs")
        require(manifest["metadata_receipt_sha256"] == digest and
                manifest["pre_fit_freeze_sha256"] == source["pre_fit_freeze_sha256"],
                "Epoch manifest pre-fit metadata binding differs")
    require(snapshot.blob("results/Q15-E005/pre_fit_freeze.json", PRE_FIT_COMMIT) ==
            snapshot.blob("results/Q15-E005/pre_fit_freeze.json"), "Pre-fit freeze changed after commit")
    require(snapshot.blob(f"{EXTERNAL_ROOT}/inference_freeze.json", INFERENCE_FREEZE_COMMIT) ==
            snapshot.blob(f"{EXTERNAL_ROOT}/inference_freeze.json"), "Inference freeze changed after commit")
    snapshot.require_ancestor(PRE_FIT_COMMIT, INFERENCE_FREEZE_COMMIT)
    snapshot.require_ancestor(INFERENCE_FREEZE_COMMIT, RESULT_COMMIT)
    snapshot.require_ancestor(RESULT_COMMIT, RESULT_HEAD)
    pre_fit_at = snapshot.committed_at(PRE_FIT_COMMIT)
    inference_at = snapshot.committed_at(INFERENCE_FREEZE_COMMIT)
    source_completed_at = datetime.fromisoformat(source_complete["completed_at_utc"])
    inference_completed_at = datetime.fromisoformat(completion["completed_at_utc"])
    require(pre_fit_at < source_completed_at < inference_at < inference_completed_at,
            "Freeze and completion recorded chronology differs")
    same_number(source["counts"]["deep_inner"], 8, "Eight inner source fits")
    same_number(source["counts"]["deep_final"], 6, "Six final source fits")
    archived_holm = snapshot.document(f"{EXTERNAL_ROOT}/holm_two_cohorts.json")
    cohorts, people, seeds, models = {}, [], [], []
    for dataset in COHORTS:
        cohort, person_rows, seed_rows, model_rows = audit_cohort(snapshot, dataset)
        cohorts[dataset] = cohort
        people.extend(person_rows)
        seeds.extend(seed_rows)
        models.extend(model_rows)
        require(validator["coverage"][dataset]["n_trials"] == cohort["n_unique_trials"],
                "Validator trial coverage differs")
    ordered = sorted((cohort["primary"]["raw_p"], dataset) for dataset, cohort in cohorts.items())
    previous = 0.0
    for rank, (value, dataset) in enumerate(ordered):
        previous = max(previous, min(1.0, (2 - rank) * value))
        cohorts[dataset]["primary"]["holm_p"] = previous
        same_number(previous, archived_holm["cohorts"][dataset]["holm_adjusted_p_value"], "Holm p")
    for row in models:
        primary = cohorts[row["dataset"]]["primary"]
        row.update({"primary_delta_mean": primary["mean_delta"], "primary_ci_low": primary["ci_low"],
                    "primary_ci_high": primary["ci_high"], "primary_raw_p": primary["raw_p"],
                    "primary_holm_p": primary["holm_p"]})
    output.mkdir(parents=True, exist_ok=True)
    (output / "tables").mkdir(exist_ok=True)
    (output / "evidence").mkdir(exist_ok=True)
    for name, rows in (("q15_external_subjects.csv", people), ("q15_seed_metrics.csv", seeds),
                       ("q15_model_summary.csv", models)):
        pd.DataFrame(rows).to_csv(output / "tables" / name, index=False, float_format="%.17g")
    report = {
        "schema_version": 1, "audit_type": "paper_saved_prediction_reconstruction",
        "passed": True, "result_branch_head": RESULT_HEAD, "verified_results_commit": RESULT_COMMIT,
        "scientific_code_revision": SCIENTIFIC_CODE, "job_id": JOB,
        "fits_performed_by_this_audit": 0, "raw_eeg_loaded_by_this_audit": False,
        "checkpoints_deserialized_by_this_audit": False, "inference_performed_by_this_audit": False,
        "independent_raw_to_prediction_replay": "reported by archived validator; not rerun by this paper audit",
        "github_hash_bindings_checked_against_verified_result_commit": publication_verified,
        "validator_artifact_hash_bindings_checked": validator_verified,
        "source_artifact_hash_bindings_checked": source_verified,
        "frozen_source_artifact_hash_bindings_checked": frozen_models_verified,
        "original_source_fits": 15, "source_inner_deep_fits": 8, "source_final_deep_fits": 6,
        "source_shallow_fits": 1, "new_source_fits": 0, "target_fits": 0,
        "source_selected_epochs": source["selected_epochs"],
        "committed_gate_chronology": {
            "pre_fit_freeze_commit": PRE_FIT_COMMIT,
            "pre_fit_freeze_committed_at": pre_fit_at.isoformat(),
            "source_complete_recorded_at": source_completed_at.isoformat(),
            "inference_freeze_commit": INFERENCE_FREEZE_COMMIT,
            "inference_freeze_committed_at": inference_at.isoformat(),
            "inference_complete_recorded_at": inference_completed_at.isoformat(),
            "freeze_contents_unchanged": True,
            "frozen_metadata_manifest_and_source_validation_bindings_match": True,
            "interpretation": "Immutable ancestor ordering and archived completion timestamps checked; not independent physical execution timing",
        },
        "status": status["status"], "scientific_validation_passed": True,
        "github_results_backup_verified": True, "physical_shutdown_confirmed": status["physical_shutdown_confirmed"],
        "calibration_limitations": validator["calibration_limitations"],
        "statistics_plan": freeze["statistics"], "cohorts": cohorts,
        "cohort_summary_sd_interpretation": "Sample standard deviation across person means; descriptive, not SE",
        "class_recall_interpretation": "Equal-person, then equal-seed mean; sessions pooled within person",
        "primary_ci_interpretation": "20,000 paired person percentile bootstrap resamples; not simultaneous CIs",
        "primary_p_interpretation": "20,000 two-sided paired person sign flips; plus-one p; Holm family of two cohorts",
        "floating_point_ties": "Sign flip extremeness uses observed absolute mean minus 1e-15; argmax chooses left on exact probability tie",
        "descriptive_extras": ["Person dispersion", "Class-specific recall", "Seed dispersion", "Sign counts"],
        "extra_primary_tests_added": False,
        "input_sha256": snapshot.input_sha256,
        "audit_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (output / "evidence" / "q15_numbers.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    lines = ["# Independent reconstruction of Q15 paper numbers", "",
             ("The audit reads immutable Git blobs and saved probabilities. It performs no model fitting, "
             "checkpoint inference, checkpoint deserialization, or raw EEG loading."), "",
             f"Results branch head: `{RESULT_HEAD}`. Verified scientific results commit: `{RESULT_COMMIT}`.", "",
             "| Cohort | Persons | Unique trials | Broad BA | Shared BA | CSP BA | Shared − broad, pp (95% CI) | Holm p |",
             "|---|---:|---:|---:|---:|---:|---|---:|"]
    for dataset, cohort in cohorts.items():
        ba, p = cohort["balanced_accuracy"], cohort["primary"]
        lines.append(f"| {dataset} | {cohort['n_persons']} | {cohort['n_unique_trials']:,} | "
                     f"{ba['BROAD_EEGNET']*100:.4f}% | {ba['MU_BETA_SHARED']*100:.4f}% | "
                     f"{ba['CSP4_LDA']*100:.4f}% | {p['mean_delta']*100:+.4f} "
                     f"({p['ci_low']*100:+.4f}, {p['ci_high']*100:+.4f}) | {p['holm_p']:.8g} |")
    lines.extend(["", ("Balanced accuracy is calculated after pooling declared sessions within a person, "
                  "separately for each seed; deep-model seed means then receive equal person weighting. "
                  "The primary paired contrast and all archived person confusion matrices, 20,000 bootstrap "
                  "draws, sign-flip p values, and the two-cohort Holm correction reproduce within 1e-12."), "",
                  (f"The audit confirms {publication_verified} publication digest bindings at the verified result "
                  f"commit, {validator_verified} validator artifact bindings, {source_verified} source artifact "
                  f"bindings and {frozen_models_verified} frozen source artifact bindings. The publication "
                  "snapshot of job_status.json is checked at its committed revision rather than incorrectly "
                  "compared with the later final job status."), "",
                  ("The archived cloud validator reports independent raw metadata, raw-to-epoch and frozen "
                  "checkpoint prediction replays. Those operations are not repeated in this paper audit."), "",
                  ("Original source fitting comprised eight inner deep fits, six final deep fits, and one "
                  "CSP–LDA fit. Migration reused those 15 fits; it added no source fit and performed no "
                  "target fit. Broad/shared selected training durations were 14/19 epochs."), "",
                  ("Cho2017 comprises 10,520 retained trials: most persons have 200, but persons 7, 9 and 46 "
                  "have 240. Seven model/seed variants per trial are repeated predictions rather than "
                  "independent observations. Lee2019_MI comprises 10,800 trials in 108 sessions."), "",
                  ("The complete benchmark is an adapter evaluation with calibration limitations. Raw physical "
                  "voltage calibration, the original Cho hardware reference and hardware cue latency remain "
                  "unverified. Completion does not establish physical Pod shutdown."), "",
                  ("Person standard deviations, mean seed dispersion, class-specific recalls and sign counts "
                  "are descriptive additions. They are not new predeclared confirmatory tests. Individual "
                  "95% bootstrap confidence intervals are not simultaneous intervals.")])
    (output / "evidence" / "q15_numbers.md").write_text("\n".join(lines) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    report = run(args.repo.resolve(), args.output.resolve())
    print(json.dumps({"passed": report["passed"], "cohorts": report["cohorts"],
                      "fits_performed_by_this_audit": 0}, indent=2))


if __name__ == "__main__":
    main()
