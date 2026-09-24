"""Q11-E001 spectral-fusion/capacity runner; source-only, resumable at fit level.

Selection (four inner source folds) must finish and be frozen before final
target inference. This module imports frozen Q9 utility functions but never
changes Q9 files, outputs, or selection. See research_runs/Q11-E001/PROTOCOL.md.
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
from threadpoolctl import threadpool_limits

from mi_eeg.data.bnci_epochs import load_configured_epochs
from mi_eeg.models.eegnet_training import (
    build_eegnet,
    evaluate_cross_entropy,
    predict_probabilities,
    seed_everything,
    train_one_epoch,
)
from scripts import q9_neural as q9
from scripts.run_eegnet import (
    cpu_state,
    score_predictions,
    sha256_file,
    source_files,
    verify_q4_identity,
    write_json,
)

MATRIX = ROOT / "research_runs/Q11-E001/MATRIX.json"
Q8_CONFIG = ROOT / "research_runs/Q8-E001/results/config.json"
Q8_META = ROOT / "research_runs/Q8-E001/results/trial_metadata.csv"
CONDITIONS = (
    "FOUR_BAND_SHARED", "TWO_BAND_INDEPENDENT", "TWO_BAND_EARLY_STACK",
    "BROAD_CAPACITY_MATCHED",
)
SELECTION_SEED = 20260923
FINAL_SEEDS = (20260924, 20260925, 20260926)
MAX_EPOCHS = 40
REQUIRED_INNER = ("checkpoint.pt", "learning_curve.csv", "fit_manifest.csv", "model_receipt.json")
REQUIRED_FINAL = REQUIRED_INNER + ("predictions.csv", "metrics.csv", "confusion.csv")


def parameter_count(model: torch.nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)


class BandFusion(torch.nn.Module):
    def __init__(self, architecture: dict, count: int, independent: bool, device: torch.device):
        super().__init__()
        self.count = count
        self.independent = independent
        self.branches = torch.nn.ModuleList(
            [build_eegnet(architecture, device) for _ in range(count if independent else 1)]
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim != 4 or x.shape[1] != self.count or x.shape[2:] != (22, 750):
            raise ValueError(f"Band fusion expects [batch,{self.count},22,750]")
        if self.independent:
            logits = [branch(x[:, band]) for band, branch in enumerate(self.branches)]
            return torch.stack(logits, dim=0).mean(dim=0)
        batch, bands, channels, times = x.shape
        logits = self.branches[0](x.reshape(batch * bands, channels, times))
        return logits.reshape(batch, bands, -1).mean(dim=1)


def model_for(config: dict, device: torch.device) -> torch.nn.Module:
    arch = config["architecture"]
    condition = config["condition"]
    if condition == "FOUR_BAND_SHARED":
        return BandFusion(arch, 4, False, device)
    if condition == "TWO_BAND_INDEPENDENT":
        return BandFusion(arch, 2, True, device)
    return build_eegnet(arch, device)


def _capacity_plan(base_arch: dict) -> dict:
    """Model-structure-only census: no EEG, labels, validation or target data."""
    cpu = torch.device("cpu")
    baseline = build_eegnet(base_arch, cpu)
    count_one = parameter_count(baseline)
    count_two = 2 * count_one
    del baseline
    options = []
    for f1 in range(8, 33):
        arch = {**base_arch, "F1": f1, "D": 2, "F2": 2 * f1}
        candidate = build_eegnet(arch, cpu)
        options.append({"F1": f1, "D": 2, "F2": 2 * f1,
                        "parameter_count": parameter_count(candidate)})
        del candidate
    chosen = min(options, key=lambda row: (abs(row["parameter_count"] - count_two), row["F1"]))
    return {"reference_single_branch_count": count_one,
            "reference_independent_two_branch_count": count_two,
            "candidates": options, "chosen": chosen,
            "relative_parameter_mismatch": abs(chosen["parameter_count"] - count_two) / count_two,
            "criterion": "minimum_absolute_count_difference_then_lowest_F1_no_EEG_used"}


def locked_settings(condition: str, data_dir: Path, output: Path) -> dict:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    row = next((entry for entry in matrix["conditions"] if entry["name"] == condition), None)
    if row is None or row["experiment_id"] != "Q11-E001" or row["inner_fits"] != 36 or row["final_fits"] != 27:
        raise AssertionError("Condition differs from Q11-E001 execution matrix")
    q8 = json.loads(Q8_CONFIG.read_text(encoding="utf-8"))
    if q8["subjects"] != list(range(1, 10)) or q8["training"]["max_epochs"] != MAX_EPOCHS:
        raise AssertionError("Frozen Q8 subject/epoch contract changed")
    if (q8["training"]["selection_seed"] != SELECTION_SEED
            or q8["training"]["final_seeds"] != list(FINAL_SEEDS)):
        raise AssertionError("Frozen Q8 seeds changed")
    plan = _capacity_plan(q8["architecture"])
    architecture = dict(q8["architecture"])
    if condition == "BROAD_CAPACITY_MATCHED":
        architecture.update({key: plan["chosen"][key] for key in ("F1", "D", "F2")})
    if condition == "TWO_BAND_EARLY_STACK":
        architecture["n_chans"] = 44
    pre = dict(q8["preprocessing"])
    pre["bands"] = row["bands"]
    pre["artifact_policy"] = "include_all"
    train = {key: value for key, value in q8["training"].items()
             if key not in {"device", "inner_curve_source", "inner_fits_retrained", "epoch_selection"}}
    config = {
        "experiment_id": "Q11-E001", "condition": condition, "bands": row["bands"],
        "fusion": row["fusion"], "preprocessing": pre, "architecture": architecture,
        "capacity_plan": plan, "training": train, "input": q8["input"],
        "subjects": q8["subjects"], "class_ids": q8["class_ids"],
        "source_only_selection": True, "target_fitted_transform": False,
        "data_dir": str(data_dir.resolve()), "q8_config_sha256": sha256_file(Q8_CONFIG),
        "execution_matrix_sha256": sha256_file(MATRIX),
        "runner_sha256": sha256_file(Path(__file__)),
    }
    path = output / "run_config.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != config:
            raise AssertionError("Q11 run_config differs; refusing to mix protocols")
    else:
        write_json(path, config)
    return config


def _load_data(config: dict, data_dir: Path, device: torch.device, output: Path):
    with threadpool_limits(limits=2):
        bands, meta, audit = load_configured_epochs(
            config["subjects"], data_dir, config["preprocessing"], config["class_ids"])
    if len(meta) != 5184 or int(meta.artifact_flagged.sum()) != 488:
        raise AssertionError("Q8 trial/flag population changed")
    verify_q4_identity(meta, pd.read_csv(Q8_META))
    names = list(config["bands"])
    if list(bands) != names:
        raise AssertionError("Band order differs from frozen matrix")
    scaled = [bands[name] * np.float32(config["input"]["volts_to_microvolts"])
              for name in names]
    if any(value.shape != (5184, 22, 750) or not np.isfinite(value).all() for value in scaled):
        raise AssertionError("Invalid EEG shape or nonfinite signal")
    signal = scaled[0] if len(scaled) == 1 else np.stack(scaled, axis=1)
    if config["condition"] == "TWO_BAND_EARLY_STACK":
        signal = signal.reshape(5184, 44, 750)
    files = {"files": source_files(data_dir, config["subjects"]),
             "q8_metadata_sha256": sha256_file(Q8_META)}
    path = output / "source_files.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != files:
            raise AssertionError("Original BNCI MAT hashes changed on resume")
    else:
        write_json(path, files)
    metadata_path = output / "trial_metadata.csv"
    if metadata_path.exists():
        verify_q4_identity(meta, pd.read_csv(metadata_path))
    else:
        q9.atomic_csv(metadata_path, meta)
    if not (output / "data_audit.csv").exists():
        q9.atomic_csv(output / "data_audit.csv", audit)
    x = torch.from_numpy(signal).to(device)
    y = torch.as_tensor(meta.label.to_numpy(np.int64) - 1, dtype=torch.long, device=device)
    return x, y, meta


def _fit(x: torch.Tensor, y: torch.Tensor, train: np.ndarray, validation: np.ndarray | None,
         seed: int, epochs: int, config: dict, device: torch.device):
    train_cfg = config["training"]
    seed_everything(seed, bool(train_cfg["deterministic_algorithms"]))
    model = model_for(config, device)
    optimizer = torch.optim.Adam(model.parameters(), lr=float(train_cfg["learning_rate"]),
                                 weight_decay=float(train_cfg["weight_decay"]))
    train_idx = torch.as_tensor(np.asarray(train).copy(), dtype=torch.long, device=device)
    val_idx = None if validation is None else torch.as_tensor(
        np.asarray(validation).copy(), dtype=torch.long, device=device)
    curves = []
    for epoch in range(1, epochs + 1):
        train_ce = train_one_epoch(model, optimizer, x, y, train_idx, train_cfg["batch_size"])
        val_ce = math.nan if val_idx is None else evaluate_cross_entropy(
            model, x, y, val_idx, train_cfg["batch_size"])
        curves.append({"epoch": epoch, "train_ce": train_ce, "val_ce": val_ce})
    return model, curves


def _inner_path(output: Path, subject: int, inner: int) -> Path:
    return output / "inner" / f"loso_s{subject}" / f"inner_{inner}"


def _final_path(output: Path, subject: int, seed: int) -> Path:
    return output / "final" / f"loso_s{subject}" / f"seed_{seed}"


def _model_receipt(model: torch.nn.Module, config: dict) -> dict:
    return {"condition": config["condition"], "fusion": config["fusion"],
            "architecture": config["architecture"],
            "trainable_parameter_count": parameter_count(model),
            "parameter_shapes": {name: list(value.shape) for name, value in model.named_parameters()
                                 if value.requires_grad},
            "capacity_reference_two_branch_count":
            config["capacity_plan"]["reference_independent_two_branch_count"],
            "target_or_EEG_used_to_size_model": False}


def assert_pretarget_git_freeze() -> str:
    """Refuse first target inference if Q11 code/protocol lacks a local Git freeze."""
    files = [
        "research_runs/Q11-E001/MATRIX.json", "research_runs/Q11-E001/PROTOCOL.md",
        "scripts/q11_neural.py", "scripts/q11_batch.py", "scripts/validate_q11_e001.py",
        "scripts/q9_neural.py", "src/mi_eeg/data/bnci_epochs.py",
        "src/mi_eeg/models/eegnet_training.py",
    ]
    for command in (("ls-files", "--error-unmatch", "--", *files),
                    ("diff", "--quiet", "--", *files),
                    ("diff", "--cached", "--quiet", "--", *files)):
        result = subprocess.run(["git", *command], cwd=ROOT, capture_output=True,
                                text=True, check=False)
        if result.returncode:
            raise RuntimeError("Q11 code/protocol is not committed unchanged; target inference blocked")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()
    if len(head) != 40:
        raise RuntimeError("Cannot establish Q11 Git pretarget commit")
    return head


def _run_inner(output: Path, subject: int, inner: int, x: torch.Tensor, y: torch.Tensor,
               meta: pd.DataFrame, config: dict, device: torch.device) -> None:
    directory = _inner_path(output, subject, inner)
    if q9._fit_complete(directory, REQUIRED_INNER):
        print(f"{config['condition']} S{subject} inner {inner}: existing fit verified", flush=True)
        return
    directory.mkdir(parents=True, exist_ok=True)
    train_subjects, validation_subjects, train, validation = q9._source_partition(meta, subject, inner)
    info = {"experiment_id": "Q11-E001", "condition": config["condition"],
            "fold": f"loso_s{subject}", "target_subject": subject, "stage": "inner",
            "inner_fold": inner, "seed": SELECTION_SEED,
            "train_subjects": train_subjects, "validation_subjects": validation_subjects,
            "n_train": len(train), "n_validation": len(validation), "epochs_trained": MAX_EPOCHS}
    write_json(directory / "status.json", {"status": "running", **info, "started_at_utc": q9.now_utc()})
    started = time.perf_counter()
    try:
        model, curves = _fit(x, y, train, validation, SELECTION_SEED, MAX_EPOCHS, config, device)
        q9.atomic_csv(directory / "learning_curve.csv", pd.DataFrame(curves))
        q9.atomic_csv(directory / "fit_manifest.csv", q9._fit_manifest(
            meta, subject, "inner", inner, SELECTION_SEED, train, validation, MAX_EPOCHS))
        write_json(directory / "model_receipt.json", _model_receipt(model, config))
        q9.atomic_checkpoint(directory / "checkpoint.pt", {**info, "model_state": cpu_state(model)})
        q9._mark_complete(directory, REQUIRED_INNER, {**info,
                          "elapsed_seconds": time.perf_counter() - started})
        del model
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
            if not q9._fit_complete(directory, REQUIRED_INNER):
                return False
            curves[inner] = pd.read_csv(directory / "learning_curve.csv").to_dict("records")
        chosen, detail = q9.select_mean_rank(curves)
        rows.append({"fold": f"loso_s{subject}", "subject": subject,
                     "selected_epochs": chosen, "selection_rule": "mean_rank",
                     "selected_mean_rank": float(detail.loc[detail.selected, "mean_rank"].iloc[0]),
                     "selection_seed": SELECTION_SEED, "target_result_used": False})
        detail.insert(0, "fold", f"loso_s{subject}")
        detail.insert(1, "subject", subject)
        details.append(detail)
    chosen_frame = pd.DataFrame(rows)
    selection_path = output / "selection.csv"
    if selection_path.exists():
        pd.testing.assert_frame_equal(pd.read_csv(selection_path), chosen_frame, check_dtype=False)
    else:
        q9.atomic_csv(selection_path, chosen_frame)
        q9.atomic_csv(output / "mean_rank_epoch_details.csv", pd.concat(details, ignore_index=True))
    receipt = {"status": "frozen_before_Q11_target_inference",
               "rule": "Q8_mean_within_fold_CE_rank",
               "selection_sha256": sha256_file(selection_path), "inner_fits": 36,
               "selection_seed": SELECTION_SEED, "target_result_used": False,
               "mean_rank_details_sha256": sha256_file(output / "mean_rank_epoch_details.csv"),
               "run_config_sha256": sha256_file(output / "run_config.json")}
    path = output / "selection_provenance.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != receipt:
            raise AssertionError("Frozen Q11 selection receipt changed")
    else:
        write_json(path, receipt)
    return True


def _run_final(output: Path, subject: int, seed: int, x: torch.Tensor, y: torch.Tensor,
               meta: pd.DataFrame, config: dict, device: torch.device) -> None:
    if not _freeze_selection(output, config):
        raise RuntimeError("All 36 source-only inner fits required before target inference")
    selection_path = output / "selection.csv"
    selection_hash = sha256_file(selection_path)
    selected = int(pd.read_csv(selection_path).set_index("subject").loc[subject, "selected_epochs"])
    if selected not in range(1, MAX_EPOCHS + 1):
        raise AssertionError("Selected epoch outside 1..40")
    directory = _final_path(output, subject, seed)
    if q9._fit_complete(directory, REQUIRED_FINAL):
        old = json.loads((directory / "status.json").read_text(encoding="utf-8"))
        if old["selection_sha256"] != selection_hash or old["selected_epochs"] != selected:
            raise AssertionError("Completed final fit differs from frozen source selection")
        print(f"{config['condition']} S{subject} seed {seed}: existing fit verified", flush=True)
        return
    directory.mkdir(parents=True, exist_ok=True)
    train = np.flatnonzero((meta.subject != subject).to_numpy())
    test = np.flatnonzero((meta.subject == subject).to_numpy())
    train_subjects = [value for value in range(1, 10) if value != subject]
    if len(train) != 4608 or len(test) != 576:
        raise AssertionError("Q8 LOSO trial population changed")
    info = {"experiment_id": "Q11-E001", "condition": config["condition"],
            "fold": f"loso_s{subject}", "target_subject": subject, "stage": "full",
            "seed": seed, "train_subjects": train_subjects, "test_subjects": [subject],
            "n_train": len(train), "n_test": len(test),
            "selected_epochs": selected, "selection_sha256": selection_hash}
    write_json(directory / "status.json", {"status": "running", **info, "started_at_utc": q9.now_utc()})
    started = time.perf_counter()
    try:
        model, curves = _fit(x, y, train, None, seed, selected, config, device)
        probabilities = predict_probabilities(model, x, test, config["training"]["batch_size"])
        if probabilities.shape != (576, 4):
            raise AssertionError("Unexpected target probability shape")
        part = meta.iloc[test].copy().reset_index(drop=True)
        part["experiment_id"] = "Q11-E001"
        part["condition"] = config["condition"]
        part["fold"] = f"loso_s{subject}"
        part["seed"] = seed
        part["selected_epochs"] = selected
        part["selection_rule"] = "mean_rank"
        part["y_true"] = part.label.astype(int)
        part["y_pred"] = probabilities.argmax(axis=1).astype(int) + 1
        for cls in range(4):
            part[f"p_class_{cls + 1}"] = probabilities[:, cls]
        metrics, confusion = score_predictions(part, [1, 2, 3, 4], f"loso_s{subject}", seed, len(train))
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
        write_json(directory / "model_receipt.json", _model_receipt(model, config))
        q9.atomic_checkpoint(directory / "checkpoint.pt", {**info, "model_state": cpu_state(model)})
        q9._mark_complete(directory, REQUIRED_FINAL, {**info,
                          "elapsed_seconds": time.perf_counter() - started})
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()
        print(f"{config['condition']} S{subject} seed {seed}: complete", flush=True)
    except Exception:
        q9._record_failure(directory, {**info, "elapsed_seconds": time.perf_counter() - started})
        raise


def _aggregate(output: Path, config: dict) -> None:
    complete_inner = [_inner_path(output, subject, inner) for subject in range(1, 10)
                      for inner in range(1, 5)
                      if q9._fit_complete(_inner_path(output, subject, inner), REQUIRED_INNER)]
    complete_final = [_final_path(output, subject, seed) for subject in range(1, 10)
                      for seed in FINAL_SEEDS
                      if q9._fit_complete(_final_path(output, subject, seed), REQUIRED_FINAL)]
    selection_done = (output / "selection_provenance.json").exists()
    status = {"experiment_id": "Q11-E001", "condition": config["condition"],
              "status": "complete" if len(complete_inner) == 36 and len(complete_final) == 27 else
              "selection_complete" if selection_done and not complete_final else "running",
              "completed_inner_fits": len(complete_inner), "expected_inner_fits": 36,
              "completed_final_fits": len(complete_final), "expected_final_fits": 27,
              "selection_frozen": selection_done, "updated_at_utc": q9.now_utc()}
    if complete_final:
        for source, dest in (("predictions.csv", "predictions.csv"),
                             ("metrics.csv", "per_subject_metrics.csv"),
                             ("confusion.csv", "confusion_matrices.csv")):
            q9.atomic_csv(output / dest, pd.concat(
                [pd.read_csv(directory / source) for directory in complete_final], ignore_index=True))
    if complete_inner or complete_final:
        q9.atomic_csv(output / "fit_manifest.csv", pd.concat(
            [pd.read_csv(directory / "fit_manifest.csv") for directory in complete_inner + complete_final],
            ignore_index=True))
    write_json(output / "status.json", status)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", required=True, choices=CONDITIONS)
    parser.add_argument("--phase", required=True, choices=("selection", "final"))
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--output-root", type=Path, default=ROOT / "results")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--target-subject", type=int, choices=range(1, 10))
    args = parser.parse_args()
    if args.phase == "final":
        # The source-only selection can be smoke-tested before the Git freeze;
        # final target inference cannot. A subsequent code change is also
        # prevented by the run_config and batch SHA256 locks.
        assert_pretarget_git_freeze()
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable; no CPU simulation fallback")
    device = torch.device(args.device)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    mne.set_log_level("ERROR")
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    output = args.output_root.resolve() / "Q11-E001" / args.condition
    output.mkdir(parents=True, exist_ok=True)
    config = locked_settings(args.condition, args.data_dir, output)
    environment_path = output / "environment.json"
    environment = q9._versions()
    if environment_path.exists():
        old = json.loads(environment_path.read_text(encoding="utf-8"))
        for key in ("packages", "torch_cuda_runtime", "cuda_device_name"):
            if old.get(key) != environment.get(key):
                raise AssertionError(f"Q11 environment {key} changed during resume")
    else:
        write_json(environment_path, environment)
    if args.phase == "final" and not _freeze_selection(output, config):
        raise RuntimeError("All 36 source-only inner fits must freeze selection first")
    x, y, meta = _load_data(config, args.data_dir.resolve(), device, output)
    subjects = [args.target_subject] if args.target_subject else list(range(1, 10))
    try:
        for subject in subjects:
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
