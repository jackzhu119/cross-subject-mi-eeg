"""Q15-E005 BNCI-only 21-channel source training, fail-closed by default.

This is a new model, not an alteration of frozen Q14 checkpoints. The default
invocation is read-only dry-run. Source fitting requires two independently
verified, real raw-file metadata audits *and* a committed pre-fit freeze
receipt. No external EEG or target labels are loaded here.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import joblib
import numpy as np
from scipy.signal import resample_poly

from scripts import q14_source

CONTRACT = ROOT / "research_runs/PAPER_RELEASE_20260927/Q15_CONTRACT.json"
CONTRACT_CHECKER = CONTRACT.with_name("q15_validate_contract.py")
METADATA_AUDITOR = ROOT / "scripts/q15_metadata_audit.py"
Q14_CONFIG = ROOT / "research_runs/Q14-E001/CONFIG.json"
Q8_SOURCE_PROVENANCE = ROOT / "research_runs/Q8-E001/results/source_files.json"
DEPENDENCY_SPEC = ROOT / "requirements-paper-cu128.txt"
BNCI_LOADER = ROOT / "src/mi_eeg/data/bnci_epochs.py"
EEGNET_HELPER = ROOT / "src/mi_eeg/models/eegnet_training.py"
AUDIT_RECEIPTS = {
    "Lee2019_MI": ROOT / "results/Q15-V001/metadata_audit_receipt.json",
    "Cho2017": ROOT / "results/Q15-V002/metadata_audit_receipt.json",
}
OUTPUT = ROOT / "results/Q15-E005"
FREEZE = OUTPUT / "pre_fit_freeze.json"
MODELS = ("BROAD_EEGNET", "MU_BETA_SHARED")
SOURCE_SCRIPT = Path(__file__).resolve()


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected a JSON object: {path}")
    return value


def _sha(path: Path) -> str:
    return q14_source.sha256(path)


def _git_bytes(path: Path) -> bytes:
    """Return committed HEAD bytes, not the mutable working-tree file."""
    relative = path.resolve().relative_to(ROOT).as_posix()
    result = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return result.stdout


def _assert_committed_unchanged(path: Path) -> None:
    if not path.is_file() or _git_bytes(path) != path.read_bytes():
        raise AssertionError(f"Pre-fit freeze input is uncommitted or modified: {path}")


def _contract_checker():
    spec = importlib.util.spec_from_file_location("q15_validate_contract", CONTRACT_CHECKER)
    if spec is None or spec.loader is None:
        raise AssertionError("Q15 contract checker unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metadata_auditor():
    spec = importlib.util.spec_from_file_location("q15_metadata_audit", METADATA_AUDITOR)
    if spec is None or spec.loader is None:
        raise AssertionError("Q15 raw metadata auditor unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derive_config() -> dict:
    """Pin every Q14 setting except the predeclared input channel/time shape."""
    _contract_checker().validate_contract()
    plan = _json(CONTRACT)["new_source_arm"]
    config = copy.deepcopy(_json(Q14_CONFIG))
    if config["source_trial_start_s"] - config["cue_relative_start_s"] != 2.0:
        raise AssertionError("BNCI cue origin changed")
    config["channels"] = plan["channels"]
    config["cue_relative_start_s"], config["cue_relative_stop_exclusive_s"] = plan[
        "cue_window_s_half_open"
    ]
    config["source_trial_start_s"] = 2.0 + config["cue_relative_start_s"]
    config["source_trial_stop_exclusive_s"] = 2.0 + config["cue_relative_stop_exclusive_s"]
    config["n_times"] = plan["n_times"]
    config["architecture"].update(plan["architecture_changes_from_q14"])
    config["q14_e002_inner_groups"] = plan["source_only_inner_groups"]
    if config["source_trial_start_s"] != 2.5 or config["source_trial_stop_exclusive_s"] != 4.5:
        raise AssertionError("Unexpected Q15 BNCI window")
    if config["channels"] != [c for c in _json(Q14_CONFIG)["channels"] if c != "FCz"]:
        raise AssertionError("Unexpected Q15 channel rule")
    if config["architecture"]["n_chans"] != 21 or config["n_times"] != 320:
        raise AssertionError("Unexpected Q15 model input dimensions")
    return config


def _replay_metadata_receipt(dataset: str, path: Path, channels: list[str]) -> dict:
    """A structural and byte-level gate, never a raw-EEG scientific validator."""
    receipt = _json(path)
    if receipt.get("schema_version") != 1 or receipt.get("dataset") != dataset:
        raise AssertionError(f"Q15 {dataset} receipt identity mismatch")
    if receipt.get("status") != "metadata_passed_non_authorizing":
        raise AssertionError(f"Q15 {dataset} raw audit has not passed")
    required_true = (
        "metadata_only", "raw_hashes_verified", "provider_inventory_verified",
        "provider_manifest_authenticated", "all_expected_files_hashed",
    )
    if any(receipt.get(k) is not True for k in required_true):
        raise AssertionError(f"Q15 {dataset} raw provenance is not established")
    if any(receipt.get(k) is not False for k in (
        "predictions_computed", "model_predictions_computed", "performance_metrics_computed",
        "external_prediction_authorized", "source_training_authorized", "synthetic_fixture",
    )):
        raise AssertionError(f"Q15 {dataset} receipt is synthetic or outcome-contaminated")
    if receipt.get("target_fits") != 0:
        raise AssertionError("Target fit is forbidden")
    if receipt.get("auditor_sha256") != _sha(METADATA_AUDITOR):
        raise AssertionError("Metadata auditor code differs from the receipt")
    if not isinstance(receipt.get("provider_manifest_sha256"), str) or len(receipt["provider_manifest_sha256"]) != 64:
        raise AssertionError("Provider inventory digest missing")
    manifest_path = Path(receipt.get("provider_manifest_path") or "")
    if not manifest_path.is_absolute() or not manifest_path.is_file():
        raise AssertionError("Provider inventory file unavailable")
    if _sha(manifest_path) != receipt["provider_manifest_sha256"]:
        raise AssertionError("Provider inventory file changed after metadata audit")
    reproduced = _metadata_auditor().audit_manifest(manifest_path, synthetic_fixture=False)
    if reproduced != receipt:
        raise AssertionError("Metadata receipt cannot be reproduced from raw files")
    files = receipt.get("files")
    if not isinstance(files, list) or not files:
        raise AssertionError("No raw-file audit inventory")
    expected_ids = receipt.get("expected_file_ids")
    if not isinstance(expected_ids, list) or len(expected_ids) != len(files):
        raise AssertionError("Raw-file inventory incomplete")
    if len(set(expected_ids)) != len(files) or {row.get("file_id") for row in files} != set(expected_ids):
        raise AssertionError("Raw-file IDs are missing or duplicated")
    for row in files:
        raw_path = Path(row["path"])
        if not raw_path.is_absolute() or not raw_path.is_file():
            raise AssertionError(f"Audited raw file unavailable: {raw_path}")
        if _sha(raw_path) != row.get("sha256"):
            raise AssertionError(f"Audited raw file changed: {raw_path}")
        if not set(channels).issubset(row.get("channels", [])):
            raise AssertionError(f"Q15 required channel absent: {raw_path}")
    cohort_spec = next(item for item in _json(CONTRACT)["metadata_audits"] if item["dataset"] == dataset)
    _contract_checker().validate_metadata_receipt(receipt, cohort_spec, channels)
    return receipt


def preflight_metadata() -> dict[str, dict]:
    config = derive_config()
    return {
        dataset: _replay_metadata_receipt(dataset, path, config["channels"])
        for dataset, path in AUDIT_RECEIPTS.items()
    }


def _freeze_payload(receipts: dict[str, dict]) -> dict:
    return {
        "schema_version": 1,
        "experiment_id": "Q15-E005",
        "status": "pre_fit_frozen_pending_commit",
        "external_outcomes_inspected": False,
        "source_only": True,
        "target_fits": 0,
        "contract_sha256": _sha(CONTRACT),
        "contract_checker_sha256": _sha(CONTRACT_CHECKER),
        "q14_config_sha256": _sha(Q14_CONFIG),
        "q8_bnci_source_provenance_sha256": _sha(Q8_SOURCE_PROVENANCE),
        "dependency_spec_sha256": _sha(DEPENDENCY_SPEC),
        "bnci_loader_sha256": _sha(BNCI_LOADER),
        "eegnet_training_helper_sha256": _sha(EEGNET_HELPER),
        "metadata_auditor_sha256": _sha(METADATA_AUDITOR),
        "runner_sha256": _sha(SOURCE_SCRIPT),
        "q14_source_helper_sha256": _sha(Path(q14_source.__file__)),
        "metadata_receipt_sha256": {
            dataset: _sha(AUDIT_RECEIPTS[dataset]) for dataset in sorted(receipts)
        },
        "metadata_receipt_status": {
            dataset: receipts[dataset]["status"] for dataset in sorted(receipts)
        },
        "allowed_fits": {"deep": 14, "shallow": 1, "external_target": 0},
    }


def prepare_freeze() -> Path:
    """Prepare a receipt; a separate reviewed Git commit is still required."""
    receipts = preflight_metadata()
    payload = _freeze_payload(receipts)
    for path in (CONTRACT, CONTRACT_CHECKER, Q14_CONFIG, Q8_SOURCE_PROVENANCE, DEPENDENCY_SPEC, BNCI_LOADER, EEGNET_HELPER, METADATA_AUDITOR, SOURCE_SCRIPT, Path(q14_source.__file__), *AUDIT_RECEIPTS.values()):
        _assert_committed_unchanged(path)
    if FREEZE.exists() and _json(FREEZE) != payload:
        raise AssertionError("Existing Q15 pre-fit freeze differs")
    q14_source.atomic_json(FREEZE, payload)
    return FREEZE


def _verify_committed_freeze() -> dict:
    receipts = preflight_metadata()
    if not FREEZE.is_file():
        raise AssertionError("Q15 pre-fit freeze missing; no source fit allowed")
    recorded = _json(FREEZE)
    if recorded != _freeze_payload(receipts):
        raise AssertionError("Q15 pre-fit freeze no longer matches audited inputs")
    for path in (CONTRACT, CONTRACT_CHECKER, Q14_CONFIG, Q8_SOURCE_PROVENANCE, DEPENDENCY_SPEC, BNCI_LOADER, EEGNET_HELPER, METADATA_AUDITOR, SOURCE_SCRIPT, Path(q14_source.__file__), FREEZE, *AUDIT_RECEIPTS.values()):
        _assert_committed_unchanged(path)
    return recorded


def load_source(config: dict, data_dir: Path):
    """Filter at native 250 Hz, epoch 2 s, then remove FCz and resample."""
    preprocessing = {
        "sampling_rate_hz": 250,
        "bands": config["bands_hz"],
        "filter": config["filter"],
        "trial_start_s": config["source_trial_start_s"],
        "trial_stop_exclusive_s": config["source_trial_stop_exclusive_s"],
        "artifact_policy": config["artifact_policy"],
        "baseline": None,
    }
    arrays, meta, audit = q14_source.load_configured_epochs(
        config["source_subjects"], data_dir, preprocessing, config["class_map"]
    )
    ordered = json.loads(audit.iloc[0]["eeg_channel_names"])
    if any(json.loads(row) != ordered for row in audit["eeg_channel_names"]):
        raise AssertionError("BNCI channel order drifted across runs")
    if ordered != _json(Q14_CONFIG)["channels"]:
        raise AssertionError("BNCI full channel order differs from Q14 audit")
    indices = [ordered.index(name) for name in config["channels"]]
    if indices != [i for i, name in enumerate(ordered) if name != "FCz"]:
        raise AssertionError("Q15 selected more than the declared channel removal")
    expected_trials = 9 * 2 * 6 * 24
    if len(meta) != expected_trials or meta["sample_id"].duplicated().any():
        raise AssertionError("Unexpected BNCI binary trial identity/count")
    if set(meta["subject"]) != set(range(1, 10)) or set(meta["label"]) != {1, 2}:
        raise AssertionError("Unexpected BNCI subjects or binary labels")
    common = transform_bands(arrays, indices, config, expected_trials)
    return common, meta.reset_index(drop=True), audit


def transform_bands(arrays: dict, indices: list[int], config: dict, n_trials: int) -> dict:
    """Testable fixed source spatial selection and 250-to-160 Hz resampling."""
    if indices != [index for index in range(22) if index != 3]:
        raise AssertionError("Q15 may remove FCz only")
    common = {}
    for band, values in arrays.items():
        if values.shape != (n_trials, 22, 500):
            raise AssertionError(f"Unexpected Q15 native {band} shape: {values.shape}")
        transformed = resample_poly(values[:, indices, :], 16, 25, axis=2)
        if transformed.shape != (n_trials, 21, config["n_times"]):
            raise AssertionError(f"Unexpected Q15 {band} shape: {transformed.shape}")
        common[band] = np.ascontiguousarray(
            transformed.astype(np.float32) * config["volts_to_microvolts"]
        )
        if not np.isfinite(common[band]).all():
            raise AssertionError(f"Nonfinite Q15 {band} EEG")
    return common


def _build_model(name: str, config: dict, device):
    import torch

    from mi_eeg.models.eegnet_training import build_eegnet

    if name == "BROAD_EEGNET":
        return build_eegnet(config["architecture"], device)
    if name != "MU_BETA_SHARED":
        raise ValueError(name)
    n_chans = config["architecture"]["n_chans"]
    n_times = config["architecture"]["n_times"]

    class SharedBandEEGNet(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.eegnet = build_eegnet(config["architecture"], device)

        def forward(self, x):
            if x.ndim != 4 or tuple(x.shape[1:]) != (2, n_chans, n_times):
                raise ValueError(f"Expected [batch,2,{n_chans},{n_times}], got {tuple(x.shape)}")
            n = x.shape[0]
            return self.eegnet(x.reshape(n * 2, n_chans, n_times)).reshape(n, 2, 2).mean(1)

    return SharedBandEEGNet().to(device)


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
    curve = []
    for epoch in range(1, epochs + 1):
        train_ce = train_one_epoch(model, optimizer, x, y, train, config["batch_size"])
        val_ce = None if val is None else evaluate_cross_entropy(
            model, x, y, val, config["batch_size"]
        )
        if not np.isfinite(train_ce) or (val_ce is not None and not np.isfinite(val_ce)):
            raise AssertionError("Nonfinite Q15 source cross entropy")
        curve.append({"epoch": epoch, "train_ce": train_ce, "val_ce": val_ce})
    return model, curve


def _fit_csp(path: Path, arrays, meta, config, protocol_sha: str) -> None:
    source = config["source_subjects"]
    train = np.flatnonzero(meta["subject"].isin(source).to_numpy())
    required = {
        "experiment_id": "Q15-E005",
        "model": "CSP4_LDA",
        "train_subjects": source,
        "train_sample_ids_sha256": q14_source.sha_ids(meta.iloc[train]["sample_id"].to_numpy()),
        "protocol_sha256": protocol_sha,
    }
    manifest_path = path / "manifest.json"
    model_file = path / "model.joblib"
    if manifest_path.exists():
        old = _json(manifest_path)
        if old.get("status") != "complete" or any(old.get(k) != v for k, v in required.items()):
            raise AssertionError("Existing Q15 CSP fit protocol mismatch")
        if not model_file.is_file() or _sha(model_file) != old.get("model_sha256"):
            raise AssertionError("Existing Q15 CSP artifact corrupted")
        return
    pipeline = q14_source._csp_pipeline()
    pipeline.fit(arrays["broad"][train].astype(np.float64), meta.iloc[train]["label"].to_numpy())
    path.mkdir(parents=True, exist_ok=True)
    temp = path / "model.joblib.tmp"
    joblib.dump(pipeline, temp)
    os.replace(temp, model_file)
    q14_source.atomic_json(
        manifest_path,
        {**required, "status": "complete", "model_sha256": _sha(model_file), "n_source_trials": len(train)},
    )


def run_source(data_dir: Path, device_name: str) -> None:
    """Exactly 14 neural + one CSP BNCI source fits; no target predictions."""
    freeze = _verify_committed_freeze()  # Before source EEG loading or any fit.
    source_files = q14_source.source_file_receipt(data_dir)  # Before data loader/download.
    import torch

    config = derive_config()
    device = torch.device(device_name)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    if device.type == "cpu":
        torch.set_num_threads(min(4, torch.get_num_threads()))
    root = OUTPUT / "source"
    run_config = {
        "experiment_id": "Q15-E005",
        "status": "source_fitting_not_external_validation",
        "pre_fit_freeze_sha256": _sha(FREEZE),
        "contract_sha256": freeze["contract_sha256"],
        "runner_sha256": freeze["runner_sha256"],
        "source_file_receipt_sha256": hashlib.sha256(
            json.dumps(source_files, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "data_dir": str(data_dir.resolve()),
        "device": device_name,
        "runtime": q14_source.runtime_receipt(),
    }
    run_config_path = root / "run_config.json"
    if run_config_path.exists() and _json(run_config_path) != run_config:
        raise AssertionError("Existing Q15 run config differs; resume blocked")
    root.mkdir(parents=True, exist_ok=True)
    q14_source.atomic_json(run_config_path, run_config)
    q14_source.atomic_json(root / "source_files.json", {"files": source_files})
    arrays, meta, audit = load_source(config, data_dir)
    q14_source.atomic_csv(root / "source_metadata.csv", meta)
    q14_source.atomic_csv(root / "source_audit.csv", audit)
    y = torch.as_tensor(meta["label"].to_numpy() - 1, dtype=torch.long, device=device)
    source = config["source_subjects"]
    groups = config["q14_e002_inner_groups"]
    if sorted(s for group in groups for s in group) != source:
        raise AssertionError("Q15 source-only groups do not partition 9 source subjects")
    protocol_sha = _sha(FREEZE)
    for model_name in MODELS:
        x = q14_source.deep_input(model_name, arrays).to(device)
        base = root / model_name / "all_source"
        curves = {}
        for fold, validation_subjects in enumerate(groups, 1):
            train_subjects = [s for s in source if s not in validation_subjects]
            if set(train_subjects) & set(validation_subjects):
                raise AssertionError("Q15 inner train/validation leakage")
            train = np.flatnonzero(meta["subject"].isin(train_subjects).to_numpy())
            val = np.flatnonzero(meta["subject"].isin(validation_subjects).to_numpy())
            job = base / f"inner_{fold:02d}"
            required = {
                "experiment_id": "Q15-E005", "model": model_name,
                "inner_fold": fold, "train_subjects": train_subjects,
                "validation_subjects": validation_subjects,
                "train_sample_ids_sha256": q14_source.sha_ids(meta.iloc[train]["sample_id"].to_numpy()),
                "validation_sample_ids_sha256": q14_source.sha_ids(meta.iloc[val]["sample_id"].to_numpy()),
                "seed": config["selection_seed"], "epochs": config["max_epochs"],
                "protocol_sha256": protocol_sha,
            }
            curve = q14_source._verify_fit(job, required)
            if curve is None:
                model, curve = _fit_deep(
                    model_name, x, y, train, val, config["selection_seed"],
                    config["max_epochs"], config, device
                )
                q14_source._save_fit(job, model, curve, required)
                del model
            curves[fold] = curve
        selected = q14_source.mean_rank_epoch(curves, config["max_epochs"])
        selection = {
            "experiment_id": "Q15-E005", "model": model_name,
            "source_subjects": source, "validation_groups": groups,
            "selected_epoch": selected,
            "selection_rule": config["source_only_epoch_rule"],
            "inner_curve_sha256": [
                _sha(base / f"inner_{fold:02d}" / "curve.json") for fold in range(1, 5)
            ],
            "protocol_sha256": protocol_sha,
        }
        selection_path = base / "selection.json"
        if selection_path.exists() and _json(selection_path) != selection:
            raise AssertionError("Q15 source-only epoch selection changed")
        q14_source.atomic_json(selection_path, selection)
        train = np.flatnonzero(meta["subject"].isin(source).to_numpy())
        for seed in config["final_seeds"]:
            job = base / f"final_seed_{seed}"
            required = {
                "experiment_id": "Q15-E005", "model": model_name,
                "train_subjects": source,
                "train_sample_ids_sha256": q14_source.sha_ids(meta.iloc[train]["sample_id"].to_numpy()),
                "seed": seed, "epochs": selected, "protocol_sha256": protocol_sha,
            }
            if q14_source._verify_fit(job, required) is None:
                model, curve = _fit_deep(
                    model_name, x, y, train, None, seed, selected, config, device
                )
                q14_source._save_fit(job, model, curve, required)
                del model
        del x
        if device.type == "cuda":
            torch.cuda.empty_cache()
    _fit_csp(root / "CSP4_LDA" / "all_source", arrays, meta, config, protocol_sha)
    q14_source.atomic_json(
        root / "source_stage_complete.json",
        {
            "experiment_id": "Q15-E005",
            "status": "fits_complete_pending_independent_source_validation",
            "deep_fit_count": 14,
            "shallow_fit_count": 1,
            "external_predictions_computed": False,
            "external_prediction_authorized": False,
            "pre_fit_freeze_sha256": protocol_sha,
            "completed_at_utc": datetime.now(UTC).isoformat(),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-freeze", action="store_true", help="Write a pending pre-fit freeze receipt after real metadata audits")
    parser.add_argument("--execute", action="store_true", help="Fit the BNCI-only source models after committed freeze")
    parser.add_argument("--data-dir", type=Path, help="18 preverified BNCI MAT files; required with --execute")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    args = parser.parse_args()
    if args.execute and args.prepare_freeze:
        parser.error("Choose either --prepare-freeze or --execute")
    if args.execute:
        if args.data_dir is None:
            parser.error("--data-dir is required with --execute")
        run_source(args.data_dir, args.device)
    elif args.prepare_freeze:
        print(prepare_freeze())
    else:
        try:
            preflight_metadata()
        except (AssertionError, FileNotFoundError, KeyError) as exc:
            print(json.dumps({"status": "blocked_metadata_or_freeze_pending", "reason": str(exc), "fits_started": 0}, ensure_ascii=False))
            return
        print(json.dumps({"status": "metadata_ready_pre_fit_freeze_still_required", "fits_started": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
