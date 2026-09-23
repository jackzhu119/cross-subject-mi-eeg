"""Run Q6-E001: Q5 EEGNet plus source-train-only channel standardization.

The only experimental change from Q5 is the input transform.  Each of four
inner fits learns its own scaler from six source subjects; the three final
fits share one scaler learned from all eight source subjects.  The held-out
target never contributes fitted statistics.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import shutil
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

import mne
import numpy as np
import pandas as pd
import torch
from threadpoolctl import threadpool_limits

from mi_eeg.data.bnci_epochs import load_configured_epochs
from mi_eeg.evaluation.splits import iter_loso
from mi_eeg.preprocessing.source_normalization import (
    ChannelStandardizer,
    apply_channel_standardizer,
    fit_source_channel_standardizer,
)
from mi_eeg.provenance import capture_startup_provenance
from scripts.run_eegnet import (
    METRIC_COLUMNS,
    cpu_state,
    fit_for_epochs,
    score_predictions,
    seed_manifest,
    sha256_file,
    source_files,
    verify_q4_identity,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/q6_e001_source_channel_zscore.json"
Q5_CONFIG = ROOT / "configs/q5_e001_eegnet.json"
RESULTS_DIR = ROOT / "results/Q6-E001"
EXPECTED_RECEIPTS_PER_FOLD = 5


def assert_single_factor_protocol(config: dict, parent: dict) -> None:
    """Reject experimental drift disguised as the normalization ablation."""
    if config.get("experiment_id") != "Q6-E001" or parent.get("experiment_id") != "Q5-E001":
        raise ValueError("Q6-E001 and Q5-E001 experiment IDs are mandatory")
    for key in ("dataset", "subjects", "class_ids", "preprocessing", "architecture", "training"):
        if config.get(key) != parent.get(key):
            raise ValueError(f"Q6 {key} differs from frozen Q5 protocol")
    q6_input = copy.deepcopy(config.get("input", {}))
    normalization = q6_input.pop("normalization", None)
    if q6_input != parent.get("input"):
        raise ValueError("Q6 input changed beyond declared channel standardization")
    expected_normalization = {
        "kind": "per_channel_source_train_zscore",
        "fit_axes": ["trials", "time"],
        "variance_ddof": 0,
        "statistics_dtype": "float64",
        "application_dtype": "float32",
        "min_std_microvolts": 1e-6,
        "zero_variance_policy": "raise",
    }
    if normalization != expected_normalization:
        raise ValueError("Q6 normalization declaration differs from implemented transform")
    for key in ("split", "primary_population", "secondary_strata", "primary_metric"):
        if config.get("evaluation", {}).get(key) != parent.get("evaluation", {}).get(key):
            raise ValueError(f"Q6 evaluation.{key} differs from Q5")
    if config["evaluation"].get("parent_comparator") != "Q5-E001 EEGNet frozen microvolt-only baseline":
        raise ValueError("Q6 parent comparator is not the frozen Q5 baseline")


def _expected_fold_files(config: dict) -> list[str]:
    files = [
        "status.json", "learning_curves.csv", "fit_manifest.csv", "selection.csv",
        "predictions.csv", "per_subject_metrics.csv", "confusion_matrices.csv",
        "normalization/inner_1.json", "normalization/inner_2.json",
        "normalization/inner_3.json", "normalization/inner_4.json",
        "normalization/full.json",
    ]
    files.extend(f"inner_{i}.pt" for i in range(1, 5))
    files.extend(f"seed_{seed}.pt" for seed in config["training"]["final_seeds"])
    return files


def _complete_fold_dir(output: Path, fold: str, config: dict) -> Path | None:
    candidates = sorted((output / "folds").glob(f"{fold}*"))
    completed = []
    for path in candidates:
        status_path = path / "status.json"
        if not status_path.is_file():
            continue
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if status.get("status") == "complete":
            missing = [name for name in _expected_fold_files(config) if not (path / name).is_file()]
            if missing:
                raise AssertionError(f"Completed fold {path} is missing artifacts: {missing}")
            completed.append(path)
    if len(completed) > 1:
        raise AssertionError(f"More than one completed checkpoint exists for {fold}")
    return completed[0] if completed else None


def _save_normalizer(
    attempt: Path, fitted: ChannelStandardizer, *, fold: str, stage: str, inner_fold: int | None
) -> str:
    name = f"inner_{inner_fold}.json" if stage == "inner" else "full.json"
    path = attempt / "normalization" / name
    write_json(path, fitted.receipt(fold=fold, stage=stage, inner_fold=inner_fold))
    return sha256_file(path)


def aggregate_complete_folds(output: Path, config: dict) -> None:
    completed = [
        path for s in config["subjects"]
        if (path := _complete_fold_dir(output, f"loso_s{s}", config)) is not None
    ]
    if not completed:
        return
    names = (
        "fit_manifest", "learning_curves", "selection", "predictions",
        "per_subject_metrics", "confusion_matrices",
    )
    collections = {name: [] for name in names}
    receipts = []
    for directory in completed:
        for name, frames in collections.items():
            frames.append(pd.read_csv(directory / f"{name}.csv"))
        for name in ("inner_1", "inner_2", "inner_3", "inner_4", "full"):
            receipts.append(json.loads((directory / "normalization" / f"{name}.json").read_text(encoding="utf-8")))
    for name, frames in collections.items():
        pd.concat(frames, ignore_index=True).to_csv(output / f"{name}.csv", index=False)
    write_json(output / "normalization_receipts.json", receipts)
    frame = pd.concat(collections["per_subject_metrics"], ignore_index=True)
    summary = frame[frame.stratum == "all"].groupby("seed")[METRIC_COLUMNS].agg(["mean", "std"])
    summary.columns = [f"{metric}_{stat}" for metric, stat in summary.columns]
    summary.reset_index().to_csv(output / "summary_by_seed.csv", index=False)
    subject_seed = frame[frame.stratum == "all"].pivot(
        index=["subject", "seed"], columns="model", values="balanced_accuracy"
    ).reset_index()
    subject_seed.to_csv(output / "subject_seed_metrics.csv", index=False)
    status = json.loads((output / "status.json").read_text(encoding="utf-8"))
    status["completed_folds"] = len(completed)
    status["completed_inner_fits"] = len(completed) * config["training"]["inner_folds"]
    status["completed_final_fits"] = len(completed) * len(config["training"]["final_seeds"])
    status["q6_complete"] = len(completed) == len(config["subjects"])
    write_json(output / "status.json", status)


def run_fold(
    output: Path,
    fold: str,
    train: np.ndarray,
    test: np.ndarray,
    signal_microvolts: np.ndarray,
    raw_x: torch.Tensor,
    y: torch.Tensor,
    meta: pd.DataFrame,
    config: dict,
    device: torch.device,
) -> Path:
    target = int(meta.iloc[test].subject.unique().item())
    source_subjects = sorted(int(s) for s in meta.iloc[train].subject.unique())
    if len(source_subjects) != 8 or target in source_subjects:
        raise AssertionError("LOSO must provide eight source subjects and one untouched target")
    complete = _complete_fold_dir(output, fold, config)
    if complete is not None:
        return complete
    training = config["training"]
    fold_root = output / "folds"
    attempt = fold_root / fold
    retry = 0
    while attempt.exists():
        retry += 1
        attempt = fold_root / f"{fold}_retry{retry}"
    attempt.mkdir(parents=True)
    started = time.perf_counter()
    write_json(attempt / "status.json", {"status": "running", "fold": fold, "target_subject": target})
    curve_rows: list[dict] = []
    manifest_rows: list[dict] = []
    validation_losses: list[np.ndarray] = []
    try:
        pair_size = len(source_subjects) // training["inner_folds"]
        if pair_size != 2 or len(source_subjects) % training["inner_folds"]:
            raise AssertionError("Eight source subjects must split into four sorted pairs")
        for inner_fold in range(1, training["inner_folds"] + 1):
            validation_subjects = source_subjects[(inner_fold - 1) * pair_size : inner_fold * pair_size]
            train_subjects = [s for s in source_subjects if s not in validation_subjects]
            inner_train = np.flatnonzero(meta.subject.isin(train_subjects).to_numpy())
            inner_validation = np.flatnonzero(meta.subject.isin(validation_subjects).to_numpy())
            if len(inner_train) != 3456 or len(inner_validation) != 1152:
                raise AssertionError("Unexpected source-train/validation trial counts")
            fitted = fit_source_channel_standardizer(
                signal_microvolts, meta, inner_train, train_subjects,
                min_std_microvolts=config["input"]["normalization"]["min_std_microvolts"],
            )
            receipt_sha = _save_normalizer(
                attempt, fitted, fold=fold, stage="inner", inner_fold=inner_fold
            )
            normalized_x = apply_channel_standardizer(raw_x, fitted)
            model, curve = fit_for_epochs(
                normalized_x, y, inner_train, inner_validation,
                training["selection_seed"], training["max_epochs"], config, device,
            )
            validation_losses.append(np.array([row["val_ce"] for row in curve]))
            curve_rows.extend(
                {"fold": fold, "stage": "inner", "inner_fold": inner_fold,
                 "seed": training["selection_seed"], **row} for row in curve
            )
            manifest_rows.extend(
                seed_manifest(fold, "inner", inner_fold, training["selection_seed"],
                              train_subjects, target, validation_subjects, training["max_epochs"])
            )
            torch.save(
                {"fold": fold, "stage": "inner", "inner_fold": inner_fold,
                 "seed": training["selection_seed"], "model_state": cpu_state(model),
                 "normalization_receipt_sha256": receipt_sha},
                attempt / f"inner_{inner_fold}.pt",
            )
            print(f"{fold} inner {inner_fold}/4: completed {training['max_epochs']} epochs", flush=True)
            del model, normalized_x
        mean_validation_loss = np.mean(np.stack(validation_losses, axis=0), axis=0)
        selected_epochs = int(np.argmin(mean_validation_loss) + 1)
        selection = {
            "fold": fold, "selected_epochs": selected_epochs,
            "validation_ce": float(mean_validation_loss[selected_epochs - 1]),
        }
        fitted_final = fit_source_channel_standardizer(
            signal_microvolts, meta, train, source_subjects,
            min_std_microvolts=config["input"]["normalization"]["min_std_microvolts"],
        )
        if fitted_final.n_trials != 4608:
            raise AssertionError("Final standardizer must fit all eight source subjects")
        receipt_sha = _save_normalizer(
            attempt, fitted_final, fold=fold, stage="full", inner_fold=None
        )
        normalized_x = apply_channel_standardizer(raw_x, fitted_final)
        for seed in training["final_seeds"]:
            model, curve = fit_for_epochs(
                normalized_x, y, train, None, seed, selected_epochs, config, device
            )
            curve_rows.extend(
                {"fold": fold, "stage": "full", "inner_fold": math.nan,
                 "seed": seed, **row} for row in curve
            )
            manifest_rows.extend(
                seed_manifest(fold, "full", None, seed, source_subjects,
                              target, None, selected_epochs)
            )
            torch.save(
                {"fold": fold, "stage": "full", "seed": seed,
                 "selected_epochs": selected_epochs, "model_state": cpu_state(model),
                 "normalization_receipt_sha256": receipt_sha},
                attempt / f"seed_{seed}.pt",
            )
            from mi_eeg.models.eegnet_training import predict_probabilities

            probabilities = predict_probabilities(
                model, normalized_x, test, training["batch_size"]
            )
            part = meta.iloc[test].copy().reset_index(drop=True)
            part["fold"] = fold
            part["seed"] = seed
            part["y_true"] = part.label.astype(int)
            part["y_pred"] = probabilities.argmax(axis=1).astype(int) + 1
            for index, label in enumerate(sorted(config["class_ids"].values())):
                part[f"p_class_{label}"] = probabilities[:, index]
            part.to_csv(attempt / f"predictions_seed_{seed}.csv", index=False)
            metric_rows, confusion_rows = score_predictions(
                part, [1, 2, 3, 4], fold, seed, len(train)
            )
            # Q5's historic writer omitted this required confusion identifier.
            # Q6 emits it both per seed and in its aggregate from the start.
            for row in confusion_rows:
                row["model"] = "EEGNet"
            pd.DataFrame(metric_rows).to_csv(attempt / f"metrics_seed_{seed}.csv", index=False)
            pd.DataFrame(confusion_rows).to_csv(attempt / f"confusion_seed_{seed}.csv", index=False)
            print(
                f"{fold} seed {seed}: target BA={metric_rows[0]['balanced_accuracy']:.4f} "
                f"(source-selected {selected_epochs} epochs)", flush=True,
            )
            del model
        del normalized_x
        pd.DataFrame(curve_rows).to_csv(attempt / "learning_curves.csv", index=False)
        pd.DataFrame(manifest_rows).to_csv(attempt / "fit_manifest.csv", index=False)
        pd.DataFrame([selection]).to_csv(attempt / "selection.csv", index=False)
        for name, pattern in (
            ("predictions", "predictions_seed_{}.csv"),
            ("per_subject_metrics", "metrics_seed_{}.csv"),
            ("confusion_matrices", "confusion_seed_{}.csv"),
        ):
            pd.concat(
                [pd.read_csv(attempt / pattern.format(seed)) for seed in training["final_seeds"]],
                ignore_index=True,
            ).to_csv(attempt / f"{name}.csv", index=False)
        write_json(
            attempt / "status.json",
            {"status": "complete", "fold": fold, "target_subject": target,
             "selected_epochs": selected_epochs,
             "elapsed_seconds": time.perf_counter() - started},
        )
        return attempt
    except Exception:
        write_json(
            attempt / "failure.json",
            {"traceback": traceback.format_exc(), "elapsed_seconds": time.perf_counter() - started},
        )
        write_json(attempt / "status.json", {"status": "failed", "fold": fold})
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--device", choices=("cpu", "cuda"))
    parser.add_argument("--resume", action="store_true", help="Reuse completed Q6 folds; keep failed attempts")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    parent = json.loads(Q5_CONFIG.read_text(encoding="utf-8"))
    assert_single_factor_protocol(config, parent)
    output = args.output_dir.resolve()
    if output == (ROOT / "results/Q5-E001").resolve() or "Q5-E001" in output.parts:
        raise ValueError("Q6 output cannot be placed in the immutable Q5-E001 results directory")
    device_name = args.device or config["training"]["device"]
    if device_name == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    device = torch.device(device_name)
    if args.resume:
        if not output.is_dir() or not (output / "config.json").is_file():
            raise FileNotFoundError(f"Cannot resume without saved Q6 config: {output}")
        previous = json.loads((output / "config.json").read_text(encoding="utf-8"))
        if previous != config:
            raise ValueError("Resume config differs from saved Q6 experiment config")
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        history = output / "attempt_history" / f"resume_{stamp}"
        for old in (output / "provenance", output / "failure.json", output / "runtime.json", output / "status.json"):
            if old.exists():
                history.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old), str(history / old.name))
        capture_startup_provenance(ROOT, output)
    else:
        if output.exists() and any(output.iterdir()):
            raise FileExistsError(f"Refusing to overwrite existing Q6 run: {output}")
        output.mkdir(parents=True, exist_ok=True)
        write_json(output / "config.json", config)
        capture_startup_provenance(ROOT, output)
    started = time.perf_counter()
    try:
        torch.set_num_threads(config["training"]["torch_threads"])
        torch.set_num_interop_threads(1)
        mne.set_log_level("ERROR")
        write_json(
            output / "runtime.json",
            {"started_at_utc": datetime.now(UTC).isoformat(), "device": str(device),
             "torch_version": torch.__version__, "cuda_available": torch.cuda.is_available()},
        )
        write_json(
            output / "status.json",
            {"status": "loading", "completed_folds": 0, "completed_inner_fits": 0,
             "completed_final_fits": 0, "q6_complete": False},
        )
        with threadpool_limits(limits=2):
            bands, meta, audit = load_configured_epochs(
                config["subjects"], args.data_dir.resolve(),
                config["preprocessing"], config["class_ids"],
            )
        records = source_files(args.data_dir.resolve(), config["subjects"])
        if args.resume and (output / "source_files.json").is_file():
            previous = json.loads((output / "source_files.json").read_text(encoding="utf-8"))
            if [(r["bytes"], r["sha256"]) for r in previous] != [
                (r["bytes"], r["sha256"]) for r in records
            ]:
                raise ValueError("Resume source MAT hashes differ from saved Q6 run")
        write_json(output / "source_files.json", records)
        q4_meta = pd.read_csv(ROOT / "outputs/Q4-E001/trial_metadata.csv")
        verify_q4_identity(meta, q4_meta)
        if len(meta) != 5184 or int(meta.artifact_flagged.sum()) != 488:
            raise AssertionError("Q6 trial population differs from Q4/Q5")
        if args.resume and (output / "trial_metadata.csv").is_file():
            verify_q4_identity(meta, pd.read_csv(output / "trial_metadata.csv"))
        meta.to_csv(output / "trial_metadata.csv", index=False)
        audit.to_csv(output / "data_audit.csv", index=False)
        signal = bands["broad"]
        if signal.shape != (5184, 22, 750):
            raise AssertionError(f"Unexpected EEG array shape: {signal.shape}")
        signal *= np.float32(config["input"]["volts_to_microvolts"])
        if not np.isfinite(signal).all():
            raise AssertionError("Non-finite microvolt EEG before source-only scaling")
        raw_x = torch.from_numpy(signal).to(device)
        y = torch.as_tensor(meta.label.to_numpy(dtype=np.int64) - 1, dtype=torch.long, device=device)
        write_json(
            output / "data_contract.json",
            {"shape": list(signal.shape), "labels": {"source": [1, 2, 3, 4], "torch": [0, 1, 2, 3]},
             "fixed_scale": config["input"]["volts_to_microvolts"],
             "normalization": config["input"]["normalization"],
             "q4_trial_identity": "exact row-wise match passed",
             "target_fitted_transform": False,
             "signal_min_microvolts": float(signal.min()),
             "signal_max_microvolts": float(signal.max())},
        )
        write_json(
            output / "status.json",
            {"status": "running", "completed_folds": 0, "completed_inner_fits": 0,
             "completed_final_fits": 0, "q6_complete": False,
             "started_at_utc": datetime.now(UTC).isoformat()},
        )
        for fold, train, test in iter_loso(meta):
            if _complete_fold_dir(output, fold, config) is None:
                run_fold(output, fold, train, test, signal, raw_x, y, meta, config, device)
            aggregate_complete_folds(output, config)
        aggregate_complete_folds(output, config)
        final_status = json.loads((output / "status.json").read_text(encoding="utf-8"))
        final_status.update(
            {"status": "complete", "q6_complete": True,
             "elapsed_seconds_this_invocation": time.perf_counter() - started,
             "finished_at_utc": datetime.now(UTC).isoformat()},
        )
        write_json(output / "status.json", final_status)
    except Exception:
        write_json(
            output / "failure.json",
            {"traceback": traceback.format_exc(),
             "elapsed_seconds_this_invocation": time.perf_counter() - started},
        )
        write_json(output / "status.json", {"status": "failed", "q6_complete": False})
        raise


if __name__ == "__main__":
    main()
