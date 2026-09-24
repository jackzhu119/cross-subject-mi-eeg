"""Q10-A001: fixed source-only log-Euclidean covariance comparators.

This is an explicitly *log-Euclidean* implementation, not affine-invariant
pyRiemann MDM/tangent space. No target-subject label or statistic enters fit.
The command has atomic per-attempt receipts and a read-only validation mode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
import traceback
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import scipy
import sklearn
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "research_runs/Q10-A001/MATRIX.json"
Q8_METADATA = ROOT / "research_runs/Q8-E001/results/trial_metadata.csv"
Q8_SOURCES = ROOT / "research_runs/Q8-E001/results/source_files.json"
IDENTITY_COLUMNS = [
    "sample_id", "subject", "session", "run", "trial", "label", "event_sample",
    "artifact_flagged",
]
CLASSES = np.array([1, 2, 3, 4], dtype=np.int64)
EXPECTED_CONDITIONS = (
    "BROAD_LOGE_MDM", "BROAD_LOGE_LOGREG", "MUBETA_LOGE_LDA", "MUBETA_LOGE_SVM",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_array(array: np.ndarray) -> str:
    arr = np.ascontiguousarray(array, dtype="<f8")
    return hashlib.sha256(arr.tobytes()).hexdigest()


def sha256_ids(sample_ids: list[str]) -> str:
    digest = hashlib.sha256()
    for sample_id in sample_ids:
        encoded = sample_id.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _atomic_bytes(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def atomic_json(path: Path, content: object) -> None:
    _atomic_bytes(path, (json.dumps(content, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    _atomic_bytes(path, frame.to_csv(index=False, float_format="%.12g").encode("utf-8"))


def atomic_joblib(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(fd)
    try:
        joblib.dump(obj, name, compress=3, protocol=4)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def read_matrix(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("experiment_id") != "Q10-A001":
        raise ValueError("Wrong experiment ID")
    if config.get("subjects") != list(range(1, 10)):
        raise ValueError("Q10 requires the frozen nine-subject cohort")
    if [c["id"] for c in config["conditions"]] != list(EXPECTED_CONDITIONS):
        raise ValueError("Condition matrix changed; freeze a new experiment ID")
    if config["preprocessing"]["artifact_policy"] != "include_all":
        raise ValueError("Q10 must retain the Q8 include-all trial population")
    if config["evaluation"]["target_fitted_transform"] is not False:
        raise ValueError("Target-fitted transform is forbidden")
    return config


def read_q8_metadata(config: dict, q8_path: Path = Q8_METADATA) -> pd.DataFrame:
    if sha256_file(q8_path) != config["q8_trial_metadata_sha256"]:
        raise AssertionError("Frozen Q8 trial metadata SHA256 mismatch")
    q8 = pd.read_csv(q8_path)
    if list(q8.columns) != IDENTITY_COLUMNS or len(q8) != 5184:
        raise AssertionError("Unexpected Q8 trial metadata schema/count")
    if q8.sample_id.duplicated().any():
        raise AssertionError("Duplicate Q8 trial IDs")
    return q8


def assert_q8_identity(meta: pd.DataFrame, q8: pd.DataFrame) -> None:
    """Check exact ordered trial/label/session/artifact identity, not just counts."""
    if not set(IDENTITY_COLUMNS).issubset(meta):
        raise AssertionError("Loaded metadata lacks Q8 identity columns")
    left = meta[IDENTITY_COLUMNS].reset_index(drop=True).astype(str)
    right = q8[IDENTITY_COLUMNS].reset_index(drop=True).astype(str)
    if not left.equals(right):
        raise AssertionError("Loaded trial metadata differs from frozen Q8 identity")
    if len(meta) != 5184 or meta.sample_id.duplicated().any():
        raise AssertionError("Q10 requires exactly 5,184 distinct trials")
    for subject in range(1, 10):
        rows = meta.loc[meta.subject == subject]
        if len(rows) != 576 or sorted(rows.label.value_counts().tolist()) != [144] * 4:
            raise AssertionError(f"Subject {subject} class/trial count differs from Q8")


def verify_raw_mat_hashes(data_dir: Path, reference_path: Path = Q8_SOURCES) -> list[dict]:
    """Match Q8's 18 public MAT files by basename, byte size and SHA256."""
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    expected = {Path(record["path"]).name: record for record in reference}
    if len(expected) != 18:
        raise AssertionError("Q8 source-file manifest must identify 18 unique MAT files")
    records = []
    for basename, record in sorted(expected.items()):
        matches = list(data_dir.rglob(basename))
        if len(matches) != 1:
            raise AssertionError(f"Expected exactly one {basename} below {data_dir}")
        path = matches[0]
        size = path.stat().st_size
        digest = sha256_file(path)
        if size != int(record["bytes"]) or digest != record["sha256"]:
            raise AssertionError(f"Raw file {basename} differs from frozen Q8 source")
        records.append({"basename": basename, "bytes": size, "sha256": digest})
    return records


def logcov_features(trials: np.ndarray, shrinkage: float, *, chunk_size: int = 128) -> np.ndarray:
    """Trial-wise, fixed log-Euclidean SPD features with Frobenius vectorization.

    Every trial is transformed independently. No cross-trial or target-derived
    reference/scaling is estimated here; those are fit inside each LOSO fold.
    """
    trials = np.asarray(trials)
    if trials.ndim != 3 or trials.shape[2] < 2:
        raise ValueError("Expected trials × channels × time, with at least two samples")
    if not 0 < shrinkage < 1 or chunk_size < 1:
        raise ValueError("Invalid covariance shrinkage/chunk size")
    if not np.isfinite(trials).all():
        raise ValueError("Nonfinite EEG values")
    n_trials, n_channels, n_times = trials.shape
    upper = np.triu_indices(n_channels)
    weights = np.where(upper[0] == upper[1], 1.0, math.sqrt(2.0))
    output = np.empty((n_trials, len(upper[0])), dtype=np.float64)
    eye = np.eye(n_channels, dtype=np.float64)
    for start in range(0, n_trials, chunk_size):
        stop = min(start + chunk_size, n_trials)
        block = np.asarray(trials[start:stop], dtype=np.float64).copy()
        block -= block.mean(axis=2, keepdims=True)
        covariance = np.matmul(block, block.transpose(0, 2, 1)) / (n_times - 1)
        trace_scale = np.trace(covariance, axis1=1, axis2=2) / n_channels
        covariance *= 1.0 - shrinkage
        covariance += (shrinkage * trace_scale)[:, None, None] * eye
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        if not np.isfinite(eigenvalues).all() or np.any(eigenvalues <= 0):
            raise FloatingPointError("Covariance is not strictly positive definite")
        logm = (eigenvectors * np.log(eigenvalues)[:, None, :]) @ eigenvectors.transpose(0, 2, 1)
        output[start:stop] = logm[:, upper[0], upper[1]] * weights
    if not np.isfinite(output).all():
        raise FloatingPointError("Nonfinite log covariance")
    return output


def softmax(scores: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=np.float64)
    shifted = scores - scores.max(axis=1, keepdims=True)
    exp_scores = np.exp(shifted)
    return exp_scores / exp_scores.sum(axis=1, keepdims=True)


def fit_predict_source_only(
    source_features: np.ndarray,
    source_labels: np.ndarray,
    target_features: np.ndarray,
    condition: dict,
) -> tuple[np.ndarray, object, dict]:
    """Fit without access to target labels, IDs, artifacts or per-target statistics."""
    train = np.asarray(source_features, dtype=np.float64)
    test = np.asarray(target_features, dtype=np.float64)
    y = np.asarray(source_labels, dtype=np.int64)
    if train.ndim != 2 or test.ndim != 2 or train.shape[1] != test.shape[1]:
        raise ValueError("Source/target geometry feature dimensions differ")
    if not np.isfinite(train).all() or not np.isfinite(test).all():
        raise ValueError("Nonfinite geometry features")
    if not np.array_equal(np.unique(y), CLASSES):
        raise ValueError("All four classes are required in source training")
    classifier = condition["classifier"]
    if classifier == "log_euclidean_nearest_class_mean":
        class_means = np.stack([train[y == label].mean(axis=0) for label in CLASSES])
        own_class = np.searchsorted(CLASSES, y)
        within = np.sum((train - class_means[own_class]) ** 2, axis=1)
        temperature = max(float(np.median(within)), np.finfo(float).tiny)
        squared_distance = np.sum((test[:, None, :] - class_means[None, :, :]) ** 2, axis=2)
        probabilities = softmax(-squared_distance / temperature)
        model = {"class_means": class_means, "temperature": temperature, "classes": CLASSES}
        fitted = {
            "geometry_source_class_means_sha256": sha256_array(class_means),
            "source_only_similarity_temperature": temperature,
            "probability_semantics": "uncalibrated_normalized_similarity",
        }
    else:
        # The log-Euclidean reference and StandardScaler see source trials only.
        reference = train.mean(axis=0)
        scaler = StandardScaler().fit(train - reference)
        x_source = scaler.transform(train - reference)
        x_target = scaler.transform(test - reference)
        if classifier == "multinomial_logistic_regression":
            estimator = LogisticRegression(
                C=float(condition["C"]), solver=condition["solver"],
                max_iter=int(condition["max_iter"]), tol=float(condition["tol"]),
            )
        elif classifier == "shrinkage_lda":
            estimator = LinearDiscriminantAnalysis(
                solver=condition["solver"], shrinkage=condition["shrinkage"]
            )
        elif classifier == "linear_svc_with_libsvm_source_only_probability_calibration":
            estimator = SVC(
                kernel="linear", C=float(condition["C"]), probability=True,
                random_state=int(condition["random_state"]),
            )
        else:
            raise ValueError(f"Unknown fixed Q10 classifier: {classifier}")
        estimator.fit(x_source, y)
        if not np.array_equal(estimator.classes_, CLASSES):
            raise AssertionError("Fitted classifier class order changed")
        probabilities = estimator.predict_proba(x_target)
        model = {"reference": reference, "scaler": scaler, "estimator": estimator}
        fitted = {
            "source_reference_sha256": sha256_array(reference),
            "source_scaler_mean_sha256": sha256_array(scaler.mean_),
            "source_scaler_scale_sha256": sha256_array(scaler.scale_),
            "probability_semantics": (
                "source_only_libsvm_cv_calibrated" if isinstance(estimator, SVC)
                else "classifier_predict_proba"
            ),
        }
    probabilities = np.asarray(probabilities, dtype=np.float64)
    if probabilities.shape != (len(test), 4) or not np.isfinite(probabilities).all():
        raise AssertionError("Invalid four-class probability dimensions/values")
    if np.any(probabilities < 0) or not np.allclose(probabilities.sum(axis=1), 1, atol=1e-7):
        raise AssertionError("Probabilities are negative or fail to sum to one")
    return probabilities, model, fitted


def classification_metrics(truth: np.ndarray, prediction: np.ndarray) -> dict:
    return {
        "balanced_accuracy": float(balanced_accuracy_score(truth, prediction)),
        "accuracy": float(accuracy_score(truth, prediction)),
        "macro_f1": float(f1_score(truth, prediction, labels=CLASSES, average="macro", zero_division=0)),
    }


def source_target_indices(meta: pd.DataFrame, target: int) -> tuple[np.ndarray, np.ndarray]:
    source = np.flatnonzero(meta.subject.to_numpy() != target)
    test = np.flatnonzero(meta.subject.to_numpy() == target)
    if len(source) != 4608 or len(test) != 576:
        raise AssertionError("LOSO must contain 4,608 source and 576 target trials")
    if target in set(meta.iloc[source].subject) or len(set(meta.iloc[source].subject)) != 8:
        raise AssertionError("Target leaked into source training")
    return source, test


def expected_attempt_dir(output: Path, condition_id: str, target: int) -> Path:
    return output / "folds" / condition_id / f"loso_s{target}"


def find_complete_attempt(output: Path, condition_id: str, target: int) -> Path | None:
    fold_dir = expected_attempt_dir(output, condition_id, target)
    complete = []
    for attempt in sorted(fold_dir.glob("attempt_*")):
        status_file = attempt / "status.json"
        if not status_file.exists():
            continue
        status = json.loads(status_file.read_text(encoding="utf-8"))
        if status.get("status") == "complete":
            complete.append(attempt)
    if len(complete) > 1:
        raise AssertionError(f"More than one complete attempt for {condition_id}/S{target}")
    return complete[0] if complete else None


def next_attempt_dir(output: Path, condition_id: str, target: int) -> Path:
    fold_dir = expected_attempt_dir(output, condition_id, target)
    fold_dir.mkdir(parents=True, exist_ok=True)
    existing = list(fold_dir.glob("attempt_*"))
    numbered = [int(p.name.split("_")[1]) for p in existing if p.name.split("_")[-1].isdigit()]
    attempt = fold_dir / f"attempt_{max(numbered, default=0) + 1:03d}"
    attempt.mkdir()
    return attempt


def initialize_output(output: Path, config: dict, *, resume: bool) -> dict:
    config_sha = sha256_file(MATRIX)
    code_sha = sha256_file(Path(__file__))
    if output.exists() and any(output.iterdir()):
        if not resume:
            raise FileExistsError("Output exists; pass --resume to preserve all attempts")
        if not (output / "config.json").is_file() or sha256_file(output / "config.json") != config_sha:
            raise AssertionError("Existing output configuration differs from frozen Q10 matrix")
        provenance = json.loads((output / "provenance.json").read_text(encoding="utf-8"))
        if provenance["runner_sha256"] != code_sha:
            raise AssertionError("Runner changed since this output started; use a new experiment ID")
        if provenance["q8_metadata_sha256"] != config["q8_trial_metadata_sha256"]:
            raise AssertionError("Q8 metadata declaration changed")
        return provenance
    output.mkdir(parents=True, exist_ok=True)
    _atomic_bytes(output / "config.json", MATRIX.read_bytes())
    provenance = {
        "experiment_id": "Q10-A001",
        "created_utc": utc_now(),
        "matrix_sha256": config_sha,
        "runner_sha256": code_sha,
        "q8_metadata_sha256": sha256_file(Q8_METADATA),
        "q8_source_manifest_sha256": sha256_file(Q8_SOURCES),
        "versions": {
            "python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__,
            "pandas": pd.__version__, "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
        "target_fitted_transform": False,
    }
    atomic_json(output / "provenance.json", provenance)
    atomic_json(output / "status.json", {"status": "running", "completed_outer_fits": 0, "expected_outer_fits": 36})
    return provenance


def write_attempt(
    output: Path,
    condition: dict,
    target: int,
    features: dict[str, np.ndarray],
    meta: pd.DataFrame,
    provenance: dict,
) -> Path:
    condition_id = condition["id"]
    source, test = source_target_indices(meta, target)
    attempt = next_attempt_dir(output, condition_id, target)
    atomic_json(attempt / "status.json", {
        "status": "running", "condition": condition_id, "target_subject": target,
        "started_utc": utc_now(),
    })
    try:
        all_features = np.concatenate([features[band] for band in condition["bands"]], axis=1)
        source_subjects = sorted(int(v) for v in meta.iloc[source].subject.unique())
        # The fit function has no target labels or target metadata argument.
        probabilities, fitted_model, fitted_receipt = fit_predict_source_only(
            all_features[source], meta.iloc[source].label.to_numpy(dtype=np.int64),
            all_features[test], condition,
        )
        predictions = meta.iloc[test][IDENTITY_COLUMNS].copy().reset_index(drop=True)
        predictions.insert(0, "experiment_id", "Q10-A001")
        predictions.insert(1, "condition", condition_id)
        predictions["fold"] = f"loso_s{target}"
        predictions["y_true"] = predictions.label.astype(int)
        predictions["y_pred"] = CLASSES[np.argmax(probabilities, axis=1)]
        for class_index, class_id in enumerate(CLASSES):
            predictions[f"p_class_{class_id}"] = probabilities[:, class_index]
        truth = predictions.y_true.to_numpy(dtype=np.int64)
        prediction = predictions.y_pred.to_numpy(dtype=np.int64)
        metrics = classification_metrics(truth, prediction)
        matrix = confusion_matrix(truth, prediction, labels=CLASSES)
        confusion = pd.DataFrame([
            {"condition": condition_id, "subject": target, "true_class": int(a),
             "predicted_class": int(b), "count": int(matrix[i, j])}
            for i, a in enumerate(CLASSES) for j, b in enumerate(CLASSES)
        ])
        atomic_joblib(attempt / "model.joblib", fitted_model)
        atomic_csv(attempt / "predictions.csv", predictions)
        atomic_json(attempt / "metrics.json", {
            "experiment_id": "Q10-A001", "condition": condition_id, "subject": target,
            "n_source": 4608, "n_target": 576, **metrics,
        })
        atomic_csv(attempt / "confusion.csv", confusion)
        receipt = {
            "experiment_id": "Q10-A001",
            "condition": condition_id,
            "target_subject": target,
            "source_subjects": source_subjects,
            "n_source_trials": len(source),
            "n_target_trials": len(test),
            "ordered_source_sample_ids_sha256": sha256_ids(meta.iloc[source].sample_id.tolist()),
            "ordered_target_sample_ids_sha256": sha256_ids(meta.iloc[test].sample_id.tolist()),
            "bands": condition["bands"],
            "classifier": condition["classifier"],
            "fit_scope": "source_subjects_only",
            "target_fitted_transform": False,
            "target_label_based_selection": False,
            "prediction_rule": "argmax_probability",
            "model_sha256": sha256_file(attempt / "model.joblib"),
            "matrix_sha256": provenance["matrix_sha256"],
            "runner_sha256": provenance["runner_sha256"],
            **fitted_receipt,
        }
        atomic_json(attempt / "receipt.json", receipt)
        atomic_json(attempt / "status.json", {
            "status": "complete", "condition": condition_id, "target_subject": target,
            "finished_utc": utc_now(), "balanced_accuracy": metrics["balanced_accuracy"],
            "model_sha256": receipt["model_sha256"],
        })
        return attempt
    except Exception as exc:
        # Preserve the error and any partial attempt; never reinterpret failure as a negative BA.
        atomic_json(attempt / "status.json", {
            "status": "failed", "condition": condition_id, "target_subject": target,
            "failed_utc": utc_now(), "error_type": type(exc).__name__,
            "error": str(exc), "traceback": traceback.format_exc(),
        })
        raise


def validate_attempt(
    attempt: Path, condition: dict, target: int, q8: pd.DataFrame, provenance: dict,
) -> tuple[pd.DataFrame, dict, pd.DataFrame, dict]:
    required = ["status.json", "receipt.json", "model.joblib", "predictions.csv", "metrics.json", "confusion.csv"]
    missing = [name for name in required if not (attempt / name).is_file()]
    if missing:
        raise AssertionError(f"{attempt}: missing {missing}")
    status = json.loads((attempt / "status.json").read_text(encoding="utf-8"))
    receipt = json.loads((attempt / "receipt.json").read_text(encoding="utf-8"))
    metrics = json.loads((attempt / "metrics.json").read_text(encoding="utf-8"))
    predictions = pd.read_csv(attempt / "predictions.csv")
    confusion = pd.read_csv(attempt / "confusion.csv")
    condition_id = condition["id"]
    source_subjects = [subject for subject in range(1, 10) if subject != target]
    source_ids = q8.loc[q8.subject != target, "sample_id"].tolist()
    target_q8 = q8.loc[q8.subject == target, IDENTITY_COLUMNS].reset_index(drop=True)
    if status.get("status") != "complete" or receipt.get("condition") != condition_id:
        raise AssertionError(f"{attempt}: incomplete or incorrect condition")
    if status.get("target_subject") != target or receipt.get("target_subject") != target:
        raise AssertionError(f"{attempt}: wrong target subject")
    if receipt.get("source_subjects") != source_subjects or receipt.get("n_source_trials") != 4608:
        raise AssertionError(f"{attempt}: incorrect source population")
    if receipt.get("n_target_trials") != 576 or receipt.get("target_fitted_transform") is not False:
        raise AssertionError(f"{attempt}: target-fitting or target-count violation")
    if receipt.get("target_label_based_selection") is not False:
        raise AssertionError(f"{attempt}: target-based selection declaration violation")
    if receipt.get("ordered_source_sample_ids_sha256") != sha256_ids(source_ids):
        raise AssertionError(f"{attempt}: source trial ID hash mismatch")
    if receipt.get("ordered_target_sample_ids_sha256") != sha256_ids(target_q8.sample_id.tolist()):
        raise AssertionError(f"{attempt}: target trial ID hash mismatch")
    if receipt.get("matrix_sha256") != provenance["matrix_sha256"]:
        raise AssertionError(f"{attempt}: matrix SHA mismatch")
    if receipt.get("runner_sha256") != provenance["runner_sha256"]:
        raise AssertionError(f"{attempt}: runner SHA mismatch")
    if receipt.get("model_sha256") != sha256_file(attempt / "model.joblib"):
        raise AssertionError(f"{attempt}: fitted model SHA mismatch")
    if len(predictions) != 576 or predictions.sample_id.duplicated().any():
        raise AssertionError(f"{attempt}: wrong prediction count or duplicate trials")
    if not predictions[IDENTITY_COLUMNS].astype(str).equals(target_q8.astype(str)):
        raise AssertionError(f"{attempt}: prediction/Q8 trial identity mismatch")
    if not predictions.condition.eq(condition_id).all() or not predictions.fold.eq(f"loso_s{target}").all():
        raise AssertionError(f"{attempt}: wrong prediction condition/fold")
    y_true = predictions.y_true.to_numpy(dtype=np.int64)
    y_pred = predictions.y_pred.to_numpy(dtype=np.int64)
    if not np.array_equal(y_true, target_q8.label.to_numpy(dtype=np.int64)):
        raise AssertionError(f"{attempt}: true labels differ from Q8")
    probs = predictions[[f"p_class_{label}" for label in CLASSES]].to_numpy(dtype=np.float64)
    if not np.isfinite(probs).all() or np.any(probs < 0) or not np.allclose(probs.sum(axis=1), 1, atol=1e-7):
        raise AssertionError(f"{attempt}: invalid probabilities")
    if not np.array_equal(y_pred, CLASSES[np.argmax(probs, axis=1)]):
        raise AssertionError(f"{attempt}: y_pred is not probability argmax")
    recomputed = classification_metrics(y_true, y_pred)
    for metric, value in recomputed.items():
        if not math.isclose(float(metrics[metric]), value, rel_tol=0, abs_tol=1e-10):
            raise AssertionError(f"{attempt}: {metric} differs from predictions")
    observed_matrix = confusion.pivot(index="true_class", columns="predicted_class", values="count")
    expected_matrix = confusion_matrix(y_true, y_pred, labels=CLASSES)
    if not np.array_equal(observed_matrix.loc[CLASSES, CLASSES].to_numpy(), expected_matrix):
        raise AssertionError(f"{attempt}: confusion matrix differs from predictions")
    return predictions, metrics, confusion, receipt


def validate_run(output: Path) -> dict:
    """Validate every declared LOSO cell before marking the run complete."""
    config = read_matrix(MATRIX)
    q8 = read_q8_metadata(config)
    if not (output / "config.json").is_file() or sha256_file(output / "config.json") != sha256_file(MATRIX):
        raise AssertionError("Q10-A001 saved configuration differs from the frozen matrix")
    provenance_path = output / "provenance.json"
    if not provenance_path.is_file():
        raise AssertionError("Missing Q10-A001 provenance")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if provenance.get("matrix_sha256") != sha256_file(MATRIX):
        raise AssertionError("Q10-A001 matrix hash changed")
    if provenance.get("runner_sha256") != sha256_file(Path(__file__)):
        raise AssertionError("Q10-A001 runner hash changed")
    if provenance.get("q8_source_manifest_sha256") != sha256_file(Q8_SOURCES):
        raise AssertionError("Q8 source manifest changed")

    prediction_frames: list[pd.DataFrame] = []
    metric_rows: list[dict] = []
    confusion_frames: list[pd.DataFrame] = []
    receipt_rows: list[dict] = []
    for condition in config["conditions"]:
        for target in range(1, 10):
            attempt = find_complete_attempt(output, condition["id"], target)
            if attempt is None:
                raise AssertionError(f"Missing completed fit {condition['id']}/S{target}")
            predictions, metrics, confusion, receipt = validate_attempt(
                attempt, condition, target, q8, provenance
            )
            prediction_frames.append(predictions)
            metric_rows.append(metrics)
            confusion_frames.append(confusion)
            receipt_rows.append({
                "condition": condition["id"], "target_subject": target,
                "attempt": str(attempt.relative_to(output)).replace("\\", "/"),
                "model_sha256": receipt["model_sha256"],
                "ordered_source_sample_ids_sha256": receipt["ordered_source_sample_ids_sha256"],
                "ordered_target_sample_ids_sha256": receipt["ordered_target_sample_ids_sha256"],
            })
    predictions = pd.concat(prediction_frames, ignore_index=True)
    if len(predictions) != 4 * 5184:
        raise AssertionError("Q10-A001 prediction inventory is incomplete")
    metrics = pd.DataFrame(metric_rows)
    if len(metrics) != 36 or metrics.groupby("condition").size().tolist() != [9] * 4:
        raise AssertionError("Q10-A001 fit metrics inventory is incomplete")
    summary = (metrics.groupby("condition").balanced_accuracy
               .agg(["mean", "std", "min", "max"]).reset_index())
    atomic_csv(output / "predictions.csv", predictions)
    atomic_csv(output / "subject_metrics.csv", metrics)
    atomic_csv(output / "confusion_matrices.csv", pd.concat(confusion_frames, ignore_index=True))
    atomic_csv(output / "summary.csv", summary)
    atomic_csv(output / "completion_receipts.csv", pd.DataFrame(receipt_rows))
    report = {
        "experiment_id": "Q10-A001",
        "status": "passed_scientific_artifact_validation",
        "scope": "complete_fit_receipts_and_prediction_level_recalculation_not_external_confirmation",
        "outer_fits_validated": 36,
        "prediction_rows_validated": len(predictions),
        "conditions": [condition["id"] for condition in config["conditions"]],
        "target_fitted_transform": False,
        "q8_metadata_sha256": sha256_file(Q8_METADATA),
    }
    atomic_json(output / "validation_report.json", report)
    atomic_json(output / "status.json", {
        "status": "complete_validated", "completed_outer_fits": 36,
        "expected_outer_fits": 36, "finished_utc": utc_now(),
    })
    return report


def run_experiment(data_dir: Path, output: Path, *, resume: bool) -> dict:
    """Run 36 fixed outer fits, preserving all failed attempts on resume."""
    config = read_matrix(MATRIX)
    q8 = read_q8_metadata(config)
    provenance = initialize_output(output, config, resume=resume)
    raw_files = verify_raw_mat_hashes(data_dir)
    if len(raw_files) != 18:
        raise AssertionError("Expected exactly 18 source MAT files")

    # The existing loader implements the same run-local Q8 filtering and
    # trial identity.  No transform parameter is learned from a target cohort.
    sys.path.insert(0, str(ROOT / "src"))
    from mi_eeg.data.bnci_epochs import load_configured_epochs

    with threadpool_limits(limits=2):
        raw_bands, meta, audit = load_configured_epochs(
            config["subjects"], data_dir, config["preprocessing"], config["class_ids"]
        )
        assert_q8_identity(meta, q8)
        if int(meta.artifact_flagged.sum()) != 488:
            raise AssertionError("Q8 artifact-flag population changed")
        if list(raw_bands) != ["broad", "mu", "beta"]:
            raise AssertionError("Q10-A001 band order changed")
        atomic_csv(output / "data_audit.csv", audit)
        features = {
            name: logcov_features(
                values.astype(np.float64) * 1_000_000.0,
                float(config["geometry"]["shrinkage_to_scaled_identity"]),
                chunk_size=int(config["geometry"]["feature_chunk_trials"]),
            )
            for name, values in raw_bands.items()
        }
        del raw_bands
        for condition in config["conditions"]:
            for target in range(1, 10):
                complete = find_complete_attempt(output, condition["id"], target)
                if complete is not None:
                    validate_attempt(complete, condition, target, q8, provenance)
                    print(f"{condition['id']} S{target}: validated resume", flush=True)
                    continue
                write_attempt(output, condition, target, features, meta, provenance)
                count = sum(
                    find_complete_attempt(output, c["id"], subject) is not None
                    for c in config["conditions"] for subject in range(1, 10)
                )
                atomic_json(output / "status.json", {
                    "status": "running", "completed_outer_fits": count,
                    "expected_outer_fits": 36, "updated_utc": utc_now(),
                })
                print(f"{condition['id']} S{target}: complete ({count}/36)", flush=True)
    return validate_run(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run all 36 fixed LOSO source fits")
    run.add_argument("--data-dir", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, default=ROOT / "results/Q10-A001")
    run.add_argument("--resume", action="store_true")
    validate = sub.add_parser("validate", help="independently validate saved fits")
    validate.add_argument("--output-dir", type=Path, default=ROOT / "results/Q10-A001")
    args = parser.parse_args()
    result = (run_experiment(args.data_dir, args.output_dir, resume=args.resume)
              if args.command == "run" else validate_run(args.output_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
