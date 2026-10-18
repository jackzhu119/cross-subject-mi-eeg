"""Fixed traditional source-only CSP + shrinkage LDA comparator.

This is a conventional comparator, not an additional neural selector. There is
one fit per prespecified source population and seed. It accepts source inputs
only, never selects hyperparameters, and has no target-fitting API.

CAR18 has rank at most 17. A fixed scipy.linalg.helmert(18, full=False)
projection removes its constant direction before CSP. Each source trial supplies
a trace-normalized covariance. Class covariance averages give equal weight to
people within each source cohort and then equal weight to cohorts. Both class
covariances receive fixed 0.1 trace-scaled spherical shrinkage. The two smallest
and two largest generalized eigenvectors provide four CSP components.

LDA uses sklearn's standard lsqr solver, automatic Ledoit-Wolf shrinkage, and
equal class priors. Since its fit API has no sample weights, a frozen 8192-row
source feature resample balances cohort/class cells exactly and people within
each cell to within one row, drawing trials with replacement. These repeated
rows are training weights in an approximation, not new independent EEG trials.

References for the implementations:
https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.helmert.html
https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.eigh.html
https://scikit-learn.org/stable/modules/generated/sklearn.discriminant_analysis.LinearDiscriminantAnalysis.html
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

import numpy as np
import scipy
from scipy.linalg import eigh, helmert
from scipy.special import expit
import sklearn
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis


CONTRACT = {
    "pipeline": "CSP_LDA",
    "selector": "fixed",
    "input": "same_fresh18_dimensionless_broad_view_as_neural_pipelines",
    "channels": 18,
    "n_times": 320,
    "fixed_projection": "scipy.linalg.helmert(18,full=False)",
    "projected_rank": 17,
    "trial_covariance": "temporally_centered_outer_product_divided_by_its_trace",
    "class_covariance_weighting": "equal_person_within_cohort_then_equal_cohort",
    "csp_covariance_shrinkage": 0.1,
    "csp_shrinkage_target": "trace(class_covariance)/17_times_identity",
    "generalized_eigenproblem": "C_left_v=lambda_(C_left+C_right)_v",
    "eigenvector_order": [0, 1, 15, 16],
    "feature": "log(component_variance/sum_of_four_selected_component_variances)",
    "feature_variance_ddof": 0,
    "lda_solver": "lsqr",
    "lda_shrinkage": "auto",
    "lda_priors": [0.5, 0.5],
    "lda_resample_rows": 8192,
    "lda_resampling": "exact_equal_cohort_class_then_person_counts_differ_at_most_one_with_replacement",
    "source_hyperparameter_search": False,
    "target_fits": 0,
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _array_hash(value):
    value = np.ascontiguousarray(value)
    digest = hashlib.sha256()
    digest.update(_json({"shape": list(value.shape), "dtype": value.dtype.str}).encode())
    digest.update(memoryview(value).cast("B"))
    return digest.hexdigest()


def _broad(X):
    X = np.asarray(X)
    if X.ndim == 4:
        _require(X.shape[1:] == (3, 18, 320), "CSP requires the same [n,3,18,320] trial inputs")
        X = X[:, 0]
    _require(X.ndim == 3 and X.shape[1:] == (18, 320) and len(X) > 0,
             "CSP broad input must have shape [n,18,320] with nonempty trials")
    _require(np.issubdtype(X.dtype, np.number) and not np.iscomplexobj(X) and np.isfinite(X).all(),
             "CSP input must be finite real EEG values")
    result = np.array(X, dtype=np.float64, copy=True)
    result -= result.mean(axis=-1, keepdims=True)
    return result


def _source_records(sources):
    _require(isinstance(sources, dict) and sources, "A nonempty source-person dictionary is required")
    aliases = {"bnci": "bnci", "BNCI2014_001": "bnci", "yang": "yang", "Yang2025_2C": "yang",
               "synthetic_bnci": "synthetic_bnci", "synthetic_yang": "synthetic_yang"}
    checked = {}
    for key in sorted(sources):
        source = sources[key]
        _require(isinstance(key, str) and source.get("role") == "source", "CSP fit rejects non-source roles")
        _require(source.get("dataset") in aliases, "An external/unregistered dataset was passed to CSP fitting")
        y = np.asarray(source["y"])
        _require(y.ndim == 1 and np.issubdtype(y.dtype, np.integer) and set(y.tolist()) == {0, 1},
                 "Each source person must have both integer labels 0 and 1")
        X = _broad(source["X"])
        _require(len(X) == len(y), "CSP source X/y trial counts differ")
        checksum = source.get("input_sha256")
        _require(isinstance(checksum, str) and re.fullmatch("[0-9a-f]{64}", checksum),
                 "CSP source input SHA256 binding is required")
        checked[key] = {"X": X, "y": y.astype(np.int64, copy=False), "dataset": aliases[source["dataset"]],
                        "input_sha256": checksum}
    cohorts = {source["dataset"] for source in checked.values()}
    _require(cohorts <= {"bnci", "yang"} or cohorts <= {"synthetic_bnci", "synthetic_yang"},
             "Synthetic and real CSP cohorts must not be mixed")
    return checked


def _features_from_broad(X, projection, filters):
    reduced = np.einsum("pc,nct->npt", projection, X, optimize=True)
    components = np.einsum("kp,npt->nkt", filters, reduced, optimize=True)
    variances = np.var(components, axis=-1, ddof=0)
    total = variances.sum(axis=1, keepdims=True)
    _require(np.isfinite(variances).all() and np.all(variances > 0) and np.all(total > 0),
             "Zero/nonfinite CSP component variance; a trial cannot be silently dropped")
    features = np.log(variances / total)
    _require(features.shape == (len(X), 4) and np.isfinite(features).all(), "Invalid fixed CSP log-variance features")
    return features


def _balanced_feature_resample(features, sources, seed):
    rng = np.random.default_rng(seed)
    cohorts = sorted({source["dataset"] for source in sources.values()})
    total = CONTRACT["lda_resample_rows"]
    _require(total % (2 * len(cohorts)) == 0, "LDA resample must balance all source cohort/class cells")
    cell_budget = total // (2 * len(cohorts))
    sampled_X, sampled_y, counts, sample_identity = [], [], [], []
    for cohort in cohorts:
        people = sorted(key for key, source in sources.items() if source["dataset"] == cohort)
        base, remainder = divmod(cell_budget, len(people))
        _require(base > 0, "Fixed LDA sampling budget cannot represent every source person")
        for label in (0, 1):
            extras = set(rng.permutation(len(people))[:remainder].tolist())
            for index, person in enumerate(people):
                n = base + int(index in extras)
                choices = np.flatnonzero(sources[person]["y"] == label)
                selected = rng.choice(choices, size=n, replace=True)
                sampled_X.append(features[person][selected])
                sampled_y.append(np.full(n, label, dtype=np.int64))
                counts.append({"cohort": cohort, "subject": person, "class": label,
                               "original_class_trials": int(len(choices)), "sampled_rows": n,
                               "distinct_sampled_trials": int(len(np.unique(selected)))})
                sample_identity.append({"subject": person, "class": label, "trial_indices": selected.tolist()})
    X, y = np.concatenate(sampled_X), np.concatenate(sampled_y)
    _require(X.shape == (total, 4) and Counter(y.tolist()) == {0: total // 2, 1: total // 2},
             "Fixed LDA resample class counts changed")
    # A fixed permutation avoids incidental dependence on class/subject block order.
    order = rng.permutation(total)
    identity = hashlib.sha256(_json({"selected": sample_identity, "order": order.tolist()}).encode()).hexdigest()
    return X[order], y[order], counts, identity


@dataclass(frozen=True)
class CSPModel:
    projection: np.ndarray
    filters: np.ndarray
    eigenvalues: np.ndarray
    class_covariances: np.ndarray
    regularized_class_covariances: np.ndarray
    lda_coef: np.ndarray
    lda_intercept: np.ndarray
    lda_means: np.ndarray
    lda_covariance: np.ndarray
    metadata: dict


ARRAY_NAMES = ("projection", "filters", "eigenvalues", "class_covariances", "regularized_class_covariances",
               "lda_coef", "lda_intercept", "lda_means", "lda_covariance")


def _validated_model(arrays, metadata):
    shapes = {"projection": (17, 18), "filters": (4, 17), "eigenvalues": (17,),
              "class_covariances": (2, 17, 17), "regularized_class_covariances": (2, 17, 17),
              "lda_coef": (1, 4), "lda_intercept": (1,), "lda_means": (2, 4), "lda_covariance": (4, 4)}
    _require(metadata.get("contract") == CONTRACT and metadata.get("target_fits") == 0,
             "CSP model does not match the fixed source-only contract")
    prepared = {}
    for name in ARRAY_NAMES:
        value = np.array(arrays[name], dtype=np.float64, copy=True)
        _require(value.shape == shapes[name] and np.isfinite(value).all(), f"Invalid CSP model parameter: {name}")
        value.setflags(write=False)
        prepared[name] = value
    _require(np.allclose(prepared["projection"] @ prepared["projection"].T, np.eye(17), atol=1e-12, rtol=0)
             and np.allclose(prepared["projection"] @ np.ones(18), 0, atol=1e-12, rtol=0),
             "CSP fixed projection does not remove exactly the CAR constant direction")
    return CSPModel(**prepared, metadata=json.loads(_json(metadata)))


def fit(sources: dict, seed: int = 20261013) -> CSPModel:
    """Fit one fixed conventional baseline using authenticated source roles only."""
    _require(isinstance(seed, (int, np.integer)) and not isinstance(seed, (bool, np.bool_)) and 0 <= seed < 2**63,
             "A nonnegative fixed integer CSP sampling seed is required")
    source = _source_records(sources)
    projection = helmert(18, full=False).astype(np.float64)
    cohorts = sorted({person["dataset"] for person in source.values()})
    per_person = {}
    for key, person in source.items():
        reduced = np.einsum("pc,nct->npt", projection, person["X"], optimize=True)
        covariance = np.einsum("npt,nqt->npq", reduced, reduced, optimize=True)
        traces = np.trace(covariance, axis1=1, axis2=2)
        _require(np.isfinite(covariance).all() and np.all(traces > 0), "Zero/nonfinite source trial covariance")
        covariance /= traces[:, None, None]
        per_person[key] = np.stack([covariance[person["y"] == label].mean(axis=0) for label in (0, 1)])
    class_covariances = np.mean([
        np.mean([per_person[key] for key, person in source.items() if person["dataset"] == cohort], axis=0)
        for cohort in cohorts
    ], axis=0)
    class_covariances = (class_covariances + class_covariances.transpose(0, 2, 1)) / 2
    ridge = CONTRACT["csp_covariance_shrinkage"]
    regularized = np.stack([(1 - ridge) * covariance + ridge * np.trace(covariance) / 17 * np.eye(17)
                             for covariance in class_covariances])
    eigenvalues, eigenvectors = eigh(regularized[0], regularized.sum(axis=0), driver="gvd", check_finite=True)
    filters = eigenvectors[:, CONTRACT["eigenvector_order"]].T.copy()
    # CSP variances ignore sign; canonical signs keep serialized parameters stable.
    for row in filters:
        if row[np.argmax(np.abs(row))] < 0:
            row *= -1
    features = {key: _features_from_broad(person["X"], projection, filters) for key, person in source.items()}
    X_lda, y_lda, counts, resample_hash = _balanced_feature_resample(features, source, int(seed))
    lda = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto", priors=[0.5, 0.5])
    lda.fit(X_lda, y_lda)
    _require(np.array_equal(lda.classes_, [0, 1]), "Unexpected LDA class order")
    metadata = {
        "schema_version": 1, "family": "CONVENTIONAL_FIXED_BASELINE", "contract": CONTRACT,
        "seed": int(seed), "source_input_hashes": {key: person["input_sha256"] for key, person in source.items()},
        "source_subjects": sorted(source), "source_cohorts": cohorts,
        "source_cohort_person_counts": dict(Counter(person["dataset"] for person in source.values())),
        "source_original_trial_counts": {key: len(person["y"]) for key, person in source.items()},
        "lda_balanced_resample_counts": counts, "lda_resample_sha256": resample_hash,
        "repeated_rows_are_independent_subjects_or_trials": False,
        "n_conventional_fits": 1, "new_neural_fits": 0, "target_fits": 0,
        "synthetic_inputs": all(cohort.startswith("synthetic_") for cohort in cohorts),
        "numpy_version": np.__version__, "scipy_version": scipy.__version__, "sklearn_version": sklearn.__version__,
        "csp_module_sha256": _file_hash(__file__),
    }
    arrays = {"projection": projection, "filters": filters, "eigenvalues": eigenvalues,
              "class_covariances": class_covariances, "regularized_class_covariances": regularized,
              "lda_coef": lda.coef_, "lda_intercept": lda.intercept_,
              "lda_means": lda.means_, "lda_covariance": lda.covariance_}
    model = _validated_model(arrays, metadata)
    # This source-feature check verifies the plain-numeric inference export only.
    score = X_lda @ model.lda_coef[0] + model.lda_intercept[0]
    exported = np.column_stack((expit(-score), expit(score)))
    _require(np.allclose(exported, lda.predict_proba(X_lda), atol=2e-14, rtol=2e-14),
             "Serialized numeric LDA decision rule differs from sklearn")
    return model


def predict(model: CSPModel, X: np.ndarray) -> np.ndarray:
    """Return fixed left/right probabilities [n,2]; reads no target labels."""
    before = model_hash(model)
    features = _features_from_broad(_broad(X), model.projection, model.filters)
    score = features @ model.lda_coef[0] + model.lda_intercept[0]
    probability = np.column_stack((expit(-score), expit(score)))
    _require(probability.shape == (len(features), 2) and np.isfinite(probability).all(), "Invalid CSP/LDA probabilities")
    _require(model_hash(model) == before, "CSP prediction changed fixed source parameters")
    return probability


def model_hash(model: CSPModel) -> str:
    state = {"arrays": {name: _array_hash(getattr(model, name)) for name in ARRAY_NAMES}, "metadata": model.metadata}
    return hashlib.sha256(_json(state).encode()).hexdigest()


def save_model(model: CSPModel, path: str | Path) -> dict:
    """Atomically save only numeric arrays and JSON strings; never pickle."""
    path = Path(path)
    _require(path.suffix == ".npz", "CSP parameters must use a .npz filename")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {name: getattr(model, name) for name in ARRAY_NAMES}
    payload.update(metadata_json=np.array(_json(model.metadata)), model_sha256=np.array(model_hash(model)))
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    try:
        with temporary.open("wb") as stream:
            np.savez_compressed(stream, **payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return {"path": str(path), "sha256": _file_hash(path), "model_sha256": model_hash(model),
            "seed": model.metadata["seed"], "source_input_hashes": model.metadata["source_input_hashes"],
            "family": "CONVENTIONAL_FIXED_BASELINE", "new_neural_fits": 0, "target_fits": 0}


def load_model(path: str | Path) -> CSPModel:
    with np.load(path, allow_pickle=False) as data:
        _require(set(data.files) == set(ARRAY_NAMES) | {"metadata_json", "model_sha256"}, "Unexpected CSP parameter file schema")
        model = _validated_model({name: data[name] for name in ARRAY_NAMES}, json.loads(data["metadata_json"].item()))
        expected = data["model_sha256"].item()
    _require(model_hash(model) == expected, "CSP serialized model hash mismatch")
    return model
