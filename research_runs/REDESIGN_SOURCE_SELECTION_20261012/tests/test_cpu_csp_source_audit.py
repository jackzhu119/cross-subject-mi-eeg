"""Software-only synthetic checks. They are not EEG scientific evidence."""
import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
import pytest

STUDY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDY / "scripts"))
sys.path.insert(0, str(STUDY.parents[1] / "src"))
import cpu_csp_source_audit as execute
import validate_cpu_csp_source_audit as check
from mi_eeg.models.q15_csp import FixedCARBasis


def synthetic_records():
    # Two synthetic labels per source participant, no EEG or real participants.
    return [{"sample_id": f"software_s{person}_label{label}", "subject": person,
             "session": "synthetic", "run": 0, "trial": label,
             "label": label, "artifact_flagged": bool(label == 2), "event_sample": label}
            for person in range(1, 10) for label in (1, 2)]


def config():
    return {"schema_version": 1, "source_subjects": list(range(1, 10)), "expected_new_source_fits": 10,
            "target_fits": 0, "bands": "broad", "artifact_policy": "include_all",
            "target_predictions_enabled": False, "cpu_threads": 1, "parameters": execute.PARAMETERS.copy()}


def test_default_cli_is_a_dry_run_without_model_or_eeg_access():
    result = subprocess.run([sys.executable, str(STUDY / "scripts/cpu_csp_source_audit.py")],
                            capture_output=True, text=True, check=True)
    receipt = json.loads(result.stdout)
    assert receipt["status"] == "DRY_RUN_NO_DATA_LOADED_NO_FITS"
    assert receipt["new_source_fits"] == receipt["target_fits"] == receipt["new_neural_fits"] == 0
    assert receipt["planned_new_source_fits"] == 10


@pytest.mark.parametrize("field,value", [("target_fits", 1), ("expected_new_source_fits", 9),
                                          ("artifact_policy", "exclude_flagged"), ("cpu_threads", 4),
                                          ("target_predictions_enabled", True), ("source_subjects", [1, 2])])
def test_configuration_rejects_changed_source_scope_and_target_activity(field, value):
    amended = config()
    amended[field] = value
    with pytest.raises(ValueError, match="configuration changed"):
        execute.validate_config(amended)


def test_configuration_rejects_target_or_outcome_driven_csp_amendment():
    amended = config()
    amended["parameters"]["norm_trace"] = True
    with pytest.raises(ValueError, match="parameters"):
        execute.validate_config(amended)


@pytest.fixture
def software_freeze(monkeypatch):
    """Only public protocol bytes are mocked; no raw EEG or estimators read."""
    (STUDY / "results").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="software-freeze-only-", dir=STUDY / "results") as folder:
        folder = Path(folder)
        configuration, gate, receipt_path = folder / "config.json", folder / "gate.json", folder / "freeze.json"
        configuration.write_text(json.dumps(config()))
        gate.write_text(json.dumps({"status": "PASS"}))
        files = [configuration, gate, Path(execute.__file__), Path(check.__file__), execute.RAW_PROVENANCE,
                 execute.ROOT / "src/mi_eeg/data/q15_context.py", execute.ROOT / "src/mi_eeg/models/q15_csp.py",
                 execute.EXECUTION_CONTRACT, execute.ORIGINAL_PROTOCOL]
        content = {execute.rel(path): path.read_bytes() for path in files}
        receipt = {"protocol_commit": "a" * 40,
                   "public_verification": {"status": "PASS", "commit_sha": "a" * 40,
                                           "repository": execute.PUBLIC_REPOSITORY, "branch": "software-test-only"},
                   "protocol_files": {execute.rel(path): execute.sha(path) for path in files}}
        receipt_path.write_text(json.dumps(receipt))
        monkeypatch.setattr(execute.subprocess, "run", lambda *args, **kwargs: None)
        monkeypatch.setattr(execute, "git", lambda *args: content[args[1].split(":", 1)[1]])
        observations = []
        def public_bytes(revision, name):
            observations.append((revision, name))
            return content[name]
        monkeypatch.setattr(execute, "public_commit_bytes", public_bytes)
        yield configuration, gate, receipt_path, receipt, content, observations


def test_public_freeze_requires_actual_pinned_source_readback(software_freeze):
    configuration, gate, path, receipt, content, observations = software_freeze
    execute.verify_preanalysis(configuration, gate, path)
    assert {name for revision, name in observations} == set(content)
    assert {revision for revision, name in observations} == {receipt["protocol_commit"]}


@pytest.mark.parametrize("field,value", [("status", "UNVERIFIED"), ("commit_sha", "b" * 40),
                                        ("repository", "another-account/repository"), ("branch", "")])
def test_public_freeze_rejects_missing_or_different_publication_identity(software_freeze, field, value):
    configuration, gate, path, receipt, _, _ = software_freeze
    receipt["public_verification"][field] = value
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="public read-back verification"):
        execute.verify_preanalysis(configuration, gate, path)


def test_public_pass_dictionary_does_not_hide_different_public_bytes(software_freeze, monkeypatch):
    configuration, gate, path, _, _, _ = software_freeze
    monkeypatch.setattr(execute, "public_commit_bytes", lambda revision, name: b"unrelated public bytes")
    with pytest.raises(ValueError, match="Public preanalysis source bytes differ"):
        execute.verify_preanalysis(configuration, gate, path)


def test_public_freeze_rejects_omitted_original_transform_contract(software_freeze):
    configuration, gate, path, receipt, _, _ = software_freeze
    del receipt["protocol_files"][execute.rel(execute.EXECUTION_CONTRACT)]
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="receipt omits"):
        execute.verify_preanalysis(configuration, gate, path)


def test_public_freeze_rejects_local_postcommit_changes(software_freeze):
    configuration, gate, path, _, _, _ = software_freeze
    configuration.write_text(json.dumps(config(), indent=2))
    with pytest.raises(ValueError, match="differs from the committed plan"):
        execute.verify_preanalysis(configuration, gate, path)


@pytest.mark.parametrize("held_out", range(1, 10))
def test_every_loso_source_partition_excludes_held_out_person_and_trials(held_out):
    records = synthetic_records()
    train, evaluation = execute.partition_records(records, held_out)
    assert len(train) == 16 and len(evaluation) == 2
    assert not (set(train) & set(evaluation))
    assert held_out not in {records[index]["subject"] for index in train}
    assert {records[index]["subject"] for index in evaluation} == {held_out}


def test_partition_rejects_duplicate_ids_or_missing_class():
    records = synthetic_records()
    records[0]["sample_id"] = records[1]["sample_id"]
    with pytest.raises(ValueError, match="identity"):
        execute.partition_records(records, 1)
    records = [row for row in synthetic_records() if not (row["subject"] == 1 and row["label"] == 2)]
    with pytest.raises(ValueError, match="both hand classes"):
        execute.partition_records(records, 1)


def test_validator_detects_source_person_leakage_and_changed_native_label():
    records = synthetic_records()
    train, evaluation = execute.partition_records(records, 1)
    partition = {"held_out_subject": 1, "train_records": [records[index] for index in train],
                 "evaluation_records": [records[index] for index in evaluation]}
    predictions = [{**row, "prediction": row["label"], "p_left": .8 if row["label"] == 1 else .2,
                    "p_right": .2 if row["label"] == 1 else .8} for row in partition["evaluation_records"]]
    check.validate_partition(partition, predictions, 1, records)
    partition["train_records"].append(records[0])
    with pytest.raises(ValueError, match="Partition differs"):
        check.validate_partition(partition, predictions, 1, records)
    partition["train_records"] = [records[index] for index in train]
    predictions[0]["label"] = 2
    with pytest.raises(ValueError, match="prediction identities/labels"):
        check.validate_partition(partition, predictions, 1, records)


def test_independent_balanced_accuracy_uses_person_level_confusion_not_accuracy():
    rows = [{"subject": 1, "label": 1, "prediction": 1, "p_left": .8}] * 8
    rows += [{"subject": 1, "label": 2, "prediction": 1, "p_left": .8}] * 2
    output = check.participant_metrics(rows)[0]
    assert output["balanced_accuracy_percent"] == 50
    assert output["left_true_left_pred"] == 8
    assert output["right_true_left_pred"] == 2
    assert output["predicted_left_percent"] == 100


def test_a_constant_declaration_of_ten_fits_does_not_validate_missing_artifacts(monkeypatch):
    monkeypatch.setattr(check, "verify_preanalysis", lambda: (config(), {"protocol_commit": "a" * 40}))
    (STUDY / "results").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="software-test-only-", dir=STUDY / "results") as folder:
        folder = Path(folder)
        (folder / "run_manifest.json").write_text(json.dumps({"new_source_fits": 10, "target_fits": 0,
                                                              "status": "completed_pending_independent_validation"}))
        (folder / "execution_status.json").write_text(json.dumps({"new_source_fits_started": 10, "new_source_fits_completed": 10}))
        with pytest.raises(ValueError, match="runtime_provenance"):
            check.validate(folder, Path("no EEG must be accessed in this test"))


def test_old_pickle_is_not_deserialized_when_runtime_versions_differ():
    supplied = config()
    supplied["frozen_model"] = {"path": "/no-such-original-model.joblib", "sha256": execute.ORIGINAL_MODEL_SHA,
                                 "runtime_versions": {name: "original-version" for name in
                                                      ("numpy", "scipy", "scikit-learn", "mne", "joblib")}}
    receipt = execute.original_replay_policy(supplied, {"numpy": "different-version"})
    assert receipt["status"] == "SKIP"
    assert receipt["model_deserialized"] is False
    assert receipt["reason"] == "original_model_runtime_versions_do_not_match"


def test_fixed_basis_is_constant_rank_20_and_projects_out_only_common_reference():
    values = np.random.default_rng(20261012).normal(size=(2, 21, 320))
    adapter = FixedCARBasis()
    transformed = adapter.transform(values)
    assert transformed.shape == (2, 20, 320)
    np.testing.assert_allclose(adapter.basis @ adapter.basis.T, np.eye(20), atol=5e-16, rtol=0)
    car = values - values.mean(axis=1, keepdims=True)
    restored = np.einsum("ca,nat->nct", adapter.basis.T, transformed)
    np.testing.assert_allclose(restored, car, atol=1e-14, rtol=1e-14)
    with pytest.raises(ValueError, match="finite Q15"):
        adapter.transform(np.full((1, 21, 320), np.nan))
    with pytest.raises(ValueError, match="finite Q15"):
        adapter.transform(np.ones((1, 20, 320)))


def test_numerical_hash_binds_labels_shape_dtype_and_values():
    base = np.array([1, 2], dtype=np.int64)
    assert execute.array_hash(base) != execute.array_hash(base.astype(np.int32))
    assert execute.array_hash(base) != execute.array_hash(base.reshape(1, 2))
    assert execute.array_hash(base) != execute.array_hash(np.array([2, 1], dtype=np.int64))
    epochs = np.arange(8, dtype=np.float32).reshape(2, 2, 2)
    actual_estimator_input = np.ascontiguousarray(epochs, dtype=np.float64)
    assert execute.array_hash(epochs) != execute.array_hash(actual_estimator_input)
    np.testing.assert_array_equal(epochs, actual_estimator_input)


def test_written_prediction_probability_mapping_is_revalidated(tmp_path):
    records = synthetic_records()[:2]
    path = tmp_path / "predictions.csv"
    execute.write_predictions(path, records, [0, 1], np.array([1, 2]), np.array([[.8, .2], [.2, .8]]))
    rows = check.read_predictions(path)
    assert [row["prediction"] for row in rows] == [1, 2]
    text = path.read_text().replace("1,0.8,0.2", "2,0.8,0.2")
    path.write_text(text)
    with pytest.raises(ValueError, match="probability decision"):
        check.read_predictions(path)
