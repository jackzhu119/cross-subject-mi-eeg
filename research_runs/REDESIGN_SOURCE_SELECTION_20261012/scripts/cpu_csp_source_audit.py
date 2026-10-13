#!/usr/bin/env python3
"""New source-only CSP diagnostic; never an original Q15 run reconstruction.

Default use is a dry run. Real fits require a committed, publicly verified
preanalysis plan and a passing historical baseline audit. No target EEG is read.
The ten new source fits and training-set performance are explicitly distinct
from the unarchived calculations described in the retrospective CSP report.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote
from urllib.request import Request, urlopen
import uuid

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
CONFIG = STUDY / "config/cpu_csp_diagnostic.json"
GATE = STUDY / "evidence/baseline_audit_gate.json"
FREEZE = STUDY / "evidence/cpu_csp_preanalysis_commit_receipt.json"
RAW_PROVENANCE = ROOT / "research_runs/Q8-E001/results/source_files.json"
EXECUTION_CONTRACT = ROOT / "research_runs/Q15-EXECUTION-20261003/EXECUTION_CONTRACT.json"
ORIGINAL_PROTOCOL = ROOT / "research_runs/PAPER_RELEASE_20260927/Q15_CONTRACT.json"
PUBLIC_REPOSITORY = "jackzhu119/cross-subject-mi-eeg"
ORIGINAL_MODEL_SHA = "15ee57321177bca17472bd0fe211f1a42557291203b4e5700caf74a093bdd61f"
SUBJECTS = list(range(1, 10))
LIBRARIES = ("numpy", "scipy", "pandas", "scikit-learn", "mne", "joblib", "threadpoolctl")
PARAMETERS = {
    "fixed_car_basis_channels": 21, "n_components": 4, "reg": None,
    "log": True, "cov_est": "concat", "norm_trace": False, "rank": "full",
    "component_order": "mutual_info", "transform_into": "average_power",
    "scaler": "StandardScaler", "lda_solver": "svd",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def rel(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def validate_config(config):
    expected = {
        "schema_version": 1, "source_subjects": SUBJECTS,
        "expected_new_source_fits": 10, "target_fits": 0,
        "bands": "broad", "artifact_policy": "include_all",
        "target_predictions_enabled": False, "cpu_threads": 1,
        "parameters": PARAMETERS,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"Preanalysis CSP configuration changed: {key}")
    return config


def public_commit_bytes(revision, name):
    """Read immutable public source bytes; no credentials or EEG are requested."""
    url = f"https://raw.githubusercontent.com/{PUBLIC_REPOSITORY}/{revision}/{quote(name, safe='/')}"
    with urlopen(Request(url, headers={"User-Agent": "q15-source-preanalysis-verification"}), timeout=30) as response:
        if response.status != 200:
            raise ValueError("Public preanalysis source read-back did not return HTTP 200")
        return response.read()


def verify_preanalysis(config_path=CONFIG, gate_path=GATE, freeze_path=FREEZE):
    """Require protocol files both in the public commit and unchanged locally."""
    config = validate_config(json.loads(Path(config_path).read_text()))
    gate = json.loads(Path(gate_path).read_text())
    if gate.get("status") != "PASS":
        raise ValueError("Historical baseline audit must pass before new source fits")
    receipt = json.loads(Path(freeze_path).read_text())
    revision = receipt.get("protocol_commit", "")
    if not isinstance(revision, str) or len(revision) != 40 or any(character not in "0123456789abcdef" for character in revision):
        raise ValueError("Preanalysis commit SHA is missing")
    public = receipt.get("public_verification", {})
    if (public.get("status") != "PASS" or public.get("commit_sha") != revision or not public.get("branch")
            or public.get("repository") != PUBLIC_REPOSITORY):
        raise ValueError("Preanalysis public read-back verification is missing")
    subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", revision, "HEAD"], check=True)
    protected = receipt.get("protocol_files", {})
    required = [Path(config_path), Path(gate_path), Path(__file__), HERE / "validate_cpu_csp_source_audit.py",
                RAW_PROVENANCE, ROOT / "src/mi_eeg/data/q15_context.py",
                ROOT / "src/mi_eeg/models/q15_csp.py", EXECUTION_CONTRACT, ORIGINAL_PROTOCOL]
    if not isinstance(protected, dict) or any(rel(path) not in protected for path in required):
        raise ValueError("Preanalysis receipt omits configuration, implementation, gate, or provenance")
    for name, expected in protected.items():
        path = ROOT / name
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError("Preanalysis file cannot be symlinked or escape the repository")
        committed = git("show", f"{revision}:{name}")
        if hashlib.sha256(committed).hexdigest() != expected or sha(path) != expected:
            raise ValueError(f"Preanalysis file differs from the committed plan: {name}")
    # A self-written {status: PASS} receipt is insufficient. Re-read every
    # executable/contract/input-provenance dependency from the pinned public
    # commit as well as checking its local file and git object above.
    for path in required:
        name = rel(path)
        if hashlib.sha256(public_commit_bytes(revision, name)).hexdigest() != protected[name]:
            raise ValueError(f"Public preanalysis source bytes differ: {name}")
    return config, receipt


def partition_records(records, held_out):
    """Pure identity logic used by both real execution and synthetic tests."""
    if held_out is not None and held_out not in SUBJECTS:
        raise ValueError("Held-out source participant must be 1 through 9")
    identities = [row["sample_id"] for row in records]
    if len(set(identities)) != len(identities) or any(row["subject"] not in SUBJECTS for row in records):
        raise ValueError("Source sample identity is duplicate or participant is invalid")
    train = [index for index, row in enumerate(records) if held_out is None or row["subject"] != held_out]
    evaluation = list(range(len(records))) if held_out is None else [
        index for index, row in enumerate(records) if row["subject"] == held_out]
    if not train or not evaluation:
        raise ValueError("Empty CSP source partition")
    if held_out is not None and (set(train) & set(evaluation)):
        raise AssertionError("Source held-out leakage")
    for indices in (train, evaluation):
        if set(records[index]["label"] for index in indices) != {1, 2}:
            raise ValueError("Every source partition requires both hand classes")
    return train, evaluation


def array_hash(values):
    import numpy as np
    values = np.ascontiguousarray(values)
    digest = hashlib.sha256()
    digest.update(json.dumps({"shape": list(values.shape), "dtype": values.dtype.str}, sort_keys=True).encode())
    digest.update(memoryview(values).cast("B"))
    return digest.hexdigest()


def make_pipeline():
    from mne.decoding import CSP
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from mi_eeg.models.q15_csp import FixedCARBasis
    return Pipeline([
        ("fixed_car_basis", FixedCARBasis(n_channels=21)),
        ("csp", CSP(n_components=4, reg=None, log=True, cov_est="concat", norm_trace=False,
                    rank="full", component_order="mutual_info", transform_into="average_power")),
        ("scaler", StandardScaler()),
        ("lda", LinearDiscriminantAnalysis(solver="svd")),
    ])


def write_predictions(path, records, indices, predictions, probabilities):
    import numpy as np
    predictions, probabilities = np.asarray(predictions), np.asarray(probabilities)
    if predictions.shape != (len(indices),) or probabilities.shape != (len(indices), 2):
        raise ValueError("Unexpected source prediction shape")
    if not np.isfinite(probabilities).all() or not np.allclose(probabilities.sum(axis=1), 1, rtol=0, atol=1e-10):
        raise ValueError("Invalid source prediction probabilities")
    if not np.isin(predictions, (1, 2)).all() or not ((probabilities >= 0) & (probabilities <= 1)).all():
        raise ValueError("Invalid source prediction labels or probabilities")
    fields = ["sample_id", "subject", "session", "run", "trial", "label", "artifact_flagged", "prediction", "p_left", "p_right"]
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for index, predicted, probability in zip(indices, predictions, probabilities):
            row = {name: records[index][name] for name in fields[:7]}
            row.update(prediction=int(predicted), p_left=repr(float(probability[0])), p_right=repr(float(probability[1])))
            writer.writerow(row)


def runtime_versions():
    return {name: importlib.metadata.version(name) for name in LIBRARIES}


def original_replay_policy(config, versions):
    frozen = config.get("frozen_model")
    if not frozen:
        return {"status": "SKIP", "reason": "original_frozen_model_not_configured", "model_deserialized": False}
    expected = frozen.get("runtime_versions", {})
    required = {"numpy", "scipy", "scikit-learn", "mne", "joblib"}
    if not required.issubset(expected) or any(versions.get(key) != expected[key] for key in required):
        return {"status": "SKIP", "reason": "original_model_runtime_versions_do_not_match",
                "model_deserialized": False, "required_versions": expected, "current_versions": versions}
    path = Path(frozen.get("path", ""))
    if not path.is_absolute():
        path = ROOT / path
    if frozen.get("sha256") != ORIGINAL_MODEL_SHA or not path.is_file() or path.is_symlink() or sha(path) != ORIGINAL_MODEL_SHA:
        return {"status": "SKIP", "reason": "original_trusted_frozen_model_hash_or_file_unavailable", "model_deserialized": False}
    return {"status": "ELIGIBLE", "path": str(path), "sha256": ORIGINAL_MODEL_SHA, "model_deserialized": False}


def execute(data_dir, output_dir=None):
    config, freeze = verify_preanalysis()
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ[name] = "1"
    sys.path.insert(0, str(ROOT / "src"))
    import numpy as np
    import joblib
    import mne
    from threadpoolctl import threadpool_limits
    from mi_eeg.data.q15_context import audit_bnci_source, load_bnci_source, preprocessing_contract
    mne.set_log_level("ERROR")
    run_id = "cpu-csp-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    output = Path(output_dir).resolve() if output_dir else STUDY / "results" / run_id
    if not output.is_relative_to(STUDY / "results") or output.exists():
        raise ValueError("Fresh output must be inside this study's results directory")
    output.mkdir(parents=True)
    models = STUDY / "models" / run_id
    if models.exists():
        raise ValueError("Model destination already exists")
    models.mkdir(parents=True)
    status = {"status": "source_raw_audit", "run_id": run_id, "new_source_fits_started": 0,
              "new_source_fits_completed": 0, "target_fits": 0, "target_predictions_computed": False,
              "new_neural_fits": 0, "updated_at_utc": now()}
    write_json(output / "execution_status.json", status)
    try:
        raw_audit = audit_bnci_source(Path(data_dir), RAW_PROVENANCE)
        write_json(output / "raw_metadata_audit.json", raw_audit)
        contract = preprocessing_contract()
        write_json(output / "preprocessing_contract.json", contract)
        with threadpool_limits(limits=1):
            arrays, metadata, audits = load_bnci_source(Path(data_dir), SUBJECTS, RAW_PROVENANCE)
        X, y = arrays["broad"], metadata["label"].to_numpy(dtype=np.int64)
        del arrays
        metadata.to_csv(output / "source_metadata.csv", index=False)
        audits.to_csv(output / "source_run_audit.csv", index=False)
        records = metadata.to_dict(orient="records")
        expected_counts = metadata.groupby(["subject", "session", "label"]).size()
        if X.shape != (2592, 21, 320) or len(records) != 2592 or not (expected_counts == 72).all() or len(expected_counts) != 36:
            raise ValueError("Expected 9 participants × 2 sessions × 144 binary trials")
        runtime = {"versions": runtime_versions(), "python_version": sys.version,
                   "threads": 1, "eeg_preprocessing_module_sha256": sha(ROOT / "src/mi_eeg/data/q15_context.py"),
                   "fixed_basis_module_sha256": sha(ROOT / "src/mi_eeg/models/q15_csp.py"),
                   "executor_sha256": sha(__file__), "git_head_at_execution": git("rev-parse", "HEAD").decode().strip(),
                   "label_identity_validator_sha256": sha(HERE / "validate_cpu_csp_source_audit.py"),
                   "execution_contract_sha256": sha(EXECUTION_CONTRACT),
                   "original_protocol_sha256": sha(ORIGINAL_PROTOCOL),
                   "protocol_commit": freeze["protocol_commit"], "config_sha256": sha(CONFIG),
                   "source_provenance_sha256": sha(RAW_PROVENANCE), "source_epochs_sha256": array_hash(X),
                   "source_labels_sha256": array_hash(y), "source_sample_ids_sha256": canonical_hash(metadata["sample_id"].tolist()),
                   "source_epoch_dtype": str(X.dtype), "estimator_input_dtype": "float64"}
        write_json(output / "runtime_provenance.json", runtime)
        folds = []
        for held_out in [*SUBJECTS, None]:
            fold = f"loso_s{held_out:02d}" if held_out is not None else "all_source_resubstitution"
            folder = output / "folds" / fold
            folder.mkdir(parents=True)
            model_folder = models / fold
            model_folder.mkdir()
            train, evaluation = partition_records(records, held_out)
            train_records = [records[index] for index in train]
            eval_records = [records[index] for index in evaluation]
            # Bind each digest to the exact arrays passed to the estimator.
            # Keep the whole-epoch float32 digest separately in runtime.
            train_X = np.ascontiguousarray(X[train], dtype=np.float64)
            evaluation_X = np.ascontiguousarray(X[evaluation], dtype=np.float64)
            train_y = np.ascontiguousarray(y[train])
            evaluation_y = np.ascontiguousarray(y[evaluation])
            write_json(folder / "partition.json", {"held_out_subject": held_out, "train_records": train_records,
                                                   "evaluation_records": eval_records})
            fit_receipt = {"fold": fold, "held_out_subject": held_out, "status": "started", "started_at_utc": now(),
                           "fit_ordinal": status["new_source_fits_started"] + 1, "new_source_fit": True,
                           "target_fit": False, "fit_method": "sklearn.pipeline.Pipeline.fit",
                           "training_subjects": sorted({row["subject"] for row in train_records}),
                           "n_training_trials": len(train), "n_evaluation_trials": len(evaluation),
                           "training_sample_ids_sha256": canonical_hash([row["sample_id"] for row in train_records]),
                           "evaluation_sample_ids_sha256": canonical_hash([row["sample_id"] for row in eval_records]),
                           "training_epochs_sha256": array_hash(train_X), "training_labels_sha256": array_hash(train_y),
                           "evaluation_epochs_sha256": array_hash(evaluation_X), "evaluation_labels_sha256": array_hash(evaluation_y),
                           "actual_estimator_input_dtype": "float64", "preprocessing_epoch_dtype": str(X.dtype),
                           "partition_file_sha256": sha(folder / "partition.json"), "parameters": PARAMETERS,
                           "evaluation_kind": "held_out_source_participant" if held_out is not None else "training_set_resubstitution"}
            write_json(folder / "fit_receipt.json", fit_receipt)
            status["new_source_fits_started"] += 1
            status.update(status="new_source_fitting", current_fold=fold, updated_at_utc=now())
            write_json(output / "execution_status.json", status)
            pipeline = make_pipeline()
            with threadpool_limits(limits=1):
                pipeline.fit(train_X, train_y)
                if list(pipeline.classes_) != [1, 2]:
                    raise ValueError("CSP output class order changed")
                predictions = pipeline.predict(evaluation_X)
                probabilities = pipeline.predict_proba(evaluation_X)
            model_path = model_folder / "model.joblib"
            joblib.dump(pipeline, model_path, compress=3)
            write_predictions(folder / "predictions.csv", records, evaluation, predictions, probabilities)
            fit_receipt.update(status="completed", completed_at_utc=now(), model_path=rel(model_path),
                               model_sha256=sha(model_path), predictions_sha256=sha(folder / "predictions.csv"),
                               csp_fitted_filters_shape=list(pipeline.named_steps["csp"].filters_.shape),
                               scaler_n_samples_seen=int(pipeline.named_steps["scaler"].n_samples_seen_),
                               lda_classes=[int(item) for item in pipeline.named_steps["lda"].classes_])
            write_json(folder / "fit_receipt.json", fit_receipt)
            status["new_source_fits_completed"] += 1
            write_json(output / "execution_status.json", status)
            folds.append(fold)
            print(json.dumps({"stage": "new_source_fit_complete", "fold": fold,
                              "new_source_fits_completed": status["new_source_fits_completed"], "target_fits": 0}), flush=True)
        policy = original_replay_policy(config, runtime["versions"])
        if policy["status"] == "ELIGIBLE":
            with threadpool_limits(limits=1):
                original = joblib.load(policy["path"])
                if list(original.classes_) != [1, 2]:
                    raise ValueError("Original model class mapping differs")
                predictions = original.predict(X.astype(np.float64))
                probabilities = original.predict_proba(X.astype(np.float64))
            write_predictions(output / "original_model_source_resubstitution.csv", records, list(range(len(records))), predictions, probabilities)
            policy.update(status="REPLAYED", model_deserialized=True, predictions_sha256=sha(output / "original_model_source_resubstitution.csv"),
                          interpretation="Frozen-model training-set resubstitution in matching runtime; not independent source validation")
        write_json(output / "original_model_replay_receipt.json", policy)
        write_json(output / "run_manifest.json", {"schema_version": 1, "run_id": run_id, "status": "completed_pending_independent_validation",
                                                   "folds": folds, "new_source_fits": 10, "target_fits": 0,
                                                   "new_neural_fits": 0, "parameters": PARAMETERS,
                                                   "historical_report_claims": {"train_ba_percent": 63.04, "loso_ba_percent": 61.65,
                                                   "retroactive_verification": False,
                                                   "interpretation": "New refits cannot establish provenance of an earlier unarchived run, even if rounded values coincide"}})
        status.update(status="completed_pending_independent_validation", updated_at_utc=now())
        write_json(output / "execution_status.json", status)
        print(json.dumps({"status": status["status"], "output_directory": rel(output), "new_source_fits": 10, "target_fits": 0}), flush=True)
        return output
    except Exception as error:
        status.update(status="FAILED", error_type=type(error).__name__, error_message=str(error), updated_at_utc=now())
        write_json(output / "execution_status.json", status)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Run only after public preanalysis freeze and baseline PASS")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"status": "DRY_RUN_NO_DATA_LOADED_NO_FITS", "new_source_fits": 0,
                          "planned_new_source_fits": 10, "target_fits": 0, "new_neural_fits": 0,
                          "required_config": rel(CONFIG), "required_audit_gate": rel(GATE),
                          "required_public_freeze_receipt": rel(FREEZE), "parameters": PARAMETERS}, indent=2))
        return
    if args.data_dir is None:
        parser.error("--execute requires --data-dir with the 18 original BNCI MAT files")
    execute(args.data_dir, args.output_dir)


if __name__ == "__main__":
    main()
