"""Resumable BNCI-only binary source fits for Q14-E001 and Q14-E002.

No PhysioNet imports, paths, or data reads occur in this file. Q14-E002 emits
the all-source freeze receipt only after independent source validation passes.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import joblib
import numpy as np
import pandas as pd
from scipy.signal import resample_poly
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from mi_eeg.data.bnci_epochs import load_configured_epochs

CONFIG = ROOT / "research_runs/Q14-E001/CONFIG.json"
Q8_AUDIT = ROOT / "research_runs/Q8-E001/results/data_audit.csv"
Q8_SOURCE_FILES = ROOT / "research_runs/Q8-E001/results/source_files.json"
E001_ROOT = ROOT / "results/Q14-E001"
E002_ROOT = ROOT / "results/Q14-E002"
DEEP_MODELS = ("BROAD_EEGNET", "MU_BETA_SHARED")
ALL_MODELS = (*DEEP_MODELS, "CSP4_LDA")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha_ids(ids: np.ndarray) -> str:
    return hashlib.sha256("\n".join(map(str, ids)).encode("utf-8")).hexdigest()


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp, index=False)
    os.replace(tmp, path)


def read_config() -> dict:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config["channels"] != json.loads(pd.read_csv(Q8_AUDIT).iloc[0]["eeg_channel_names"]):
        raise AssertionError("Q14 channel order disagrees with frozen BNCI data audit")
    if config["source_subjects"] != list(range(1, 10)) or config["n_times"] != 480:
        raise AssertionError("Unexpected Q14 source contract")
    return config


def runtime_receipt() -> dict:
    import torch

    packages = (
        "torch",
        "torchaudio",
        "braindecode",
        "mne",
        "moabb",
        "numpy",
        "scipy",
        "scikit-learn",
    )
    versions = {}
    for package in packages:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "packages": versions,
        "torch_cuda_runtime": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }


def load_source(
    config: dict, data_dir: Path
) -> tuple[dict[str, np.ndarray], pd.DataFrame, pd.DataFrame]:
    pre = {
        "sampling_rate_hz": config["source_native_rate_hz"],
        "bands": config["bands_hz"],
        "filter": config["filter"],
        "trial_start_s": config["source_trial_start_s"],
        "trial_stop_exclusive_s": config["source_trial_stop_exclusive_s"],
        "artifact_policy": config["artifact_policy"],
        "baseline": None,
    }
    arrays, meta, audit = load_configured_epochs(
        config["source_subjects"], data_dir, pre, config["class_map"]
    )
    if len(meta) != 9 * 2 * 6 * 24 or meta["sample_id"].duplicated().any():
        raise AssertionError("Unexpected BNCI binary trial identity or count")
    if set(meta["label"]) != {1, 2} or set(meta["subject"]) != set(range(1, 10)):
        raise AssertionError("BNCI binary labels or subjects differ from contract")
    up, down = config["source_resample_up"], config["source_resample_down"]
    common = {}
    for band, values in arrays.items():
        resampled = resample_poly(values, up, down, axis=2).astype(np.float32)
        if resampled.shape != (len(meta), 22, config["n_times"]):
            raise AssertionError(f"Unexpected resampled {band} shape: {resampled.shape}")
        common[band] = np.ascontiguousarray(resampled * config["volts_to_microvolts"])
        if not np.isfinite(common[band]).all():
            raise AssertionError(f"Nonfinite BNCI {band} input")
    return common, meta.reset_index(drop=True), audit


def source_file_receipt(data_dir: Path) -> list[dict]:
    """Verify all 18 actual BNCI files against the frozen Q8 provenance."""
    expected = {
        Path(row["path"]).name: row
        for row in json.loads(Q8_SOURCE_FILES.read_text(encoding="utf-8"))
    }
    if len(expected) != 18:
        raise AssertionError("Frozen Q8 provenance does not have 18 unique MAT files")
    records = []
    for path in sorted(data_dir.rglob("*.mat")):
        if path.name in expected:
            item = {"filename": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
            if (
                item["bytes"] != expected[path.name]["bytes"]
                or item["sha256"] != expected[path.name]["sha256"]
            ):
                raise AssertionError(f"BNCI MAT differs from frozen Q8 provenance: {path.name}")
            records.append(item)
    if len(records) != 18 or len({r["filename"] for r in records}) != 18:
        raise AssertionError("Expected exactly 18 distinct local BNCI MAT files")
    return records


def partitions(stage: str, config: dict):
    subjects = config["source_subjects"]
    if stage == "e001":
        for target in subjects:
            source = [s for s in subjects if s != target]
            groups = [source[i : i + 2] for i in range(0, 8, 2)]
            yield f"target_{target:02d}", source, groups, [target]
    elif stage == "e002":
        groups = config["q14_e002_inner_groups"]
        if sorted(subject for group in groups for subject in group) != subjects:
            raise AssertionError("All-source inner groups do not partition BNCI subjects")
        yield "all_source", subjects, groups, []
    else:
        raise ValueError(stage)


def mean_rank_epoch(curves: dict[int, list[dict]], max_epochs: int) -> int:
    if set(curves) != {1, 2, 3, 4}:
        raise AssertionError("Exactly four source-only inner curves required")
    ranks = []
    for fold in (1, 2, 3, 4):
        rows = curves[fold]
        if [row["epoch"] for row in rows] != list(range(1, max_epochs + 1)):
            raise AssertionError("Missing or reordered selection epochs")
        ce = np.asarray([row["val_ce"] for row in rows], dtype=float)
        if not np.isfinite(ce).all():
            raise AssertionError("Nonfinite source validation CE")
        ranks.append(pd.Series(ce).rank(method="average").to_numpy())
    return int(np.argmin(np.mean(ranks, axis=0)) + 1)


def _build_model(name: str, config: dict, device):
    from mi_eeg.models.eegnet_training import build_eegnet

    if name == "BROAD_EEGNET":
        return build_eegnet(config["architecture"], device)
    if name != "MU_BETA_SHARED":
        raise ValueError(name)
    import torch

    class SharedBandEEGNet(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.eegnet = build_eegnet(config["architecture"], device)

        def forward(self, x):
            if x.ndim != 4 or x.shape[1:] != (2, 22, 480):
                raise ValueError(f"Expected [batch,2,22,480], got {tuple(x.shape)}")
            n = x.shape[0]
            return self.eegnet(x.reshape(n * 2, 22, 480)).reshape(n, 2, 2).mean(1)

    return SharedBandEEGNet().to(device)


def deep_input(name: str, arrays: dict[str, np.ndarray]):
    import torch

    if name == "BROAD_EEGNET":
        return torch.from_numpy(arrays["broad"])
    return torch.from_numpy(np.stack([arrays["mu"], arrays["beta"]], axis=1))


def _fit_deep(name, x, y, train_idx, val_idx, seed, epochs, config, device):
    import torch

    from mi_eeg.models.eegnet_training import (
        evaluate_cross_entropy,
        seed_everything,
        train_one_epoch,
    )

    seed_everything(seed, deterministic=True)
    model = _build_model(name, config, device)
    optimizer = torch.optim.Adam(
        model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"]
    )
    train = torch.as_tensor(train_idx, device=device, dtype=torch.long)
    val = None if val_idx is None else torch.as_tensor(val_idx, device=device, dtype=torch.long)
    rows = []
    for epoch in range(1, epochs + 1):
        train_ce = train_one_epoch(model, optimizer, x, y, train, config["batch_size"])
        val_ce = (
            None if val is None else evaluate_cross_entropy(model, x, y, val, config["batch_size"])
        )
        if not np.isfinite(train_ce) or (val_ce is not None and not np.isfinite(val_ce)):
            raise AssertionError("Nonfinite training or source validation CE")
        rows.append({"epoch": epoch, "train_ce": train_ce, "val_ce": val_ce})
    return model, rows


def _save_fit(path, model, curve, payload):
    import torch

    path.mkdir(parents=True, exist_ok=True)
    checkpoint = path / "checkpoint.pt"
    tmp = path / "checkpoint.pt.tmp"
    torch.save(
        {
            "state_dict": {k: v.detach().cpu() for k, v in model.state_dict().items()},
            "model": payload["model"],
            "seed": payload["seed"],
            "epochs": payload["epochs"],
        },
        tmp,
    )
    os.replace(tmp, checkpoint)
    atomic_json(path / "curve.json", {"epochs": curve})
    atomic_json(
        path / "manifest.json",
        {
            **payload,
            "checkpoint_sha256": sha256(checkpoint),
            "curve_sha256": sha256(path / "curve.json"),
            "status": "complete",
        },
    )


def _verify_fit(path: Path, required: dict) -> list[dict] | None:
    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        return None
    record = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key, value in required.items():
        if record.get(key) != value:
            raise AssertionError(f"Existing fit protocol mismatch: {path}: {key}")
    for file, field in (
        (path / "checkpoint.pt", "checkpoint_sha256"),
        (path / "curve.json", "curve_sha256"),
    ):
        if not file.exists() or sha256(file) != record.get(field):
            raise AssertionError(f"Existing Q14 fit corrupted: {file}")
    if record.get("status") != "complete":
        raise AssertionError(f"Existing Q14 fit not complete: {path}")
    return json.loads((path / "curve.json").read_text(encoding="utf-8"))["epochs"]


def _load_model(path: Path, name: str, config: dict, device):
    import torch

    payload = torch.load(path, map_location=device, weights_only=True)
    if payload["model"] != name:
        raise AssertionError("Checkpoint model identity mismatch")
    model = _build_model(name, config, device)
    model.load_state_dict(payload["state_dict"], strict=True)
    model.eval()
    return model


def _csp_pipeline():
    from mne.decoding import CSP

    return Pipeline(
        [
            (
                "csp",
                CSP(
                    n_components=4,
                    reg=None,
                    log=True,
                    cov_est="concat",
                    norm_trace=False,
                    rank="full",
                    component_order="mutual_info",
                ),
            ),
            ("scaler", StandardScaler()),
            ("lda", LinearDiscriminantAnalysis(solver="svd")),
        ]
    )


def _csp_fit(path: Path, arrays, meta, source, config):
    train = np.flatnonzero(meta["subject"].isin(source).to_numpy())
    required = {
        "model": "CSP4_LDA",
        "train_subjects": source,
        "train_sample_ids_sha256": sha_ids(meta.iloc[train]["sample_id"].to_numpy()),
        "config_sha256": sha256(CONFIG),
    }
    manifest_path = path / "manifest.json"
    model_file = path / "model.joblib"
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            old.get("status") != "complete"
            or not model_file.exists()
            or any(old.get(key) != value for key, value in required.items())
            or sha256(model_file) != old["model_sha256"]
        ):
            raise AssertionError("Existing CSP fit differs or is corrupted")
        return joblib.load(model_file)
    pipeline = _csp_pipeline()
    pipeline.fit(arrays["broad"][train].astype(np.float64), meta.iloc[train]["label"].to_numpy())
    path.mkdir(parents=True, exist_ok=True)
    tmp = path / "model.joblib.tmp"
    joblib.dump(pipeline, tmp)
    os.replace(tmp, model_file)
    atomic_json(
        manifest_path,
        {
            **required,
            "status": "complete",
            "model_sha256": sha256(model_file),
            "n_source_trials": len(train),
        },
    )
    return pipeline


def _prediction_frame(meta, idx, model_name, seed, probabilities, stage):
    if probabilities.shape != (len(idx), 2) or not np.isfinite(probabilities).all():
        raise AssertionError("Invalid binary prediction probabilities")
    if not np.allclose(probabilities.sum(1), 1, atol=1e-5):
        raise AssertionError("Probabilities do not sum to one")
    frame = meta.iloc[idx][
        ["sample_id", "subject", "session", "run", "trial", "label", "artifact_flagged"]
    ].copy()
    frame["experiment_id"] = "Q14-E001" if stage == "e001" else "Q14-E002"
    frame["model"] = model_name
    frame["seed"] = seed
    frame["p_left"] = probabilities[:, 0]
    frame["p_right"] = probabilities[:, 1]
    frame["predicted_label"] = np.argmax(probabilities, axis=1) + 1
    return frame


def run_stage(stage: str, data_dir: Path, device_name: str) -> None:
    import torch

    from mi_eeg.models.eegnet_training import predict_probabilities

    config = read_config()
    root = E001_ROOT if stage == "e001" else E002_ROOT / "source"
    if stage == "e002":
        report = E001_ROOT / "validation_report.json"
        old = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
        if (
            not old.get("passed")
            or old.get("config_sha256") != sha256(CONFIG)
            or old.get("source_runner_sha256") != sha256(Path(__file__))
        ):
            raise AssertionError("Q14-E001 independent source validation must pass before Q14-E002")
    root.mkdir(parents=True, exist_ok=True)
    # Lock the exact protocol before any source arrays are loaded.
    run_config = {
        "stage": stage,
        "config_sha256": sha256(CONFIG),
        "runner_sha256": sha256(Path(__file__)),
        "data_dir": str(data_dir.resolve()),
        "device": device_name,
        "runtime": runtime_receipt(),
    }
    existing = root / "run_config.json"
    if existing.exists() and json.loads(existing.read_text(encoding="utf-8")) != run_config:
        raise AssertionError("Existing Q14 run_config mismatch")
    atomic_json(existing, run_config)
    arrays, meta, audit = load_source(config, data_dir)
    atomic_json(root / "source_files.json", {"files": source_file_receipt(data_dir)})
    atomic_csv(root / "source_metadata.csv", meta)
    atomic_csv(root / "source_audit.csv", audit)
    device = torch.device(device_name)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    y = torch.as_tensor(meta["label"].to_numpy() - 1, dtype=torch.long, device=device)
    if device.type == "cpu":
        torch.set_num_threads(min(4, torch.get_num_threads()))
    for model_name in DEEP_MODELS:
        x = deep_input(model_name, arrays).to(device)
        for label, source, groups, targets in partitions(stage, config):
            base = root / model_name / label
            curves = {}
            for fold, validation_subjects in enumerate(groups, 1):
                train_subjects = [s for s in source if s not in validation_subjects]
                if set(train_subjects) & set(validation_subjects) or set(train_subjects) & set(
                    targets
                ):
                    raise AssertionError("Source-only inner split violated")
                train = np.flatnonzero(meta["subject"].isin(train_subjects).to_numpy())
                val = np.flatnonzero(meta["subject"].isin(validation_subjects).to_numpy())
                job = base / f"inner_{fold:02d}"
                required = {
                    "stage": stage,
                    "model": model_name,
                    "outer": label,
                    "inner_fold": fold,
                    "train_subjects": train_subjects,
                    "validation_subjects": validation_subjects,
                    "target_subjects": targets,
                    "train_sample_ids_sha256": sha_ids(meta.iloc[train]["sample_id"].to_numpy()),
                    "seed": config["selection_seed"],
                    "epochs": config["max_epochs"],
                    "config_sha256": sha256(CONFIG),
                }
                curve = _verify_fit(job, required)
                if curve is None:
                    model, curve = _fit_deep(
                        model_name,
                        x,
                        y,
                        train,
                        val,
                        config["selection_seed"],
                        config["max_epochs"],
                        config,
                        device,
                    )
                    _save_fit(job, model, curve, required)
                    del model
                curves[fold] = curve
            selected = mean_rank_epoch(curves, config["max_epochs"])
            selection = {
                "stage": stage,
                "model": model_name,
                "outer": label,
                "source_subjects": source,
                "validation_groups": groups,
                "selected_epoch": selected,
                "selection_rule": config["source_only_epoch_rule"],
                "inner_curve_sha256": [
                    sha256(base / f"inner_{fold:02d}" / "curve.json") for fold in range(1, 5)
                ],
            }
            select_path = base / "selection.json"
            if (
                select_path.exists()
                and json.loads(select_path.read_text(encoding="utf-8")) != selection
            ):
                raise AssertionError("Existing source-only selection changed")
            atomic_json(select_path, selection)
            train = np.flatnonzero(meta["subject"].isin(source).to_numpy())
            eval_idx = np.flatnonzero(meta["subject"].isin(targets).to_numpy()) if targets else None
            for seed in config["final_seeds"]:
                job = base / f"final_seed_{seed}"
                required = {
                    "stage": stage,
                    "model": model_name,
                    "outer": label,
                    "train_subjects": source,
                    "target_subjects": targets,
                    "train_sample_ids_sha256": sha_ids(meta.iloc[train]["sample_id"].to_numpy()),
                    "seed": seed,
                    "epochs": selected,
                    "config_sha256": sha256(CONFIG),
                }
                if _verify_fit(job, required) is None:
                    model, curve = _fit_deep(
                        model_name, x, y, train, None, seed, selected, config, device
                    )
                    _save_fit(job, model, curve, required)
                    del model
                if targets:
                    prediction_file = job / "predictions.csv"
                    if not prediction_file.exists():
                        model = _load_model(job / "checkpoint.pt", model_name, config, device)
                        probabilities = predict_probabilities(
                            model, x, eval_idx, config["batch_size"]
                        )
                        atomic_csv(
                            prediction_file,
                            _prediction_frame(
                                meta, eval_idx, model_name, seed, probabilities, stage
                            ),
                        )
                        del model
                    else:
                        pred = pd.read_csv(prediction_file)
                        if pred["sample_id"].tolist() != meta.iloc[eval_idx]["sample_id"].tolist():
                            raise AssertionError(
                                "Existing prediction IDs differ from held-out target"
                            )
        del x
        if device.type == "cuda":
            torch.cuda.empty_cache()
    for label, source, _groups, targets in partitions(stage, config):
        base = root / "CSP4_LDA" / label
        model = _csp_fit(base, arrays, meta, source, config)
        if targets:
            prediction_file = base / "predictions.csv"
            eval_idx = np.flatnonzero(meta["subject"].isin(targets).to_numpy())
            if not prediction_file.exists():
                probabilities = model.predict_proba(arrays["broad"][eval_idx].astype(np.float64))
                atomic_csv(
                    prediction_file,
                    _prediction_frame(
                        meta, eval_idx, "CSP4_LDA", "deterministic", probabilities, stage
                    ),
                )
    atomic_json(
        root / "source_stage_complete.json",
        {
            "stage": stage,
            "status": "all_fits_attempted",
            "config_sha256": sha256(CONFIG),
            "completed_at_utc": datetime.now(UTC).isoformat(),
            "deep_fit_count": (126 if stage == "e001" else 14),
            "shallow_fit_count": (9 if stage == "e001" else 1),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["e001", "e002"], required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    args = parser.parse_args()
    run_stage(args.phase, args.data_dir, args.device)


if __name__ == "__main__":
    main()
