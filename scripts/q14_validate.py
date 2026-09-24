"""Independent Q14 source/external contract checks; never train or select a model."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, confusion_matrix

from scripts.q14_source import (
    ALL_MODELS,
    CONFIG,
    DEEP_MODELS,
    E001_ROOT,
    E002_ROOT,
    mean_rank_epoch,
    partitions,
    runtime_receipt,
    sha256,
    sha_ids,
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)


def _check_hash(path: Path, digest: str) -> None:
    if not path.exists() or sha256(path) != digest:
        raise AssertionError(f"Missing or hash-mismatched artifact: {path}")


def _committed_protocol_head() -> str:
    """Require external protocol/implementation in a real clean Git commit."""
    paths = [
        "research_runs/Q14-E001/CONFIG.json",
        "research_runs/Q14-E001/PROTOCOL.md",
        "research_runs/Q14-E001/METADATA_AUDIT.json",
        "scripts/q14_source.py",
        "scripts/q14_external.py",
        "scripts/q14_validate.py",
        "scripts/q14_batch.py",
        "tests/test_q14_external_protocol.py",
    ]
    subprocess.run(
        ["git", "ls-files", "--error-unmatch", *paths],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", *paths],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        raise AssertionError("Q14 external protocol/code must be committed and clean before freeze")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _check_manifest(path: Path, expected: dict, payload_file: str, hash_field: str) -> dict:
    record = _read(path / "manifest.json")
    if record.get("status") != "complete":
        raise AssertionError(f"Incomplete fit: {path}")
    for key, value in expected.items():
        if record.get(key) != value:
            raise AssertionError(f"Fit manifest mismatch: {path}: {key}")
    _check_hash(path / payload_file, record[hash_field])
    return record


def _verify_predictions(path: Path, meta: pd.DataFrame, target: int, model: str, seed) -> dict:
    frame = pd.read_csv(path)
    expected = meta.loc[meta["subject"] == target].reset_index(drop=True)
    if frame["sample_id"].tolist() != expected["sample_id"].tolist() or len(frame) != 288:
        raise AssertionError(f"Target prediction IDs/count mismatch: {path}")
    for key in ("subject", "session", "run", "trial", "label", "artifact_flagged"):
        if frame[key].astype(str).tolist() != expected[key].astype(str).tolist():
            raise AssertionError(f"Target prediction metadata mismatch: {path}: {key}")
    if not (frame["model"] == model).all() or not (frame["seed"].astype(str) == str(seed)).all():
        raise AssertionError(f"Prediction model/seed mismatch: {path}")
    probabilities = frame[["p_left", "p_right"]].to_numpy(dtype=float)
    if (
        not np.isfinite(probabilities).all()
        or (probabilities < 0).any()
        or (probabilities > 1).any()
    ):
        raise AssertionError(f"Invalid probabilities: {path}")
    if not np.allclose(probabilities.sum(axis=1), 1, atol=1e-5):
        raise AssertionError(f"Probability sum mismatch: {path}")
    if not np.array_equal(
        np.argmax(probabilities, axis=1) + 1, frame["predicted_label"].to_numpy()
    ):
        raise AssertionError(f"Prediction argmax mismatch: {path}")
    matrix = confusion_matrix(frame["label"], frame["predicted_label"], labels=[1, 2])
    return {
        "subject": target,
        "model": model,
        "seed": seed,
        "n_trials": len(frame),
        "balanced_accuracy": float(
            balanced_accuracy_score(frame["label"], frame["predicted_label"])
        ),
        "tn_fp_fn_tp": matrix.ravel().tolist(),
        "prediction_sha256": sha256(path),
    }


def validate_source(stage: str) -> dict:
    config = _read(CONFIG)
    root = E001_ROOT if stage == "e001" else E002_ROOT / "source"
    if stage == "e002":
        parent = _read(E001_ROOT / "validation_report.json")
        if (
            not parent.get("passed")
            or parent.get("config_sha256") != sha256(CONFIG)
            or parent.get("source_runner_sha256") != sha256(ROOT / "scripts/q14_source.py")
        ):
            raise AssertionError("Q14-E001 validation was not passed under current protocol/code")
    run = _read(root / "run_config.json")
    if run != {
        "stage": stage,
        "config_sha256": sha256(CONFIG),
        "runner_sha256": sha256(ROOT / "scripts/q14_source.py"),
        "data_dir": run.get("data_dir"),
        "device": run.get("device"),
        "runtime": runtime_receipt(),
    }:
        raise AssertionError("Q14 source run_config differs from current code/config")
    files = _read(root / "source_files.json")["files"]
    frozen = {
        Path(row["path"]).name: row
        for row in _read(ROOT / "research_runs/Q8-E001/results/source_files.json")
    }
    if len(files) != 18 or {f["filename"] for f in files} != set(frozen):
        raise AssertionError("Source file manifest does not match 18 frozen Q8 MAT files")
    for item in files:
        if (
            item["sha256"] != frozen[item["filename"]]["sha256"]
            or item["bytes"] != frozen[item["filename"]]["bytes"]
        ):
            raise AssertionError("Source MAT hash differs from frozen Q8")
    meta = pd.read_csv(root / "source_metadata.csv")
    audit = pd.read_csv(root / "source_audit.csv")
    if len(audit) != 9 * 2 * 6:
        raise AssertionError("BNCI source audit lacks one or more runs")
    for row in audit.itertuples(index=False):
        if (
            json.loads(row.eeg_channel_names) != config["channels"]
            or int(row.n_eeg_channels) != 22
            or float(row.sampling_rate_hz) != 250.0
            or int(row.n_times_per_epoch) != 750
            or int(row.n_candidate_trials) != 24
            or int(row.n_kept_trials) != 24
        ):
            raise AssertionError("BNCI binary source run changed channel/window/trial contract")
    if len(meta) != 2592 or meta["sample_id"].duplicated().any():
        raise AssertionError("Wrong binary source trial count or duplicate ID")
    if meta.groupby("subject").size().to_dict() != {s: 288 for s in range(1, 10)}:
        raise AssertionError("Every BNCI source subject must contribute 288 binary trials")
    if set(meta["label"]) != {1, 2}:
        raise AssertionError("Unexpected source labels")
    stage_receipt = _read(root / "source_stage_complete.json")
    if stage_receipt.get("stage") != stage or stage_receipt.get("status") != "all_fits_attempted":
        raise AssertionError("Source stage completion receipt missing/mismatched")
    expected_deep = 126 if stage == "e001" else 14
    expected_shallow = 9 if stage == "e001" else 1
    if (stage_receipt["deep_fit_count"], stage_receipt["shallow_fit_count"]) != (
        expected_deep,
        expected_shallow,
    ):
        raise AssertionError("Source stage fit counts differ from locked protocol")
    counts = {"deep_inner": 0, "deep_final": 0, "shallow": 0, "predictions": 0}
    metrics = []
    for model in DEEP_MODELS:
        for label, source, groups, targets in partitions(stage, config):
            base = root / model / label
            curves = {}
            for fold, val_subjects in enumerate(groups, 1):
                train_subjects = [s for s in source if s not in val_subjects]
                train_ids = meta.loc[meta["subject"].isin(train_subjects), "sample_id"].to_numpy()
                expected = {
                    "stage": stage,
                    "model": model,
                    "outer": label,
                    "inner_fold": fold,
                    "train_subjects": train_subjects,
                    "validation_subjects": val_subjects,
                    "target_subjects": targets,
                    "train_sample_ids_sha256": sha_ids(train_ids),
                    "seed": config["selection_seed"],
                    "epochs": config["max_epochs"],
                    "config_sha256": sha256(CONFIG),
                }
                path = base / f"inner_{fold:02d}"
                record = _check_manifest(path, expected, "checkpoint.pt", "checkpoint_sha256")
                _check_hash(path / "curve.json", record["curve_sha256"])
                curves[fold] = _read(path / "curve.json")["epochs"]
                counts["deep_inner"] += 1
            selected = mean_rank_epoch(curves, config["max_epochs"])
            selection = _read(base / "selection.json")
            if (
                selection["selected_epoch"] != selected
                or selection["source_subjects"] != source
                or selection["validation_groups"] != groups
            ):
                raise AssertionError("Independent source-only selection mismatch")
            if selection["inner_curve_sha256"] != [
                sha256(base / f"inner_{fold:02d}" / "curve.json") for fold in range(1, 5)
            ]:
                raise AssertionError("Selection input curve SHA mismatch")
            source_ids = meta.loc[meta["subject"].isin(source), "sample_id"].to_numpy()
            for seed in config["final_seeds"]:
                path = base / f"final_seed_{seed}"
                expected = {
                    "stage": stage,
                    "model": model,
                    "outer": label,
                    "train_subjects": source,
                    "target_subjects": targets,
                    "train_sample_ids_sha256": sha_ids(source_ids),
                    "seed": seed,
                    "epochs": selected,
                    "config_sha256": sha256(CONFIG),
                }
                record = _check_manifest(path, expected, "checkpoint.pt", "checkpoint_sha256")
                _check_hash(path / "curve.json", record["curve_sha256"])
                counts["deep_final"] += 1
                if stage == "e001":
                    metrics.append(
                        _verify_predictions(path / "predictions.csv", meta, targets[0], model, seed)
                    )
                    counts["predictions"] += 1
    for label, source, _groups, targets in partitions(stage, config):
        base = root / "CSP4_LDA" / label
        expected = {
            "model": "CSP4_LDA",
            "train_subjects": source,
            "train_sample_ids_sha256": sha_ids(
                meta.loc[meta["subject"].isin(source), "sample_id"].to_numpy()
            ),
            "config_sha256": sha256(CONFIG),
        }
        _check_manifest(base, expected, "model.joblib", "model_sha256")
        counts["shallow"] += 1
        if stage == "e001":
            metrics.append(
                _verify_predictions(
                    base / "predictions.csv", meta, targets[0], "CSP4_LDA", "deterministic"
                )
            )
            counts["predictions"] += 1
    expected_counts = {
        "deep_inner": (72 if stage == "e001" else 8),
        "deep_final": (54 if stage == "e001" else 6),
        "shallow": expected_shallow,
        "predictions": (63 if stage == "e001" else 0),
    }
    if counts != expected_counts:
        raise AssertionError(f"Fit/prediction counts: {counts} != {expected_counts}")
    result = {
        "passed": True,
        "stage": stage,
        "experiment_id": "Q14-E001" if stage == "e001" else "Q14-E002",
        "counts": counts,
        "source_subjects": config["source_subjects"],
        "source_data_sha256": sha256(root / "source_files.json"),
        "config_sha256": sha256(CONFIG),
        "source_runner_sha256": sha256(ROOT / "scripts/q14_source.py"),
        "validator_sha256": sha256(Path(__file__)),
        "interpretation": "BNCI matched-binary development only; external performance not inspected",
    }
    if stage == "e001":
        pd.DataFrame(metrics).to_csv(root / "subject_seed_metrics.csv", index=False)
        result["subject_seed_metrics_sha256"] = sha256(root / "subject_seed_metrics.csv")
    _write(root / "validation_report.json", result)
    if stage == "e002":
        git_commit = _committed_protocol_head()
        freeze_path = E002_ROOT / "freeze_receipt.json"
        prior = _read(freeze_path) if freeze_path.exists() else None
        freeze = {
            "status": "FROZEN_BEFORE_EXTERNAL_DATA_ACCESS",
            "frozen_at_utc": prior["frozen_at_utc"] if prior else datetime.now(UTC).isoformat(),
            "protocol_git_commit": prior["protocol_git_commit"] if prior else git_commit,
            "experiment_id": "Q14-E002",
            "target_dataset": config["external_dataset"],
            "target_runs": config["external_runs"],
            "target_subjects": config["external_subjects"],
            "primary_contrast": config["external_primary_contrast"],
            "models": config["models"],
            "source_validation_report_sha256": sha256(root / "validation_report.json"),
            "q14_e001_validation_report_sha256": sha256(E001_ROOT / "validation_report.json"),
            "config_sha256": sha256(CONFIG),
            "source_runner_sha256": sha256(ROOT / "scripts/q14_source.py"),
            "external_runner_sha256": sha256(ROOT / "scripts/q14_external.py"),
            "batch_runner_sha256": sha256(ROOT / "scripts/q14_batch.py"),
            "contract_tests_sha256": sha256(ROOT / "tests/test_q14_external_protocol.py"),
            "metadata_audit_sha256": sha256(ROOT / "research_runs/Q14-E001/METADATA_AUDIT.json"),
            "validator_sha256": sha256(Path(__file__)),
            "source_files_sha256": sha256(root / "source_files.json"),
            "source_metadata_sha256": sha256(root / "source_metadata.csv"),
            "source_run_config_sha256": sha256(root / "run_config.json"),
            "checkpoints": {
                model: {
                    str(seed): sha256(
                        root / model / "all_source" / f"final_seed_{seed}" / "checkpoint.pt"
                    )
                    for seed in config["final_seeds"]
                }
                for model in DEEP_MODELS
            },
            "csp_model_sha256": sha256(root / "CSP4_LDA" / "all_source" / "model.joblib"),
            "selected_epochs": {
                model: _read(root / model / "all_source" / "selection.json")["selected_epoch"]
                for model in DEEP_MODELS
            },
            "external_target_fit_count": 0,
        }
        if freeze_path.exists() and _read(freeze_path) != freeze:
            raise AssertionError("Existing freeze receipt differs; protocol cannot silently change")
        _write(freeze_path, freeze)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["e001", "e002", "external"], required=True)
    args = parser.parse_args()
    if args.stage == "external":
        report = validate_external()
    else:
        report = validate_source(args.stage)
    print(json.dumps(report, indent=2))


def validate_external() -> dict:
    """Reconstruct trial identity and all reported metrics without model training."""
    import mne
    from mne.datasets import eegbci

    from scripts.q14_external import EXTERNAL_ROOT, parse_official_checksums, verify_freeze

    config = _read(CONFIG)
    freeze = verify_freeze(config)
    freeze_sha = sha256(E002_ROOT / "freeze_receipt.json")
    if datetime.fromisoformat(freeze["frozen_at_utc"]).tzinfo is None:
        raise AssertionError("Freeze timestamp has no timezone")
    run = _read(EXTERNAL_ROOT / "run_config.json")
    if (
        run.get("config_sha256") != sha256(CONFIG)
        or run.get("freeze_receipt_sha256") != freeze_sha
        or run.get("runner_sha256") != sha256(ROOT / "scripts/q14_external.py")
        or run.get("subjects") != list(range(1, 110))
        or run.get("runs") != config["external_runs"]
    ):
        raise AssertionError("External run configuration changed after source freeze")
    official_manifest = EXTERNAL_ROOT / "physionet_SHA256SUMS.txt"
    _check_hash(official_manifest, run["official_checksum_manifest_sha256"])
    official = parse_official_checksums(official_manifest.read_text(encoding="ascii"))
    completion = _read(EXTERNAL_ROOT / "completion_receipt.json")
    if (
        completion.get("status") != "all_109_subjects_inferred"
        or completion.get("external_target_fit_count") != 0
    ):
        raise AssertionError("External inference did not complete as zero-shot")
    if completion.get("freeze_receipt_sha256") != freeze_sha:
        raise AssertionError("External completion used another source freeze")
    if (
        completion.get("official_checksum_manifest_sha256")
        != run["official_checksum_manifest_sha256"]
    ):
        raise AssertionError("External completion used another official checksum manifest")
    _check_hash(EXTERNAL_ROOT / "predictions.csv", completion["aggregate_predictions_sha256"])
    data_dir = Path(run["data_dir"])
    local_edfs = {}
    for path in data_dir.rglob("*.edf"):
        if path.name in local_edfs:
            raise AssertionError(f"Duplicate EDF basename under external data root: {path.name}")
        local_edfs[path.name] = path
    frames = []
    scored = []
    file_hashes = []
    frozen_at = datetime.fromisoformat(freeze["frozen_at_utc"])
    for subject in range(1, 110):
        output = EXTERNAL_ROOT / f"subject_{subject:03d}"
        receipt = _read(output / "receipt.json")
        if (
            receipt.get("status") != "complete"
            or receipt.get("subject") != subject
            or receipt.get("freeze_receipt_sha256") != freeze_sha
            or receipt.get("external_target_fit_count") != 0
        ):
            raise AssertionError(
                f"Subject receipt differs from frozen zero-shot protocol: {subject}"
            )
        if datetime.fromisoformat(receipt["completed_at_utc"]) < frozen_at:
            raise AssertionError("External prediction receipt predates source freeze")
        file = output / "predictions.csv"
        _check_hash(file, receipt["predictions_sha256"])
        frame = pd.read_csv(file)
        if len(frame) != receipt["n_prediction_rows"]:
            raise AssertionError("External subject prediction row count differs from receipt")
        if set(frame["experiment_id"]) != {"Q14-E002"} or set(frame["subject"]) != {subject}:
            raise AssertionError("External subject/experiment identity mismatch")
        if len(receipt["edf_files"]) != 3 or {r["run"] for r in receipt["edf_files"]} != {4, 8, 12}:
            raise AssertionError("External subject used an incorrect EDF run set")
        canonical = None
        edf_trials = []
        for record in sorted(receipt["edf_files"], key=lambda item: item["run"]):
            path = local_edfs.get(record["filename"])
            if (
                path is None
                or path.stat().st_size != record["bytes"]
                or sha256(path) != record["sha256"]
                or record["sha256"] != official.get(record["filename"])
            ):
                raise AssertionError(f"EDF missing/changed after inference: {record['filename']}")
            file_hashes.append(record)
            raw = mne.io.read_raw_edf(path, preload=False, verbose=False)
            eegbci.standardize(raw)
            if raw.info["sfreq"] != config["common_rate_hz"] or not set(
                config["channels"]
            ).issubset(raw.ch_names):
                raise AssertionError(
                    "EDF channel/rate metadata contradicts predeclared harmonization"
                )
            events, _ = mne.events_from_annotations(
                raw, event_id=config["external_event_map"], verbose=False
            )
            if len(events) == 0 or set(events[:, 2]) != {1, 2}:
                raise AssertionError("EDF event mapping lacks both predeclared classes")
            for trial, (sample, _previous, label) in enumerate(events, 1):
                edf_trials.append(
                    (
                        f"physio_s{subject:03d}_r{record['run']:02d}_t{trial:03d}",
                        record["run"],
                        trial,
                        int(sample),
                        int(label),
                    )
                )
            raw.close()
        for model in DEEP_MODELS:
            for seed in config["final_seeds"]:
                subset = frame.loc[
                    (frame["model"] == model) & (frame["seed"].astype(str) == str(seed))
                ]
                _validate_external_subset(subset, edf_trials, subject, model, seed, scored)
                if canonical is None:
                    canonical = subset[
                        ["sample_id", "run", "trial", "event_sample", "label"]
                    ].reset_index(drop=True)
        subset = frame.loc[
            (frame["model"] == "CSP4_LDA") & (frame["seed"].astype(str) == "deterministic")
        ]
        _validate_external_subset(subset, edf_trials, subject, "CSP4_LDA", "deterministic", scored)
        if len(frame) != len(edf_trials) * 7 or len(edf_trials) != receipt["n_trials"]:
            raise AssertionError("External subject has missing/extra model-seed predictions")
        class_counts = {str(k): int(v) for k, v in canonical.groupby("label").size().items()}
        run_counts = {str(k): int(v) for k, v in canonical.groupby("run").size().items()}
        if class_counts != receipt["class_counts"] or run_counts != receipt["run_counts"]:
            raise AssertionError("External subject class/run counts differ from receipt")
        frames.append(frame)
    reconstructed = pd.concat(frames, ignore_index=True)
    aggregate = pd.read_csv(EXTERNAL_ROOT / "predictions.csv")
    pd.testing.assert_frame_equal(reconstructed, aggregate, check_dtype=False, check_exact=True)
    if len(aggregate) != completion["n_prediction_rows"]:
        raise AssertionError("Aggregate prediction count differs from completion receipt")
    metrics = (
        pd.DataFrame(scored)
        .sort_values(["subject", "model", "seed"], key=lambda series: series.astype(str))
        .reset_index(drop=True)
    )
    metric_file = EXTERNAL_ROOT / "subject_seed_metrics.csv"
    metrics.to_csv(metric_file, index=False)
    subject = metrics.groupby(["subject", "model"], as_index=False)["balanced_accuracy"].mean()
    subject_file = EXTERNAL_ROOT / "subject_metrics.csv"
    subject.to_csv(subject_file, index=False)
    wide = subject.pivot(index="subject", columns="model", values="balanced_accuracy")
    if wide.shape != (109, 3) or wide.isna().any().any():
        raise AssertionError("Subject-level method comparison incomplete")
    differences = (wide["MU_BETA_SHARED"] - wide["BROAD_EEGNET"]).to_numpy()
    contrast_file = EXTERNAL_ROOT / "subject_primary_contrast.csv"
    pd.DataFrame(
        {
            "subject": wide.index.to_numpy(),
            "BROAD_EEGNET_BA": wide["BROAD_EEGNET"].to_numpy(),
            "MU_BETA_SHARED_BA": wide["MU_BETA_SHARED"].to_numpy(),
            "CSP4_LDA_BA": wide["CSP4_LDA"].to_numpy(),
            "primary_difference_shared_minus_broad": differences,
        }
    ).to_csv(contrast_file, index=False)
    pooled_file = EXTERNAL_ROOT / "pooled_confusion_by_model_seed.csv"
    (
        metrics.groupby(["model", "seed"], as_index=False)[
            [
                "true_left_pred_left",
                "true_left_pred_right",
                "true_right_pred_left",
                "true_right_pred_right",
            ]
        ]
        .sum()
        .sort_values(["model", "seed"])
        .to_csv(pooled_file, index=False)
    )
    figures = _external_figures(wide, differences, EXTERNAL_ROOT)
    rng = np.random.default_rng(20260924)
    bootstrap = differences[rng.integers(0, 109, size=(20000, 109))].mean(axis=1)
    from scipy.stats import binomtest

    nontied = int(np.count_nonzero(differences))
    paired = {
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
        "interpretation": "Descriptive external paired estimate; no target-based model selection",
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
        "experiment_id": "Q14-E002",
        "status": "independent_external_validation_passed",
        "target_dataset": config["external_dataset"],
        "n_subjects": 109,
        "n_unique_trials": int(len(aggregate) // 7),
        "n_prediction_rows": len(aggregate),
        "n_verified_edf_files": len(file_hashes),
        "external_target_fit_count": 0,
        "source_freeze_sha256": freeze_sha,
        "metrics_sha256": sha256(metric_file),
        "subject_metrics_sha256": sha256(subject_file),
        "subject_primary_contrast_sha256": sha256(contrast_file),
        "pooled_confusion_by_model_seed_sha256": sha256(pooled_file),
        "figures_sha256": figures,
        "summary": summary,
        "primary_paired_contrast": paired,
        "limitations": [
            "BNCI/PhysioNet acquisition and reference differ; a cross-dataset transfer effect cannot be attributed to a single mechanism.",
            "The binary external endpoint is not numerically comparable to frozen four-class Q5-Q9 accuracy.",
            "All PhysioNet subjects are evaluated without tuning; any future adaptation needs a new experiment ID.",
        ],
    }
    _write(EXTERNAL_ROOT / "validation_report.json", report)
    return report


def _external_figures(wide: pd.DataFrame, differences: np.ndarray, root: Path) -> dict[str, str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"BROAD_EEGNET": "#1f77b4", "MU_BETA_SHARED": "#ff7f0e", "CSP4_LDA": "#2ca02c"}
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    for model, color in colors.items():
        values = np.sort(wide[model].to_numpy())
        ax.step(
            values,
            np.arange(1, len(values) + 1) / len(values),
            where="post",
            label=model,
            color=color,
        )
    ax.axvline(0.5, color="black", linestyle="--", linewidth=1, label="binary chance")
    ax.set(
        xlabel="Subject-level balanced accuracy",
        ylabel="Empirical cumulative fraction",
        title="Q14-E002 external zero-shot: all 109 subjects",
    )
    ax.set_xlim(0, 1)
    ax.legend(loc="lower right")
    fig.tight_layout()
    ecdf = root / "external_subject_ba_ecdf.png"
    fig.savefig(ecdf, dpi=180)
    plt.close(fig)
    order = np.argsort(differences)
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.scatter(np.arange(1, len(order) + 1), differences[order], s=12, color="#6a3d9a")
    ax.axhline(0, color="black", linestyle="--", linewidth=1)
    ax.set(
        xlabel="External subject, sorted by paired effect",
        ylabel="Shared minus broad BA",
        title="Q14-E002 predeclared subject-wise paired contrast",
    )
    fig.tight_layout()
    effects = root / "external_subject_paired_effects.png"
    fig.savefig(effects, dpi=180)
    plt.close(fig)
    return {ecdf.name: sha256(ecdf), effects.name: sha256(effects)}


def _validate_external_subset(subset, edf_trials, subject, model, seed, scored):
    if len(subset) != len(edf_trials):
        raise AssertionError(f"Missing external predictions for S{subject:03d}/{model}/{seed}")
    tuples = list(
        zip(
            subset["sample_id"],
            subset["run"],
            subset["trial"],
            subset["event_sample"],
            subset["label"],
        )
    )
    if tuples != edf_trials:
        raise AssertionError(
            "Predicted trial IDs/labels disagree with independent EDF annotation read"
        )
    probabilities = subset[["p_left", "p_right"]].to_numpy(dtype=float)
    if (
        not np.isfinite(probabilities).all()
        or (probabilities < 0).any()
        or (probabilities > 1).any()
    ):
        raise AssertionError("Invalid external probabilities")
    if not np.allclose(probabilities.sum(1), 1, atol=1e-5):
        raise AssertionError("External probabilities do not sum to one")
    if not np.array_equal(
        subset["predicted_label"].to_numpy(), np.argmax(probabilities, axis=1) + 1
    ):
        raise AssertionError("External predicted label is not probability argmax")
    matrix = confusion_matrix(subset["label"], subset["predicted_label"], labels=[1, 2])
    scored.append(
        {
            "subject": subject,
            "model": model,
            "seed": seed,
            "n_trials": len(subset),
            "balanced_accuracy": float(
                balanced_accuracy_score(subset["label"], subset["predicted_label"])
            ),
            "true_left_pred_left": int(matrix[0, 0]),
            "true_left_pred_right": int(matrix[0, 1]),
            "true_right_pred_left": int(matrix[1, 0]),
            "true_right_pred_right": int(matrix[1, 1]),
            "predicted_left_share": float((subset["predicted_label"] == 1).mean()),
        }
    )


if __name__ == "__main__":
    main()
