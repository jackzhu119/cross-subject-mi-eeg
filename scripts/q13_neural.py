"""Q13 selection/source-identity/session sensitivity; fixed, source-only LOSO.

Prepared protocol: research_runs/Q13-PREP-20260926/PROTOCOL.md. This runner
does not modify frozen Q5/Q8/Q9 files. Completed fits are hash-checked on
resume; a failed fit is rerun from its fixed seed with its failure retained.
"""

from __future__ import annotations

import argparse
import hashlib
import json
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

from mi_eeg.models.eegnet_training import predict_probabilities
from scripts import q9_neural as q9
from scripts.run_eegnet import cpu_state, score_predictions, sha256_file, write_json

MATRIX = ROOT / "research_runs/Q13-PREP-20260926/MATRIX.json"
Q8_CONFIG = ROOT / "research_runs/Q8-E001/results/config.json"
Q5_CONFIG = ROOT / "results/Q5-E001/config.json"
Q5_SELECTION = ROOT / "results/Q5-E001/selection.csv"
Q9_INNER = ROOT / "results/Q9-E001/MU_BETA_SHARED/inner"
Q9_STATUS = ROOT / "results/Q9-E001/MU_BETA_SHARED/status.json"
SEEDS = (20260924, 20260925, 20260926)
SUBJECTS = tuple(range(1, 10))
SESSIONS = ("0train", "1test")
FIT_FILES = ("checkpoint.pt", "learning_curve.csv", "fit_manifest.csv",
             "predictions.csv", "metrics.csv", "confusion.csv")


def declared_conditions() -> dict[str, tuple[str, str, int | None, str | None]]:
    """Map condition to (experiment, model, k, source session)."""
    rows = {
        "Q8_FIXED20": ("Q13-E001", "Q8_BROAD", None, None),
        "Q9_SHARED_RAW_CE": ("Q13-E001", "Q9_MU_BETA_SHARED", None, None),
        "Q9_SHARED_FIXED20": ("Q13-E001", "Q9_MU_BETA_SHARED", None, None),
    }
    for prefix, model in (("Q8", "Q8_BROAD"), ("Q9_SHARED", "Q9_MU_BETA_SHARED")):
        for k in (2, 4, 6):
            rows[f"{prefix}_SRC{k}"] = ("Q13-E004", model, k, None)
        for suffix, session in (("T", "0train"), ("E", "1test")):
            rows[f"{prefix}_SOURCE_SESSION_{suffix}"] = (
                "Q13-E005", model, None, session)
    return rows


CONDITIONS = declared_conditions()


def source_windows(target: int, k: int) -> list[tuple[int, tuple[int, ...]]]:
    if target not in SUBJECTS or k not in (2, 4, 6, 8):
        raise ValueError("Expected target 1..9 and k in 2,4,6,8")
    available = tuple(subject for subject in SUBJECTS if subject != target)
    if k == 8:
        return [(0, available)]
    windows = [(start, tuple(available[(start + offset) % 8] for offset in range(k)))
               for start in (0, 2, 4, 6)]
    counts = {subject: sum(subject in subset for _, subset in windows) for subject in available}
    if set(counts.values()) != {k // 2}:
        raise AssertionError("Source-identity exposure is not balanced")
    return windows


def raw_ce_epoch(curves: list[pd.DataFrame]) -> int:
    """Earliest epoch at minimum equal-fold mean raw CE, independent of target."""
    if len(curves) != 4:
        raise AssertionError("Expected four source-only inner curves")
    values = []
    for curve in curves:
        if curve.epoch.astype(int).tolist() != list(range(1, 41)):
            raise AssertionError("Frozen inner curve must contain epochs 1..40")
        ce = curve.val_ce.to_numpy(float)
        if not np.isfinite(ce).all():
            raise AssertionError("Frozen inner CE is nonfinite")
        values.append(ce)
    means = np.mean(np.stack(values), axis=0)
    return int(np.flatnonzero(np.isclose(means, means.min(), atol=1e-12, rtol=0))[0] + 1)


def q9_source_only_epochs() -> tuple[dict[str, int], dict[str, str]]:
    status = json.loads(Q9_STATUS.read_text(encoding="utf-8"))
    if status.get("status") != "complete" or status.get("completed_inner_fits") != 36:
        raise AssertionError("Frozen Q9 36 source-only inner fits are not complete")
    chosen, hashes = {}, {}
    for target in SUBJECTS:
        curves = []
        for inner in (1, 2, 3, 4):
            directory = Q9_INNER / f"loso_s{target}" / f"inner_{inner}"
            if not frozen_q9_inner_complete(directory):
                raise AssertionError("Q9 source-only inner checkpoint missing")
            path = directory / "learning_curve.csv"
            curves.append(pd.read_csv(path))
            hashes[f"s{target}_inner{inner}"] = json.loads(
                (directory / "status.json").read_text(encoding="utf-8"))["sha256_learning_curve.csv"]
        chosen[str(target)] = raw_ce_epoch(curves)
    return chosen, hashes


def frozen_q9_inner_complete(directory: Path) -> bool:
    """Check frozen LF Git blobs against cloud receipts, even on CRLF Windows.

    This is for *read-only historical Q9 inputs* only. New Q13 fit receipts always
    require exact on-disk byte hashes for safe same-host resume.
    """
    path = directory / "status.json"
    if not path.is_file():
        return False
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("status") != "complete":
        return False
    for filename in ("checkpoint.pt", "learning_curve.csv", "fit_manifest.csv"):
        item = directory / filename
        if not item.is_file():
            raise AssertionError(f"Frozen Q9 file missing: {item}")
        expected = state.get(f"sha256_{filename}")
        if sha256_file(item) == expected:
            continue
        relative = item.relative_to(ROOT).as_posix()
        clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", relative],
                               cwd=ROOT, check=False)
        if clean.returncode:
            raise AssertionError(f"Frozen Q9 file edited: {relative}")
        original = subprocess.run(["git", "show", f"HEAD:{relative}"], cwd=ROOT,
                                  capture_output=True, check=False)
        if original.returncode or hashlib.sha256(original.stdout).hexdigest() != expected:
            raise AssertionError(f"Frozen Q9 Git blob disagrees with receipt: {relative}")
    return True


def _check_q5_reuse() -> dict[str, str]:
    """Require matching Q5/Q8 model and training contract before reusing 27 fits."""
    q5 = json.loads(Q5_CONFIG.read_text(encoding="utf-8"))
    q8 = json.loads(Q8_CONFIG.read_text(encoding="utf-8"))
    for key in ("subjects", "class_ids", "preprocessing", "input", "architecture"):
        if q5[key] != q8[key]:
            raise AssertionError(f"Q5/Q8 {key} mismatch blocks raw-CE reuse")
    for key in ("selection_seed", "final_seeds", "batch_size", "max_epochs", "optimizer",
                "learning_rate", "weight_decay", "loss", "scheduler", "augmentation"):
        if q5["training"][key] != q8["training"][key]:
            raise AssertionError(f"Q5/Q8 training {key} mismatch blocks reuse")
    selection = pd.read_csv(Q5_SELECTION)
    if sorted(selection.fold.tolist()) != [f"loso_s{i}" for i in SUBJECTS]:
        raise AssertionError("Q5 source-only raw-CE selection folds missing")
    validation_path = ROOT / "results/Q5-E001/validation_report.json"
    if not validation_path.exists() or json.loads(validation_path.read_text(
            encoding="utf-8")).get("status") != "passed":
        raise AssertionError("Q5 independent validation has not passed")
    return {"q5_config_sha256": sha256_file(Q5_CONFIG),
            "q5_selection_sha256": sha256_file(Q5_SELECTION),
            "q5_validation_sha256": sha256_file(validation_path)}


def locked_config(condition: str, data_dir: Path, output: Path) -> dict:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    experiment, method, k, session = CONDITIONS[condition]
    if matrix["total_new_deep_fits"] != 837 or matrix["final_seeds"] != list(SEEDS):
        raise AssertionError("Q13 matrix fit/seed contract changed")
    methods = matrix["methods"]
    q8 = json.loads(Q8_CONFIG.read_text(encoding="utf-8"))
    if q8["subjects"] != list(SUBJECTS) or q8["training"]["max_epochs"] != 40:
        raise AssertionError("Frozen Q8 population/epoch cap changed")
    if q8["training"]["final_seeds"] != list(SEEDS):
        raise AssertionError("Frozen Q8 seeds changed")
    pre = dict(q8["preprocessing"])
    pre["bands"] = methods[method]["bands"]
    train = {key: value for key, value in q8["training"].items()
             if key not in {"device", "inner_curve_source", "inner_fits_retrained", "epoch_selection"}}
    provenance = _check_q5_reuse()
    chosen = {str(s): 20 for s in SUBJECTS}
    if condition == "Q9_SHARED_RAW_CE":
        chosen, inner_hashes = q9_source_only_epochs()
        provenance["q9_inner_curve_sha256"] = inner_hashes
    config = {
        "experiment_id": experiment, "condition": condition, "method": method,
        "source_count": k, "source_session": session,
        "selected_epochs_by_target": chosen,
        "source_only_selection_provenance": provenance,
        "preprocessing": pre, "bands": methods[method]["bands"],
        "shared_mean_logits": methods[method]["shared_mean_logits"],
        "architecture": q8["architecture"], "training": train,
        "input": q8["input"], "subjects": q8["subjects"], "class_ids": q8["class_ids"],
        "source_fit_per_band_channel_zscore": False,
        "target_fit_or_selection": False, "data_dir": str(data_dir.resolve()),
        "q8_config_sha256": sha256_file(Q8_CONFIG),
        "matrix_sha256": sha256_file(MATRIX), "runner_sha256": sha256_file(Path(__file__)),
    }
    path = output / "run_config.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != config:
            raise AssertionError("Q13 run config changed during resume")
    else:
        write_json(path, config)
    return config


def assert_pretarget_git_freeze() -> str:
    files = ["research_runs/Q13-PREP-20260926/MATRIX.json",
             "research_runs/Q13-PREP-20260926/PROTOCOL.md",
             "scripts/q13_neural.py", "scripts/q13_batch.py", "scripts/validate_q13.py",
             "tests/test_q13.py", "scripts/q9_neural.py",
             "src/mi_eeg/data/bnci_epochs.py"]
    for command in (("ls-files", "--error-unmatch", "--", *files),
                    ("diff", "--quiet", "--", *files),
                    ("diff", "--cached", "--quiet", "--", *files)):
        result = subprocess.run(["git", *command], cwd=ROOT, capture_output=True,
                                text=True, check=False)
        if result.returncode:
            raise RuntimeError("Q13 code/protocol not committed unchanged; target inference blocked")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def fit_specs(condition: str, target: int) -> list[tuple[str, tuple[int, ...], str | None]]:
    _, _, k, session = CONDITIONS[condition]
    if k is None:
        return [("all", tuple(s for s in SUBJECTS if s != target), session)]
    return [(f"k{k}_start{start}", subset, None) for start, subset in source_windows(target, k)]


def _fit_dir(output: Path, target: int, subset_id: str, seed: int) -> Path:
    return output / "final" / f"loso_s{target}" / subset_id / f"seed_{seed}"


def fit_indices(meta: pd.DataFrame, target: int, source: tuple[int, ...],
                source_session: str | None) -> tuple[np.ndarray, np.ndarray]:
    if target in source or not source or not set(source).issubset(set(SUBJECTS)):
        raise AssertionError("Target contaminates source subset")
    chosen = meta.subject.isin(source).to_numpy().copy()
    if source_session is not None:
        if source_session not in SESSIONS:
            raise AssertionError("Unknown source session")
        chosen &= meta.session.eq(source_session).to_numpy()
    train = np.flatnonzero(chosen)
    test = np.flatnonzero(meta.subject.eq(target).to_numpy())
    expected = len(source) * (288 if source_session else 576)
    if len(train) != expected or len(test) != 576 or np.intersect1d(train, test).size:
        raise AssertionError("Unexpected source/target trial partition")
    return train, test


def fit_manifest(meta: pd.DataFrame, target: int, source: tuple[int, ...],
                 source_session: str | None, seed: int, train: np.ndarray,
                 epochs: int) -> pd.DataFrame:
    train_ids = set(np.asarray(train, dtype=int).tolist())
    rows = []
    for subject in SUBJECTS:
        for session in SESSIONS:
            ids = set(np.flatnonzero((meta.subject.eq(subject) & meta.session.eq(session)).to_numpy()).tolist())
            role = ("target_test" if subject == target else
                    "source_fit" if subject in source and (source_session is None or source_session == session)
                    else "source_excluded")
            used = len(ids & train_ids)
            if used != (len(ids) if role == "source_fit" else 0):
                raise AssertionError("Manifest and actual fit rows disagree")
            rows.append({"target_subject": target, "subject": subject, "session": session,
                         "role": role, "n_trials": len(ids), "n_used_for_fit": used,
                         "seed": seed, "epochs_trained": epochs})
    if sum(row["n_used_for_fit"] for row in rows) != len(train):
        raise AssertionError("Manifest does not reconcile with train count")
    return pd.DataFrame(rows)


def _run_fit(output: Path, config: dict, meta: pd.DataFrame, x: torch.Tensor,
             y: torch.Tensor, target: int, subset_id: str, source: tuple[int, ...],
             source_session: str | None, seed: int, device: torch.device) -> None:
    directory = _fit_dir(output, target, subset_id, seed)
    selected = int(config["selected_epochs_by_target"][str(target)])
    if not 1 <= selected <= 40:
        raise AssertionError("Epoch selection is outside frozen search range")
    if q9._fit_complete(directory, FIT_FILES):
        state = json.loads((directory / "status.json").read_text(encoding="utf-8"))
        for key, value in (("selected_epochs", selected), ("train_subjects", list(source)),
                           ("source_session", source_session), ("seed", seed)):
            if state.get(key) != value:
                raise AssertionError(f"Completed Q13 fit {key} differs from run plan")
        return
    train, test = fit_indices(meta, target, source, source_session)
    info = {"experiment_id": config["experiment_id"], "condition": config["condition"],
            "target_subject": target, "fold": f"loso_s{target}", "subset_id": subset_id,
            "source_count": len(source), "train_subjects": list(source),
            "source_session": source_session, "seed": seed,
            "selected_epochs": selected, "n_train": len(train), "n_test": len(test),
            "run_config_sha256": sha256_file(output / "run_config.json")}
    directory.mkdir(parents=True, exist_ok=True)
    write_json(directory / "status.json", {**info, "status": "running", "started_at_utc": q9.now_utc()})
    started = time.perf_counter()
    try:
        model, curves = q9._fit(x, y, train, None, seed, selected, config, device)
        probabilities = predict_probabilities(model, x, test, config["training"]["batch_size"])
        if probabilities.shape != (576, 4) or not np.isfinite(probabilities).all():
            raise AssertionError("Invalid target probabilities")
        part = meta.iloc[test].copy().reset_index(drop=True)
        part["experiment_id"] = config["experiment_id"]
        part["condition"] = config["condition"]
        part["fold"] = f"loso_s{target}"
        part["subset_id"] = subset_id
        part["train_subjects"] = "|".join(str(s) for s in source)
        part["source_session"] = source_session if source_session else "both"
        part["seed"] = seed
        part["selected_epochs"] = selected
        part["y_true"] = part.label.astype(int)
        part["y_pred"] = probabilities.argmax(axis=1).astype(int) + 1
        for cls in range(4):
            part[f"p_class_{cls + 1}"] = probabilities[:, cls]
        metrics, confusion = score_predictions(part, [1, 2, 3, 4], f"loso_s{target}", seed,
                                               len(train))
        q9.atomic_csv(directory / "learning_curve.csv", pd.DataFrame(curves))
        q9.atomic_csv(directory / "fit_manifest.csv", fit_manifest(
            meta, target, source, source_session, seed, train, selected))
        q9.atomic_csv(directory / "predictions.csv", part)
        metric_frame = pd.DataFrame(metrics)
        metric_frame["condition"] = config["condition"]
        metric_frame["subset_id"] = subset_id
        q9.atomic_csv(directory / "metrics.csv", metric_frame)
        confusion_frame = pd.DataFrame(confusion)
        confusion_frame["condition"] = config["condition"]
        confusion_frame["subset_id"] = subset_id
        q9.atomic_csv(directory / "confusion.csv", confusion_frame)
        q9.atomic_checkpoint(directory / "checkpoint.pt", {**info, "model_state": cpu_state(model)})
        q9._mark_complete(directory, FIT_FILES, {**info,
                          "elapsed_seconds": time.perf_counter() - started,
                          "optimizer_updates": selected * ((len(train) + 63) // 64)})
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()
    except Exception:
        q9._record_failure(directory, {**info, "elapsed_seconds": time.perf_counter() - started})
        raise


def _aggregate(output: Path, config: dict) -> None:
    condition = config["condition"]
    complete = []
    for target in SUBJECTS:
        for subset_id, _, _ in fit_specs(condition, target):
            for seed in SEEDS:
                directory = _fit_dir(output, target, subset_id, seed)
                if q9._fit_complete(directory, FIT_FILES):
                    complete.append(directory)
    expected = 108 if config["experiment_id"] == "Q13-E004" else 27
    state = {"experiment_id": config["experiment_id"], "condition": condition,
             "status": "complete" if len(complete) == expected else "running",
             "completed_final_fits": len(complete), "expected_final_fits": expected,
             "completed_inner_fits": 0, "target_fits": 0, "updated_at_utc": q9.now_utc()}
    if complete:
        for source_file, aggregate_file in (("predictions.csv", "predictions.csv"),
                                            ("metrics.csv", "per_subject_metrics.csv"),
                                            ("confusion.csv", "confusion_matrices.csv"),
                                            ("fit_manifest.csv", "fit_manifest.csv")):
            q9.atomic_csv(output / aggregate_file, pd.concat(
                [pd.read_csv(directory / source_file) for directory in complete], ignore_index=True))
    write_json(output / "status.json", state)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", required=True, choices=tuple(CONDITIONS))
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--output-root", type=Path, default=ROOT / "results")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--target-subject", type=int, choices=SUBJECTS)
    args = parser.parse_args()
    assert_pretarget_git_freeze()
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable; no CPU fallback")
    device = torch.device(args.device)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    mne.set_log_level("ERROR")
    experiment = CONDITIONS[args.condition][0]
    output = args.output_root.resolve() / experiment / args.condition
    output.mkdir(parents=True, exist_ok=True)
    config = locked_config(args.condition, args.data_dir, output)
    environment = q9._versions()
    environment_path = output / "environment.json"
    if environment_path.exists():
        old = json.loads(environment_path.read_text(encoding="utf-8"))
        for key in ("packages", "torch_cuda_runtime", "cuda_device_name"):
            if old.get(key) != environment.get(key):
                raise AssertionError(f"Q13 resume environment {key} changed")
    else:
        write_json(environment_path, environment)
    x, y, meta, _ = q9._load_data(config, args.data_dir.resolve(), device, output)
    targets = (args.target_subject,) if args.target_subject else SUBJECTS
    try:
        for target in targets:
            for subset_id, source, session in fit_specs(args.condition, target):
                for seed in SEEDS:
                    _run_fit(output, config, meta, x, y, target, subset_id, source,
                             session, seed, device)
            _aggregate(output, config)
        _aggregate(output, config)
    except Exception:
        write_json(output / "last_failure.json", {"time_utc": q9.now_utc(),
                                                  "traceback": traceback.format_exc()})
        _aggregate(output, config)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
