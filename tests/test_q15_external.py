"""Synthetic-only inference contract and person-statistics tests; no real fits."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from scripts import q15_external as external


def trial_meta(subject=1, sessions=(1,)):
    rows = []
    for session in sessions:
        for trial, label in enumerate((1, 1, 2, 2)):
            rows.append({"sample_id": f"S{subject:03d}/ses{session}/t{trial}",
                         "subject": subject, "session": session, "run": "offline_train",
                         "label": label, "file_id": f"s{subject}-{session}.mat",
                         "raw_sha256": "a" * 64, "cue_sample_native": 2000 + 4000 * trial})
    return pd.DataFrame(rows)


def person_predictions(subject, dataset, *, broad_correct=2, shared_correct=3):
    meta = trial_meta(subject, external.DATASETS[dataset][2])
    rows = []
    for name in external.ALL_MODELS:
        seeds = external.SEEDS if name in external.DEEP_MODELS else ("deterministic",)
        for seed in seeds:
            correct = broad_correct if name == "BROAD_EEGNET" else shared_correct
            predicted = meta["label"].to_numpy().copy()
            for start in range(0, len(meta), 4):
                predicted[start + correct:start + 4] = 3 - predicted[start + correct:start + 4]
            probabilities = np.full((len(meta), 2), 0.1)
            probabilities[np.arange(len(meta)), predicted - 1] = 0.9
            rows.append(external._prediction_frame(meta, dataset, name, seed, probabilities))
    return pd.concat(rows, ignore_index=True)


def test_fixed_plan_pools_sessions_within_person_and_preserves_three_seeds():
    plan = external.STATISTICS
    assert plan["inference_unit"] == "person"
    assert plan["bootstrap_draws"] == plan["sign_flip_draws"] == 20000
    assert external.SEEDS == (20260924, 20260925, 20260926)
    assert "pool_declared_sessions" in plan["session_aggregation"]
    assert plan["target_fits"] == 0 and plan["outcome_based_selection"] is False


def test_balanced_accuracy_uses_equal_class_recalls_not_trial_accuracy():
    labels = np.array([1, 1, 1, 1, 2])
    score = external.confusion_and_ba(labels, np.ones(5, dtype=int))
    assert score["confusion_matrix_rows_actual_left_right"] == [[4, 0], [1, 0]]
    assert score["balanced_accuracy"] == 0.5
    assert score["left_recall"] == 1.0 and score["right_recall"] == 0.0
    with pytest.raises(AssertionError, match="Both binary"):
        external.confusion_and_ba([1, 1], [1, 1])


def test_seed_scores_averaged_before_equal_person_cohort_mean(monkeypatch):
    monkeypatch.setattr(external, "DATASETS", {"Cho2017": ("Q15-E006", 2, [1]),
                                            "Lee2019_MI": ("Q15-E007", 2, [1, 2])})
    frame = pd.concat([person_predictions(subject, "Lee2019_MI") for subject in (1, 2)],
                      ignore_index=True)
    result = external.summarize_cohort(frame, "Lee2019_MI")
    assert result["n_persons"] == 2 and result["n_sessions"] == 4
    assert result["primary_contrast"]["n_persons"] == 2
    assert result["cohort_equal_person_mean_balanced_accuracy"]["BROAD_EEGNET"] == 0.5
    assert result["cohort_equal_person_mean_balanced_accuracy"]["MU_BETA_SHARED"] == 0.75
    assert result["primary_contrast"]["mean_paired_balanced_accuracy_difference"] == 0.25
    assert len(result["session_strata"]) == 2 * 2 * 7
    assert all(len(row["models"]["BROAD_EEGNET"]["per_seed"]) == 3 for row in result["persons"])
    assert result["status"].endswith("pending_independent_raw_prediction_replay")


def test_primary_uses_mean_seed_ba_instead_of_ensemble_argmax(monkeypatch):
    monkeypatch.setattr(external, "DATASETS", {"Cho2017": ("Q15-E006", 2, [1]),
                                            "Lee2019_MI": ("Q15-E007", 2, [1, 2])})
    frame = pd.concat([person_predictions(subject, "Cho2017", broad_correct=4)
                       for subject in (1, 2)], ignore_index=True)
    # One perfect broadband seed and two entirely wrong seeds. The contract
    # requires mean BA=1/3, not the 0 BA of an averaged-probability ensemble.
    wrong = (frame["model"] == "BROAD_EEGNET") & frame["seed"].isin(
        [str(seed) for seed in external.SEEDS[1:]])
    frame.loc[wrong, ["p_left", "p_right"]] = frame.loc[wrong, ["p_right", "p_left"]].to_numpy()
    frame.loc[wrong, "predicted_label"] = 3 - frame.loc[wrong, "label"]
    result = external.summarize_cohort(frame, "Cho2017")
    assert result["cohort_equal_person_mean_balanced_accuracy"]["BROAD_EEGNET"] == pytest.approx(1 / 3)
    assert result["persons"][0]["models"]["BROAD_EEGNET"]["seed_sample_standard_deviation"] == pytest.approx(
        np.std([1, 0, 0], ddof=1))


@pytest.mark.parametrize("mutation,message", [
    (lambda frame: frame.drop(frame.index[0]), "metadata differs"),
    (lambda frame: pd.concat([frame, frame.iloc[:1]]), "duplicate prediction"),
    (lambda frame: frame.assign(seed="best_seed"), "model/seed coverage"),
    (lambda frame: frame.assign(label=1), "class coverage"),
    (lambda frame: frame.assign(p_left=0.9, p_right=0.9), "not normalized"),
    (lambda frame: frame.assign(p_left=np.nan), "schema/coverage"),
    (lambda frame: frame.assign(predicted_label=3), "argmax"),
])
def test_prediction_coverage_probabilities_labels_and_seeds_fail_closed(mutation, message):
    with pytest.raises(AssertionError, match=message):
        external.validate_prediction_frame(mutation(person_predictions(1, "Cho2017")), "Cho2017")


def test_metadata_cannot_be_changed_consistently_across_all_models():
    expected = trial_meta()
    frame = person_predictions(1, "Cho2017").assign(cue_sample_native=0)
    with pytest.raises(AssertionError, match="metadata differs"):
        external.validate_prediction_frame(frame, "Cho2017", expected)


def test_person_bootstrap_and_sign_flip_are_deterministic_and_bounded():
    effects = np.array([0.1, -0.2, 0.3, 0.0])
    first = external.paired_statistics(effects)
    assert first == external.paired_statistics(effects)
    assert first["n_persons"] == 4
    assert first["mean_paired_balanced_accuracy_difference"] == pytest.approx(0.05)
    assert 0 < first["two_sided_person_sign_flip_p_value"] <= 1
    assert len(first["paired_person_bootstrap_percentile_95_ci"]) == 2
    zero = external.paired_statistics(np.zeros(54))
    assert zero["two_sided_person_sign_flip_p_value"] == 1.0
    assert zero["paired_person_bootstrap_percentile_95_ci"] == [0.0, 0.0]
    for invalid in ([np.nan, 0], [0], [1.1, 0]):
        with pytest.raises(AssertionError):
            external.paired_statistics(np.array(invalid))


def test_holm_correction_requires_both_predeclared_cohorts():
    summaries = {"Cho2017": {"primary_contrast": {"two_sided_person_sign_flip_p_value": 0.04}},
                 "Lee2019_MI": {"primary_contrast": {"two_sided_person_sign_flip_p_value": 0.01}}}
    corrected = external.holm_two_cohorts(summaries)["cohorts"]
    assert corrected["Lee2019_MI"]["holm_adjusted_p_value"] == 0.02
    assert corrected["Cho2017"]["holm_adjusted_p_value"] == 0.04
    summaries["Cho2017"]["primary_contrast"]["two_sided_person_sign_flip_p_value"] = 0.015
    assert external.holm_two_cohorts(summaries)["cohorts"]["Cho2017"]["holm_adjusted_p_value"] == 0.02
    with pytest.raises(AssertionError, match="both predeclared"):
        external.holm_two_cohorts({"Cho2017": summaries["Cho2017"]})


def test_inference_gate_blocks_before_target_loader_or_model_import(monkeypatch, tmp_path):
    monkeypatch.setattr(external, "FREEZE", tmp_path / "missing.json")
    monkeypatch.setattr(external, "load_person", lambda *_: pytest.fail("target opened before freeze"))
    monkeypatch.setattr(external, "_load_source_models", lambda *_: pytest.fail("model loaded before freeze"))
    with pytest.raises(AssertionError, match="freeze missing"):
        external.run_external({"Cho2017": tmp_path / "cho.json", "Lee2019_MI": tmp_path / "lee.json"}, "cpu")


def test_fabricated_source_status_receipt_must_replay(monkeypatch, tmp_path):
    receipt = {"status": "source_validated_non_authorizing", "deep_fit_count": 14,
               "shallow_fit_count": 1, "target_fits": 0, "external_predictions_computed": False,
               "passed": True, "external_prediction_authorized": False}
    path = tmp_path / "source_validation.json"
    path.write_text(json.dumps(receipt))
    monkeypatch.setattr(external, "SOURCE_VALIDATION", path)
    monkeypatch.setattr(external, "_module", lambda *_: SimpleNamespace(
        validate_source=lambda *_, **__: {**receipt, "deep_fit_count": 13}))
    with pytest.raises(AssertionError, match="cannot be reproduced"):
        external._verify_source_validation()
    receipt["target_fits"] = 1
    path.write_text(json.dumps(receipt))
    with pytest.raises(AssertionError, match="source-only gate"):
        external._verify_source_validation()


def write_person_artifacts(tmp_path, subject=1, sessions=(1,)):
    meta = trial_meta(subject, sessions)
    csv, npz = tmp_path / f"s{subject}.csv", tmp_path / f"s{subject}.npz"
    meta.to_csv(csv, index=False)
    np.savez(npz, **{band: np.zeros((len(meta), 21, 320), dtype=np.float32)
                    for band in ("broad", "mu", "beta")})
    return {"subject": subject, "sessions": list(sessions), "n_trials": len(meta),
            "npz_path": str(npz), "npz_sha256": external._sha(npz),
            "metadata_path": str(csv), "metadata_sha256": external._sha(csv),
            "raw_file_ids": sorted(meta["file_id"].unique())}


def test_epoch_loader_checks_hashes_shape_dtype_and_trial_provenance(tmp_path):
    row = write_person_artifacts(tmp_path)
    arrays, meta = external.load_person(row, "Cho2017")
    assert arrays["broad"].shape == (4, 21, 320)
    assert meta["run"].tolist() == ["offline_train"] * 4
    np.savez(row["npz_path"], **{band: np.zeros((4, 21, 320), dtype=np.float64)
                               for band in ("broad", "mu", "beta")})
    with pytest.raises(AssertionError, match="changed after gate"):
        external.load_person(row, "Cho2017")
    row["npz_sha256"] = external._sha(Path(row["npz_path"]))
    with pytest.raises(AssertionError, match="dtype/shape"):
        external.load_person(row, "Cho2017")


def test_epoch_manifest_requires_actual_independent_replay(monkeypatch, tmp_path):
    row = write_person_artifacts(tmp_path)
    audit = tmp_path / "audit.json"
    audit.write_text("{}")
    monkeypatch.setattr(external.q15_source, "AUDIT_RECEIPTS", {"Cho2017": audit})
    monkeypatch.setattr(external, "DATASETS", {"Cho2017": ("Q15-E006", 1, [1])})
    manifest = {"schema_version": 1, "dataset": "Cho2017", "status": "epochs_verified_non_authorizing",
                "preprocessing": external._preprocessing_contract(), "subjects": [row],
                "expected_subject_ids": [1], "metadata_receipt_sha256": external._sha(audit)}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(external, "_module", lambda *_: SimpleNamespace(
        validate_epoch_manifest=lambda _: {**manifest, "metadata_receipt_sha256": "0" * 64}))
    with pytest.raises(AssertionError, match="cannot be independently reproduced"):
        external._validated_manifest(path, "Cho2017")
    manifest["preprocessing"]["target_normalization"] = True
    path.write_text(json.dumps(manifest))
    with pytest.raises(AssertionError, match="preprocessing differs"):
        external._validated_manifest(path, "Cho2017")


def test_inference_freeze_requires_both_cohorts_and_committed_identical_inputs(monkeypatch, tmp_path):
    with pytest.raises(AssertionError, match="Both Q15 cohorts"):
        external._freeze_payload({"Cho2017": tmp_path / "cho.json"})
    manifests = {dataset: tmp_path / (dataset + ".json") for dataset in external.DATASETS}
    monkeypatch.setattr(external, "FREEZE", tmp_path / "freeze.json")
    monkeypatch.setattr(external, "_freeze_payload", lambda _: {"statistics": external.STATISTICS})
    monkeypatch.setattr(external, "_committed_inputs", lambda _: [tmp_path / "changed.py"])
    monkeypatch.setattr(external.q15_source, "_assert_committed_unchanged", lambda _: (_ for _ in ()).throw(
        AssertionError("uncommitted or modified")))
    with pytest.raises(AssertionError, match="uncommitted or modified"):
        external.prepare_freeze(manifests)
    assert not external.FREEZE.exists()


def test_small_synthetic_orchestration_resume_and_corruption_fail_closed(monkeypatch, tmp_path):
    """Mock prediction only; exercise file receipts without fitting a model."""
    monkeypatch.setattr(external, "DATASETS", {"Cho2017": ("Q15-E006", 2, [1]),
                                            "Lee2019_MI": ("Q15-E007", 2, [1, 2])})
    monkeypatch.setattr(external, "OUTPUT", tmp_path / "output")
    freeze = tmp_path / "freeze.json"
    freeze.write_text("{}")
    monkeypatch.setattr(external, "FREEZE", freeze)
    monkeypatch.setattr(external, "verify_freeze", lambda _: {})
    monkeypatch.setattr(external, "_load_source_models", lambda *_: ({}, None))
    calls = []

    def prediction(_arrays, meta, dataset, *_args):
        calls.append((dataset, int(meta.iloc[0]["subject"])))
        return person_predictions(int(meta.iloc[0]["subject"]), dataset)

    monkeypatch.setattr(external, "predict_person", prediction)
    manifests = {}
    for dataset, (_, _, sessions) in external.DATASETS.items():
        directory = tmp_path / dataset
        directory.mkdir()
        persons = [write_person_artifacts(directory, subject, sessions) for subject in (1, 2)]
        file = directory / "manifest.json"
        file.write_text(json.dumps({"subjects": persons}))
        manifests[dataset] = file
    first = external.run_external(manifests, "cpu")
    assert first["scientific_validation_passed"] is False
    assert first["target_fits"] == first["new_model_fits"] == 0
    assert len(calls) == 4
    external.run_external(manifests, "cpu")
    assert len(calls) == 4  # All predictions resumed via exact receipts.
    file = external.OUTPUT / "Q15-E006/subject_001/predictions.csv"
    file.write_text("corrupt\n")
    with pytest.raises(AssertionError, match="resume blocked"):
        external.run_external(manifests, "cpu")
    assert len(calls) == 4
