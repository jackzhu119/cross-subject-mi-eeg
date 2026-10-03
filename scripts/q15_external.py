"""Q15-E006/E007 source-frozen zero-target-fit inference and person statistics.

No raw-MAT preprocessing occurs here. The independently replayed epoch manifest
is the only accepted target interface. Both cohorts, the six source checkpoints,
the CSP pipeline, this code, and the fixed statistical plan must be committed in
one inference freeze before the first prediction. Completion remains pending an
independent raw-to-prediction replay; an orchestration receipt is not a pass.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import q15_source

RUNNER = Path(__file__).resolve()
SOURCE_OUTPUT = ROOT / "results/Q15-E005"
SOURCE_VALIDATOR = ROOT / "scripts/q15_validate_source.py"
SOURCE_VALIDATION = SOURCE_OUTPUT / "source_validation.json"
PREPROCESSOR = ROOT / "scripts/q15_preprocess_external.py"
OUTPUT = ROOT / "results/Q15-EXTERNAL"
FREEZE = OUTPUT / "inference_freeze.json"
DATASETS = {"Cho2017": ("Q15-E006", 52, [1]), "Lee2019_MI": ("Q15-E007", 54, [1, 2])}
DEEP_MODELS = ("BROAD_EEGNET", "MU_BETA_SHARED")
ALL_MODELS = (*DEEP_MODELS, "CSP4_LDA")
SEEDS = (20260924, 20260925, 20260926)
META_FIELDS = ("sample_id", "subject", "session", "run", "label", "file_id",
               "raw_sha256", "cue_sample_native")

# Frozen before any target prediction. Neither CLI options nor observed scores
# can change the number of draws, seeds, unit of inference, or family of tests.
STATISTICS = {
    "schema_version": 1,
    "primary_contrast": "MU_BETA_SHARED_minus_BROAD_EEGNET",
    "inference_unit": "person",
    "within_person_aggregation": "balanced_accuracy_per_seed_then_three_seed_mean",
    "session_aggregation": "pool_declared_sessions_within_person_before_balanced_accuracy",
    "cohort_aggregation": "equal_person_mean",
    "confidence_level": 0.95,
    "confidence_interval": "paired_person_bootstrap_percentile",
    "bootstrap_draws": 20000,
    "bootstrap_seed": 20260924,
    "hypothesis_test": "two_sided_paired_person_sign_flip_monte_carlo_plus_one",
    "sign_flip_draws": 20000,
    "sign_flip_seed": 20261003,
    "multiplicity": "Holm_two_predeclared_cohorts",
    "context_comparator": "CSP4_LDA",
    "target_fits": 0,
    "outcome_based_selection": False,
}


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("Expected a JSON object")
    return value


def _sha(path: Path) -> str:
    return q15_source._sha(path)


def _atomic_json(path: Path, value: dict) -> None:
    q15_source.q14_source.atomic_json(path, value)


def _module(path: Path, name: str):
    if not path.is_file():
        raise AssertionError(f"Independent adapter or validator not implemented: {name}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Independent verifier unavailable: {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _verify_source_validation() -> dict:
    """Re-run source validation; a status-only JSON can never authorize inference."""
    if not SOURCE_VALIDATION.is_file():
        raise AssertionError("Independent Q15 source validation missing")
    recorded = _json(SOURCE_VALIDATION)
    required = {
        "status": "source_validated_non_authorizing", "deep_fit_count": 14,
        "shallow_fit_count": 1, "target_fits": 0, "external_predictions_computed": False,
        "passed": True, "external_prediction_authorized": False,
    }
    if any(recorded.get(key) != value for key, value in required.items()):
        raise AssertionError("Q15 source validation has not passed the source-only gate")
    reproduced = _module(SOURCE_VALIDATOR, "q15_validate_source").validate_source(
        SOURCE_OUTPUT, write_report=False)
    if reproduced != recorded:
        raise AssertionError("Independent Q15 source validation cannot be reproduced")
    return recorded


def _preprocessing_contract() -> dict:
    from mi_eeg.data.q15_context import preprocessing_contract
    return preprocessing_contract()


def _validated_manifest(path: Path, dataset: str) -> dict:
    manifest = _json(path)
    if manifest.get("schema_version") != 1 or manifest.get("dataset") != dataset:
        raise AssertionError("Q15 epoch manifest identity mismatch")
    if manifest.get("status") != "epochs_verified_non_authorizing":
        raise AssertionError("Q15 epoch manifest has not passed independent preprocessing")
    if manifest.get("preprocessing") != _preprocessing_contract():
        raise AssertionError("Q15 target preprocessing differs from frozen contract")
    _, size, sessions = DATASETS[dataset]
    persons = manifest.get("subjects", [])
    expected = list(range(1, size + 1))
    if manifest.get("expected_subject_ids") != expected:
        raise AssertionError("Q15 person inventory changed")
    if len(persons) != size or sorted(row.get("subject", -1) for row in persons) != expected:
        raise AssertionError("Q15 epoch manifest has missing or duplicate persons")
    if manifest.get("metadata_receipt_sha256") != _sha(q15_source.AUDIT_RECEIPTS[dataset]):
        raise AssertionError("Q15 epoch manifest differs from the real raw audit")
    for row in persons:
        if row.get("sessions") != sessions or row.get("n_trials", 0) <= 0:
            raise AssertionError("Q15 epoch session/trial inventory changed")
        for path_key, sha_key in (("npz_path", "npz_sha256"), ("metadata_path", "metadata_sha256")):
            file = Path(row.get(path_key, ""))
            if not file.is_absolute() or not file.is_file() or file.is_symlink():
                raise AssertionError("Q15 epoch artifact missing or unsafe")
            if _sha(file) != row.get(sha_key):
                raise AssertionError("Q15 epoch artifact changed")
    # Raw-MAT auditor and frozen preprocessing independently reconstruct all
    # identities and epoch hashes. A caller's receipt flags are insufficient.
    replay = _module(PREPROCESSOR, "q15_preprocess_external").validate_epoch_manifest(path)
    if replay != manifest:
        raise AssertionError("Q15 epoch manifest cannot be independently reproduced")
    return manifest


def _checkpoint_hashes(config: dict) -> dict:
    paths = [SOURCE_OUTPUT / "pre_fit_freeze.json"]
    for name in DEEP_MODELS:
        base = SOURCE_OUTPUT / "source" / name / "all_source"
        paths.append(base / "selection.json")
        paths.extend(base / f"final_seed_{seed}" / "checkpoint.pt" for seed in SEEDS)
    paths.append(SOURCE_OUTPUT / "source/CSP4_LDA/all_source/model.joblib")
    if config["final_seeds"] != list(SEEDS):
        raise AssertionError("Q15 frozen source seeds changed")
    return {file.relative_to(ROOT).as_posix(): _sha(file) for file in paths}


def _freeze_payload(manifests: dict[str, Path]) -> dict:
    if set(manifests) != set(DATASETS):
        raise AssertionError("Both Q15 cohorts must be frozen before first target prediction")
    _verify_source_validation()
    config = q15_source.derive_config()
    checked = {dataset: _validated_manifest(path, dataset) for dataset, path in manifests.items()}
    return {
        "schema_version": 1, "status": "frozen_before_external_prediction_pending_commit",
        "source_arm": "Q15-E005", "external_arms": {k: v[0] for k, v in DATASETS.items()},
        "target_fits": 0, "new_model_fits": 0, "target_outcomes_inspected": False,
        "statistics": STATISTICS, "preprocessing": _preprocessing_contract(),
        "source_validation_sha256": _sha(SOURCE_VALIDATION),
        "source_validator_sha256": _sha(SOURCE_VALIDATOR),
        "contract_sha256": _sha(q15_source.CONTRACT),
        "runner_sha256": _sha(RUNNER), "preprocessor_sha256": _sha(PREPROCESSOR),
        "execution_contract_sha256": _sha(q15_source.EXECUTION_CONTRACT),
        "context_preprocessor_sha256": _sha(q15_source.CONTEXT_PREPROCESSOR),
        "real_metadata_adapter_sha256": _sha(q15_source.REAL_METADATA_ADAPTER),
        "csp_basis_sha256": _sha(q15_source.CSP_BASIS),
        "external_validator_sha256": _sha(ROOT / "scripts/q15_validate_external.py"),
        "training_helper_sha256": _sha(q15_source.EEGNET_HELPER),
        "source_runner_sha256": _sha(Path(q15_source.__file__)),
        "dependency_spec_sha256": _sha(q15_source.DEPENDENCY_SPEC),
        "source_checkpoints": _checkpoint_hashes(config),
        "metadata_receipts": {dataset: _sha(q15_source.AUDIT_RECEIPTS[dataset]) for dataset in DATASETS},
        "epoch_manifests": {dataset: {"path": str(manifests[dataset].resolve()),
                                     "sha256": _sha(manifests[dataset]),
                                     "n_persons": len(checked[dataset]["subjects"])}
                            for dataset in DATASETS},
    }


def _committed_inputs(manifests: dict[str, Path]) -> list[Path]:
    return [RUNNER, SOURCE_VALIDATOR, SOURCE_VALIDATION, PREPROCESSOR,
            q15_source.EXECUTION_CONTRACT, q15_source.CONTEXT_PREPROCESSOR,
            q15_source.REAL_METADATA_ADAPTER, q15_source.CSP_BASIS,
            ROOT / "scripts/q15_validate_external.py",
            q15_source.CONTRACT, Path(q15_source.__file__), q15_source.EEGNET_HELPER,
            q15_source.DEPENDENCY_SPEC, *q15_source.AUDIT_RECEIPTS.values(),
            *manifests.values()]


def prepare_freeze(manifests: dict[str, Path]) -> Path:
    payload = _freeze_payload(manifests)
    for path in _committed_inputs(manifests):
        q15_source._assert_committed_unchanged(path)
    if FREEZE.exists() and _json(FREEZE) != payload:
        raise AssertionError("Existing Q15 inference freeze differs; do not mix protocols")
    _atomic_json(FREEZE, payload)
    return FREEZE


def verify_freeze(manifests: dict[str, Path]) -> dict:
    if not FREEZE.is_file():
        raise AssertionError("Committed Q15 inference freeze missing; no predictions allowed")
    recorded = _json(FREEZE)
    if recorded != _freeze_payload(manifests):
        raise AssertionError("Q15 inference freeze no longer matches verified inputs")
    for path in [*_committed_inputs(manifests), FREEZE]:
        q15_source._assert_committed_unchanged(path)
    return recorded


def load_person(row: dict, dataset: str) -> tuple[dict, pd.DataFrame]:
    """Read only independently hash-locked epochs; never fit a target transform."""
    for file_key, hash_key in (("npz_path", "npz_sha256"), ("metadata_path", "metadata_sha256")):
        if _sha(Path(row[file_key])) != row[hash_key]:
            raise AssertionError("Q15 person artifact changed after gate")
    with np.load(row["npz_path"], allow_pickle=False) as archive:
        if set(archive.files) != {"broad", "mu", "beta"}:
            raise AssertionError("Q15 epoch band set differs")
        arrays = {band: archive[band] for band in archive.files}
    meta = pd.read_csv(row["metadata_path"], dtype={"sample_id": str, "file_id": str,
                                                  "raw_sha256": str, "run": str})
    if any(field not in meta for field in META_FIELDS) or meta.empty or meta.isna().any().any():
        raise AssertionError("Q15 trial metadata missing or empty")
    if len(meta) != row["n_trials"] or meta["sample_id"].duplicated().any():
        raise AssertionError("Q15 trial identity/count drifted")
    if set(meta["subject"]) != {row["subject"]} or sorted(meta["session"].unique()) != DATASETS[dataset][2]:
        raise AssertionError("Q15 person/session scope differs")
    if set(meta["label"]) != {1, 2}:
        raise AssertionError("Q15 person lacks declared binary classes")
    for _, session in meta.groupby("session"):
        if set(session["label"]) != {1, 2}:
            raise AssertionError("Q15 session lacks declared binary classes")
    if not set(meta["file_id"]).issubset(set(row["raw_file_ids"])):
        raise AssertionError("Q15 epoch raw provenance differs")
    if not meta["raw_sha256"].str.fullmatch(r"[0-9a-f]{64}").all():
        raise AssertionError("Q15 raw trial digest absent")
    if not np.issubdtype(meta["cue_sample_native"].dtype, np.integer) or (meta["cue_sample_native"] < 0).any():
        raise AssertionError("Q15 native cue sample invalid")
    for values in arrays.values():
        if values.dtype != np.float32 or values.shape != (len(meta), 21, 320):
            raise AssertionError("Q15 target dtype/shape differs from frozen source")
        if not np.isfinite(values).all():
            raise AssertionError("Q15 target EEG contains nonfinite values")
    return arrays, meta


def _load_source_models(config: dict, device):
    import joblib
    import torch

    deep = {}
    for name in DEEP_MODELS:
        base = SOURCE_OUTPUT / "source" / name / "all_source"
        selection = _json(base / "selection.json")
        for seed in SEEDS:
            payload = torch.load(base / f"final_seed_{seed}" / "checkpoint.pt",
                                 map_location=device, weights_only=True)
            if (payload.get("model"), payload.get("seed"), payload.get("epochs")) != (
                    name, seed, selection["selected_epoch"]):
                raise AssertionError("Q15 checkpoint seed/epoch/model differs")
            model = q15_source._build_model(name, config, device)
            model.load_state_dict(payload["state_dict"], strict=True)
            model.eval()
            deep[name, seed] = model
    csp = joblib.load(SOURCE_OUTPUT / "source/CSP4_LDA/all_source/model.joblib")
    if list(csp.named_steps["lda"].classes_) != [1, 2]:
        raise AssertionError("Q15 frozen CSP binary class order differs")
    return deep, csp


def _state_digest(model) -> str:
    digest = hashlib.sha256()
    for key, value in sorted(model.state_dict().items()):
        digest.update(key.encode())
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def _prediction_frame(meta: pd.DataFrame, dataset: str, name: str, seed,
                      probabilities: np.ndarray) -> pd.DataFrame:
    if probabilities.shape != (len(meta), 2) or not np.isfinite(probabilities).all():
        raise AssertionError("Invalid Q15 probability dimensions or values")
    if (probabilities < 0).any() or (probabilities > 1).any() or not np.allclose(
            probabilities.sum(1), 1, rtol=1e-6, atol=1e-7):
        raise AssertionError("Invalid Q15 probability distribution")
    frame = meta.loc[:, list(META_FIELDS)].copy()
    frame["dataset"], frame["experiment_id"] = dataset, DATASETS[dataset][0]
    frame["model"], frame["seed"] = name, str(seed)
    frame["p_left"], frame["p_right"] = probabilities[:, 0], probabilities[:, 1]
    frame["predicted_label"] = np.argmax(probabilities, axis=1) + 1
    return frame


def predict_person(arrays: dict, meta: pd.DataFrame, dataset: str, deep: dict,
                   csp, config: dict, device) -> pd.DataFrame:
    import torch

    from mi_eeg.models.eegnet_training import predict_probabilities

    parts = []
    for name in DEEP_MODELS:
        values = arrays["broad"] if name == "BROAD_EEGNET" else np.stack(
            [arrays["mu"], arrays["beta"]], axis=1)
        x = torch.from_numpy(values).to(device)
        for seed in SEEDS:
            model = deep[name, seed]
            model.eval()
            before = _state_digest(model)
            probabilities = predict_probabilities(model, x, range(len(meta)), config["batch_size"])
            if _state_digest(model) != before:
                raise AssertionError("Q15 target inference altered frozen model state")
            parts.append(_prediction_frame(meta, dataset, name, seed, probabilities))
        del x
    parts.append(_prediction_frame(meta, dataset, "CSP4_LDA", "deterministic",
                                   csp.predict_proba(arrays["broad"].astype(np.float64))))
    return pd.concat(parts, ignore_index=True)


def validate_prediction_frame(frame: pd.DataFrame, dataset: str,
                              expected_meta: pd.DataFrame | None = None) -> None:
    required = {*META_FIELDS, "dataset", "experiment_id", "model", "seed", "p_left",
                "p_right", "predicted_label"}
    if not required.issubset(frame.columns) or frame.empty or frame[list(required)].isna().any().any():
        raise AssertionError("Q15 prediction schema/coverage invalid")
    if set(frame["dataset"]) != {dataset} or set(frame["experiment_id"]) != {DATASETS[dataset][0]}:
        raise AssertionError("Q15 prediction cohort identity invalid")
    expected_variants = {(name, str(seed)) for name in DEEP_MODELS for seed in SEEDS}
    expected_variants.add(("CSP4_LDA", "deterministic"))
    work = frame.assign(seed=frame["seed"].astype(str))
    if set(zip(work["model"], work["seed"])) != expected_variants:
        raise AssertionError("Q15 prediction model/seed coverage invalid")
    if work.duplicated(["sample_id", "model", "seed"]).any():
        raise AssertionError("Q15 duplicate prediction identity")
    probabilities = work[["p_left", "p_right"]].to_numpy(dtype=float)
    if not np.isfinite(probabilities).all() or (probabilities < 0).any() or (probabilities > 1).any():
        raise AssertionError("Q15 prediction probabilities invalid")
    if not np.allclose(probabilities.sum(1), 1, rtol=1e-6, atol=1e-7):
        raise AssertionError("Q15 prediction probabilities not normalized")
    if not np.array_equal(work["predicted_label"].to_numpy(), probabilities.argmax(1) + 1):
        raise AssertionError("Q15 prediction argmax mismatch")
    if not np.issubdtype(work["subject"].dtype, np.integer) or (work["subject"] <= 0).any():
        raise AssertionError("Q15 prediction person IDs invalid")
    if not np.issubdtype(work["session"].dtype, np.integer):
        raise AssertionError("Q15 prediction session IDs invalid")
    reference = None if expected_meta is None else expected_meta.loc[:, list(META_FIELDS)].sort_values("sample_id").reset_index(drop=True)
    for _, variant in work.groupby(["model", "seed"], sort=True):
        observed = variant.loc[:, list(META_FIELDS)].sort_values("sample_id").reset_index(drop=True)
        if reference is None:
            reference = observed
        if not observed.equals(reference):
            raise AssertionError("Q15 trial metadata differs across frozen seeds/models")
        if set(observed["label"]) != {1, 2}:
            raise AssertionError("Q15 binary prediction class coverage invalid")


def confusion_and_ba(labels, predicted) -> dict:
    labels, predicted = np.asarray(labels), np.asarray(predicted)
    if labels.shape != predicted.shape or labels.ndim != 1 or set(labels) != {1, 2}:
        raise AssertionError("Both binary classes required for balanced accuracy")
    if not set(predicted).issubset({1, 2}):
        raise AssertionError("Unexpected predicted class")
    confusion = np.array([[np.sum((labels == actual) & (predicted == outcome))
                           for outcome in (1, 2)] for actual in (1, 2)], dtype=int)
    recalls = confusion.diagonal() / confusion.sum(1)
    return {"n_trials": len(labels), "confusion_matrix_rows_actual_left_right": confusion.tolist(),
            "left_recall": float(recalls[0]), "right_recall": float(recalls[1]),
            "balanced_accuracy": float(recalls.mean())}


def paired_statistics(differences: np.ndarray) -> dict:
    """Bounded person-level draws; never treat sessions, trials, or seeds as n."""
    values = np.asarray(differences, dtype=np.float64)
    if values.ndim != 1 or len(values) < 2 or not np.isfinite(values).all():
        raise AssertionError("Invalid person-level paired differences")
    if (np.abs(values) > 1).any():
        raise AssertionError("Balanced accuracy difference outside [-1,1]")
    bootstrap = np.empty(STATISTICS["bootstrap_draws"])
    rng = np.random.default_rng(STATISTICS["bootstrap_seed"])
    for first in range(0, len(bootstrap), 1000):
        count = min(1000, len(bootstrap) - first)
        bootstrap[first:first + count] = values[rng.integers(0, len(values),
                                                         size=(count, len(values)))].mean(1)
    rng = np.random.default_rng(STATISTICS["sign_flip_seed"])
    observed = abs(float(values.mean()))
    extreme = 0
    for first in range(0, STATISTICS["sign_flip_draws"], 1000):
        count = min(1000, STATISTICS["sign_flip_draws"] - first)
        signs = 2 * rng.integers(0, 2, size=(count, len(values))) - 1
        extreme += int(np.sum(np.abs((signs * values).mean(1)) >= observed - 1e-15))
    return {"n_persons": len(values), "mean_paired_balanced_accuracy_difference": float(values.mean()),
            "paired_person_bootstrap_percentile_95_ci": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
            "two_sided_person_sign_flip_p_value": (extreme + 1) / (STATISTICS["sign_flip_draws"] + 1),
            "statistics_plan": STATISTICS}


def summarize_cohort(frame: pd.DataFrame, dataset: str) -> dict:
    validate_prediction_frame(frame, dataset)
    expected_people = set(range(1, DATASETS[dataset][1] + 1))
    if set(frame["subject"]) != expected_people:
        raise AssertionError("Q15 cohort person coverage invalid")
    all_people, session_scores = [], []
    for subject in sorted(expected_people):
        person = frame.loc[frame["subject"] == subject]
        if sorted(person["session"].unique()) != DATASETS[dataset][2]:
            raise AssertionError("Q15 declared sessions missing from person")
        models = {}
        for name in ALL_MODELS:
            seeds = list(SEEDS) if name in DEEP_MODELS else ["deterministic"]
            per_seed = {}
            for seed in seeds:
                part = person.loc[(person["model"] == name) & (person["seed"].astype(str) == str(seed))]
                if part.empty:
                    raise AssertionError("Q15 person model/seed missing")
                per_seed[str(seed)] = confusion_and_ba(part["label"], part["predicted_label"])
                for session, session_part in part.groupby("session"):
                    session_scores.append({"subject": subject, "session": int(session), "model": name,
                                           "seed": str(seed), **confusion_and_ba(
                                               session_part["label"], session_part["predicted_label"])})
            values = np.array([score["balanced_accuracy"] for score in per_seed.values()])
            models[name] = {"within_person_seed_mean_balanced_accuracy": float(values.mean()),
                            "seed_sample_standard_deviation": float(values.std(ddof=1)) if len(values) > 1 else None,
                            "per_seed": per_seed}
        difference = models["MU_BETA_SHARED"]["within_person_seed_mean_balanced_accuracy"] - models["BROAD_EEGNET"]["within_person_seed_mean_balanced_accuracy"]
        all_people.append({"subject": subject, "models": models, "primary_paired_difference": difference})
    primary = paired_statistics(np.array([row["primary_paired_difference"] for row in all_people]))
    return {"schema_version": 1, "dataset": dataset, "experiment_id": DATASETS[dataset][0],
            "status": "descriptive_statistics_pending_independent_raw_prediction_replay",
            "target_fits": 0, "new_model_fits": 0,
            "n_persons": len(all_people), "n_sessions": sum(len(DATASETS[dataset][2]) for _ in all_people),
            "cohort_equal_person_mean_balanced_accuracy": {
                name: float(np.mean([row["models"][name]["within_person_seed_mean_balanced_accuracy"]
                                     for row in all_people])) for name in ALL_MODELS},
            "primary_contrast": primary, "persons": all_people, "session_strata": session_scores}


def holm_two_cohorts(summaries: dict[str, dict]) -> dict:
    if set(summaries) != set(DATASETS):
        raise AssertionError("Holm family requires both predeclared Q15 cohorts")
    ordered = sorted((summary["primary_contrast"]["two_sided_person_sign_flip_p_value"], dataset)
                     for dataset, summary in summaries.items())
    result, maximum = {}, 0.0
    for rank, (value, dataset) in enumerate(ordered):
        if not np.isfinite(value) or not 0 <= value <= 1:
            raise AssertionError("Invalid family p value")
        maximum = max(maximum, min(1.0, (2 - rank) * value))
        result[dataset] = {"uncorrected_two_sided_p_value": value, "holm_adjusted_p_value": maximum}
    return {"family": ["Q15-E006", "Q15-E007"], "method": "Holm", "cohorts": result,
            "status": "pending_independent_raw_prediction_replay"}


def run_external(manifests: dict[str, Path], device_name: str) -> dict:
    verify_freeze(manifests)  # Before importing models or opening target epoch arrays.
    import torch

    freeze_sha = _sha(FREEZE)
    config = q15_source.derive_config()
    device = torch.device(device_name)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    deep, csp = _load_source_models(config, device)
    summaries = {}
    for dataset in DATASETS:
        manifest = _json(manifests[dataset])
        root = OUTPUT / DATASETS[dataset][0]
        frames = []
        for row in sorted(manifest["subjects"], key=lambda item: item["subject"]):
            arrays, meta = load_person(row, dataset)
            directory = root / f"subject_{row['subject']:03d}"
            prediction = directory / "predictions.csv"
            receipt_file = directory / "receipt.json"
            expected = {"status": "complete_pending_independent_raw_prediction_replay",
                        "dataset": dataset, "subject": row["subject"],
                        "inference_freeze_sha256": freeze_sha, "npz_sha256": row["npz_sha256"],
                        "metadata_sha256": row["metadata_sha256"], "target_fits": 0,
                        "new_model_fits": 0, "n_trials": len(meta), "n_prediction_rows": 7 * len(meta)}
            if receipt_file.exists():
                receipt = _json(receipt_file)
                if any(receipt.get(key) != value for key, value in expected.items()) or not prediction.is_file() or receipt.get("predictions_sha256") != _sha(prediction):
                    raise AssertionError("Existing Q15 predictions mismatch/corrupt; resume blocked")
                frame = pd.read_csv(prediction, dtype={"seed": str, "sample_id": str, "run": str,
                                                       "file_id": str, "raw_sha256": str},
                                    float_precision="round_trip")
            else:
                if prediction.exists():
                    raise AssertionError("Unreceipted Q15 prediction output exists; resume blocked")
                frame = predict_person(arrays, meta, dataset, deep, csp, config, device)
                validate_prediction_frame(frame, dataset, meta)
                q15_source.q14_source.atomic_csv(prediction, frame)
                _atomic_json(receipt_file, {**expected, "predictions_sha256": _sha(prediction)})
            validate_prediction_frame(frame, dataset, meta)
            frames.append(frame)
            print(json.dumps({"stage": "external_person_complete", "dataset": dataset,
                              "subject": row["subject"], "target_fits": 0}), flush=True)
        aggregate = pd.concat(frames, ignore_index=True)
        q15_source.q14_source.atomic_csv(root / "predictions.csv", aggregate)
        summaries[dataset] = summarize_cohort(aggregate, dataset)
        _atomic_json(root / "statistics.json", summaries[dataset])
    _atomic_json(OUTPUT / "holm_two_cohorts.json", holm_two_cohorts(summaries))
    completion = {"schema_version": 1, "status": "inference_complete_pending_independent_raw_prediction_replay",
                  "target_fits": 0, "new_model_fits": 0, "scientific_validation_passed": False,
                  "inference_freeze_sha256": freeze_sha, "statistics_plan": STATISTICS,
                  "cohort_prediction_sha256": {dataset: _sha(OUTPUT / DATASETS[dataset][0] / "predictions.csv") for dataset in DATASETS},
                  "cohort_statistics_sha256": {dataset: _sha(OUTPUT / DATASETS[dataset][0] / "statistics.json") for dataset in DATASETS},
                  "holm_sha256": _sha(OUTPUT / "holm_two_cohorts.json"),
                  "completed_at_utc": datetime.now(UTC).isoformat()}
    _atomic_json(OUTPUT / "completion_receipt.json", completion)
    return completion


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cho-manifest", type=Path, required=True)
    parser.add_argument("--lee-manifest", type=Path, required=True)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--prepare-freeze", action="store_true")
    action.add_argument("--execute", action="store_true")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    args = parser.parse_args()
    manifests = {"Cho2017": args.cho_manifest.resolve(), "Lee2019_MI": args.lee_manifest.resolve()}
    if args.prepare_freeze:
        print(prepare_freeze(manifests))
    elif args.execute:
        print(json.dumps(run_external(manifests, args.device)))
    else:
        verify_freeze(manifests)
        print(json.dumps({"status": "inference_freeze_verified_no_predictions", "target_fits": 0,
                          "new_model_fits": 0, "predictions_computed": False}))


if __name__ == "__main__":
    main()
