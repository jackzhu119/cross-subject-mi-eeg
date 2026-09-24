"""Resumable, source-only Q9 EEGNet frequency-ablation runner.

Run selection for an E001 condition before final inference. Every inner fit
uses six source subjects, validates on two other source subjects, and never
uses the outer target. A single E001 selection file is frozen only after all
36 inner fits exist. E002 uses Q8's already frozen source-only epochs and has
no inner fits. Q4--Q8 artifacts are read-only.

Examples::

    python scripts/q9_neural.py --condition MU_BETA_SHARED --phase selection \
        --data-dir data/raw --device cuda
    python scripts/q9_neural.py --condition MU_BETA_SHARED --phase final \
        --data-dir data/raw --device cuda

An interrupted invocation resumes at the first missing *fit*. A fit interrupted
mid-epoch is restarted from its fixed seed; completed fits, checkpoints and
failure records are retained. The script never silently changes the protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

# Required by deterministic CUDA matrix operations. Set before torch imports
# and before the first CUDA context is initialized.
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mne
import numpy as np
import pandas as pd
import torch
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
from scripts.run_eegnet import (
    cpu_state,
    score_predictions,
    sha256_file,
    source_files,
    verify_q4_identity,
    write_json,
)

MATRIX = ROOT / "research_runs/Q9-E001/Q9_BATCH_MATRIX.json"
Q8_CONFIG = ROOT / "research_runs/Q8-E001/results/config.json"
Q8_META = ROOT / "research_runs/Q8-E001/results/trial_metadata.csv"
Q8_SELECTION = ROOT / "research_runs/Q8-E001/results/predeclared_selection.csv"
Q8_PROVENANCE = ROOT / "research_runs/Q8-E001/results/selection_provenance.json"
CONDITIONS = {
    "MID_8_30": ("Q9-E001", {"mid": [8, 30]}, False),
    "MU_8_13": ("Q9-E001", {"mu": [8, 13]}, False),
    "BETA_13_30": ("Q9-E001", {"beta": [13, 30]}, False),
    "MU_BETA_SHARED": ("Q9-E001", {"mu": [8, 13], "beta": [13, 30]}, True),
    "MID_8_30_Q8_EPOCHS": ("Q9-E002", {"mid": [8, 30]}, False),
    "MU_BETA_SHARED_Q8_EPOCHS": ("Q9-E002", {"mu": [8, 13], "beta": [13, 30]}, True),
    "MU_BETA_SHARED_SOURCE_CLEAN": ("Q9-E004", {"mu": [8, 13], "beta": [13, 30]}, True),
    "MU_BETA_SHARED_SOURCE_NORM": ("Q9-E005", {"mu": [8, 13], "beta": [13, 30]}, True),
}
SELECTION_SEED = 20260923
FINAL_SEEDS = (20260924, 20260925, 20260926)
MAX_EPOCHS = 40


def now_utc() -> str:
    return datetime.now(UTC).isoformat()


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp, index=False)
    os.replace(tmp, path)


def atomic_checkpoint(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, tmp)
    os.replace(tmp, path)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _versions() -> dict:
    packages = ("torch", "braindecode", "mne", "moabb", "numpy", "pandas", "scipy", "scikit-learn")
    versions = {}
    for package in packages:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    try:
        git_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        git_head = None
    return {
        "captured_at_utc": now_utc(),
        "python": sys.version,
        "platform": platform.platform(),
        "packages": versions,
        "torch_cuda_runtime": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "git_head": git_head,
    }


def _locked_settings(condition: str, data_dir: Path, output: Path) -> tuple[dict, dict]:
    experiment_id, bands, shared = CONDITIONS[condition]
    matrix = _read_json(MATRIX)
    row = next((r for r in matrix["conditions"] if r["name"] == condition), None)
    if row is None or row["experiment_id"] != experiment_id:
        raise AssertionError("Condition does not match the frozen Q9 batch matrix")
    q8 = _read_json(Q8_CONFIG)
    if q8["subjects"] != list(range(1, 10)) or q8["training"]["max_epochs"] != MAX_EPOCHS:
        raise AssertionError("Q8 source-only baseline contract changed")
    if q8["training"]["selection_seed"] != SELECTION_SEED:
        raise AssertionError("Selection seed disagrees with frozen Q8")
    if q8["training"]["final_seeds"] != list(FINAL_SEEDS):
        raise AssertionError("Final seeds disagree with frozen Q8")
    pre = dict(q8["preprocessing"])
    pre["bands"] = bands
    # Q9-E004 is a source-only training exclusion; it must not be implemented
    # by rejecting target epochs at data-load time.
    pre["artifact_policy"] = "include_all"
    config = {
        "experiment_id": experiment_id,
        "condition": condition,
        "bands": bands,
        "shared_mean_logits": shared,
        "source_only_selection": experiment_id != "Q9-E002",
        "fixed_q8_epochs": experiment_id == "Q9-E002",
        "source_training_artifact_exclusion": experiment_id == "Q9-E004",
        "source_fit_per_band_channel_zscore": experiment_id == "Q9-E005",
        "preprocessing": pre,
        "architecture": q8["architecture"],
        "training": {key: value for key, value in q8["training"].items()
                     if key not in {"device", "inner_curve_source", "inner_fits_retrained", "epoch_selection"}},
        "input": q8["input"],
        "subjects": q8["subjects"],
        "class_ids": q8["class_ids"],
        "data_dir": str(data_dir.resolve()),
        "q8_config_sha256": sha256_file(Q8_CONFIG),
        "q9_matrix_sha256": sha256_file(MATRIX),
        "runner_sha256": sha256_file(Path(__file__)),
    }
    lock_file = output / "run_config.json"
    if lock_file.exists():
        old = _read_json(lock_file)
        if old != config:
            raise AssertionError("Existing Q9 run_config differs; refusing to mix protocols")
    else:
        write_json(lock_file, config)
    return config, row


class SharedBandEEGNet(torch.nn.Module):
    """One EEGNet's weights process mu and beta; mean logits before CE."""

    def __init__(self, architecture: dict, device: torch.device) -> None:
        super().__init__()
        self.eegnet = build_eegnet(architecture, device)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim != 4 or x.shape[1] != 2:
            raise ValueError("Shared fusion expects [trials, 2 bands, 22 channels, 750 times]")
        n, bands, chans, times = x.shape
        logits = self.eegnet(x.reshape(n * bands, chans, times))
        return logits.reshape(n, bands, -1).mean(dim=1)


def _build_model(config: dict, device: torch.device) -> torch.nn.Module:
    arch = config["architecture"]
    return SharedBandEEGNet(arch, device) if config["shared_mean_logits"] else build_eegnet(arch, device)


def _fit(
    x: torch.Tensor, y: torch.Tensor, train: np.ndarray, validation: np.ndarray | None,
    seed: int, epochs: int, config: dict, device: torch.device,
) -> tuple[torch.nn.Module, list[dict]]:
    train_cfg = config["training"]
    seed_everything(seed, bool(train_cfg["deterministic_algorithms"]))
    model = _build_model(config, device)
    optimizer = torch.optim.Adam(
        model.parameters(), lr=float(train_cfg["learning_rate"]),
        weight_decay=float(train_cfg["weight_decay"]),
    )
    train_idx = torch.as_tensor(np.asarray(train).copy(), dtype=torch.long, device=device)
    val_idx = None if validation is None else torch.as_tensor(
        np.asarray(validation).copy(), dtype=torch.long, device=device
    )
    curves = []
    for epoch in range(1, epochs + 1):
        train_ce = train_one_epoch(model, optimizer, x, y, train_idx, train_cfg["batch_size"])
        val_ce = math.nan if val_idx is None else evaluate_cross_entropy(
            model, x, y, val_idx, train_cfg["batch_size"]
        )
        curves.append({"epoch": epoch, "train_ce": train_ce, "val_ce": val_ce})
    return model, curves


def select_mean_rank(curves: dict[int, list[dict]]) -> tuple[int, pd.DataFrame]:
    """Exactly Q8's within-fold average-rank rule, including average ties."""
    if set(curves) != {1, 2, 3, 4}:
        raise AssertionError("Expected four source-only inner folds")
    columns = {}
    for inner, rows in curves.items():
        if [int(row["epoch"]) for row in rows] != list(range(1, MAX_EPOCHS + 1)):
            raise AssertionError(f"Inner fold {inner} lacks exact epochs 1..40")
        ce = np.array([float(row["val_ce"]) for row in rows], dtype=float)
        if not np.isfinite(ce).all():
            raise AssertionError(f"Inner fold {inner} has nonfinite validation CE")
        columns[inner] = ce
    pivot = pd.DataFrame(columns, index=range(1, MAX_EPOCHS + 1))
    ranks = pivot.rank(axis=0, method="average", ascending=True)
    means = ranks.mean(axis=1)
    minimum = float(means.min())
    selected = min(int(epoch) for epoch, value in means.items()
                   if np.isclose(float(value), minimum, atol=1e-12, rtol=0))
    details = pd.DataFrame({"epoch": list(range(1, MAX_EPOCHS + 1)),
                            **{f"rank_inner_{i}": ranks[i].to_numpy() for i in range(1, 5)},
                            "mean_rank": means.to_numpy(),
                            "selected": [e == selected for e in range(1, MAX_EPOCHS + 1)]})
    return selected, details


def _fit_complete(directory: Path, required: tuple[str, ...]) -> bool:
    status_file = directory / "status.json"
    if not status_file.exists():
        return False
    state = _read_json(status_file)
    if state.get("status") != "complete":
        return False
    for filename in required:
        path = directory / filename
        if not path.is_file() or state.get(f"sha256_{filename}") != sha256_file(path):
            raise AssertionError(f"Completed fit {directory} is missing or corrupted {filename}")
    return True


def _mark_complete(directory: Path, required: tuple[str, ...], info: dict) -> None:
    info = dict(info)
    info["status"] = "complete"
    info["completed_at_utc"] = now_utc()
    for filename in required:
        info[f"sha256_{filename}"] = sha256_file(directory / filename)
    write_json(directory / "status.json", info)


def _record_failure(directory: Path, context: dict) -> None:
    failure_dir = directory / "failures"
    failure_dir.mkdir(parents=True, exist_ok=True)
    key = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    failure = {"time_utc": now_utc(), **context, "traceback": traceback.format_exc()}
    write_json(failure_dir / f"attempt_{key}.json", failure)
    write_json(directory / "status.json", {"status": "failed", **context, "failure": key})


def _inner_path(output: Path, target: int, inner_fold: int) -> Path:
    return output / "inner" / f"loso_s{target}" / f"inner_{inner_fold}"


def _final_path(output: Path, target: int, seed: int) -> Path:
    return output / "final" / f"loso_s{target}" / f"seed_{seed}"


def _source_partition(meta: pd.DataFrame, target: int, inner_fold: int) -> tuple[list[int], list[int], np.ndarray, np.ndarray]:
    source = [s for s in range(1, 10) if s != target]
    validation_subjects = source[2 * (inner_fold - 1):2 * inner_fold]
    training_subjects = [s for s in source if s not in validation_subjects]
    if len(training_subjects) != 6 or len(validation_subjects) != 2 or target in training_subjects + validation_subjects:
        raise AssertionError("Invalid source-only inner partition")
    train = np.flatnonzero(meta.subject.isin(training_subjects).to_numpy())
    validation = np.flatnonzero(meta.subject.isin(validation_subjects).to_numpy())
    if len(train) != 3456 or len(validation) != 1152:
        raise AssertionError("Unexpected source-only inner trial counts")
    return training_subjects, validation_subjects, train, validation


def source_training_indices(meta: pd.DataFrame, candidates: np.ndarray, *, exclude_flagged: bool) -> np.ndarray:
    """Apply E004 only to train rows, never to validation or outer test rows."""
    candidates = np.asarray(candidates, dtype=np.int64)
    if not exclude_flagged:
        return candidates.copy()
    chosen = candidates[~meta.iloc[candidates].artifact_flagged.to_numpy(dtype=bool)]
    if not len(chosen) or meta.iloc[chosen].artifact_flagged.any():
        raise AssertionError("Source-clean training retained no trials or a flagged trial")
    return chosen


def _sample_ids_hash(ids: list[str]) -> str:
    digest = hashlib.sha256()
    for sample_id in ids:
        encoded = sample_id.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def fit_source_band_standardizer(
    signal: np.ndarray, meta: pd.DataFrame, train: np.ndarray, train_subjects: list[int],
) -> dict:
    """Q6 float64/ddof=0 recipe, fitted separately for each Q9 band."""
    if signal.ndim != 4 or signal.shape[1:] != (2, 22, 750):
        raise ValueError("Source-norm requires two aligned 22x750 bands")
    train = np.asarray(train, dtype=np.int64)
    if not len(train) or len(np.unique(train)) != len(train) or train.min() < 0 or train.max() >= len(meta):
        raise ValueError("Invalid source fit indices")
    expected = tuple(sorted(train_subjects))
    observed = tuple(sorted(int(s) for s in meta.iloc[train].subject.unique()))
    required = np.flatnonzero(meta.subject.isin(expected).to_numpy())
    if observed != expected or not np.array_equal(np.sort(train), required):
        raise ValueError("Normalizer must use all and only the declared source-train subjects")
    values = signal[train]
    if not np.isfinite(values).all():
        raise ValueError("Nonfinite source EEG")
    mean = values.mean(axis=(0, 3), dtype=np.float64)
    std = values.std(axis=(0, 3), dtype=np.float64, ddof=0)
    if mean.shape != (2, 22) or std.shape != (2, 22):
        raise AssertionError("Invalid per-band channel moments")
    if not np.isfinite(mean).all() or not np.isfinite(std).all() or np.any(std < 1e-6):
        raise ValueError("Nonfinite or near-zero source EEG channel variance")
    return {
        "method": "per_band_per_channel_source_train_zscore",
        "fit_axes": ["trials", "time"],
        "statistics_dtype": "float64", "application_dtype": "float32", "variance_ddof": 0,
        "min_std_microvolts": 1e-6,
        "n_train_trials": len(train), "n_time_samples_per_trial": 750,
        "train_subjects": list(expected),
        "ordered_train_sample_ids_sha256": _sample_ids_hash(
            meta.iloc[train].sample_id.astype(str).tolist()),
        "band_order": ["mu", "beta"],
        "channel_mean_microvolts": mean.tolist(),
        "channel_std_microvolts": std.tolist(),
        "target_fitted_transform": False,
    }


def apply_source_band_standardizer(x: torch.Tensor, receipt: dict) -> torch.Tensor:
    if x.ndim != 4 or tuple(x.shape[1:]) != (2, 22, 750):
        raise ValueError("Expected two-band EEG input")
    mean = torch.as_tensor(receipt["channel_mean_microvolts"], dtype=x.dtype, device=x.device)
    std = torch.as_tensor(receipt["channel_std_microvolts"], dtype=x.dtype, device=x.device)
    transformed = (x - mean[None, :, :, None]) / std[None, :, :, None]
    if not torch.isfinite(transformed).all():
        raise FloatingPointError("Source-normalized EEG has nonfinite values")
    return transformed


def _fit_manifest(meta: pd.DataFrame, target: int, stage: str, inner_fold: int | None,
                  seed: int, train: np.ndarray, validation: np.ndarray | None,
                  epochs: int) -> pd.DataFrame:
    train_ids = set(int(i) for i in train)
    val_ids = set() if validation is None else set(int(i) for i in validation)
    if train_ids & val_ids or any(int(meta.iloc[i].subject) == target for i in train_ids | val_ids):
        raise AssertionError("Target or overlap appeared in fit manifest")
    rows = []
    for subject in range(1, 10):
        idx = set(int(i) for i in np.flatnonzero((meta.subject == subject).to_numpy()))
        role = ("outer_test_excluded" if stage == "inner" else "test") if subject == target else (
            "validation" if idx & val_ids else "train")
        n_used = len(idx & train_ids)
        rows.append({"fold": f"loso_s{target}", "stage": stage, "inner_fold": inner_fold,
                     "seed": seed, "subject": subject, "role": role,
                     "n_trials": len(idx), "n_used_for_fit": n_used,
                     "n_excluded_from_fit": len(idx) - n_used if role == "train" else 0,
                     "n_used_for_validation": len(idx & val_ids), "epochs_trained": epochs})
    if sum(row["n_used_for_fit"] for row in rows) != len(train):
        raise AssertionError("Manifest training trial counts do not reconcile")
    return pd.DataFrame(rows)


def _required_fit_files(config: dict, stage: str) -> tuple[str, ...]:
    common = ("checkpoint.pt", "learning_curve.csv", "fit_manifest.csv")
    if stage == "full":
        common += ("predictions.csv", "metrics.csv", "confusion.csv")
    if config["source_fit_per_band_channel_zscore"]:
        common += ("normalization_receipt.json",)
    return common


def _fit_input(config: dict, x: torch.Tensor, signal: np.ndarray, meta: pd.DataFrame,
               train: np.ndarray, train_subjects: list[int], directory: Path) -> torch.Tensor:
    if not config["source_fit_per_band_channel_zscore"]:
        return x
    receipt = fit_source_band_standardizer(signal, meta, train, train_subjects)
    receipt_path = directory / "normalization_receipt.json"
    if receipt_path.exists() and _read_json(receipt_path) != receipt:
        raise AssertionError("Existing source-only normalization receipt differs")
    if not receipt_path.exists():
        write_json(receipt_path, receipt)
    return apply_source_band_standardizer(x, receipt)


def _load_data(config: dict, data_dir: Path, device: torch.device, output: Path) -> tuple[torch.Tensor, torch.Tensor, pd.DataFrame, np.ndarray]:
    with threadpool_limits(limits=2):
        bands, meta, audit = load_configured_epochs(
            config["subjects"], data_dir, config["preprocessing"], config["class_ids"]
        )
    if len(meta) != 5184 or int(meta.artifact_flagged.sum()) != 488:
        raise AssertionError("Trial or artifact population differs from frozen Q8")
    verify_q4_identity(meta, pd.read_csv(Q8_META))
    expected_names = list(config["bands"])
    if list(bands) != expected_names:
        raise AssertionError("Frequency band order changed")
    scaled = [bands[name] * np.float32(config["input"]["volts_to_microvolts"])
              for name in expected_names]
    if any(arr.shape != (5184, 22, 750) or not np.isfinite(arr).all() for arr in scaled):
        raise AssertionError("Invalid Q9 EEG shape or values")
    signal = np.stack(scaled, axis=1) if config["shared_mean_logits"] else scaled[0]
    if config["shared_mean_logits"] and signal.shape != (5184, 2, 22, 750):
        raise AssertionError("Invalid shared-band EEG shape")
    hashes = source_files(data_dir, config["subjects"])
    source_record = {"files": hashes, "q8_metadata_sha256": sha256_file(Q8_META)}
    source_file = output / "source_files.json"
    if source_file.exists() and _read_json(source_file) != source_record:
        raise AssertionError("BNCI MAT files differ from this run's original source hash lock")
    if not source_file.exists():
        write_json(source_file, source_record)
    trial_file = output / "trial_metadata.csv"
    if trial_file.exists():
        verify_q4_identity(meta, pd.read_csv(trial_file))
    else:
        atomic_csv(trial_file, meta)
    if not (output / "data_audit.csv").exists():
        atomic_csv(output / "data_audit.csv", audit)
    x = torch.from_numpy(signal).to(device)
    y = torch.as_tensor(meta.label.to_numpy(np.int64) - 1, dtype=torch.long, device=device)
    return x, y, meta, signal


def _run_inner(output: Path, target: int, inner_fold: int, x: torch.Tensor, y: torch.Tensor,
               meta: pd.DataFrame, signal: np.ndarray, config: dict, device: torch.device) -> None:
    directory = _inner_path(output, target, inner_fold)
    required = _required_fit_files(config, "inner")
    if _fit_complete(directory, required):
        print(f"{config['condition']} S{target} inner {inner_fold}: resume completed fit", flush=True)
        return
    directory.mkdir(parents=True, exist_ok=True)
    train_subjects, validation_subjects, candidate_train, validation = _source_partition(meta, target, inner_fold)
    train = source_training_indices(meta, candidate_train,
                                    exclude_flagged=config["source_training_artifact_exclusion"])
    info = {"experiment_id": config["experiment_id"], "condition": config["condition"],
            "fold": f"loso_s{target}", "target_subject": target, "stage": "inner",
            "inner_fold": inner_fold, "seed": SELECTION_SEED,
            "train_subjects": train_subjects, "validation_subjects": validation_subjects,
            "n_train": len(train), "n_train_candidates": len(candidate_train),
            "n_flagged_source_train_excluded": len(candidate_train) - len(train),
            "n_validation": len(validation), "epochs_trained": MAX_EPOCHS}
    write_json(directory / "status.json", {"status": "running", **info, "started_at_utc": now_utc()})
    started = time.perf_counter()
    try:
        fit_x = _fit_input(config, x, signal, meta, train, train_subjects, directory)
        model, curves = _fit(fit_x, y, train, validation, SELECTION_SEED, MAX_EPOCHS, config, device)
        atomic_csv(directory / "learning_curve.csv", pd.DataFrame(curves))
        manifest = _fit_manifest(meta, target, "inner", inner_fold, SELECTION_SEED,
                                 train, validation, MAX_EPOCHS)
        atomic_csv(directory / "fit_manifest.csv", manifest)
        atomic_checkpoint(directory / "checkpoint.pt", {**info, "model_state": cpu_state(model)})
        _mark_complete(directory, required, {**info, "elapsed_seconds": time.perf_counter() - started})
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()
        print(f"{config['condition']} S{target} inner {inner_fold}: complete", flush=True)
    except Exception:
        _record_failure(directory, {**info, "elapsed_seconds": time.perf_counter() - started})
        raise


def _freeze_selection(output: Path, config: dict) -> bool:
    rows, details = [], []
    for target in range(1, 10):
        curves = {}
        for inner in range(1, 5):
            directory = _inner_path(output, target, inner)
            if not _fit_complete(directory, _required_fit_files(config, "inner")):
                return False
            curves[inner] = pd.read_csv(directory / "learning_curve.csv").to_dict("records")
        selected, detail = select_mean_rank(curves)
        rows.append({"fold": f"loso_s{target}", "subject": target, "selected_epochs": selected,
                     "selection_rule": "mean_rank", "selected_mean_rank":
                     float(detail.loc[detail.selected, "mean_rank"].iloc[0]),
                     "selection_seed": SELECTION_SEED, "target_result_used": False})
        detail.insert(0, "fold", f"loso_s{target}")
        detail.insert(1, "subject", target)
        details.append(detail)
    selection = pd.DataFrame(rows)
    outfile = output / "selection.csv"
    if outfile.exists():
        pd.testing.assert_frame_equal(pd.read_csv(outfile), selection, check_dtype=False)
    else:
        atomic_csv(outfile, selection)
        atomic_csv(output / "mean_rank_epoch_details.csv", pd.concat(details, ignore_index=True))
    provenance = {"status": "frozen_before_Q9_target_inference", "rule": "Q8_mean_within_fold_CE_rank",
                  "selection_sha256": sha256_file(outfile), "inner_fits": 36,
                  "selection_seed": SELECTION_SEED, "target_result_used": False,
                  "mean_rank_details_sha256": sha256_file(output / "mean_rank_epoch_details.csv"),
                  "run_config_sha256": sha256_file(output / "run_config.json")}
    path = output / "selection_provenance.json"
    if path.exists() and _read_json(path) != provenance:
        raise AssertionError("Selection provenance changed after freeze")
    if not path.exists():
        write_json(path, provenance)
    return True


def _q8_fixed_selection(output: Path) -> pd.DataFrame:
    provenance = _read_json(Q8_PROVENANCE)
    if sha256_file(Q8_SELECTION) != provenance["predeclared_selection_sha256"]:
        raise AssertionError("Frozen Q8 selection checksum does not match its provenance")
    frame = pd.read_csv(Q8_SELECTION)
    if frame.subject.tolist() != list(range(1, 10)) or frame.target_result_used.astype(str).str.lower().eq("true").any():
        raise AssertionError("Invalid Q8 source-only selection")
    record = {"source": str(Q8_SELECTION.relative_to(ROOT)).replace("\\", "/"),
              "sha256": sha256_file(Q8_SELECTION), "rule": "frozen_Q8_source_only_epoch_numbers"}
    locked = output / "q8_selection_reference.json"
    if locked.exists() and _read_json(locked) != record:
        raise AssertionError("Frozen Q8 epoch reference changed")
    if not locked.exists():
        write_json(locked, record)
    return frame


def _selected_epochs(output: Path, config: dict, target: int) -> tuple[int, str]:
    if config["fixed_q8_epochs"]:
        frame = _q8_fixed_selection(output)
        selection_hash = sha256_file(Q8_SELECTION)
    else:
        provenance_path = output / "selection_provenance.json"
        if not provenance_path.exists() or not (output / "selection.csv").exists():
            raise RuntimeError("All 36 inner fits and a frozen selection are required before target inference")
        provenance = _read_json(provenance_path)
        selection_hash = sha256_file(output / "selection.csv")
        if provenance["selection_sha256"] != selection_hash or not _freeze_selection(output, config):
            raise AssertionError("Source-only selection was changed or incomplete")
        frame = pd.read_csv(output / "selection.csv")
    rows = frame.loc[frame.subject == target]
    if len(rows) != 1:
        raise AssertionError(f"Missing unique selected epoch for S{target}")
    epochs = int(rows.selected_epochs.iloc[0])
    if epochs not in range(1, MAX_EPOCHS + 1):
        raise AssertionError("Selected epoch is outside frozen 1..40 range")
    return epochs, selection_hash


def _run_final(output: Path, target: int, seed: int, x: torch.Tensor, y: torch.Tensor,
               meta: pd.DataFrame, signal: np.ndarray, config: dict, device: torch.device) -> None:
    selected, selection_hash = _selected_epochs(output, config, target)
    directory = _final_path(output, target, seed)
    required = _required_fit_files(config, "full")
    if _fit_complete(directory, required):
        old = _read_json(directory / "status.json")
        if old["selected_epochs"] != selected or old["selection_sha256"] != selection_hash:
            raise AssertionError("Completed final fit disagrees with frozen selection")
        print(f"{config['condition']} S{target} seed {seed}: resume completed fit", flush=True)
        return
    directory.mkdir(parents=True, exist_ok=True)
    candidate_train = np.flatnonzero((meta.subject != target).to_numpy())
    train = source_training_indices(meta, candidate_train,
                                    exclude_flagged=config["source_training_artifact_exclusion"])
    test = np.flatnonzero((meta.subject == target).to_numpy())
    source_subjects = [s for s in range(1, 10) if s != target]
    if len(candidate_train) != 4608 or len(test) != 576:
        raise AssertionError("LOSO trial population differs from frozen Q8")
    info = {"experiment_id": config["experiment_id"], "condition": config["condition"],
            "fold": f"loso_s{target}", "target_subject": target, "stage": "full",
            "seed": seed, "train_subjects": source_subjects, "test_subjects": [target],
            "n_train": len(train), "n_train_candidates": len(candidate_train),
            "n_flagged_source_train_excluded": len(candidate_train) - len(train),
            "n_test": len(test), "selected_epochs": selected,
            "selection_sha256": selection_hash}
    write_json(directory / "status.json", {"status": "running", **info, "started_at_utc": now_utc()})
    started = time.perf_counter()
    try:
        fit_x = _fit_input(config, x, signal, meta, train, source_subjects, directory)
        model, curves = _fit(fit_x, y, train, None, seed, selected, config, device)
        probabilities = predict_probabilities(model, fit_x, test, config["training"]["batch_size"])
        if probabilities.shape != (576, 4):
            raise AssertionError("Unexpected four-class target prediction shape")
        part = meta.iloc[test].copy().reset_index(drop=True)
        part["experiment_id"] = config["experiment_id"]
        part["condition"] = config["condition"]
        part["fold"] = f"loso_s{target}"
        part["seed"] = seed
        part["selected_epochs"] = selected
        part["selection_rule"] = "frozen_Q8_epochs" if config["fixed_q8_epochs"] else "mean_rank"
        part["y_true"] = part.label.astype(int)
        part["y_pred"] = probabilities.argmax(axis=1).astype(int) + 1
        for i in range(4):
            part[f"p_class_{i + 1}"] = probabilities[:, i]
        metrics, confusion = score_predictions(part, [1, 2, 3, 4], f"loso_s{target}", seed, len(train))
        atomic_csv(directory / "learning_curve.csv", pd.DataFrame(curves))
        manifest = _fit_manifest(meta, target, "full", None, seed, train, None, selected)
        atomic_csv(directory / "fit_manifest.csv", manifest)
        atomic_csv(directory / "predictions.csv", part)
        metric_frame = pd.DataFrame(metrics)
        metric_frame["condition"] = config["condition"]
        metric_frame["selected_epochs"] = selected
        atomic_csv(directory / "metrics.csv", metric_frame)
        confusion_frame = pd.DataFrame(confusion)
        confusion_frame["condition"] = config["condition"]
        atomic_csv(directory / "confusion.csv", confusion_frame)
        atomic_checkpoint(directory / "checkpoint.pt", {**info, "model_state": cpu_state(model)})
        _mark_complete(directory, required, {**info, "elapsed_seconds": time.perf_counter() - started})
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()
        primary = metric_frame.loc[metric_frame.stratum == "all", "balanced_accuracy"].iloc[0]
        print(f"{config['condition']} S{target} seed {seed}: complete BA={primary:.4f}", flush=True)
    except Exception:
        _record_failure(directory, {**info, "elapsed_seconds": time.perf_counter() - started})
        raise


def _aggregate(output: Path, config: dict) -> None:
    complete_inner, complete_final = [], []
    for target in range(1, 10):
        if not config["fixed_q8_epochs"]:
            for inner in range(1, 5):
                directory = _inner_path(output, target, inner)
                if _fit_complete(directory, _required_fit_files(config, "inner")):
                    complete_inner.append(directory)
        for seed in FINAL_SEEDS:
            directory = _final_path(output, target, seed)
            if _fit_complete(directory, _required_fit_files(config, "full")):
                complete_final.append(directory)
    expected_inner = 0 if config["fixed_q8_epochs"] else 36
    selection_done = config["fixed_q8_epochs"] or (output / "selection_provenance.json").exists()
    status = {"experiment_id": config["experiment_id"], "condition": config["condition"],
              "status": "complete" if len(complete_final) == 27 and len(complete_inner) == expected_inner else
              "selection_complete" if selection_done and len(complete_final) == 0 else "running",
              "completed_inner_fits": len(complete_inner), "expected_inner_fits": expected_inner,
              "completed_final_fits": len(complete_final), "expected_final_fits": 27,
              "selection_frozen": selection_done, "updated_at_utc": now_utc()}
    if complete_final:
        for source_name, dest_name in (("predictions.csv", "predictions.csv"),
                                       ("metrics.csv", "per_subject_metrics.csv"),
                                       ("confusion.csv", "confusion_matrices.csv")):
            frames = [pd.read_csv(directory / source_name) for directory in complete_final]
            atomic_csv(output / dest_name, pd.concat(frames, ignore_index=True))
    if complete_inner or complete_final:
        frames = [pd.read_csv(d / "fit_manifest.csv") for d in complete_inner + complete_final]
        atomic_csv(output / "fit_manifest.csv", pd.concat(frames, ignore_index=True))
    write_json(output / "status.json", status)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", choices=tuple(CONDITIONS), required=True)
    parser.add_argument("--phase", choices=("selection", "final"), required=True)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--output-root", type=Path, default=ROOT / "results")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--target-subject", type=int, choices=range(1, 10))
    args = parser.parse_args()
    if args.condition.endswith("_Q8_EPOCHS") and args.phase == "selection":
        parser.error("Q9-E002 fixed-duration controls have no selection phase")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable; Q9 GPU run cannot start")
    device = torch.device(args.device)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    mne.set_log_level("ERROR")
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    experiment_id = CONDITIONS[args.condition][0]
    output = args.output_root.resolve() / experiment_id / args.condition
    output.mkdir(parents=True, exist_ok=True)
    config, _ = _locked_settings(args.condition, args.data_dir, output)
    environment_file = output / "environment.json"
    current_environment = _versions()
    if environment_file.exists():
        old_environment = _read_json(environment_file)
        for key in ("packages", "torch_cuda_runtime", "cuda_device_name"):
            if old_environment.get(key) != current_environment.get(key):
                raise AssertionError(f"Q9 environment {key} changed during resume")
        if old_environment.get("python", "").split()[0] != current_environment["python"].split()[0]:
            raise AssertionError("Q9 Python version changed during resume")
    else:
        write_json(environment_file, current_environment)
    if args.phase == "final" and not config["fixed_q8_epochs"]:
        # Refuse target inference before the 36 source-only inner fits freeze.
        if not _freeze_selection(output, config):
            raise RuntimeError("Selection incomplete: run --phase selection first")
    if args.phase == "final" and config["fixed_q8_epochs"]:
        _q8_fixed_selection(output)
    x, y, meta, signal = _load_data(config, args.data_dir.resolve(), device, output)
    targets = [args.target_subject] if args.target_subject else list(range(1, 10))
    started = time.perf_counter()
    try:
        for target in targets:
            if args.phase == "selection":
                for inner in range(1, 5):
                    _run_inner(output, target, inner, x, y, meta, signal, config, device)
            else:
                for seed in FINAL_SEEDS:
                    _run_final(output, target, seed, x, y, meta, signal, config, device)
            _aggregate(output, config)
        if args.phase == "selection":
            if _freeze_selection(output, config):
                print(f"{args.condition}: all 36 inner fits complete; selection frozen", flush=True)
            else:
                print(f"{args.condition}: partial selection; no target predictions permitted", flush=True)
        _aggregate(output, config)
    except Exception:
        write_json(output / "last_failure.json", {"time_utc": now_utc(), "phase": args.phase,
                                                  "traceback": traceback.format_exc()})
        _aggregate(output, config)
        raise
    finally:
        print(f"{args.condition} {args.phase}: invocation elapsed {time.perf_counter() - started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
