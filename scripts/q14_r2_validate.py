"""Independent EDF, custody, prediction, and statistical validation for R2.

This validator does not fit or choose any model. It reads native EDF event
coordinates, including the nine 128-Hz files, then audits the entire 109-person
cohort and reproduces the frozen subject-level paired comparison.
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

from scripts import q14_external, q14_r2_external, q14_r2_migration, q14_validate
from scripts.q14_source import (
    ALL_MODELS,
    CONFIG,
    DEEP_MODELS,
    E002_ROOT,
    runtime_receipt,
    sha256,
)

ID = q14_r2_migration.ID
RESULT = ROOT / "results" / ID
EXTERNAL = RESULT / "external"


def _hash(path: Path, expected: str) -> None:
    if not path.is_file() or sha256(path) != expected:
        raise AssertionError(f"Q14-R2 missing or changed artifact: {path}")


def _trial_index(
    records: list[dict], edfs: dict[str, Path], official: dict, config: dict, amendment: dict
) -> list[tuple]:
    trials = []
    for record in sorted(records, key=lambda row: row["run"]):
        filename = record["filename"]
        path = edfs.get(filename)
        if (
            path is None
            or path.stat().st_size != record["bytes"]
            or sha256(path) != record["sha256"]
            or record["sha256"] != official.get(filename)
        ):
            raise AssertionError(f"Unverified official EDF: {filename}")
        raw = mne.io.read_raw_edf(path, preload=False, verbose=False)
        try:
            eegbci.standardize(raw)
            subject = record["subject"]
            rate = q14_r2_external.expected_rate(subject, amendment) if subject >= 88 else 160
            if raw.info["sfreq"] != rate or not set(config["channels"]).issubset(raw.ch_names):
                raise AssertionError(f"Native EDF channel/rate mismatch: {filename}")
            events, _ = mne.events_from_annotations(
                raw, event_id=config["external_event_map"], verbose=False
            )
            if len(events) < 2 or set(events[:, 2]) != {1, 2}:
                raise AssertionError(f"EDF event classes incomplete: {filename}")
            for trial, (sample, _previous, label) in enumerate(events, 1):
                if sample + int(3.5 * rate) > raw.n_times:
                    raise AssertionError(f"Incomplete fixed cue epoch: {filename}")
                trials.append(
                    (
                        f"physio_s{subject:03d}_r{record['run']:02d}_t{trial:03d}",
                        record["run"],
                        trial,
                        int(sample),
                        int(label),
                    )
                )
        finally:
            raw.close()
    return trials


def validate(data_dir: Path | None = None) -> dict:
    config = q14_r2_migration.read(CONFIG)
    amendment = q14_r2_migration.read(q14_r2_migration.AMENDMENT)
    q14_external.verify_freeze(config)
    freeze_sha = sha256(E002_ROOT / "freeze_receipt.json")
    run = q14_r2_migration.read(EXTERNAL / "run_config.json")
    resolved_data = Path(run["data_dir"])
    if data_dir is not None:
        q14_r2_migration.same(
            str(data_dir.resolve()), str(resolved_data.resolve()), "validator data directory"
        )
    q14_r2_migration.same(run["runtime"], runtime_receipt(), "R2 runtime")
    origin = q14_r2_migration.audit_r1_origin(resolved_data, run["device"], config, freeze_sha)
    official_file = EXTERNAL / "physionet_SHA256SUMS.txt"
    _hash(official_file, origin["official_checksum_manifest_sha256"])
    official = q14_external.parse_official_checksums(official_file.read_text(encoding="ascii"))
    metadata = q14_r2_migration.read(EXTERNAL / "metadata_preflight.json")
    expected_preflight = {
        "status": "OFFICIAL_66_EDF_METADATA_VERIFIED_BEFORE_NEW_PREDICTIONS",
        "resumption_id": ID,
        "amendment_sha256": sha256(q14_r2_migration.AMENDMENT),
        "official_checksum_manifest_sha256": sha256(official_file),
        "edf_files": q14_r2_external.preflight_remaining(
            resolved_data, config, amendment, official
        ),
        "n_files": 66,
        "n_128_hz_runs": 9,
        "target_outcomes_scored": False,
    }
    q14_r2_migration.same(metadata, expected_preflight, "metadata-only preflight receipt")
    migration = q14_r2_migration.read(EXTERNAL / "migration_receipt.json")
    expected_migration = {
        **origin,
        "amendment_sha256": sha256(q14_r2_migration.AMENDMENT),
        "metadata_preflight_sha256": sha256(EXTERNAL / "metadata_preflight.json"),
        "data_dir": str(resolved_data.resolve()),
        "device": run["device"],
    }
    q14_r2_migration.same(migration, expected_migration, "R2 origin/custody receipt")
    migration_sha = sha256(EXTERNAL / "migration_receipt.json")
    expected_run = {
        "resumption_id": ID,
        "original_experiment_id": "Q14-E002",
        "runner_sha256": sha256(ROOT / "scripts/q14_r2_migration.py"),
        "adapter_sha256": sha256(ROOT / "scripts/q14_r2_external.py"),
        "original_runner_sha256": sha256(ROOT / "scripts/q14_external.py"),
        "config_sha256": sha256(CONFIG),
        "amendment_sha256": sha256(q14_r2_migration.AMENDMENT),
        "freeze_receipt_sha256": freeze_sha,
        "migration_receipt_sha256": migration_sha,
        "metadata_preflight_sha256": sha256(EXTERNAL / "metadata_preflight.json"),
        "official_checksum_manifest_sha256": sha256(official_file),
        "data_dir": str(resolved_data.resolve()),
        "device": run["device"],
        "subjects": list(q14_r2_migration.ALL),
        "runs": config["external_runs"],
        "runtime": runtime_receipt(),
    }
    q14_r2_migration.same(run, expected_run, "R2 run config")
    completion = q14_r2_migration.read(EXTERNAL / "completion_receipt.json")
    for key, expected in {
        "status": "all_109_subjects_inferred_under_r2_amendment",
        "resumption_id": ID,
        "original_experiment_id": "Q14-E002",
        "n_original_subjects_byte_identical": 87,
        "n_new_subjects": 22,
        "n_subjects": 109,
        "n_resampled_subjects": 3,
        "freeze_receipt_sha256": freeze_sha,
        "migration_receipt_sha256": migration_sha,
        "metadata_preflight_sha256": sha256(EXTERNAL / "metadata_preflight.json"),
        "official_checksum_manifest_sha256": sha256(official_file),
        "external_target_fit_count": 0,
    }.items():
        q14_r2_migration.same(completion.get(key), expected, f"R2 completion {key}")
    _hash(EXTERNAL / "predictions.csv", completion["aggregate_predictions_sha256"])
    folders = sorted(path.name for path in EXTERNAL.glob("subject_???") if path.is_dir())
    q14_r2_migration.same(
        folders, [f"subject_{s:03d}" for s in range(1, 110)], "109 complete subject directories"
    )
    edfs = {}
    for path in resolved_data.rglob("*.edf"):
        if path.name in edfs:
            raise AssertionError(f"Duplicate external EDF basename: {path.name}")
        edfs[path.name] = path
    inherited = {item["subject"]: item for item in migration["copied_subjects_hash_verified"]}
    q14_r2_migration.same(
        sorted(inherited), list(q14_r2_migration.COPIED), "87 migrated subject records"
    )
    preflight_by_name = {item["filename"]: item for item in metadata["edf_files"]}
    frames = []
    scored = []
    verified_edfs = 0
    frozen_at = datetime.fromisoformat(
        q14_r2_migration.read(E002_ROOT / "freeze_receipt.json")["frozen_at_utc"]
    )
    for subject in q14_r2_migration.ALL:
        folder = EXTERNAL / f"subject_{subject:03d}"
        receipt_file = folder / "receipt.json"
        prediction_file = folder / "predictions.csv"
        receipt = q14_r2_migration.read(receipt_file)
        for key, expected in {
            "status": "complete",
            "subject": subject,
            "source_models": config["models"],
            "external_target_fit_count": 0,
            "freeze_receipt_sha256": freeze_sha,
            "official_checksum_manifest_sha256": sha256(official_file),
        }.items():
            q14_r2_migration.same(receipt.get(key), expected, f"S{subject:03d} receipt {key}")
        if datetime.fromisoformat(receipt["completed_at_utc"]) < frozen_at:
            raise AssertionError(f"S{subject:03d} predates frozen source")
        _hash(prediction_file, receipt["predictions_sha256"])
        if subject in inherited:
            _hash(receipt_file, inherited[subject]["receipt_sha256"])
            _hash(prediction_file, inherited[subject]["predictions_sha256"])
            _hash(
                q14_r2_migration.R1 / f"subject_{subject:03d}/receipt.json",
                inherited[subject]["receipt_sha256"],
            )
        else:
            q14_r2_migration.same(receipt.get("resumption_id"), ID, "R2 new subject ID")
            q14_r2_migration.same(
                receipt.get("migration_receipt_sha256"), migration_sha, "R2 migration link"
            )
            q14_r2_migration.same(
                receipt.get("metadata_preflight_sha256"),
                sha256(EXTERNAL / "metadata_preflight.json"),
                "R2 metadata link",
            )
        records = receipt.get("edf_files")
        if not isinstance(records, list) or len(records) != 3:
            raise AssertionError(f"S{subject:03d} has wrong EDF count")
        q14_r2_migration.same({item["run"] for item in records}, {4, 8, 12}, "subject EDF run set")
        for item in records:
            q14_r2_migration.same(item["subject"], subject, "EDF subject")
            q14_r2_migration.same(
                item["filename"], f"S{subject:03d}R{item['run']:02d}.edf", "EDF filename"
            )
            if subject in q14_r2_migration.NEW:
                prior = preflight_by_name[item["filename"]]
                for key in ("subject", "run", "filename", "bytes", "sha256"):
                    q14_r2_migration.same(item[key], prior[key], f"R2 EDF {key}")
        if subject in q14_r2_migration.NEW:
            q14_r2_migration.same(
                receipt.get("native_rates_hz"),
                {
                    str(item["run"]): preflight_by_name[item["filename"]]["native_rate_hz"]
                    for item in records
                },
                "native rate provenance",
            )
        trials = _trial_index(records, edfs, official, config, amendment)
        verified_edfs += len(records)
        frame = pd.read_csv(prediction_file)
        q14_r2_migration.same(
            len(frame), receipt["n_prediction_rows"], "subject prediction row count"
        )
        q14_r2_migration.same(len(trials), receipt["n_trials"], "trial count")
        q14_r2_migration.same(len(frame), 7 * len(trials), "seven predictions per trial")
        q14_r2_migration.same(set(frame["subject"]), {subject}, "prediction subject")
        q14_r2_migration.same(set(frame["experiment_id"]), {"Q14-E002"}, "frozen model study ID")
        canonical = None
        for model in DEEP_MODELS:
            for seed in config["final_seeds"]:
                subset = frame.loc[
                    (frame["model"] == model) & (frame["seed"].astype(str) == str(seed))
                ]
                q14_validate._validate_external_subset(subset, trials, subject, model, seed, scored)
                if canonical is None:
                    canonical = subset
        subset = frame.loc[
            (frame["model"] == "CSP4_LDA") & (frame["seed"].astype(str) == "deterministic")
        ]
        q14_validate._validate_external_subset(
            subset, trials, subject, "CSP4_LDA", "deterministic", scored
        )
        q14_r2_migration.same(
            {str(k): int(v) for k, v in canonical.groupby("run").size().items()},
            receipt["run_counts"],
            "run trial counts",
        )
        q14_r2_migration.same(
            {str(k): int(v) for k, v in canonical.groupby("label").size().items()},
            receipt["class_counts"],
            "class trial counts",
        )
        frames.append(frame)
    q14_r2_migration.same(verified_edfs, 327, "all 327 official EDFs")
    reconstructed = pd.concat(frames, ignore_index=True)
    aggregate = pd.read_csv(EXTERNAL / "predictions.csv")
    pd.testing.assert_frame_equal(reconstructed, aggregate, check_dtype=False, check_exact=True)
    q14_r2_migration.same(
        len(aggregate), completion["n_prediction_rows"], "aggregate prediction row count"
    )
    metrics = (
        pd.DataFrame(scored)
        .sort_values(["subject", "model", "seed"], key=lambda column: column.astype(str))
        .reset_index(drop=True)
    )
    subject_metrics = metrics.groupby(["subject", "model"], as_index=False)[
        "balanced_accuracy"
    ].mean()
    wide = subject_metrics.pivot(index="subject", columns="model", values="balanced_accuracy")
    if wide.shape != (109, 3) or wide.isna().any().any():
        raise AssertionError("Incomplete 109-by-3 external subject metric table")
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
                "native_rate_hz": [
                    128 if subject in amendment["native_128_hz_subjects"] else 160
                    for subject in wide.index
                ],
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
        "protocol_amendment": "R2 metadata-triggered 128-to-160-Hz polyphase resampling",
    }
    native = wide.index.isin(amendment["native_128_hz_subjects"])
    sensitivity = {
        "resampled_128_hz_subjects": amendment["native_128_hz_subjects"],
        "n_resampled_subjects": int(native.sum()),
        "n_native_160_hz_subjects": int((~native).sum()),
        "resampled_mean_difference": float(differences[native].mean()),
        "native_160_hz_mean_difference": float(differences[~native].mean()),
        "role": "descriptive sensitivity only; no alternate primary endpoint or model selection",
    }
    q14_external._atomic_json(EXTERNAL / "native_rate_sensitivity.json", sensitivity)
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
        "status": "independent_external_protocol_amendment_validation_passed",
        "n_subjects": 109,
        "n_original_subjects_byte_identical": 87,
        "n_new_subjects": 22,
        "n_resampled_subjects": 3,
        "n_unique_trials": int(len(aggregate) // 7),
        "n_prediction_rows": len(aggregate),
        "n_verified_official_edf_files": verified_edfs,
        "external_target_fit_count": 0,
        "source_freeze_sha256": freeze_sha,
        "migration_receipt_sha256": migration_sha,
        "metadata_preflight_sha256": sha256(EXTERNAL / "metadata_preflight.json"),
        "official_checksum_manifest_sha256": sha256(official_file),
        "r1_run_config_sha256": origin["r1_run_config_sha256"],
        "old_platform": origin["old_platform"],
        "new_platform": origin["new_platform"],
        "runtime_fields_except_platform_identical": True,
        "protocol_amended_after_partial_external_execution": True,
        "subject_seed_metrics_sha256": sha256(metric_file),
        "subject_metrics_sha256": sha256(subject_file),
        "subject_primary_contrast_sha256": sha256(contrast_file),
        "pooled_confusion_sha256": sha256(confusion_file),
        "native_rate_sensitivity_sha256": sha256(EXTERNAL / "native_rate_sensitivity.json"),
        "figures_sha256": figures,
        "summary": summary,
        "primary_paired_contrast": primary,
        "native_rate_sensitivity": sensitivity,
        "limitations": [
            "R2 was amended after a metadata-triggered R1 failure; it is not an unchanged original Q14-E002 execution.",
            "Only three subjects needed 128-to-160-Hz resampling; their subgroup is descriptive, not separately powered.",
            "BNCI and PhysioNet acquisition/reference differ, so the external contrast does not identify one mechanism.",
            "Binary external BA cannot be directly compared numerically with four-class Q5-Q9 results.",
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
