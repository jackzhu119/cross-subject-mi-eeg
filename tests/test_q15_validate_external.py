"""Synthetic validator tests only: mocked gates are never real clearance receipts.

Toy tensors/models exercise replay and file integrity without reading an EEG
original, fitting a model, or executing a target cohort. Real gate entrypoints
remain unmocked in the fail-closed tests.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts import q15_external as runner
from scripts import q15_validate_external as validator


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def metadata(subject=1, sessions=(1,)):
    return pd.DataFrame([{"sample_id": f"synthetic/S{subject}/ses{session}/trial{trial}",
                         "subject": subject, "session": session, "run": "synthetic_offline",
                         "label": label, "file_id": f"synthetic_s{subject}_{session}.mat",
                         "raw_sha256": "a" * 64, "cue_sample_native": 2000 + 4000 * trial}
                        for session in sessions for trial, label in enumerate((1, 1, 2, 2))])


def probabilities(meta, correct=3):
    predicted = meta["label"].to_numpy().copy()
    for start in range(0, len(meta), 4):
        predicted[start + correct:start + 4] = 3 - predicted[start + correct:start + 4]
    result = np.full((len(meta), 2), 0.1)
    result[np.arange(len(meta)), predicted - 1] = 0.9
    return result


def frame_for(meta, dataset, broad_correct=2, shared_correct=3):
    parts = []
    for name in validator.ALL_MODELS:
        seeds = validator.SEEDS if name in validator.DEEP_MODELS else ("deterministic",)
        for seed in seeds:
            values = probabilities(meta, broad_correct if name == "BROAD_EEGNET" else shared_correct)
            frame = meta.loc[:, list(validator.META_FIELDS)].copy()
            frame["dataset"], frame["experiment_id"] = dataset, validator.DATASETS[dataset][0]
            frame["model"], frame["seed"] = name, str(seed)
            frame["p_left"], frame["p_right"] = values[:, 0], values[:, 1]
            frame["predicted_label"] = values.argmax(1) + 1
            parts.append(frame)
    return pd.concat(parts, ignore_index=True)


@pytest.fixture
def small_cohorts(monkeypatch):
    """Replace counts for tiny math fixtures, never for a real executable gate."""
    monkeypatch.setattr(validator, "DATASETS", {"Cho2017": ("Q15-E006", 2, (1,), 8),
                                             "Lee2019_MI": ("Q15-E007", 2, (1, 2), 16)})
    monkeypatch.setattr(runner, "DATASETS", {"Cho2017": ("Q15-E006", 2, [1]),
                                          "Lee2019_MI": ("Q15-E007", 2, [1, 2])})


def test_frozen_inventory_and_plan_match_runner_without_importing_its_calculations():
    assert validator.DATASETS["Cho2017"] == ("Q15-E006", 52, (1,), 10520)
    assert validator.DATASETS["Lee2019_MI"] == ("Q15-E007", 54, (1, 2), 10800)
    assert validator.STATISTICS == runner.STATISTICS
    assert validator._session_class_counts("Cho2017", 7) == {1: 120, 2: 120}
    assert validator._session_class_counts("Cho2017", 8) == {1: 100, 2: 100}
    assert validator._session_class_counts("Lee2019_MI", 1) == {1: 50, 2: 50}


def test_confusion_reconstruction_equal_class_recall():
    result = validator._score([1, 1, 1, 1, 2], [1, 1, 1, 1, 1])
    assert result["confusion_matrix_rows_actual_left_right"] == [[4, 0], [1, 0]]
    assert result["balanced_accuracy"] == 0.5
    with pytest.raises(AssertionError, match="canonical classes"):
        validator._score([1, 1], [1, 1])


def test_independent_person_draws_reproduce_frozen_runner_exactly():
    for values in (np.zeros(54), np.array([0.1, -0.2, 0.3, 0.0]),
                   np.linspace(-0.35, 0.45, 52), np.full(54, 0.25)):
        assert validator.independent_paired_statistics(values) == runner.paired_statistics(values)
    zero = validator.independent_paired_statistics(np.zeros(54))
    assert zero["two_sided_person_sign_flip_p_value"] == 1
    assert zero["paired_person_bootstrap_percentile_95_ci"] == [0.0, 0.0]


@pytest.mark.parametrize("values", [[0], [np.nan, 0], [1.01, 0], [[0, 0], [0, 0]]])
def test_independent_paired_effects_reject_invalid_units(values):
    with pytest.raises(AssertionError, match="person-level"):
        validator.independent_paired_statistics(values)


def test_independent_summary_preserves_sessions_three_seeds_and_people(small_cohorts):
    for dataset, spec in validator.DATASETS.items():
        frame = pd.concat([frame_for(metadata(subject, spec[2]), dataset) for subject in (1, 2)])
        result = validator.independent_summary(frame, dataset)
        assert result == runner.summarize_cohort(frame, dataset)
        assert result["n_persons"] == 2 and result["n_sessions"] == 2 * len(spec[2])
        assert result["primary_contrast"]["n_persons"] == 2
        assert result["cohort_equal_person_mean_balanced_accuracy"]["BROAD_EEGNET"] == 0.5
        assert result["cohort_equal_person_mean_balanced_accuracy"]["MU_BETA_SHARED"] == 0.75
        assert len(result["session_strata"]) == 2 * len(spec[2]) * 7


def test_three_seed_mean_is_not_probability_ensemble(small_cohorts):
    frame = pd.concat([frame_for(metadata(subject), "Cho2017", broad_correct=4) for subject in (1, 2)])
    mask = (frame["model"] == "BROAD_EEGNET") & frame["seed"].isin(map(str, validator.SEEDS[1:]))
    frame.loc[mask, ["p_left", "p_right"]] = frame.loc[mask, ["p_right", "p_left"]].to_numpy()
    frame.loc[mask, "predicted_label"] = 3 - frame.loc[mask, "label"]
    result = validator.independent_summary(frame, "Cho2017")
    assert result == runner.summarize_cohort(frame, "Cho2017")
    assert result["cohort_equal_person_mean_balanced_accuracy"]["BROAD_EEGNET"] == pytest.approx(1 / 3)


def test_independent_holm_family_and_monotonicity():
    summaries = {"Cho2017": {"primary_contrast": {"two_sided_person_sign_flip_p_value": 0.015}},
                 "Lee2019_MI": {"primary_contrast": {"two_sided_person_sign_flip_p_value": 0.01}}}
    assert validator.independent_holm(summaries) == runner.holm_two_cohorts(summaries)
    assert validator.independent_holm(summaries)["cohorts"]["Cho2017"]["holm_adjusted_p_value"] == 0.02
    with pytest.raises(AssertionError, match="both predeclared"):
        validator.independent_holm({"Cho2017": summaries["Cho2017"]})


@pytest.mark.parametrize("change,message", [
    (lambda frame: frame.drop(frame.index[0]), "trial coverage"),
    (lambda frame: pd.concat([frame, frame.iloc[:1]]), "trial coverage"),
    (lambda frame: frame.assign(seed="chosen_best"), "three-seed coverage"),
    (lambda frame: frame.assign(label=3), "metadata differs"),
    (lambda frame: frame.assign(cue_sample_native=0), "metadata differs"),
    (lambda frame: frame.assign(p_left=0.9, p_right=0.9), "not normalized"),
    (lambda frame: frame.assign(p_left=np.nan), "schema/null"),
    (lambda frame: frame.assign(predicted_label=3), "argmax"),
])
def test_prediction_schema_coverage_labels_and_hash_metadata_fail_closed(change, message):
    meta = metadata()
    with pytest.raises(AssertionError, match=message):
        validator._validate_prediction_frame(change(frame_for(meta, "Cho2017")), "Cho2017", meta)


def test_saved_probabilities_must_match_independent_replay():
    meta = metadata()
    frame = frame_for(meta, "Cho2017")
    replay = {(name, str(seed)): probabilities(meta, 2 if name == "BROAD_EEGNET" else 3)
              for name in validator.ALL_MODELS
              for seed in (validator.SEEDS if name in validator.DEEP_MODELS else ("deterministic",))}
    validator._compare_replay(frame, meta, replay)
    # A normalized distribution with unchanged argmax still fails numerical replay.
    frame.loc[0, ["p_left", "p_right"]] = [0.8, 0.2]
    with pytest.raises(AssertionError, match="frozen-checkpoint replay"):
        validator._compare_replay(frame, meta, replay)


def test_actual_gate_requires_both_cohorts_and_missing_freeze_blocks_before_model_import(monkeypatch, tmp_path):
    with pytest.raises(AssertionError, match="Both complete"):
        validator.validate_external({"Cho2017": tmp_path / "cho.json"}, "cpu")
    monkeypatch.setattr(validator, "FREEZE", tmp_path / "absent.json")
    monkeypatch.setattr(validator, "_device", lambda *_: pytest.fail("model device before freeze"))
    monkeypatch.setattr(validator, "_load_models", lambda *_: pytest.fail("model loaded before freeze"))
    with pytest.raises(AssertionError, match="Artifact missing"):
        validator.validate_external({"Cho2017": tmp_path / "cho.json", "Lee2019_MI": tmp_path / "lee.json"}, "cpu")
    assert not (validator.OUTPUT / "validation_report.json").exists()


def test_actual_gate_rejects_fabricated_completion_receipt(monkeypatch, tmp_path):
    freeze = tmp_path / "inference_freeze.json"
    write_json(freeze, {"passed": True, "scientific_validation_passed": True,
                        "status": "completed_with_calibration_limitations"})
    monkeypatch.setattr(validator, "FREEZE", freeze)
    with pytest.raises(AssertionError, match="Inference freeze differs"):
        validator._verify_inputs({"Cho2017": tmp_path / "cho.json", "Lee2019_MI": tmp_path / "lee.json"})


class SyntheticCSP:
    """No fit method and no fitted EEG model; only fixture probabilities."""
    def predict_proba(self, values):
        return np.tile([0.5, 0.5], (len(values), 1))


def toy_models(mutate=False):
    torch = pytest.importorskip("torch")

    class Toy(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.register_buffer("unchanged", torch.tensor([0.0]))

        def forward(self, values):
            if mutate:
                self.unchanged.add_(1)
            first = values.reshape(len(values), -1)[:, 0]
            return torch.stack((first, -first), dim=1)

    return {(name, seed): Toy() for name in validator.DEEP_MODELS for seed in validator.SEEDS}


def test_direct_synthetic_replay_preserves_models_and_maps_probability_columns():
    torch = pytest.importorskip("torch")
    models = toy_models()
    meta = metadata()
    arrays = {band: np.zeros((4, 21, 320), dtype=np.float32) for band in ("broad", "mu", "beta")}
    arrays["mu"][:, 0, 0] = arrays["beta"][:, 0, 0] = np.where(meta["label"] == 1, 2, -2)
    states = {key: validator._state_digest(model) for key, model in models.items()}
    result = validator._replay_person(arrays, meta, models, SyntheticCSP(), {"batch_size": 3}, torch.device("cpu"))
    assert len(result) == 7
    assert result["BROAD_EEGNET", str(validator.SEEDS[0])].argmax(1).tolist() == [0, 0, 0, 0]
    assert (result["MU_BETA_SHARED", str(validator.SEEDS[0])].argmax(1) + 1).tolist() == meta["label"].tolist()
    assert {key: validator._state_digest(model) for key, model in models.items()} == states


def test_synthetic_replay_detects_model_state_mutation():
    torch = pytest.importorskip("torch")
    arrays = {band: np.zeros((4, 21, 320), dtype=np.float32) for band in ("broad", "mu", "beta")}
    with pytest.raises(AssertionError, match="altered frozen neural state"):
        validator._replay_person(arrays, metadata(), toy_models(mutate=True), SyntheticCSP(),
                                  {"batch_size": 4}, torch.device("cpu"))


@pytest.fixture
def synthetic_completed_outputs(monkeypatch, tmp_path, small_cohorts):
    """Mocked gate/loader only; these fixtures cannot pass real scientific gates."""
    torch = pytest.importorskip("torch")
    monkeypatch.setattr(validator, "ROOT", tmp_path)
    monkeypatch.setattr(validator, "OUTPUT", tmp_path / "results/Q15-EXTERNAL")
    monkeypatch.setattr(validator, "FREEZE", validator.OUTPUT / "inference_freeze.json")
    monkeypatch.setattr(validator, "_session_class_counts", lambda *_: {1: 2, 2: 2})
    write_json(validator.FREEZE, {"synthetic_test_fixture": True, "not_a_real_scientific_freeze": True})
    freeze_sha = validator._sha(validator.FREEZE)
    manifests, checked, audits = {}, {}, {}
    models, csp = toy_models(), SyntheticCSP()
    config = {"batch_size": 3}
    summaries = {}
    for dataset, (experiment, _, sessions, _) in validator.DATASETS.items():
        rows, frames = [], []
        for subject in (1, 2):
            meta = metadata(subject, sessions)
            epoch_dir = tmp_path / "synthetic-epochs" / dataset
            epoch_dir.mkdir(parents=True, exist_ok=True)
            csv, npz = epoch_dir / f"s{subject}.csv", epoch_dir / f"s{subject}.npz"
            meta.to_csv(csv, index=False)
            arrays = {band: np.zeros((len(meta), 21, 320), dtype=np.float32) for band in ("broad", "mu", "beta")}
            arrays["mu"][:, 0, 0] = arrays["beta"][:, 0, 0] = np.where(meta["label"] == 1, 2, -2)
            np.savez(npz, **arrays)
            row = {"subject": subject, "sessions": list(sessions), "n_trials": len(meta),
                   "npz_path": str(npz), "npz_sha256": validator._sha(npz),
                   "metadata_path": str(csv), "metadata_sha256": validator._sha(csv),
                   "raw_file_ids": sorted(meta["file_id"].unique())}
            rows.append(row)
            directory = validator.OUTPUT / experiment / f"subject_{subject:03d}"
            directory.mkdir(parents=True)
            replay = validator._replay_person(arrays, meta, models, csp, config, torch.device("cpu"))
            parts = []
            for (name, seed), values in replay.items():
                frame = meta.copy()
                frame["dataset"], frame["experiment_id"] = dataset, experiment
                frame["model"], frame["seed"] = name, seed
                frame["p_left"], frame["p_right"] = values[:, 0], values[:, 1]
                frame["predicted_label"] = values.argmax(1) + 1
                parts.append(frame)
            frame = pd.concat(parts, ignore_index=True)
            prediction = directory / "predictions.csv"
            frame.to_csv(prediction, index=False)
            write_json(directory / "receipt.json", {"status": "complete_pending_independent_raw_prediction_replay",
                       "dataset": dataset, "subject": subject, "inference_freeze_sha256": freeze_sha,
                       "npz_sha256": row["npz_sha256"], "metadata_sha256": row["metadata_sha256"],
                       "target_fits": 0, "new_model_fits": 0, "n_trials": len(meta),
                       "n_prediction_rows": 7 * len(meta), "predictions_sha256": validator._sha(prediction)})
            frames.append(frame)
        aggregate = pd.concat(frames, ignore_index=True)
        root = validator.OUTPUT / experiment
        aggregate.to_csv(root / "predictions.csv", index=False)
        summaries[dataset] = runner.summarize_cohort(aggregate, dataset)
        write_json(root / "statistics.json", summaries[dataset])
        manifest_path = validator.OUTPUT / "manifests" / f"{dataset}.json"
        checked[dataset] = {"synthetic_test_fixture": True, "subjects": rows}
        write_json(manifest_path, checked[dataset])
        manifests[dataset] = manifest_path
        audits[dataset] = {"synthetic_test_fixture": True,
                           "files": [None] * (2 * len(sessions))}
    holm = runner.holm_two_cohorts(summaries)
    write_json(validator.OUTPUT / "holm_two_cohorts.json", holm)
    completion = {"schema_version": 1, "status": "inference_complete_pending_independent_raw_prediction_replay",
                  "target_fits": 0, "new_model_fits": 0, "scientific_validation_passed": False,
                  "inference_freeze_sha256": freeze_sha, "statistics_plan": runner.STATISTICS,
                  "cohort_prediction_sha256": {dataset: validator._sha(validator.OUTPUT / spec[0] / "predictions.csv")
                                               for dataset, spec in validator.DATASETS.items()},
                  "cohort_statistics_sha256": {dataset: validator._sha(validator.OUTPUT / spec[0] / "statistics.json")
                                               for dataset, spec in validator.DATASETS.items()},
                  "holm_sha256": validator._sha(validator.OUTPUT / "holm_two_cohorts.json")}
    write_json(validator.OUTPUT / "completion_receipt.json", completion)
    monkeypatch.setattr(validator, "_verify_inputs", lambda _: ({"source_checkpoints": {}}, config, checked, audits))
    monkeypatch.setattr(validator, "_load_models", lambda *_: (models, csp))
    return manifests


def test_synthetic_completed_replay_read_only_then_report_preserves_limitations(synthetic_completed_outputs):
    manifests = synthetic_completed_outputs
    report = validator.validate_external(manifests, "cpu", write_report=False)
    report_file = validator.OUTPUT / "validation_report.json"
    assert not report_file.exists()
    assert report["passed"] is True and report["status"] == "completed_with_calibration_limitations"
    assert report["coverage"]["Cho2017"]["n_prediction_rows"] == 56
    assert report["coverage"]["Lee2019_MI"]["n_sessions"] == 4
    assert report["target_fits"] == report["new_model_fits"] == 0
    assert all(report[key] is False for key in ("calibration_verified", "native_export_units_verified",
                                              "cho_original_reference_verified", "hardware_cue_latency_verified"))
    assert len(report["calibration_limitations"]) == 3
    written = validator.validate_external(manifests, "cpu", write_report=True)
    assert json.loads(report_file.read_text()) == written == report
    assert validator.validate_external(manifests, "cpu", write_report=False) == written
    assert all(relative.startswith("results/Q15-EXTERNAL/") for relative in report["artifact_sha256"])


def test_synthetic_committed_manifest_paths_outside_output_remain_valid_inputs(synthetic_completed_outputs, monkeypatch):
    manifests = synthetic_completed_outputs
    outside = validator.ROOT / "synthetic-manifest-inputs"
    outside.mkdir()
    moved = {}
    for dataset, path in manifests.items():
        destination = outside / path.name
        path.rename(destination)
        moved[dataset] = destination
    report = validator.validate_external(moved, "cpu", write_report=False)
    assert set(report["epoch_manifest_sha256"]) == set(validator.DATASETS)
    assert all("synthetic-manifest-inputs" not in relative for relative in report["artifact_sha256"])


@pytest.mark.parametrize("artifact,change,message", [
    ("Q15-E006/subject_001/predictions.csv", lambda path: path.write_text("corrupt\n"), "SHA256 mismatch"),
    ("Q15-E006/statistics.json", lambda path: write_json(path, {"passed": True}), "statistics differ"),
    ("holm_two_cohorts.json", lambda path: write_json(path, {"passed": True}), "Holm statistics differ"),
    ("completion_receipt.json", lambda path: write_json(path, {"passed": True}), "completion receipt differs"),
    ("Q15-E006/extra-fit.joblib", lambda path: path.write_bytes(b"unexpected fixture"), "Unexpected or missing"),
])
def test_synthetic_output_corruption_never_writes_pass(synthetic_completed_outputs, artifact, change, message):
    path = validator.OUTPUT / artifact
    change(path)
    with pytest.raises(AssertionError, match=message):
        validator.validate_external(synthetic_completed_outputs, "cpu")
    assert not (validator.OUTPUT / "validation_report.json").exists()


def test_symlinked_prediction_file_rejected(tmp_path):
    source = tmp_path / "fixture.csv"
    source.write_text("synthetic\n")
    link = tmp_path / "symlink.csv"
    link.symlink_to(source)
    with pytest.raises(AssertionError, match="symlinked"):
        validator._checked_file(link, validator._sha(source))


@pytest.mark.parametrize("digest", [None, "", "a" * 63, "A" * 64, 42])
def test_supplied_hash_must_be_present_lowercase_sha256(tmp_path, digest):
    path = tmp_path / "synthetic-fixture.csv"
    path.write_text("fixture bytes\n")
    assert validator._checked_file(path) == path
    with pytest.raises(AssertionError, match="Missing or malformed artifact SHA256"):
        validator._checked_file(path, digest)


def test_synthetic_missing_prediction_digest_fails_even_when_probabilities_replay(synthetic_completed_outputs):
    path = validator.OUTPUT / "Q15-E006/subject_001/receipt.json"
    receipt = json.loads(path.read_text())
    receipt.pop("predictions_sha256")
    write_json(path, receipt)
    with pytest.raises(AssertionError, match="Missing or malformed artifact SHA256"):
        validator.validate_external(synthetic_completed_outputs, "cpu")


def test_nonfinite_json_status_cannot_be_accepted(tmp_path):
    path = tmp_path / "fixture.json"
    path.write_text('{"value": NaN}')
    with pytest.raises(ValueError, match="Nonfinite JSON"):
        validator._json(path)
