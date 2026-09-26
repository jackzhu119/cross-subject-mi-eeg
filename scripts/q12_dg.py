"""Source-only Q12 domain-generalization runner (no target adaptation).

Selection must finish in all 36 source-only inner folds before final target
inference. The runner is resumable per fit and never changes Q8/Q9 results.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mne
import numpy as np
import pandas as pd
import torch

from mi_eeg.models.eegnet_training import (
    build_eegnet,
    evaluate_cross_entropy,
    predict_probabilities,
    seed_everything,
    train_one_epoch,
)
from scripts import q9_neural as q9
from scripts import q11_neural as q11
from scripts.run_eegnet import cpu_state, score_predictions, sha256_file, write_json

MATRIX = ROOT / "research_runs/Q12-PREP-20260926/MATRIX.json"
PROTOCOL = ROOT / "research_runs/Q12-PREP-20260926/PROTOCOL.md"
Q8_CONFIG = ROOT / "research_runs/Q8-E001/results/config.json"
SELECTION_SEED = 20260923
FINAL_SEEDS = (20260924, 20260925, 20260926)
MAX_EPOCHS = 40
INNER_FILES = ("checkpoint.pt", "learning_curve.csv", "fit_manifest.csv", "model_receipt.json")
FINAL_FILES = INNER_FILES + ("predictions.csv", "metrics.csv", "confusion.csv")


def matrix_conditions() -> dict[str, dict]:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    rows = matrix["conditions"]
    if (len(rows) != 6 or len({r["id"] for r in rows}) != 6
            or matrix["totals"] != {"inner_fits": 216, "final_fits": 162, "new_deep_fits": 378}
            or any(r["inner_fits"] != 36 or r["final_fits"] != 27 for r in rows)):
        raise AssertionError("Q12 condition/fit matrix differs from frozen proposal")
    return {row["id"]: row for row in rows}


def settings(condition: str, data_dir: Path, output: Path) -> dict:
    row = matrix_conditions()[condition]
    q8 = json.loads(Q8_CONFIG.read_text(encoding="utf-8"))
    if (q8["subjects"] != list(range(1, 10))
            or q8["training"]["max_epochs"] != MAX_EPOCHS
            or q8["training"]["selection_seed"] != SELECTION_SEED
            or q8["training"]["final_seeds"] != list(FINAL_SEEDS)):
        raise AssertionError("Q8 source subject/seed/epoch contract changed")
    training = {key: value for key, value in q8["training"].items()
                if key not in {"device", "inner_curve_source", "inner_fits_retrained",
                               "epoch_selection", "augmentation"}}
    config = {
        "experiment_id": row["experiment_id"], "condition": condition,
        "method": row["method"], "method_parameters": {
            key: value for key, value in row.items()
            if key not in {"id", "experiment_id", "method", "inner_fits", "final_fits"}},
        "preprocessing": q8["preprocessing"], "architecture": q8["architecture"],
        "training": training, "input": q8["input"], "subjects": q8["subjects"],
        "class_ids": q8["class_ids"], "source_only_selection": True,
        "target_fitted_transform": False, "data_dir": str(data_dir.resolve()),
        "q8_config_sha256": sha256_file(Q8_CONFIG),
        "matrix_sha256": sha256_file(MATRIX), "protocol_sha256": sha256_file(PROTOCOL),
        "runner_sha256": sha256_file(Path(__file__)),
    }
    path = output / "run_config.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != config:
            raise AssertionError("Q12 run_config differs; refuse mixed-protocol resume")
    else:
        write_json(path, config)
    return config


def _check_exact_source_partition(meta: pd.DataFrame, train: np.ndarray,
                                  train_subjects: list[int]) -> None:
    train = np.asarray(train, dtype=np.int64)
    if (not len(train) or len(np.unique(train)) != len(train) or train.min() < 0
            or train.max() >= len(meta) or len(train_subjects) != len(set(train_subjects))):
        raise ValueError("Invalid source-training index/subject inventory")
    expected = np.flatnonzero(meta.subject.isin(train_subjects).to_numpy())
    if not np.array_equal(np.sort(train), expected):
        raise ValueError("Source transform must fit all and only declared training subjects")


def fit_source_whitener(x: torch.Tensor, meta: pd.DataFrame, train: np.ndarray,
                        train_subjects: list[int], ridge_fraction: float = 0.05) -> dict:
    """Fit group-equal spatial covariance only on exact source-training trials."""
    if x.ndim != 3 or x.shape[0] != len(meta) or x.shape[2] < 2:
        raise ValueError("Expected aligned trials × channels × time EEG")
    if not (0 < ridge_fraction < 1):
        raise ValueError("Ridge fraction must be predeclared in (0,1)")
    _check_exact_source_partition(meta, train, train_subjects)
    n_channels, n_times = x.shape[1:]
    covariance = torch.zeros((n_channels, n_channels), dtype=torch.float64, device=x.device)
    counts = {}
    for subject in sorted(train_subjects):
        indices = np.asarray(train)[meta.iloc[train].subject.to_numpy() == subject]
        counts[str(subject)] = len(indices)
        group_sum = torch.zeros_like(covariance)
        for chunk in np.array_split(indices, max(1, math.ceil(len(indices) / 64))):
            values = x[torch.as_tensor(chunk.copy(), dtype=torch.long, device=x.device)].to(torch.float64)
            values = values - values.mean(dim=-1, keepdim=True)
            group_sum += torch.bmm(values, values.transpose(1, 2)).sum(dim=0) / (n_times - 1)
        covariance += group_sum / len(indices) / len(train_subjects)
    covariance = (covariance + covariance.T) / 2
    mean_eigenvalue = torch.trace(covariance) / n_channels
    ridge = ridge_fraction * mean_eigenvalue
    eigenvalues, vectors = torch.linalg.eigh(covariance)
    if (not torch.isfinite(eigenvalues).all() or not torch.isfinite(vectors).all()
            or float(mean_eigenvalue) <= 0 or float(eigenvalues[0] + ridge) <= 0):
        raise FloatingPointError("Nonpositive or nonfinite source covariance")
    weight = (vectors * (eigenvalues + ridge).rsqrt()) @ vectors.T * mean_eigenvalue.sqrt()
    if not torch.isfinite(weight).all():
        raise FloatingPointError("Nonfinite source whitener")
    return {
        "method": "source_subject_equal_covariance_whitening",
        "ridge_fraction": ridge_fraction, "center_each_trial_over_time": True,
        "covariance_dtype": "float64", "application_dtype": "float32",
        "train_subjects": sorted(train_subjects), "train_subject_trial_counts": counts,
        "n_train_trials": len(train), "n_time_samples": n_times,
        "ordered_train_sample_ids_sha256": q9._sample_ids_hash(
            meta.iloc[train].sample_id.astype(str).tolist()),
        "mean_eigenvalue": float(mean_eigenvalue), "ridge": float(ridge),
        "source_covariance_eigenvalues": eigenvalues.cpu().tolist(),
        "spatial_weight": weight.cpu().tolist(), "target_fitted_transform": False,
    }


def apply_source_whitener(x: torch.Tensor, receipt: dict) -> torch.Tensor:
    weight = torch.as_tensor(receipt["spatial_weight"], dtype=x.dtype, device=x.device)
    if x.ndim != 3 or weight.shape != (x.shape[1], x.shape[1]):
        raise ValueError("Whitener/channel shapes disagree")
    result = torch.einsum("cd,ndt->nct", weight, x)
    if not torch.isfinite(result).all():
        raise FloatingPointError("Nonfinite whitened EEG")
    return result


def training_augmentation(batch: torch.Tensor, method: str, parameters: dict) -> torch.Tensor:
    """Only call from source-training mini-batches, never validation/inference."""
    if method not in {"channel_dropout", "gain_perturb", "channel_and_gain"}:
        raise ValueError("Not a Q12 training-only augmentation")
    result = batch
    if method in {"gain_perturb", "channel_and_gain"}:
        low, high = float(parameters["gain_low"]), float(parameters["gain_high"])
        if (low, high) != (0.8, 1.2):
            raise AssertionError("Unfrozen gain range")
        gain = torch.empty((*batch.shape[:2], 1), dtype=batch.dtype, device=batch.device)
        result = result * gain.uniform_(low, high)
    if method in {"channel_dropout", "channel_and_gain"}:
        probability = float(parameters["channel_dropout_probability"])
        if probability != 0.10:
            raise AssertionError("Unfrozen channel-dropout probability")
        mask = torch.rand((*batch.shape[:2], 1), device=batch.device) >= probability
        result = result * mask / (1.0 - probability)
    return result


def _train_augmented_epoch(model: torch.nn.Module, optimizer: torch.optim.Optimizer,
                           x: torch.Tensor, y: torch.Tensor, train_indices: torch.Tensor,
                           batch_size: int, method: str, parameters: dict) -> float:
    model.train()
    shuffled = train_indices[torch.randperm(len(train_indices), device=x.device)]
    total = 0.0
    for part in shuffled.split(batch_size):
        optimizer.zero_grad(set_to_none=True)
        logits = model(training_augmentation(x[part], method, parameters))
        loss = torch.nn.functional.cross_entropy(logits, y[part])
        if not torch.isfinite(loss):
            raise FloatingPointError("Nonfinite augmented source training loss")
        loss.backward()
        optimizer.step()
        total += float(loss.detach()) * len(part)
    return total / len(train_indices)


def _balanced_group_epoch(model: torch.nn.Module, optimizer: torch.optim.Optimizer,
                          x: torch.Tensor, y: torch.Tensor, meta: pd.DataFrame,
                          train: np.ndarray, subjects: list[int], batch_size: int,
                          method: str, log_weights: torch.Tensor,
                          group_step_size: float = 0.05) -> tuple[float, torch.Tensor]:
    """One matched batch sampler/step budget for balanced ERM and GroupDRO."""
    if method not in {"balanced_erm", "group_dro"}:
        raise ValueError("Invalid group-risk method")
    if group_step_size != 0.05:
        raise AssertionError("Unfrozen GroupDRO step size")
    _check_exact_source_partition(meta, train, subjects)
    subject_array = meta.iloc[train].subject.to_numpy()
    groups = [torch.as_tensor(np.asarray(train)[subject_array == s].copy(), dtype=torch.long,
                              device=x.device) for s in sorted(subjects)]
    if any(len(group) == 0 for group in groups) or batch_size < len(groups):
        raise AssertionError("Cannot construct source-balanced batch")
    model.train()
    total_unweighted = 0.0
    steps = math.ceil(len(train) / batch_size)
    for step in range(steps):
        base, extras = divmod(batch_size, len(groups))
        sizes = [base + (int((g - step) % len(groups) < extras)) for g in range(len(groups))]
        sampled = [group[torch.randint(len(group), (sizes[g],), device=x.device)]
                   for g, group in enumerate(groups)]
        joined = torch.cat(sampled)
        optimizer.zero_grad(set_to_none=True)
        logits = model(x[joined])
        losses = torch.stack([
            torch.nn.functional.cross_entropy(l, y[idx])
            for l, idx in zip(logits.split(sizes), sampled)
        ])
        if not torch.isfinite(losses).all():
            raise FloatingPointError("Nonfinite source group loss")
        if method == "group_dro":
            log_weights = log_weights + group_step_size * losses.detach()
            log_weights = log_weights - torch.logsumexp(log_weights, dim=0)
            weights = log_weights.exp()
        else:
            weights = torch.full_like(losses, 1.0 / len(groups))
        objective = torch.dot(weights.to(losses.dtype), losses)
        objective.backward()
        optimizer.step()
        total_unweighted += float(losses.detach().mean())
    return total_unweighted / steps, log_weights


def _fit_input(config: dict, x: torch.Tensor, meta: pd.DataFrame, train: np.ndarray,
               train_subjects: list[int], directory: Path) -> torch.Tensor:
    if config["method"] != "whiten":
        return x
    receipt = fit_source_whitener(x, meta, train, train_subjects,
                                  float(config["method_parameters"]["ridge_fraction"]))
    path = directory / "source_whitener.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != receipt:
            raise AssertionError("Whitening receipt changed during resume")
    else:
        write_json(path, receipt)
    return apply_source_whitener(x, receipt)


def _fit(x: torch.Tensor, y: torch.Tensor, meta: pd.DataFrame, train: np.ndarray,
         validation: np.ndarray | None, train_subjects: list[int], seed: int, epochs: int,
         config: dict, device: torch.device) -> tuple[torch.nn.Module, list[dict], dict]:
    settings = config["training"]
    seed_everything(seed, bool(settings["deterministic_algorithms"]))
    model = build_eegnet(config["architecture"], device)
    optimizer = torch.optim.Adam(model.parameters(), lr=float(settings["learning_rate"]),
                                 weight_decay=float(settings["weight_decay"]))
    train_idx = torch.as_tensor(np.asarray(train).copy(), dtype=torch.long, device=device)
    val_idx = None if validation is None else torch.as_tensor(
        np.asarray(validation).copy(), dtype=torch.long, device=device)
    log_weights = torch.full((len(train_subjects),), -math.log(len(train_subjects)),
                             dtype=torch.float64, device=device)
    curves = []
    method = config["method"]
    for epoch in range(1, epochs + 1):
        if method in {"balanced_erm", "group_dro"}:
            group_step_size = float(config["method_parameters"].get("group_step_size", 0.05))
            train_ce, log_weights = _balanced_group_epoch(
                model, optimizer, x, y, meta, train, train_subjects,
                int(settings["batch_size"]), method, log_weights, group_step_size)
        elif method in {"channel_dropout", "gain_perturb", "channel_and_gain"}:
            train_ce = _train_augmented_epoch(model, optimizer, x, y, train_idx,
                                              int(settings["batch_size"]), method,
                                              config["method_parameters"])
        elif method == "whiten":
            train_ce = train_one_epoch(model, optimizer, x, y, train_idx,
                                       int(settings["batch_size"]))
        else:
            raise AssertionError("Unknown Q12 method")
        val_ce = math.nan if val_idx is None else evaluate_cross_entropy(
            model, x, y, val_idx, int(settings["batch_size"]))
        curves.append({"epoch": epoch, "train_ce": train_ce, "val_ce": val_ce})
    group_receipt = {"train_subjects": sorted(train_subjects),
                     "final_group_weights": log_weights.exp().cpu().tolist()
                     if method == "group_dro" else None,
                     "balanced_batches": method in {"balanced_erm", "group_dro"},
                     "nominal_batch_size": int(settings["batch_size"])}
    return model, curves, group_receipt


def _model_receipt(model: torch.nn.Module, config: dict, group: dict) -> dict:
    return {"experiment_id": config["experiment_id"], "condition": config["condition"],
            "architecture": config["architecture"], "method": config["method"],
            "method_parameters": config["method_parameters"], "group_training": group,
            "parameter_shapes": {name: list(value.shape) for name, value in model.named_parameters()
                                 if value.requires_grad},
            "trainable_parameter_count": sum(p.numel() for p in model.parameters()
                                             if p.requires_grad)}


def _inner_path(output: Path, subject: int, inner: int) -> Path:
    return output / "inner" / f"loso_s{subject}" / f"inner_{inner}"


def _final_path(output: Path, subject: int, seed: int) -> Path:
    return output / "final" / f"loso_s{subject}" / f"seed_{seed}"


def _required(config: dict, final: bool) -> tuple[str, ...]:
    files = FINAL_FILES if final else INNER_FILES
    if config["method"] == "whiten":
        files += ("source_whitener.json",)
    return files


def assert_pretarget_git_freeze() -> str:
    files = (
        "research_runs/Q12-PREP-20260926/PROTOCOL.md",
        "research_runs/Q12-PREP-20260926/MATRIX.json",
        "scripts/q12_dg.py", "scripts/q12_batch.py", "scripts/validate_q12.py",
        "scripts/q9_neural.py", "scripts/q9_batch.py", "scripts/q9_validate_batch.py",
        "scripts/q11_neural.py", "scripts/validate_q11_e001.py",
        "scripts/publish_research_run.py",
        "src/mi_eeg/data/bnci_epochs.py", "src/mi_eeg/models/eegnet_training.py",
    )
    for command in (("ls-files", "--error-unmatch", "--", *files),
                    ("diff", "--quiet", "--", *files),
                    ("diff", "--cached", "--quiet", "--", *files)):
        result = subprocess.run(["git", *command], cwd=ROOT, capture_output=True,
                                text=True, check=False)
        if result.returncode:
            raise RuntimeError("Q12 protocol/runner is not committed unchanged; target inference blocked")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()
    if len(head) != 40:
        raise RuntimeError("Cannot identify Q12 pretarget freeze commit")
    return head


def _run_inner(output: Path, subject: int, inner: int, x: torch.Tensor, y: torch.Tensor,
               meta: pd.DataFrame, config: dict, device: torch.device) -> None:
    directory = _inner_path(output, subject, inner)
    required = _required(config, False)
    if q9._fit_complete(directory, required):
        print(f"{config['condition']} S{subject} inner {inner}: verified resume", flush=True)
        return
    directory.mkdir(parents=True, exist_ok=True)
    train_subjects, validation_subjects, train, validation = q9._source_partition(meta, subject, inner)
    info = {"experiment_id": config["experiment_id"], "condition": config["condition"],
            "fold": f"loso_s{subject}", "target_subject": subject, "stage": "inner",
            "inner_fold": inner, "seed": SELECTION_SEED,
            "train_subjects": train_subjects, "validation_subjects": validation_subjects,
            "n_train": len(train), "n_validation": len(validation), "epochs_trained": MAX_EPOCHS}
    write_json(directory / "status.json", {"status": "running", **info,
                                           "started_at_utc": q9.now_utc()})
    started = time.perf_counter()
    try:
        fit_x = _fit_input(config, x, meta, train, train_subjects, directory)
        model, curves, group = _fit(fit_x, y, meta, train, validation, train_subjects,
                                    SELECTION_SEED, MAX_EPOCHS, config, device)
        q9.atomic_csv(directory / "learning_curve.csv", pd.DataFrame(curves))
        q9.atomic_csv(directory / "fit_manifest.csv", q9._fit_manifest(
            meta, subject, "inner", inner, SELECTION_SEED, train, validation, MAX_EPOCHS))
        write_json(directory / "model_receipt.json", _model_receipt(model, config, group))
        q9.atomic_checkpoint(directory / "checkpoint.pt", {**info, "model_state": cpu_state(model)})
        q9._mark_complete(directory, required, {**info,
                          "elapsed_seconds": time.perf_counter() - started})
        del fit_x, model
        if device.type == "cuda":
            torch.cuda.empty_cache()
    except Exception:
        q9._record_failure(directory, {**info, "elapsed_seconds": time.perf_counter() - started})
        raise


def _freeze_selection(output: Path, config: dict) -> bool:
    rows, details = [], []
    for subject in range(1, 10):
        curves = {}
        for inner in range(1, 5):
            directory = _inner_path(output, subject, inner)
            if not q9._fit_complete(directory, _required(config, False)):
                return False
            curves[inner] = pd.read_csv(directory / "learning_curve.csv").to_dict("records")
        selected, detail = q9.select_mean_rank(curves)
        rows.append({"fold": f"loso_s{subject}", "subject": subject,
                     "selected_epochs": selected, "selection_rule": "mean_rank",
                     "selected_mean_rank": float(detail.loc[detail.selected, "mean_rank"].iloc[0]),
                     "selection_seed": SELECTION_SEED, "target_result_used": False})
        detail.insert(0, "fold", f"loso_s{subject}")
        detail.insert(1, "subject", subject)
        details.append(detail)
    selected_frame = pd.DataFrame(rows)
    path = output / "selection.csv"
    if path.exists():
        pd.testing.assert_frame_equal(pd.read_csv(path), selected_frame, check_dtype=False)
    else:
        q9.atomic_csv(path, selected_frame)
        q9.atomic_csv(output / "mean_rank_epoch_details.csv", pd.concat(details, ignore_index=True))
    receipt = {"status": "frozen_before_Q12_target_inference", "condition": config["condition"],
               "rule": "Q8_equal_inner_mean_validation_CE_rank", "inner_fits": 36,
               "selection_seed": SELECTION_SEED, "target_result_used": False,
               "selection_sha256": sha256_file(path),
               "mean_rank_details_sha256": sha256_file(output / "mean_rank_epoch_details.csv"),
               "run_config_sha256": sha256_file(output / "run_config.json")}
    receipt_path = output / "selection_provenance.json"
    if receipt_path.exists():
        if json.loads(receipt_path.read_text(encoding="utf-8")) != receipt:
            raise AssertionError("Q12 source-only selection receipt changed")
    else:
        write_json(receipt_path, receipt)
    return True


def _run_final(output: Path, subject: int, seed: int, x: torch.Tensor, y: torch.Tensor,
               meta: pd.DataFrame, config: dict, device: torch.device) -> None:
    if not _freeze_selection(output, config):
        raise RuntimeError("All 36 Q12 source-only inner fits required before target inference")
    selection_path = output / "selection.csv"
    selection_hash = sha256_file(selection_path)
    selected = int(pd.read_csv(selection_path).set_index("subject").loc[subject, "selected_epochs"])
    if selected not in range(1, MAX_EPOCHS + 1):
        raise AssertionError("Selected epoch outside 1..40")
    directory = _final_path(output, subject, seed)
    required = _required(config, True)
    if q9._fit_complete(directory, required):
        status = json.loads((directory / "status.json").read_text(encoding="utf-8"))
        if status["selection_sha256"] != selection_hash or status["selected_epochs"] != selected:
            raise AssertionError("Completed Q12 fit does not match frozen source selection")
        print(f"{config['condition']} S{subject} seed {seed}: verified resume", flush=True)
        return
    directory.mkdir(parents=True, exist_ok=True)
    train = np.flatnonzero((meta.subject != subject).to_numpy())
    test = np.flatnonzero((meta.subject == subject).to_numpy())
    subjects = [value for value in range(1, 10) if value != subject]
    if len(train) != 4608 or len(test) != 576:
        raise AssertionError("Q8 LOSO trial identity changed")
    info = {"experiment_id": config["experiment_id"], "condition": config["condition"],
            "fold": f"loso_s{subject}", "target_subject": subject, "stage": "full",
            "seed": seed, "train_subjects": subjects, "test_subjects": [subject],
            "n_train": len(train), "n_test": len(test), "selected_epochs": selected,
            "selection_sha256": selection_hash}
    write_json(directory / "status.json", {"status": "running", **info,
                                           "started_at_utc": q9.now_utc()})
    started = time.perf_counter()
    try:
        fit_x = _fit_input(config, x, meta, train, subjects, directory)
        model, curves, group = _fit(fit_x, y, meta, train, None, subjects, seed,
                                    selected, config, device)
        probabilities = predict_probabilities(model, fit_x, test,
                                              int(config["training"]["batch_size"]))
        if probabilities.shape != (576, 4):
            raise AssertionError("Unexpected target probability shape")
        part = meta.iloc[test].copy().reset_index(drop=True)
        part["experiment_id"] = config["experiment_id"]
        part["condition"] = config["condition"]
        part["fold"] = f"loso_s{subject}"
        part["seed"] = seed
        part["selected_epochs"] = selected
        part["selection_rule"] = "mean_rank"
        part["y_true"] = part.label.astype(int)
        part["y_pred"] = probabilities.argmax(axis=1).astype(int) + 1
        for cls in range(4):
            part[f"p_class_{cls + 1}"] = probabilities[:, cls]
        metrics, confusion = score_predictions(part, [1, 2, 3, 4], f"loso_s{subject}", seed,
                                               len(train))
        q9.atomic_csv(directory / "learning_curve.csv", pd.DataFrame(curves))
        q9.atomic_csv(directory / "fit_manifest.csv", q9._fit_manifest(
            meta, subject, "full", None, seed, train, None, selected))
        q9.atomic_csv(directory / "predictions.csv", part)
        metric_frame = pd.DataFrame(metrics)
        metric_frame["condition"] = config["condition"]
        metric_frame["selected_epochs"] = selected
        q9.atomic_csv(directory / "metrics.csv", metric_frame)
        confusion_frame = pd.DataFrame(confusion)
        confusion_frame["condition"] = config["condition"]
        q9.atomic_csv(directory / "confusion.csv", confusion_frame)
        write_json(directory / "model_receipt.json", _model_receipt(model, config, group))
        q9.atomic_checkpoint(directory / "checkpoint.pt", {**info, "model_state": cpu_state(model)})
        q9._mark_complete(directory, required, {**info,
                          "elapsed_seconds": time.perf_counter() - started})
        del fit_x, model
        if device.type == "cuda":
            torch.cuda.empty_cache()
        print(f"{config['condition']} S{subject} seed {seed}: complete", flush=True)
    except Exception:
        q9._record_failure(directory, {**info, "elapsed_seconds": time.perf_counter() - started})
        raise


def _aggregate(output: Path, config: dict) -> None:
    inner = [_inner_path(output, subject, fold) for subject in range(1, 10)
             for fold in range(1, 5)
             if q9._fit_complete(_inner_path(output, subject, fold), _required(config, False))]
    final = [_final_path(output, subject, seed) for subject in range(1, 10)
             for seed in FINAL_SEEDS
             if q9._fit_complete(_final_path(output, subject, seed), _required(config, True))]
    selection_done = (output / "selection_provenance.json").exists()
    state = {"experiment_id": config["experiment_id"], "condition": config["condition"],
             "status": "complete" if len(inner) == 36 and len(final) == 27 else
             "selection_complete" if selection_done and not final else "running",
             "completed_inner_fits": len(inner), "expected_inner_fits": 36,
             "completed_final_fits": len(final), "expected_final_fits": 27,
             "selection_frozen": selection_done, "updated_at_utc": q9.now_utc()}
    if final:
        for source, destination in (("predictions.csv", "predictions.csv"),
                                    ("metrics.csv", "per_subject_metrics.csv"),
                                    ("confusion.csv", "confusion_matrices.csv")):
            q9.atomic_csv(output / destination, pd.concat(
                [pd.read_csv(directory / source) for directory in final], ignore_index=True))
    if inner or final:
        q9.atomic_csv(output / "fit_manifest.csv", pd.concat(
            [pd.read_csv(directory / "fit_manifest.csv") for directory in inner + final],
            ignore_index=True))
    write_json(output / "status.json", state)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", required=True, choices=sorted(matrix_conditions()))
    parser.add_argument("--phase", required=True, choices=("selection", "final"))
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--output-root", type=Path, default=ROOT / "results")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--target-subject", type=int, choices=range(1, 10))
    args = parser.parse_args()
    if args.phase == "final":
        assert_pretarget_git_freeze()
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable; no CPU simulation fallback")
    device = torch.device(args.device)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    mne.set_log_level("ERROR")
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    row = matrix_conditions()[args.condition]
    output = args.output_root.resolve() / row["experiment_id"] / args.condition
    output.mkdir(parents=True, exist_ok=True)
    config = settings(args.condition, args.data_dir.resolve(), output)
    environment_path = output / "environment.json"
    environment = q9._versions()
    if environment_path.exists():
        old = json.loads(environment_path.read_text(encoding="utf-8"))
        for key in ("packages", "torch_cuda_runtime", "cuda_device_name"):
            if old.get(key) != environment.get(key):
                raise AssertionError(f"Q12 environment {key} changed during resume")
    else:
        write_json(environment_path, environment)
    if args.phase == "final" and not _freeze_selection(output, config):
        raise RuntimeError("All 36 source-only inner fits required before Q12 target inference")
    x, y, meta = q11._load_data(config, args.data_dir.resolve(), device, output)
    targets = [args.target_subject] if args.target_subject else list(range(1, 10))
    try:
        for subject in targets:
            if args.phase == "selection":
                for inner in range(1, 5):
                    _run_inner(output, subject, inner, x, y, meta, config, device)
            else:
                for seed in FINAL_SEEDS:
                    _run_final(output, subject, seed, x, y, meta, config, device)
            _aggregate(output, config)
        if args.phase == "selection":
            _freeze_selection(output, config)
        _aggregate(output, config)
    except Exception:
        write_json(output / "last_failure.json", {"time_utc": q9.now_utc(),
                                                  "phase": args.phase,
                                                  "traceback": traceback.format_exc()})
        _aggregate(output, config)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
