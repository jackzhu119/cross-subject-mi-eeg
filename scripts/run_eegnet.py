"""Run the fixed source-only, four-class EEGNet LOSO experiment Q5-E001."""

from __future__ import annotations

import argparse
import hashlib
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
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from threadpoolctl import threadpool_limits

from mi_eeg.data.bnci_epochs import load_configured_epochs
from mi_eeg.evaluation.splits import iter_loso
from mi_eeg.models.eegnet_training import (
    build_eegnet,
    evaluate_cross_entropy,
    predict_probabilities,
    seed_everything,
    train_one_epoch,
)
from mi_eeg.provenance import capture_startup_provenance

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = [
    "sample_id", "subject", "session", "run", "trial", "label", "event_sample",
    "artifact_flagged",
]
METRIC_COLUMNS = [
    "balanced_accuracy", "accuracy", "macro_f1", "macro_precision", "macro_recall",
    "cohen_kappa",
]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_files(data_dir: Path, subjects: list[int]) -> list[dict]:
    expected = {
        f"A{subject:02d}{session}" for subject in subjects for session in ("T", "E")
    }
    records = [
        {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(data_dir.rglob("*.mat"))
        if path.stem in expected
    ]
    if len(records) != len(expected):
        raise FileNotFoundError(f"Expected {len(expected)} local BNCI MAT files; found {len(records)}")
    return records


def verify_q4_identity(meta: pd.DataFrame, q4_meta: pd.DataFrame) -> None:
    if not set(IDENTITY).issubset(meta.columns) or not set(IDENTITY).issubset(q4_meta.columns):
        raise AssertionError("Q4/Q5 metadata is missing fields needed for exact trial identity")
    pd.testing.assert_frame_equal(
        meta[IDENTITY].reset_index(drop=True),
        q4_meta[IDENTITY].reset_index(drop=True),
        check_dtype=False,
        check_exact=True,
    )


def metrics(y_true: np.ndarray, y_pred: np.ndarray, labels: list[int]) -> dict[str, float]:
    return {
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "macro_precision": float(
            precision_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
        ),
        "macro_recall": float(
            recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
        ),
        "cohen_kappa": float(cohen_kappa_score(y_true, y_pred, labels=labels)),
    }


def seed_manifest(
    fold: str,
    stage: str,
    inner_fold: int | None,
    seed: int,
    train_subjects: list[int],
    target_subject: int,
    validation_subjects: list[int] | None,
    epochs: int,
) -> list[dict]:
    rows = []
    for subject in range(1, 10):
        if subject == target_subject:
            role = "outer_test_excluded" if stage == "inner" else "test"
        elif validation_subjects and subject in validation_subjects:
            role = "validation"
        else:
            role = "train"
        rows.append(
            {
                "fold": fold,
                "stage": stage,
                "inner_fold": inner_fold,
                "seed": seed,
                "subject": subject,
                "role": role,
                "n_trials": 576,
                "epochs_trained": epochs,
            }
        )
    if sorted(s for s in range(1, 10) if s != target_subject and s not in (validation_subjects or [])) != sorted(train_subjects):
        raise AssertionError("Manifest train subjects disagree with the requested fit")
    return rows


def fit_for_epochs(
    x: torch.Tensor,
    y: torch.Tensor,
    train_idx: np.ndarray,
    validation_idx: np.ndarray | None,
    seed: int,
    epochs: int,
    config: dict,
    device: torch.device,
) -> tuple[torch.nn.Module, list[dict]]:
    training = config["training"]
    architecture = config["architecture"]
    seed_everything(seed, training["deterministic_algorithms"])
    model = build_eegnet(architecture, device)
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=training["learning_rate"],
        weight_decay=training["weight_decay"],
    )
    train_tensor = torch.as_tensor(train_idx, dtype=torch.long, device=device)
    validation_tensor = (
        None if validation_idx is None else torch.as_tensor(validation_idx, dtype=torch.long, device=device)
    )
    curves: list[dict] = []
    for epoch in range(1, epochs + 1):
        train_ce = train_one_epoch(
            model, optimizer, x, y, train_tensor, training["batch_size"]
        )
        val_ce = (
            math.nan
            if validation_tensor is None
            else evaluate_cross_entropy(
                model, x, y, validation_tensor, training["batch_size"]
            )
        )
        curves.append({"epoch": epoch, "train_ce": train_ce, "val_ce": val_ce})
    return model, curves


def cpu_state(model: torch.nn.Module) -> dict[str, torch.Tensor]:
    return {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}


def score_predictions(
    part: pd.DataFrame, labels: list[int], fold: str, seed: int, n_train: int
) -> tuple[list[dict], list[dict]]:
    metric_rows, confusion_rows = [], []
    for stratum in ("all", "unflagged", "flagged"):
        subset = part if stratum == "all" else part[part.artifact_flagged == (stratum == "flagged")]
        if subset.empty:
            continue
        truth, pred = subset.y_true.to_numpy(), subset.y_pred.to_numpy()
        metric_rows.append(
            {
                "fold": fold,
                "subject": int(subset.subject.iloc[0]),
                "seed": seed,
                "model": "EEGNet",
                "stratum": stratum,
                "n_train": n_train,
                "n_test": len(subset),
                "n_classes_present": int(subset.y_true.nunique()),
                **metrics(truth, pred, labels),
            }
        )
        matrix = confusion_matrix(truth, pred, labels=labels)
        for i, true_label in enumerate(labels):
            for j, predicted_label in enumerate(labels):
                confusion_rows.append(
                    {
                        "fold": fold,
                        "subject": int(subset.subject.iloc[0]),
                        "seed": seed,
                        "stratum": stratum,
                        "true_label": true_label,
                        "predicted_label": predicted_label,
                        "count": int(matrix[i, j]),
                    }
                )
    return metric_rows, confusion_rows


def aggregate_complete_folds(output: Path, config: dict) -> None:
    completed_dirs = []
    for fold in (f"loso_s{s}" for s in config["subjects"]):
        candidates = sorted((output / "folds").glob(f"{fold}*"))
        complete = [
            path for path in candidates
            if (path / "status.json").is_file()
            and json.loads((path / "status.json").read_text(encoding="utf-8")).get("status") == "complete"
        ]
        if len(complete) > 1:
            raise AssertionError(f"More than one completed checkpoint exists for {fold}")
        completed_dirs.extend(complete)
    if not completed_dirs:
        return
    collections = {name: [] for name in ("fit_manifest", "learning_curves", "selection", "predictions", "per_subject_metrics", "confusion_matrices")}
    for directory in completed_dirs:
        for name, frames in collections.items():
            path = directory / f"{name}.csv"
            if path.is_file():
                frames.append(pd.read_csv(path))
    for name, frames in collections.items():
        if frames:
            pd.concat(frames, ignore_index=True).to_csv(output / f"{name}.csv", index=False)
    if collections["per_subject_metrics"]:
        frame = pd.concat(collections["per_subject_metrics"], ignore_index=True)
        summary = frame[frame.stratum == "all"].groupby("seed")[METRIC_COLUMNS].agg(["mean", "std"])
        summary.columns = [f"{metric}_{stat}" for metric, stat in summary.columns]
        summary.reset_index().to_csv(output / "summary_by_seed.csv", index=False)
        subject_seed = frame[frame.stratum == "all"].pivot(
            index=["subject", "seed"], columns="model", values="balanced_accuracy"
        ).reset_index()
        subject_seed.to_csv(output / "subject_seed_metrics.csv", index=False)
    status = json.loads((output / "status.json").read_text(encoding="utf-8"))
    status["completed_folds"] = len(completed_dirs)
    status["completed_final_fits"] = len(completed_dirs) * len(config["training"]["final_seeds"])
    status["q5_complete"] = len(completed_dirs) == len(config["subjects"])
    write_json(output / "status.json", status)


def run_fold(
    output: Path,
    fold: str,
    train: np.ndarray,
    test: np.ndarray,
    x: torch.Tensor,
    y: torch.Tensor,
    meta: pd.DataFrame,
    config: dict,
    device: torch.device,
) -> Path:
    target = int(meta.iloc[test].subject.unique().item())
    source_subjects = sorted(meta.iloc[train].subject.unique().tolist())
    batch_size = config["training"]["batch_size"]
    maximum = config["training"]["max_epochs"]
    selection_seed = config["training"]["selection_seed"]
    inner_folds = config["training"]["inner_folds"]
    fold_root = output / "folds"
    base = fold_root / fold
    attempt = base
    retry = 0
    while attempt.exists():
        status_path = attempt / "status.json"
        if status_path.is_file() and json.loads(status_path.read_text(encoding="utf-8")).get("status") == "complete":
            return attempt
        retry += 1
        attempt = fold_root / f"{fold}_retry{retry}"
    attempt.mkdir(parents=True)
    fold_started = time.perf_counter()
    write_json(attempt / "status.json", {"status": "running", "fold": fold, "target_subject": target})
    curves_rows: list[dict] = []
    manifest_rows: list[dict] = []
    validation_losses: list[np.ndarray] = []
    try:
        pair_size = len(source_subjects) // inner_folds
        if len(source_subjects) % inner_folds:
            raise AssertionError("Eight source subjects must split into four equal pairs")
        for inner_fold in range(1, inner_folds + 1):
            validation_subjects = source_subjects[(inner_fold - 1) * pair_size : inner_fold * pair_size]
            inner_train_subjects = [s for s in source_subjects if s not in validation_subjects]
            inner_train = np.flatnonzero(meta.subject.isin(inner_train_subjects).to_numpy())
            inner_validation = np.flatnonzero(meta.subject.isin(validation_subjects).to_numpy())
            model, curve = fit_for_epochs(
                x, y, inner_train, inner_validation, selection_seed, maximum, config, device
            )
            validation_losses.append(np.array([row["val_ce"] for row in curve]))
            for row in curve:
                curves_rows.append(
                    {"fold": fold, "stage": "inner", "inner_fold": inner_fold,
                     "seed": selection_seed, **row}
                )
            manifest_rows.extend(
                seed_manifest(fold, "inner", inner_fold, selection_seed,
                              inner_train_subjects, target, validation_subjects, maximum)
            )
            torch.save(
                {"fold": fold, "stage": "inner", "inner_fold": inner_fold,
                 "seed": selection_seed, "model_state": cpu_state(model)},
                attempt / f"inner_{inner_fold}.pt",
            )
            print(f"{fold} inner {inner_fold}/{inner_folds}: completed {maximum} epochs", flush=True)
            del model
        mean_validation_loss = np.mean(np.stack(validation_losses, axis=0), axis=0)
        selected_epoch = int(np.argmin(mean_validation_loss) + 1)
        selection_ce = float(mean_validation_loss[selected_epoch - 1])
        selection_row = {
            "fold": fold,
            "selected_epochs": selected_epoch,
            "validation_ce": selection_ce,
        }
        for seed in config["training"]["final_seeds"]:
            model, curve = fit_for_epochs(x, y, train, None, seed, selected_epoch, config, device)
            for row in curve:
                curves_rows.append(
                    {"fold": fold, "stage": "full", "inner_fold": math.nan,
                     "seed": seed, **row}
                )
            manifest_rows.extend(
                seed_manifest(fold, "full", None, seed, source_subjects, target,
                              None, selected_epoch)
            )
            torch.save(
                {"fold": fold, "stage": "full", "seed": seed,
                 "selected_epochs": selected_epoch, "model_state": cpu_state(model)},
                attempt / f"seed_{seed}.pt",
            )
            probabilities = predict_probabilities(model, x, test, batch_size)
            part = meta.iloc[test].copy().reset_index(drop=True)
            part["fold"] = fold
            part["seed"] = seed
            part["y_true"] = part.label.astype(int)
            part["y_pred"] = probabilities.argmax(axis=1).astype(int) + 1
            for index, label in enumerate(sorted(config["class_ids"].values())):
                part[f"p_class_{label}"] = probabilities[:, index]
            prediction_file = attempt / f"predictions_seed_{seed}.csv"
            part.to_csv(prediction_file, index=False)
            metric_rows, confusion_rows = score_predictions(part, [1, 2, 3, 4], fold, seed, len(train))
            pd.DataFrame(metric_rows).to_csv(attempt / f"metrics_seed_{seed}.csv", index=False)
            pd.DataFrame(confusion_rows).to_csv(attempt / f"confusion_seed_{seed}.csv", index=False)
            print(
                f"{fold} seed {seed}: target BA="
                f"{metric_rows[0]['balanced_accuracy']:.4f} (selection={selected_epoch} epochs)",
                flush=True,
            )
            del model
        pd.DataFrame(curves_rows).to_csv(attempt / "learning_curves.csv", index=False)
        pd.DataFrame(manifest_rows).to_csv(attempt / "fit_manifest.csv", index=False)
        pd.DataFrame([selection_row]).to_csv(attempt / "selection.csv", index=False)
        pd.concat(
            [pd.read_csv(attempt / f"predictions_seed_{seed}.csv") for seed in config["training"]["final_seeds"]],
            ignore_index=True,
        ).to_csv(attempt / "predictions.csv", index=False)
        pd.concat(
            [pd.read_csv(attempt / f"metrics_seed_{seed}.csv") for seed in config["training"]["final_seeds"]],
            ignore_index=True,
        ).to_csv(attempt / "per_subject_metrics.csv", index=False)
        pd.concat(
            [pd.read_csv(attempt / f"confusion_seed_{seed}.csv") for seed in config["training"]["final_seeds"]],
            ignore_index=True,
        ).to_csv(attempt / "confusion_matrices.csv", index=False)
        write_json(
            attempt / "status.json",
            {"status": "complete", "fold": fold, "target_subject": target,
             "selected_epochs": selected_epoch,
             "elapsed_seconds": time.perf_counter() - fold_started},
        )
        return attempt
    except Exception:
        write_json(
            attempt / "failure.json",
            {"traceback": traceback.format_exc(), "elapsed_seconds": time.perf_counter() - fold_started},
        )
        write_json(attempt / "status.json", {"status": "failed", "fold": fold})
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/q5_e001_eegnet.json")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--device", choices=("cpu", "cuda"))
    parser.add_argument("--resume", action="store_true", help="Continue from complete fold checkpoints")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    output = args.output_dir or ROOT / "results" / config["experiment_id"]
    device_name = args.device or config["training"]["device"]
    if device_name == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable in this environment")
    device = torch.device(device_name)
    output = output.resolve()
    if args.resume:
        if not output.is_dir():
            raise FileNotFoundError(f"Cannot resume: run directory does not exist: {output}")
        existing_config = json.loads((output / "config.json").read_text(encoding="utf-8"))
        if existing_config != config:
            raise ValueError("Resume config differs from the saved experiment config")
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        history = output / "attempt_history" / f"resume_{stamp}"
        for old_item in (output / "provenance", output / "failure.json", output / "runtime.json", output / "status.json"):
            if old_item.exists():
                history.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old_item), str(history / old_item.name))
        capture_startup_provenance(ROOT, output)
    else:
        if output.exists() and any(output.iterdir()):
            raise FileExistsError(f"Refusing to overwrite existing run directory: {output}")
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
            {"status": "loading", "completed_folds": 0, "completed_final_fits": 0,
             "q5_complete": False},
        )
        with threadpool_limits(limits=2):
            bands, meta, audit = load_configured_epochs(
                config["subjects"], args.data_dir.resolve(), config["preprocessing"],
                config["class_ids"],
            )
        records = source_files(args.data_dir.resolve(), config["subjects"])
        if args.resume and (output / "source_files.json").is_file():
            old_records = json.loads((output / "source_files.json").read_text(encoding="utf-8"))
            if [(r["bytes"], r["sha256"]) for r in old_records] != [(r["bytes"], r["sha256"]) for r in records]:
                raise ValueError("Resume source MAT hashes differ from the saved run")
        write_json(output / "source_files.json", records)
        q4_meta = pd.read_csv(ROOT / "outputs/Q4-E001/trial_metadata.csv")
        verify_q4_identity(meta, q4_meta)
        if len(meta) != 5184 or int(meta.artifact_flagged.sum()) != 488:
            raise AssertionError("Unexpected Q5 population size or artifact-flag count")
        if args.resume and (output / "trial_metadata.csv").is_file():
            old_meta = pd.read_csv(output / "trial_metadata.csv")
            verify_q4_identity(meta, old_meta)
        meta.to_csv(output / "trial_metadata.csv", index=False)
        audit.to_csv(output / "data_audit.csv", index=False)
        signal = bands["broad"]
        if signal.shape != (len(meta), 22, 750):
            raise AssertionError(f"Unexpected EEG array shape: {signal.shape}")
        signal *= np.float32(config["input"]["volts_to_microvolts"])
        if not np.isfinite(signal).all():
            raise AssertionError("Non-finite input after fixed volts-to-microvolts scaling")
        x = torch.from_numpy(signal).to(device)
        # PyTorch class indices are zero-based; scientific metadata remain labels 1..4.
        y = torch.as_tensor(meta.label.to_numpy(dtype=np.int64) - 1, dtype=torch.long, device=device)
        write_json(
            output / "data_contract.json",
            {"shape": list(signal.shape), "labels": {"source": [1, 2, 3, 4], "torch": [0, 1, 2, 3]},
             "fixed_scale": config["input"]["volts_to_microvolts"],
             "q4_trial_identity": "exact row-wise match passed",
             "target_fitted_transform": False,
             "signal_min_microvolts": float(signal.min()),
             "signal_max_microvolts": float(signal.max())},
        )
        status = {"status": "running", "completed_folds": 0, "completed_final_fits": 0,
                  "q5_complete": False, "started_at_utc": datetime.now(UTC).isoformat()}
        write_json(output / "status.json", status)
        for fold, train, test in iter_loso(meta):
            fold_dirs = sorted((output / "folds").glob(f"{fold}*")) if (output / "folds").exists() else []
            complete = [
                path for path in fold_dirs
                if (path / "status.json").is_file()
                and json.loads((path / "status.json").read_text(encoding="utf-8")).get("status") == "complete"
            ]
            if len(complete) > 1:
                raise AssertionError(f"Duplicate completed folds detected for {fold}")
            if not complete:
                run_fold(output, fold, train, test, x, y, meta, config, device)
            aggregate_complete_folds(output, config)
        aggregate_complete_folds(output, config)
        final_status = json.loads((output / "status.json").read_text(encoding="utf-8"))
        final_status.update(
            {"status": "complete", "q5_complete": True,
             "elapsed_seconds_this_invocation": time.perf_counter() - started,
             "finished_at_utc": datetime.now(UTC).isoformat()}
        )
        write_json(output / "status.json", final_status)
    except Exception:
        write_json(
            output / "failure.json",
            {"traceback": traceback.format_exc(), "elapsed_seconds_this_invocation": time.perf_counter() - started},
        )
        write_json(output / "status.json", {"status": "failed", "q5_complete": False})
        raise


if __name__ == "__main__":
    main()
