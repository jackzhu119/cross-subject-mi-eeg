"""Independent raw-EDF and prediction audit for Q14-E002R1 continuation.

Does not fit, choose, or alter any classifier. It re-reads all 327 official EDF
files, reconstructs trial identity, checks every prediction and subject receipt,
then computes the predeclared subject-level paired contrast. Only a fully
validated 109-subject run receives a top-level passing report.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mne
import numpy as np
import pandas as pd
from mne.datasets import eegbci
from scipy.stats import binomtest

from scripts import q14_external, q14_r1_migration, q14_validate
from scripts.q14_source import ALL_MODELS, CONFIG, DEEP_MODELS, E002_ROOT, runtime_receipt, sha256

ID = q14_r1_migration.ID
RESULT = ROOT / "results" / ID
EXTERNAL = RESULT / "external"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _same(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"Q14-E002R1 validation mismatch: {label}")


def _hash(path: Path, expected: str) -> None:
    if not path.exists() or sha256(path) != expected:
        raise AssertionError(f"Missing/hash-mismatched artifact: {path}")


def _trial_index(edf_records: list[dict], edfs: dict[str, Path], official: dict, config: dict):
    trials = []
    for record in sorted(edf_records, key=lambda value: value["run"]):
        path = edfs.get(record["filename"])
        if (
            path is None
            or path.stat().st_size != record["bytes"]
            or sha256(path) != record["sha256"]
            or record["sha256"] != official.get(record["filename"])
        ):
            raise AssertionError(f"Unverified EDF: {record['filename']}")
        raw = mne.io.read_raw_edf(path, preload=False, verbose=False)
        eegbci.standardize(raw)
        if raw.info["sfreq"] != config["common_rate_hz"] or not set(config["channels"]).issubset(
            raw.ch_names
        ):
            raise AssertionError(f"EDF channel/rate changed: {record['filename']}")
        events, _ = mne.events_from_annotations(
            raw, event_id=config["external_event_map"], verbose=False
        )
        if len(events) == 0 or set(events[:, 2]) != {1, 2}:
            raise AssertionError(f"EDF left/right events changed: {record['filename']}")
        subject = record["subject"]
        run = record["run"]
        for trial, (sample, _previous, label) in enumerate(events, 1):
            trials.append(
                (f"physio_s{subject:03d}_r{run:02d}_t{trial:03d}", run, trial, int(sample), int(label))
            )
        raw.close()
    return trials


def validate(data_dir: Path | None = None) -> dict:
    config = _read(CONFIG)
    q14_external.verify_freeze(config)
    freeze_sha = sha256(E002_ROOT / "freeze_receipt.json")
    migration_file = EXTERNAL / "migration_receipt.json"
    migration = _read(migration_file)
    run = _read(EXTERNAL / "run_config.json")
    origin_run = _read(q14_r1_migration.ORIGINAL / "run_config.json")
    resolved_data = Path(run["data_dir"])
    if data_dir is not None:
        _same(str(data_dir.resolve()), str(resolved_data.resolve()), "external data dir")
    _same(run.get("data_dir"), str(resolved_data.resolve()), "run data directory")
    _same(run.get("runtime"), runtime_receipt(), "new container runtime")
    _same(run.get("device"), migration.get("device"), "inference device")
    expected_migration = q14_r1_migration.audit_origin(
        resolved_data, run["device"], config, freeze_sha
    )
    _same(migration, expected_migration, "pre-outcome migration custody receipt")
    migration_sha = sha256(migration_file)
    for key, expected in {
        "resumption_id": ID,
        "original_experiment_id": q14_r1_migration.ORIGINAL_ID,
        "runner_sha256": sha256(ROOT / "scripts/q14_r1_migration.py"),
        "original_runner_sha256": sha256(ROOT / "scripts/q14_external.py"),
        "config_sha256": sha256(CONFIG),
        "freeze_receipt_sha256": freeze_sha,
        "migration_receipt_sha256": migration_sha,
        "original_run_config_sha256": sha256(q14_r1_migration.ORIGINAL / "run_config.json"),
        "official_checksum_manifest_sha256": origin_run["official_checksum_manifest_sha256"],
        "subjects": list(q14_r1_migration.ALL),
        "runs": config["external_runs"],
    }.items():
        _same(run.get(key), expected, f"run config {key}")
    manifest = EXTERNAL / "physionet_SHA256SUMS.txt"
    _hash(manifest, run["official_checksum_manifest_sha256"])
    official = q14_external.parse_official_checksums(manifest.read_text(encoding="ascii"))
    completion = _read(EXTERNAL / "completion_receipt.json")
    for key, expected in {
        "status": "all_109_subjects_inferred",
        "resumption_id": ID,
        "original_experiment_id": q14_r1_migration.ORIGINAL_ID,
        "n_original_subjects_byte_identical": 55,
        "n_new_subjects": 54,
        "n_subjects": 109,
        "freeze_receipt_sha256": freeze_sha,
        "migration_receipt_sha256": migration_sha,
        "official_checksum_manifest_sha256": run["official_checksum_manifest_sha256"],
        "external_target_fit_count": 0,
    }.items():
        _same(completion.get(key), expected, f"completion {key}")
    _hash(EXTERNAL / "predictions.csv", completion["aggregate_predictions_sha256"])
    edfs = q14_r1_migration._edf_index(resolved_data)
    folders = sorted(path.name for path in EXTERNAL.glob("subject_???") if path.is_dir())
    _same(folders, [f"subject_{subject:03d}" for subject in q14_r1_migration.ALL], "subject directories")
    migration_by_subject = {
        item["subject"]: item for item in migration["original_subjects_hash_verified"]
    }
    _same(sorted(migration_by_subject), list(q14_r1_migration.MIGRATED), "migrated subjects")
    _same(
        sorted(set(q14_r1_migration.ALL) - set(migration_by_subject)),
        list(range(56, 110)),
        "newly inferred subject set",
    )
    frames: list[pd.DataFrame] = []
    scored: list[dict] = []
    edf_files_verified = 0
    frozen_at = datetime.fromisoformat(
        _read(E002_ROOT / "freeze_receipt.json")["frozen_at_utc"]
    )
    for subject in q14_r1_migration.ALL:
        folder = EXTERNAL / f"subject_{subject:03d}"
        receipt_file = folder / "receipt.json"
        prediction_file = folder / "predictions.csv"
        receipt = _read(receipt_file)
        for key, expected in {
            "status": "complete",
            "subject": subject,
            "source_models": config["models"],
            "external_target_fit_count": 0,
            "freeze_receipt_sha256": freeze_sha,
            "official_checksum_manifest_sha256": run["official_checksum_manifest_sha256"],
        }.items():
            _same(receipt.get(key), expected, f"S{subject:03d} receipt {key}")
        if datetime.fromisoformat(receipt["completed_at_utc"]) < frozen_at:
            raise AssertionError(f"S{subject:03d} receipt predates frozen source")
        _hash(prediction_file, receipt["predictions_sha256"])
        if subject in migration_by_subject:
            original = q14_r1_migration.ORIGINAL / f"subject_{subject:03d}"
            record = migration_by_subject[subject]
            _hash(receipt_file, record["receipt_sha256"])
            _hash(prediction_file, record["predictions_sha256"])
            _same(sha256(receipt_file), sha256(original / "receipt.json"), "original receipt bytes")
            _same(sha256(prediction_file), sha256(original / "predictions.csv"), "original prediction bytes")
        else:
            _same(receipt.get("resumption_id"), ID, f"S{subject:03d} continuation ID")
            _same(
                receipt.get("migration_receipt_sha256"), migration_sha, f"S{subject:03d} migration"
            )
        records = receipt.get("edf_files")
        if not isinstance(records, list) or len(records) != 3:
            raise AssertionError(f"S{subject:03d} wrong EDF file count")
        _same({item["run"] for item in records}, {4, 8, 12}, "EDF run set")
        for item in records:
            _same(item["subject"], subject, "EDF subject")
            _same(item["filename"], f"S{subject:03d}R{item['run']:02d}.edf", "EDF filename")
        trials = _trial_index(records, edfs, official, config)
        edf_files_verified += len(records)
        frame = pd.read_csv(prediction_file)
        _same(len(frame), receipt["n_prediction_rows"], "subject prediction row count")
        _same(len(trials), receipt["n_trials"], "subject trial count")
        _same(len(frame), 7 * len(trials), "seven frozen model-seed predictions")
        _same(set(frame["subject"]), {subject}, "prediction subject")
        # Rows keep the original frozen experiment ID; R1 identifies only the
        # changed container and custody, never a changed model or target rule.
        _same(set(frame["experiment_id"]), {"Q14-E002"}, "frozen prediction study ID")
        canonical = None
        for model in DEEP_MODELS:
            for seed in config["final_seeds"]:
                subset = frame.loc[
                    (frame["model"] == model) & (frame["seed"].astype(str) == str(seed))
                ]
                q14_validate._validate_external_subset(
                    subset, trials, subject, model, seed, scored
                )
                if canonical is None:
                    canonical = subset
        subset = frame.loc[
            (frame["model"] == "CSP4_LDA") & (frame["seed"].astype(str) == "deterministic")
        ]
        q14_validate._validate_external_subset(
            subset, trials, subject, "CSP4_LDA", "deterministic", scored
        )
        _same(
            {str(k): int(v) for k, v in canonical.groupby("run").size().items()},
            receipt["run_counts"],
            "run counts",
        )
        _same(
            {str(k): int(v) for k, v in canonical.groupby("label").size().items()},
            receipt["class_counts"],
            "class counts",
        )
        frames.append(frame)
    _same(edf_files_verified, 327, "official EDF count")
    reconstructed = pd.concat(frames, ignore_index=True)
    aggregate = pd.read_csv(EXTERNAL / "predictions.csv")
    pd.testing.assert_frame_equal(reconstructed, aggregate, check_dtype=False, check_exact=True)
    _same(len(aggregate), completion["n_prediction_rows"], "aggregate row count")
    metrics = (
        pd.DataFrame(scored)
        .sort_values(["subject", "model", "seed"], key=lambda series: series.astype(str))
        .reset_index(drop=True)
    )
    subject_metrics = metrics.groupby(["subject", "model"], as_index=False)[
        "balanced_accuracy"
    ].mean()
    wide = subject_metrics.pivot(index="subject", columns="model", values="balanced_accuracy")
    if wide.shape != (109, 3) or wide.isna().any().any():
        raise AssertionError("External subject-level metric matrix incomplete")
    differences = (wide["MU_BETA_SHARED"] - wide["BROAD_EEGNET"]).to_numpy()
    metric_file = EXTERNAL / "subject_seed_metrics.csv"
    subject_file = EXTERNAL / "subject_metrics.csv"
    contrast_file = EXTERNAL / "subject_primary_contrast.csv"
    confusion_file = EXTERNAL / "pooled_confusion_by_model_seed.csv"
    q14_external._atomic_csv(metric_file, metrics)
    q14_external._atomic_csv(subject_file, subject_metrics)
    q14_external._atomic_csv(
        contrast_file,
        pd.DataFrame(
            {
                "subject": wide.index.to_numpy(),
                "BROAD_EEGNET_BA": wide["BROAD_EEGNET"].to_numpy(),
                "MU_BETA_SHARED_BA": wide["MU_BETA_SHARED"].to_numpy(),
                "CSP4_LDA_BA": wide["CSP4_LDA"].to_numpy(),
                "primary_difference_shared_minus_broad": differences,
            }
        ),
    )
    q14_external._atomic_csv(
        confusion_file,
        metrics.groupby(["model", "seed"], as_index=False)[
            [
                "true_left_pred_left",
                "true_left_pred_right",
                "true_right_pred_left",
                "true_right_pred_right",
            ]
        ]
        .sum()
        .sort_values(["model", "seed"]),
    )
    figures = q14_validate._external_figures(wide, differences, EXTERNAL)
    rng = np.random.default_rng(20260924)
    bootstrap = differences[rng.integers(0, 109, size=(20000, 109))].mean(axis=1)
    nontied = int(np.count_nonzero(differences))
    primary = {
        "contrast": config["external_primary_contrast"],
        "unit": "external_subject_after_averaging_three_fixed_seeds",
        "n_subjects": 109,
        "mean_difference": float(differences.mean()),
        "bootstrap_seed": 20260924,
        "bootstrap_resamples": 20000,
        "subject_bootstrap_percentile_95_ci": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
        "positive_subjects": int((differences > 0).sum()),
        "negative_subjects": int((differences < 0).sum()),
        "tied_subjects": int((differences == 0).sum()),
        "two_sided_exact_sign_test_p_excluding_ties": (
            float(binomtest(int((differences > 0).sum()), nontied, p=0.5).pvalue)
            if nontied
            else 1.0
        ),
        "interpretation": "Predeclared descriptive paired external estimate; no target-based selection",
    }
    summary = {}
    for model in ALL_MODELS:
        values = wide[model].to_numpy()
        summary[model] = {
            "mean_subject_balanced_accuracy": float(values.mean()),
            "sd_subject_balanced_accuracy": float(values.std(ddof=1)),
            "min_subject_balanced_accuracy": float(values.min()),
            "max_subject_balanced_accuracy": float(values.max()),
        }
    report = {
        "passed": True,
        "experiment_id": ID,
        "original_experiment_id": "Q14-E002",
        "status": "independent_external_migration_validation_passed",
        "n_subjects": 109,
        "n_original_subjects_byte_identical": 55,
        "n_new_subjects": 54,
        "n_unique_trials": int(len(aggregate) // 7),
        "n_prediction_rows": len(aggregate),
        "n_verified_official_edf_files": edf_files_verified,
        "external_target_fit_count": 0,
        "source_freeze_sha256": freeze_sha,
        "migration_receipt_sha256": migration_sha,
        "official_checksum_manifest_sha256": run["official_checksum_manifest_sha256"],
        "original_run_config_sha256": migration["original_run_config_sha256"],
        "old_platform": migration["old_platform"],
        "new_platform": migration["new_platform"],
        "runtime_fields_except_platform_identical": True,
        "original_completion_schema_gap": migration["original_completion_schema_gap"],
        "subject_seed_metrics_sha256": sha256(metric_file),
        "subject_metrics_sha256": sha256(subject_file),
        "subject_primary_contrast_sha256": sha256(contrast_file),
        "pooled_confusion_sha256": sha256(confusion_file),
        "figures_sha256": figures,
        "summary": summary,
        "primary_paired_contrast": primary,
        "limitations": [
            "BNCI and PhysioNet acquisition/reference and preprocessing differ; no single mechanism is identified.",
            "Binary external BA is not numerically comparable to four-class Q5-Q9 accuracy.",
            "R1 changes only runtime kernel and output custody, not source models or target protocol.",
        ],
    }
    q14_external._atomic_json(RESULT / "validation_report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.data_dir), indent=2), flush=True)


if __name__ == "__main__":
    main()
