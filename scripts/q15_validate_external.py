"""Independent Q15 raw-to-prediction replay, without any model or target fit.

The runner's receipts never constitute validation. This verifier replays the
real raw auditor and the epoch preprocessor, checks the committed inference
freeze, loads each source checkpoint independently, and reconstructs both
cohorts' person statistics. Successful adapter evaluation retains the declared
physical calibration, original Cho reference, and hardware timing limitations.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT, ROOT / "src"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

SOURCE_OUTPUT = ROOT / "results/Q15-E005"
OUTPUT = ROOT / "results/Q15-EXTERNAL"
FREEZE = OUTPUT / "inference_freeze.json"
DATASETS = {"Cho2017": ("Q15-E006", 52, (1,), 10520),
            "Lee2019_MI": ("Q15-E007", 54, (1, 2), 10800)}
DEEP_MODELS = ("BROAD_EEGNET", "MU_BETA_SHARED")
ALL_MODELS = (*DEEP_MODELS, "CSP4_LDA")
SEEDS = (20260924, 20260925, 20260926)
META_FIELDS = ("sample_id", "subject", "session", "run", "label", "file_id",
               "raw_sha256", "cue_sample_native")
PREDICTION_FIELDS = (*META_FIELDS, "dataset", "experiment_id", "model", "seed",
                     "p_left", "p_right", "predicted_label")

# Kept independently of the inference runner: a changed runner plan is rejected.
STATISTICS = {
    "schema_version": 1,
    "primary_contrast": "MU_BETA_SHARED_minus_BROAD_EEGNET",
    "inference_unit": "person",
    "within_person_aggregation": "balanced_accuracy_per_seed_then_three_seed_mean",
    "session_aggregation": "pool_declared_sessions_within_person_before_balanced_accuracy",
    "cohort_aggregation": "equal_person_mean",
    "confidence_level": 0.95,
    "confidence_interval": "paired_person_bootstrap_percentile",
    "bootstrap_draws": 20000, "bootstrap_seed": 20260924,
    "hypothesis_test": "two_sided_paired_person_sign_flip_monte_carlo_plus_one",
    "sign_flip_draws": 20000, "sign_flip_seed": 20261003,
    "multiplicity": "Holm_two_predeclared_cohorts", "context_comparator": "CSP4_LDA",
    "target_fits": 0, "outcome_based_selection": False,
}
CALIBRATION_LIMITATIONS = ["raw_voltage_calibration_not_independently_verified",
                           "cho_original_hardware_reference_not_verified",
                           "hardware_cue_latency_not_verified"]
_NO_DIGEST = object()


def _require(condition, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _reject_constant(value: str):
    raise ValueError(f"Nonfinite JSON constant: {value}")


def _json(path: Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=_reject_constant)
    _require(isinstance(value, dict), f"Expected a JSON object: {path}")
    return value


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _checked_file(path: Path, digest=_NO_DIGEST) -> Path:
    path = Path(path)
    _require(path.is_absolute() and path.is_file() and not path.is_symlink(),
             f"Artifact missing, relative, or symlinked: {path}")
    _require(not any(parent.is_symlink() for parent in path.parents),
             f"Symlinked artifact directory: {path}")
    if digest is not _NO_DIGEST:
        _require(isinstance(digest, str) and len(digest) == 64 and
                 all(character in "0123456789abcdef" for character in digest),
                 f"Missing or malformed artifact SHA256: {path}")
        _require(_sha(path) == digest, f"Artifact SHA256 mismatch: {path}")
    return path


def _committed(path: Path) -> None:
    path = _checked_file(path)
    relative = path.relative_to(ROOT).as_posix()
    result = subprocess.run(["git", "show", f"HEAD:{relative}"], cwd=ROOT,
                            capture_output=True, check=False)
    _require(result.returncode == 0 and result.stdout == path.read_bytes(),
             f"Inference input is not committed unchanged: {relative}")


def _fields(record: dict, expected: dict, label: str) -> None:
    _require(all(key in record and record[key] == value for key, value in expected.items()),
             f"{label} differs from independently expected fields")


def _config() -> dict:
    """Reconstruct the source architecture/batch size from the frozen protocol."""
    config = copy.deepcopy(_json(ROOT / "research_runs/Q14-E001/CONFIG.json"))
    arm = _json(ROOT / "research_runs/PAPER_RELEASE_20260927/Q15_CONTRACT.json")["new_source_arm"]
    config.update(channels=arm["channels"], cue_relative_start_s=0.5,
                  cue_relative_stop_exclusive_s=2.5, source_trial_start_s=2.5,
                  source_trial_stop_exclusive_s=4.5, n_times=320,
                  q14_e002_inner_groups=arm["source_only_inner_groups"])
    config["architecture"].update(arm["architecture_changes_from_q14"])
    _require(config["final_seeds"] == list(SEEDS), "Source seed inventory changed")
    _require(config["architecture"]["n_chans"] == 21 and
             config["architecture"]["n_times"] == 320 and
             config["architecture"]["n_outputs"] == 2, "Source architecture changed")
    return config


def _session_class_counts(dataset: str, subject: int) -> dict[int, int]:
    if dataset == "Cho2017":
        count = 120 if subject in (7, 9, 46) else 100
        return {1: count, 2: count}
    return {1: 50, 2: 50}


def _verify_inputs(manifests: dict[str, Path]) -> tuple[dict, dict, dict, dict]:
    """Replay mandatory gates before model import or target prediction."""
    _require(set(manifests) == set(DATASETS), "Both complete predeclared cohorts are required")
    freeze = _json(_checked_file(FREEZE))
    _fields(freeze, {
        "schema_version": 1, "status": "frozen_before_external_prediction_pending_commit",
        "source_arm": "Q15-E005", "external_arms": {k: v[0] for k, v in DATASETS.items()},
        "target_fits": 0, "new_model_fits": 0, "target_outcomes_inspected": False,
        "statistics": STATISTICS,
    }, "Inference freeze")
    code_paths = {
        "source_validation_sha256": SOURCE_OUTPUT / "source_validation.json",
        "source_validator_sha256": ROOT / "scripts/q15_validate_source.py",
        "contract_sha256": ROOT / "research_runs/PAPER_RELEASE_20260927/Q15_CONTRACT.json",
        "runner_sha256": ROOT / "scripts/q15_external.py",
        "preprocessor_sha256": ROOT / "scripts/q15_preprocess_external.py",
        "training_helper_sha256": ROOT / "src/mi_eeg/models/eegnet_training.py",
        "source_runner_sha256": ROOT / "scripts/q15_source.py",
        "dependency_spec_sha256": ROOT / "requirements-q15-runtime.txt",
        "execution_contract_sha256": ROOT / "research_runs/Q15-EXECUTION-20261003/EXECUTION_CONTRACT.json",
        "context_preprocessor_sha256": ROOT / "src/mi_eeg/data/q15_context.py",
        "real_metadata_adapter_sha256": ROOT / "scripts/q15_real_metadata.py",
        "external_validator_sha256": Path(__file__).resolve(),
        "csp_basis_sha256": ROOT / "src/mi_eeg/models/q15_csp.py",
    }
    for key, path in code_paths.items():
        _require(key in freeze, f"Inference freeze has no {key}")
        _checked_file(path, freeze[key])
        _committed(path)
    _committed(FREEZE)
    config = _config()
    source_validator = importlib.import_module("scripts.q15_validate_source")
    source_recorded = _json(SOURCE_OUTPUT / "source_validation.json")
    source_replayed = source_validator.validate_source(SOURCE_OUTPUT, write_report=False)
    _require(source_recorded == source_replayed, "Source validation cannot be independently reproduced")
    _fields(source_replayed, {"passed": True, "status": "source_validated_non_authorizing",
                            "deep_fit_count": 14, "shallow_fit_count": 1, "target_fits": 0,
                            "external_predictions_computed": False,
                            "external_prediction_authorized": False}, "Source validation")
    checkpoints = [SOURCE_OUTPUT / "pre_fit_freeze.json"]
    for name in DEEP_MODELS:
        base = SOURCE_OUTPUT / "source" / name / "all_source"
        checkpoints.append(base / "selection.json")
        checkpoints.extend(base / f"final_seed_{seed}" / "checkpoint.pt" for seed in SEEDS)
    checkpoints.append(SOURCE_OUTPUT / "source/CSP4_LDA/all_source/model.joblib")
    expected_hashes = {path.relative_to(ROOT).as_posix(): _sha(_checked_file(path))
                       for path in checkpoints}
    _require(freeze.get("source_checkpoints") == expected_hashes,
             "Frozen source checkpoint inventory or hashes differ")
    for path in checkpoints:
        _committed(path)
    source = importlib.import_module("scripts.q15_source")
    auditor = importlib.import_module("scripts.q15_real_metadata")
    preprocessor = importlib.import_module("scripts.q15_preprocess_external")
    context = importlib.import_module("mi_eeg.data.q15_context")
    _require(freeze.get("preprocessing") == context.preprocessing_contract(),
             "Frozen preprocessing differs from canonical context contract")
    _fields(freeze["preprocessing"], {"calibration_verified": False,
                                    "native_export_units_verified": False},
            "Frozen unresolved physical calibration")
    _require(set(freeze.get("metadata_receipts", {})) == set(DATASETS) and
             set(freeze.get("epoch_manifests", {})) == set(DATASETS),
             "Frozen cohort receipt or epoch inventory differs")
    verified, audits = {}, {}
    for dataset, (_, n_people, sessions, n_trials) in DATASETS.items():
        receipt_path = Path(source.AUDIT_RECEIPTS[dataset])
        _checked_file(receipt_path, freeze["metadata_receipts"][dataset])
        _committed(receipt_path)
        recorded = _json(receipt_path)
        _fields(recorded, {"dataset": dataset, "status": "metadata_passed_non_authorizing",
                          "synthetic_fixture": False, "target_fits": 0,
                          "predictions_computed": False, "metadata_only": True,
                          "raw_hashes_verified": True, "provider_inventory_verified": True,
                          "provider_manifest_authenticated": True, "all_expected_files_hashed": True,
                          "model_predictions_computed": False, "performance_metrics_computed": False,
                          "external_prediction_authorized": False, "source_training_authorized": False,
                          "native_numeric_calibration_verified": False}, "Raw metadata receipt")
        inventory = _checked_file(Path(recorded.get("provider_manifest_path", "")),
                                  recorded.get("provider_manifest_sha256"))
        _committed(inventory)
        replayed = auditor.audit_inventory(inventory)
        _require(replayed == recorded, "Raw metadata receipt cannot be independently reproduced")
        files = recorded.get("files", [])
        _require(len(files) == n_people * len(sessions), "Incomplete raw-file cohort coverage")
        _require(sum(len(row.get("events", [])) for row in files) == n_trials,
                 "Raw auditor trial totals differ from predeclared cohort")
        for row in files:
            _checked_file(Path(row["path"]), row["sha256"])
        audit_pairs = [(row["subject"], row["session"]) for row in files]
        _require(len(set(audit_pairs)) == len(files) and set(audit_pairs) == {
            (person, session) for person in range(1, n_people + 1) for session in sessions},
            "Raw auditor person/session coverage differs")
        path = _checked_file(Path(manifests[dataset]))
        _fields(freeze["epoch_manifests"][dataset], {"path": str(path.resolve()),
                    "sha256": _sha(path), "n_persons": n_people}, "Frozen epoch manifest")
        _committed(path)
        manifest = _json(path)
        _require(preprocessor.validate_epoch_manifest(path) == manifest,
                 "Epoch manifest cannot be independently replayed from raw originals")
        _require(manifest.get("dataset") == dataset and manifest.get("preprocessing") == freeze["preprocessing"],
                 "Epoch manifest identity or preprocessing differs")
        persons = manifest.get("subjects", [])
        _require([row.get("subject") for row in persons] == list(range(1, n_people + 1)) and
                 sum(row.get("n_trials", 0) for row in persons) == n_trials,
                 "Epoch manifest person/trial inventory differs")
        verified[dataset], audits[dataset] = manifest, recorded
    return freeze, config, verified, audits


def _load_person(row: dict, dataset: str) -> tuple[dict, pd.DataFrame]:
    _checked_file(Path(row["npz_path"]), row["npz_sha256"])
    _checked_file(Path(row["metadata_path"]), row["metadata_sha256"])
    with np.load(row["npz_path"], allow_pickle=False) as archive:
        _require(set(archive.files) == {"broad", "mu", "beta"}, "Epoch band inventory differs")
        arrays = {band: archive[band] for band in archive.files}
    meta = _read_frame(Path(row["metadata_path"]))
    _require(set(META_FIELDS).issubset(meta) and not meta.empty and not meta.isna().any().any(),
             "Missing or invalid canonical trial metadata")
    _require(len(meta) == row["n_trials"] and not meta["sample_id"].duplicated().any(),
             "Trial identity or count differs")
    _require(set(meta["subject"]) == {row["subject"]} and
             sorted(meta["session"].unique()) == list(DATASETS[dataset][2]),
             "Trial person/session scope differs")
    for field in ("subject", "session", "label", "cue_sample_native"):
        _require(np.issubdtype(meta[field].dtype, np.integer), f"Noninteger trial {field}")
    _require((meta["cue_sample_native"] >= 0).all() and
             meta["raw_sha256"].str.fullmatch(r"[0-9a-f]{64}").all(),
             "Invalid canonical cue or raw digest")
    _require(set(meta["file_id"]) == set(row["raw_file_ids"]), "Trial raw-file coverage differs")
    for _, session in meta.groupby("session"):
        _require(session["label"].value_counts().to_dict() == _session_class_counts(dataset, row["subject"]),
                 "Canonical left=1/right=2 session trial counts differ")
    for values in arrays.values():
        _require(values.dtype == np.float32 and values.shape == (len(meta), 21, 320) and
                 np.isfinite(values).all(), "Invalid frozen epoch tensor shape/dtype/values")
    return arrays, meta


def _read_frame(path: Path) -> pd.DataFrame:
    return pd.read_csv(_checked_file(path), dtype={"sample_id": str, "file_id": str,
                       "raw_sha256": str, "run": str, "seed": str}, float_precision="round_trip")


def _build_model(name: str, architecture: dict, device):
    import torch
    from braindecode.models import EEGNet

    parameters = {key: value for key, value in architecture.items() if key not in ("library", "model")}
    if name == "BROAD_EEGNET":
        return EEGNet(**parameters).to(device)
    _require(name == "MU_BETA_SHARED", "Unknown source model")

    class Shared(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.eegnet = EEGNet(**parameters)

        def forward(self, x):
            _require(tuple(x.shape[1:]) == (2, 21, 320), "Shared-band tensor shape differs")
            return self.eegnet(x.reshape(-1, 21, 320)).reshape(len(x), 2, 2).mean(dim=1)

    return Shared().to(device)


def _load_models(config: dict, device):
    import joblib
    import torch

    models = {}
    for name in DEEP_MODELS:
        base = SOURCE_OUTPUT / "source" / name / "all_source"
        selection = _json(base / "selection.json")
        for seed in SEEDS:
            checkpoint = torch.load(base / f"final_seed_{seed}/checkpoint.pt",
                                    map_location=device, weights_only=True)
            _fields(checkpoint, {"model": name, "seed": seed,
                                 "epochs": selection["selected_epoch"]}, "Source checkpoint")
            model = _build_model(name, config["architecture"], device)
            model.load_state_dict(checkpoint["state_dict"], strict=True)
            model.eval()
            models[name, seed] = model
    csp = joblib.load(SOURCE_OUTPUT / "source/CSP4_LDA/all_source/model.joblib")
    _require(list(csp.named_steps["lda"].classes_) == [1, 2], "CSP class-column mapping differs")
    return models, csp


def _state_digest(model) -> str:
    digest = hashlib.sha256()
    for key, tensor in sorted(model.state_dict().items()):
        values = tensor.detach().cpu().contiguous().numpy()
        digest.update(key.encode("utf-8"))
        digest.update(str(values.dtype).encode("ascii"))
        digest.update(str(values.shape).encode("ascii"))
        digest.update(values.tobytes())
    return digest.hexdigest()


def _validate_probabilities(probabilities: np.ndarray, size: int) -> None:
    _require(probabilities.shape == (size, 2) and np.isfinite(probabilities).all() and
             (probabilities >= 0).all() and (probabilities <= 1).all(),
             "Invalid prediction probabilities")
    _require(np.allclose(probabilities.sum(axis=1), 1, rtol=1e-6, atol=1e-7),
             "Prediction probabilities are not normalized")


def _replay_person(arrays: dict, meta: pd.DataFrame, models: dict, csp,
                   config: dict, device) -> dict[tuple[str, str], np.ndarray]:
    """Direct eval-mode forward passes, with before/after state checks; no fit."""
    import joblib
    import torch

    predictions = {}
    for name in DEEP_MODELS:
        values = arrays["broad"] if name == "BROAD_EEGNET" else np.stack(
            (arrays["mu"], arrays["beta"]), axis=1)
        x = torch.from_numpy(values).to(device)
        for seed in SEEDS:
            model = models[name, seed]
            model.eval()
            before = _state_digest(model)
            parts = []
            with torch.inference_mode():
                for start in range(0, len(meta), config["batch_size"]):
                    logits = model(x[start:start + config["batch_size"]])
                    _require(tuple(logits.shape) == (min(config["batch_size"], len(meta) - start), 2),
                             "Independent checkpoint logits shape differs")
                    parts.append(torch.softmax(logits, dim=1).cpu().numpy())
            _require(_state_digest(model) == before, "Independent inference altered frozen neural state")
            probabilities = np.concatenate(parts)
            _validate_probabilities(probabilities, len(meta))
            predictions[name, str(seed)] = probabilities
        del x
    before = joblib.hash(csp, hash_name="sha1")
    probabilities = np.asarray(csp.predict_proba(arrays["broad"].astype(np.float64)))
    _require(joblib.hash(csp, hash_name="sha1") == before,
             "Independent inference altered frozen CSP/scaler/LDA state")
    _validate_probabilities(probabilities, len(meta))
    predictions["CSP4_LDA", "deterministic"] = probabilities
    return predictions


def _validate_prediction_frame(frame: pd.DataFrame, dataset: str, meta: pd.DataFrame) -> None:
    _require(set(frame) == set(PREDICTION_FIELDS) and not frame.empty and
             not frame.isna().any().any(), "Prediction schema/null coverage differs")
    _require(set(frame["dataset"]) == {dataset} and
             set(frame["experiment_id"]) == {DATASETS[dataset][0]}, "Prediction cohort identity differs")
    expected = {(name, str(seed)) for name in DEEP_MODELS for seed in SEEDS}
    expected.add(("CSP4_LDA", "deterministic"))
    _require(set(zip(frame["model"], frame["seed"].astype(str))) == expected,
             "Prediction model/three-seed coverage differs")
    _require(len(frame) == 7 * len(meta) and not frame.duplicated(["sample_id", "model", "seed"]).any(),
             "Prediction trial coverage or duplicate identity differs")
    probabilities = frame[["p_left", "p_right"]].to_numpy(dtype=np.float64)
    _validate_probabilities(probabilities, len(frame))
    _require(np.array_equal(frame["predicted_label"], np.argmax(probabilities, axis=1) + 1),
             "Prediction canonical label argmax differs")
    reference = meta.loc[:, list(META_FIELDS)].sort_values("sample_id").reset_index(drop=True)
    for _, group in frame.groupby(["model", "seed"], sort=True):
        observed = group.loc[:, list(META_FIELDS)].sort_values("sample_id").reset_index(drop=True)
        _require(observed.equals(reference), "Prediction trial metadata differs from raw-replayed identities")


def _compare_replay(frame: pd.DataFrame, meta: pd.DataFrame,
                    replay: dict[tuple[str, str], np.ndarray]) -> None:
    for key, values in replay.items():
        part = frame.loc[(frame["model"] == key[0]) & (frame["seed"].astype(str) == key[1])]
        part = part.set_index("sample_id").loc[meta["sample_id"]]
        observed = part[["p_left", "p_right"]].to_numpy(dtype=float)
        _require(np.allclose(observed, values, rtol=1e-6, atol=1e-7) and
                 np.array_equal(part["predicted_label"], np.argmax(values, axis=1) + 1),
                 "Saved probabilities/labels differ from independent frozen-checkpoint replay")


def _score(labels, predicted) -> dict:
    actual, outcome = np.asarray(labels), np.asarray(predicted)
    _require(actual.ndim == 1 and actual.shape == outcome.shape and set(actual) == {1, 2} and
             set(outcome).issubset({1, 2}), "Invalid canonical classes for balanced accuracy")
    counts = np.zeros((2, 2), dtype=np.int64)
    np.add.at(counts, (actual.astype(int) - 1, outcome.astype(int) - 1), 1)
    recalls = np.diag(counts) / counts.sum(axis=1)
    return {"n_trials": len(actual), "confusion_matrix_rows_actual_left_right": counts.tolist(),
            "left_recall": float(recalls[0]), "right_recall": float(recalls[1]),
            "balanced_accuracy": float((recalls[0] + recalls[1]) / 2)}


def independent_paired_statistics(effects) -> dict:
    values = np.asarray(effects, dtype=np.float64)
    _require(values.ndim == 1 and len(values) >= 2 and np.isfinite(values).all() and
             (np.abs(values) <= 1).all(), "Invalid person-level paired effects")
    # Same frozen random draw sequence, separately reconstructed calculations.
    rng = np.random.default_rng(20260924)
    draws = rng.integers(0, len(values), size=(20000, len(values)))
    bootstrap = np.mean(np.take(values, draws), axis=1)
    rng = np.random.default_rng(20261003)
    signs = rng.integers(0, 2, size=(20000, len(values))) * 2 - 1
    simulated = np.abs(np.sum(signs * values, axis=1) / len(values))
    extreme = int(np.count_nonzero(simulated >= abs(float(values.mean())) - 1e-15))
    return {"n_persons": len(values), "mean_paired_balanced_accuracy_difference": float(values.mean()),
            "paired_person_bootstrap_percentile_95_ci": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
            "two_sided_person_sign_flip_p_value": (extreme + 1) / 20001,
            "statistics_plan": STATISTICS}


def independent_summary(frame: pd.DataFrame, dataset: str) -> dict:
    n_people, sessions = DATASETS[dataset][1:3]
    people, strata = [], []
    _require(set(frame["subject"]) == set(range(1, n_people + 1)), "Statistics person coverage differs")
    for subject in range(1, n_people + 1):
        person = frame.loc[frame["subject"] == subject]
        _require(sorted(person["session"].unique()) == list(sessions), "Statistics session coverage differs")
        models = {}
        for name in ALL_MODELS:
            seeds = SEEDS if name in DEEP_MODELS else ("deterministic",)
            per_seed = {}
            for seed in seeds:
                rows = person.loc[(person["model"] == name) & (person["seed"].astype(str) == str(seed))]
                per_seed[str(seed)] = _score(rows["label"], rows["predicted_label"])
                for session in sessions:
                    session_rows = rows.loc[rows["session"] == session]
                    strata.append({"subject": subject, "session": session, "model": name,
                                   "seed": str(seed), **_score(session_rows["label"], session_rows["predicted_label"])})
            scores = np.array([score["balanced_accuracy"] for score in per_seed.values()])
            models[name] = {"within_person_seed_mean_balanced_accuracy": float(scores.mean()),
                            "seed_sample_standard_deviation": float(scores.std(ddof=1)) if len(scores) > 1 else None,
                            "per_seed": per_seed}
        difference = models["MU_BETA_SHARED"]["within_person_seed_mean_balanced_accuracy"] - models["BROAD_EEGNET"]["within_person_seed_mean_balanced_accuracy"]
        people.append({"subject": subject, "models": models, "primary_paired_difference": difference})
    return {"schema_version": 1, "dataset": dataset, "experiment_id": DATASETS[dataset][0],
            "status": "descriptive_statistics_pending_independent_raw_prediction_replay",
            "target_fits": 0, "new_model_fits": 0, "n_persons": n_people,
            "n_sessions": n_people * len(sessions),
            "cohort_equal_person_mean_balanced_accuracy": {
                name: float(np.mean([person["models"][name]["within_person_seed_mean_balanced_accuracy"]
                                     for person in people])) for name in ALL_MODELS},
            "primary_contrast": independent_paired_statistics([person["primary_paired_difference"] for person in people]),
            "persons": people, "session_strata": strata}


def independent_holm(summaries: dict[str, dict]) -> dict:
    _require(set(summaries) == set(DATASETS), "Holm requires both predeclared separate cohorts")
    ordered = sorted((value["primary_contrast"]["two_sided_person_sign_flip_p_value"], dataset)
                     for dataset, value in summaries.items())
    adjusted, previous = {}, 0.0
    for index, (value, dataset) in enumerate(ordered):
        _require(np.isfinite(value) and 0 <= value <= 1, "Invalid Holm family p value")
        previous = max(previous, min(1.0, value * (2 - index)))
        adjusted[dataset] = {"uncorrected_two_sided_p_value": value, "holm_adjusted_p_value": previous}
    return {"family": ["Q15-E006", "Q15-E007"], "method": "Holm", "cohorts": adjusted,
            "status": "pending_independent_raw_prediction_replay"}


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _require(not path.is_symlink(), "Validation report symlink is forbidden")
    descriptor, temporary = tempfile.mkstemp(prefix=".q15-validation-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _device(device_name: str):
    import torch
    torch.use_deterministic_algorithms(True)
    device = torch.device(device_name)
    _require(device.type in ("cpu", "cuda"), "Replay device must be cpu or cuda")
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    return device


def validate_external(manifests: dict[str, Path], device_name: str = "cuda",
                      write_report: bool = True) -> dict:
    """Return a pass only after every original, tensor, prediction and statistic replays.

    Failure raises and writes no successful report. ``write_report=False`` is
    fully read-only; it does not skip any gate or reuse any prior replay result.
    """
    manifests = {dataset: Path(path) for dataset, path in manifests.items()}
    freeze, config, checked, audits = _verify_inputs(manifests)
    immutable_inputs = {path: _sha(path) for path in (FREEZE, *manifests.values())}
    device = _device(device_name)
    models, csp = _load_models(config, device)
    freeze_sha = _sha(FREEZE)
    source_hashes = freeze["source_checkpoints"]
    initial_states = {f"{name}/{seed}": _state_digest(model) for (name, seed), model in models.items()}
    import joblib
    shallow_state = joblib.hash(csp, hash_name="sha1")
    artifacts = [FREEZE, *(path for path in manifests.values() if path.is_relative_to(OUTPUT))]
    summaries, coverage = {}, {}
    for dataset, (experiment, n_people, sessions, n_trials) in DATASETS.items():
        root = OUTPUT / experiment
        frames, metadata = [], []
        for row in checked[dataset]["subjects"]:
            arrays, meta = _load_person(row, dataset)
            directory = root / f"subject_{row['subject']:03d}"
            csv, receipt_path = directory / "predictions.csv", directory / "receipt.json"
            receipt = _json(_checked_file(receipt_path))
            _fields(receipt, {"status": "complete_pending_independent_raw_prediction_replay",
                    "dataset": dataset, "subject": row["subject"], "inference_freeze_sha256": freeze_sha,
                    "npz_sha256": row["npz_sha256"], "metadata_sha256": row["metadata_sha256"],
                    "target_fits": 0, "new_model_fits": 0, "n_trials": len(meta),
                    "n_prediction_rows": 7 * len(meta)}, "Person inference receipt")
            _checked_file(csv, receipt.get("predictions_sha256"))
            frame = _read_frame(csv)
            _validate_prediction_frame(frame, dataset, meta)
            _compare_replay(frame, meta, _replay_person(arrays, meta, models, csp, config, device))
            frames.append(frame)
            metadata.append(meta)
            artifacts.extend((csv, receipt_path))
        combined = pd.concat(frames, ignore_index=True)
        expected_meta = pd.concat(metadata, ignore_index=True)
        _require(len(expected_meta) == n_trials and not expected_meta["sample_id"].duplicated().any(),
                 "Complete cohort canonical trial coverage differs")
        aggregate_path, statistics_path = root / "predictions.csv", root / "statistics.json"
        aggregate = _read_frame(aggregate_path)
        _validate_prediction_frame(aggregate, dataset, expected_meta)
        ordering = ["sample_id", "model", "seed"]
        pd.testing.assert_frame_equal(aggregate.sort_values(ordering).reset_index(drop=True),
                                      combined.sort_values(ordering).reset_index(drop=True),
                                      check_exact=True)
        summary = independent_summary(aggregate, dataset)
        _require(_json(_checked_file(statistics_path)) == summary,
                 "Cohort person/seed/session statistics differ from independent reconstruction")
        summaries[dataset] = summary
        coverage[dataset] = {"n_persons": n_people, "n_sessions": n_people * len(sessions),
                             "n_raw_files": len(audits[dataset]["files"]), "n_trials": n_trials,
                             "n_prediction_rows": 7 * n_trials, "deep_models": list(DEEP_MODELS),
                             "deep_seeds": list(SEEDS), "shallow_models": ["CSP4_LDA"]}
        artifacts.extend((aggregate_path, statistics_path))
    holm_path, completion_path = OUTPUT / "holm_two_cohorts.json", OUTPUT / "completion_receipt.json"
    holm = independent_holm(summaries)
    _require(_json(_checked_file(holm_path)) == holm, "Holm statistics differ from independent reconstruction")
    completion = _json(_checked_file(completion_path))
    _fields(completion, {"schema_version": 1,
        "status": "inference_complete_pending_independent_raw_prediction_replay",
        "target_fits": 0, "new_model_fits": 0, "scientific_validation_passed": False,
        "inference_freeze_sha256": freeze_sha, "statistics_plan": STATISTICS,
        "cohort_prediction_sha256": {dataset: _sha(OUTPUT / info[0] / "predictions.csv") for dataset, info in DATASETS.items()},
        "cohort_statistics_sha256": {dataset: _sha(OUTPUT / info[0] / "statistics.json") for dataset, info in DATASETS.items()},
        "holm_sha256": _sha(holm_path)}, "Inference completion receipt")
    artifacts.extend((holm_path, completion_path))
    for relative, digest in source_hashes.items():
        _checked_file(ROOT / relative, digest)
    final_states = {f"{name}/{seed}": _state_digest(model) for (name, seed), model in models.items()}
    _require(final_states == initial_states and joblib.hash(csp, hash_name="sha1") == shallow_state,
             "External replay changed a frozen model state")
    _require(all(_sha(path) == digest for path, digest in immutable_inputs.items()),
             "Inference freeze or epoch manifest changed during independent replay")
    expected_files = {path.resolve() for path in artifacts}
    # The prior validation report is permitted but never trusted or self-hashed.
    report_path = OUTPUT / "validation_report.json"
    actual = list(OUTPUT.rglob("*"))
    _require(not OUTPUT.is_symlink() and not any(path.is_symlink() for path in actual),
             "Symlinked external output is forbidden")
    _require({path.resolve() for path in actual if path.is_file()} ==
             expected_files | ({report_path.resolve()} if report_path.is_file() else set()),
             "Unexpected or missing external artifacts; extra fits/predictions are forbidden")
    artifact_hashes = {path.relative_to(ROOT).as_posix(): _sha(path) for path in sorted(set(artifacts))}
    report = {"schema_version": 1, "status": "completed_with_calibration_limitations",
              "passed": True, "scientific_validation_passed": True,
              "raw_auditor_replayed": True, "raw_to_epoch_replayed": True,
              "frozen_checkpoint_prediction_replayed": True, "statistics_independently_reconstructed": True,
              "target_fits": 0, "new_model_fits": 0, "model_state_unchanged": True,
              "source_deep_fit_count": 14, "source_shallow_fit_count": 1,
              "label_map": {"left_hand": 1, "right_hand": 2}, "coverage": coverage,
              "inference_freeze_sha256": freeze_sha, "validator_sha256": _sha(Path(__file__)),
              "epoch_manifest_sha256": {dataset: _sha(path) for dataset, path in manifests.items()},
              "statistics_plan": STATISTICS, "cohort_primary_contrasts": {
                  dataset: summary["primary_contrast"] for dataset, summary in summaries.items()},
              "holm_two_cohorts": {**holm, "status": "independently_reconstructed"},
              "neural_state_sha256_before_after": initial_states,
              "shallow_state_digest_before_after": {"algorithm": "joblib_sha1", "value": shallow_state},
              "probability_replay_tolerance": {"rtol": 1e-6, "atol": 1e-7, "argmax_exact": True},
              "calibration_verified": False, "native_export_units_verified": False,
              "cho_original_reference_verified": False, "hardware_cue_latency_verified": False,
              "calibration_limitations": CALIBRATION_LIMITATIONS,
              "interpretation": "Completed prospectively defined adapter benchmark; physical units, original Cho reference, and hardware cue latency remain unverified.",
              "artifact_sha256": artifact_hashes}
    if write_report:
        _atomic_json(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cho-manifest", type=Path, required=True)
    parser.add_argument("--lee-manifest", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    result = validate_external({"Cho2017": args.cho_manifest.resolve(),
                               "Lee2019_MI": args.lee_manifest.resolve()},
                              args.device, write_report=not args.no_write)
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
