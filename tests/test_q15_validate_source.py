"""Synthetic artifact-only checks: never load EEG, fit, or create usable gates."""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
import torch
from mne.decoding import CSP
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from scripts import q15_validate_source as validator

PROJECT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def mutate_json(path, change):
    value = json.loads(path.read_text())
    change(value)
    write_json(path, value)


def update_hash(job, filename, field):
    mutate_json(job / "manifest.json", lambda value: value.update({field: validator._sha(job / filename)}))


def fixture_config():
    config = json.loads((PROJECT / "research_runs/Q14-E001/CONFIG.json").read_text())
    config["channels"].remove("FCz")
    config["architecture"].update(n_chans=21, n_times=320)
    config.update(n_times=320, cue_relative_stop_exclusive_s=2.5, source_trial_stop_exclusive_s=4.5)
    config.update(execution_context_relative_s=[-1.5, 4.5], execution_reference="common_average_21", execution_filter_scope="each_real_retained_trial_context", execution_filter_padlen=27, execution_contract_sha256="c" * 64, execution_csp_basis="fixed_21_to_20_helmert")
    return config


@pytest.fixture(scope="module")
def artifact_template(tmp_path_factory):
    """Construct placeholders, not trained models, inside a test-only directory."""
    root = tmp_path_factory.mktemp("q15-synthetic-artifacts")
    config = fixture_config()
    for relative in ("research_runs/Q14-E001/CONFIG.json", "requirements-q15-runtime.txt"):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT / relative, target)
    output = root / "results/Q15-E005"
    write_json(output / "pre_fit_freeze.json", {"synthetic_test_fixture": True, "not_a_real_scientific_freeze": True})
    protocol = validator._sha(output / "pre_fit_freeze.json")
    files, frozen = [], []
    raw = root / "raw"
    raw.mkdir()
    for subject in range(1, 10):
        for session in ("E", "T"):
            path = raw / f"A{subject:02d}{session}.mat"
            path.write_bytes(f"test-placeholder-not-MAT-{path.name}".encode())
            row = {"filename": path.name, "bytes": path.stat().st_size, "sha256": validator._sha(path)}
            files.append(row)
            frozen.append({"path": str(path), "bytes": row["bytes"], "sha256": row["sha256"]})
    write_json(root / "research_runs/Q8-E001/results/source_files.json", frozen)
    stage = output / "source"
    write_json(stage / "source_files.json", {"files": files})
    import hashlib
    pins = dict(line.split("==", 1) for line in (root / "requirements-q15-runtime.txt").read_text().splitlines() if "==" in line and not line.startswith("#"))
    runtime = {"python": "3.12.synthetic-test", "packages": {**pins, "torch": "2.8.0+cu128", "torchaudio": "2.8.0+cu128"}, "cuda_available": False}
    write_json(stage / "run_config.json", {"experiment_id": "Q15-E005", "status": "source_fitting_not_external_validation", "pre_fit_freeze_sha256": protocol, "contract_sha256": "a" * 64, "runner_sha256": "b" * 64, "execution_contract_sha256": "c" * 64, "source_config": config, "source_file_receipt_sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(), "data_dir": str(raw), "device": "cpu", "runtime": runtime})
    metadata, audits = [], []
    full_channels = json.loads((root / "research_runs/Q14-E001/CONFIG.json").read_text())["channels"]
    for subject in range(1, 10):
        for session in ("0train", "1test"):
            for run in range(6):
                for trial in range(1, 25):
                    metadata.append({"sample_id": f"s{subject:02d}_{session}_r{run}_t{trial:02d}", "subject": subject, "session": session, "run": run, "trial": trial, "label": 1 if trial <= 12 else 2, "event_sample": trial * 1500, "artifact_flagged": False})
                audits.append({"subject": subject, "session": session, "run": run, "n_all_four_class_trials": 48, "n_candidate_trials": 24, "n_source_artifact_flags_all_classes": 0, "n_flagged_trials": 0, "n_rejected_trials": 0, "n_kept_trials": 24, "n_times_per_epoch": 500, "n_eeg_channels": 22, "sampling_rate_hz": 250.0, "native_sampling_rate_hz": 250.0, "artifact_policy": "include_all", "class_counts_candidate": '{"1": 12, "2": 12}', "class_counts_kept": '{"1": 12, "2": 12}', "class_counts_flagged": '{"1": 0, "2": 0}', "eeg_channel_names": json.dumps(full_channels), "output_n_times": 320, "output_n_channels": 21, "common_rate": 160, "transform_context_relative_s": json.dumps([-1.5, 4.5]), "reference": "common_average_21", "padlen": 27, "output_channel_names": json.dumps(config["channels"]), "preprocessing": "q15_uniform_trial_context_v1", "n_class_1_candidate": 12, "n_class_1_kept": 12, "n_class_1_flagged": 0, "n_class_2_candidate": 12, "n_class_2_kept": 12, "n_class_2_flagged": 0})
    meta = pd.DataFrame(metadata)
    meta.to_csv(stage / "source_metadata.csv", index=False)
    full_q8 = list(metadata)
    for subject in range(1, 10):
        for session in ("0train", "1test"):
            for run in range(6):
                for trial in range(25, 49):
                    full_q8.append({"sample_id": f"s{subject:02d}_{session}_r{run}_t{trial:02d}", "subject": subject, "session": session, "run": run, "trial": trial, "label": 3 if trial <= 36 else 4, "event_sample": trial * 1500, "artifact_flagged": False})
    pd.DataFrame(full_q8).sort_values(["subject", "session", "run", "trial"]).to_csv(root / "research_runs/Q8-E001/results/trial_metadata.csv", index=False)
    pd.DataFrame(audits).to_csv(stage / "source_audit.csv", index=False)
    from braindecode.models import EEGNet
    parameters = {key: value for key, value in config["architecture"].items() if key not in {"library", "model"}}
    with torch.random.fork_rng(devices=[]):
        eegnet = EEGNet(**parameters)
    state = eegnet.state_dict()
    for model in validator.MODELS:
        base = stage / model / "all_source"
        for fold, subjects in enumerate(config["q14_e002_inner_groups"], 1):
            train_subjects = [s for s in range(1, 10) if s not in subjects]
            train_ids = meta.loc[meta["subject"].isin(train_subjects), "sample_id"]
            val_ids = meta.loc[meta["subject"].isin(subjects), "sample_id"]
            required = {"experiment_id": "Q15-E005", "model": model, "inner_fold": fold, "train_subjects": train_subjects, "validation_subjects": subjects, "train_sample_ids_sha256": validator._ids(train_ids), "validation_sample_ids_sha256": validator._ids(val_ids), "seed": config["selection_seed"], "epochs": 40, "protocol_sha256": protocol}
            make_fit(base / f"inner_{fold:02d}", state, required, validation=True)
        selection = {"experiment_id": "Q15-E005", "model": model, "source_subjects": config["source_subjects"], "validation_groups": config["q14_e002_inner_groups"], "selected_epoch": 3, "selection_rule": config["source_only_epoch_rule"], "inner_curve_sha256": [validator._sha(base / f"inner_{fold:02d}/curve.json") for fold in range(1, 5)], "protocol_sha256": protocol}
        write_json(base / "selection.json", selection)
        for seed in config["final_seeds"]:
            required = {"experiment_id": "Q15-E005", "model": model, "train_subjects": config["source_subjects"], "train_sample_ids_sha256": validator._ids(meta["sample_id"]), "seed": seed, "epochs": 3, "protocol_sha256": protocol}
            make_fit(base / f"final_seed_{seed}", state, required, validation=False)
    csp_path = stage / "CSP4_LDA/all_source"
    csp_path.mkdir(parents=True)
    csp = CSP(n_components=4, reg=None, log=True, cov_est="concat", norm_trace=False, rank="full", component_order="mutual_info")
    csp.classes_ = np.array([1, 2])
    csp.filters_ = csp.patterns_ = np.eye(20)
    csp.mean_, csp.std_ = np.ones(4), np.ones(4)
    scaler = StandardScaler()
    scaler.n_features_in_, scaler.mean_, scaler.scale_ = 4, np.zeros(4), np.ones(4)
    scaler.var_, scaler.n_samples_seen_ = np.ones(4), 2592
    lda = LinearDiscriminantAnalysis(solver="svd")
    lda.classes_, lda.n_features_in_, lda.coef_, lda.intercept_ = np.array([1, 2]), 4, np.zeros((1, 4)), np.zeros(1)
    lda.means_, lda.priors_, lda.xbar_, lda.scalings_, lda.explained_variance_ratio_ = np.zeros((2, 4)), np.array([0.5, 0.5]), np.zeros(4), np.ones((4, 1)), np.ones(1)
    from mi_eeg.models.q15_csp import FixedCARBasis
    joblib.dump(Pipeline([("fixed_car_basis", FixedCARBasis()), ("csp", csp), ("scaler", scaler), ("lda", lda)]), csp_path / "model.joblib")
    write_json(csp_path / "manifest.json", {"experiment_id": "Q15-E005", "model": "CSP4_LDA", "train_subjects": config["source_subjects"], "train_sample_ids_sha256": validator._ids(meta["sample_id"]), "protocol_sha256": protocol, "status": "complete", "n_source_trials": 2592, "model_sha256": validator._sha(csp_path / "model.joblib")})
    write_json(stage / "source_stage_complete.json", {"experiment_id": "Q15-E005", "status": "fits_complete_pending_independent_source_validation", "deep_fit_count": 14, "shallow_fit_count": 1, "external_predictions_computed": False, "external_prediction_authorized": False, "pre_fit_freeze_sha256": protocol, "completed_at_utc": "2026-10-03T00:00:00+00:00"})
    return root


def make_fit(path, state, required, validation):
    path.mkdir(parents=True)
    model = required["model"]
    tensors = {("eegnet." + key if model == "MU_BETA_SHARED" else key): value.clone() for key, value in state.items()}
    for name, value in tensors.items():
        if name.endswith("num_batches_tracked"):
            import math
            value.add_(required["epochs"] * math.ceil(288 * len(required["train_subjects"]) / 64))
    torch.save({"state_dict": tensors, "model": model, "seed": required["seed"], "epochs": required["epochs"]}, path / "checkpoint.pt")
    curves = [{"epoch": epoch, "train_ce": 1.0 / epoch, "val_ce": (0.1 if epoch == 3 else 1.0 + epoch / 100) if validation else None} for epoch in range(1, required["epochs"] + 1)]
    write_json(path / "curve.json", {"epochs": curves})
    write_json(path / "manifest.json", {**required, "status": "complete", "checkpoint_sha256": validator._sha(path / "checkpoint.pt"), "curve_sha256": validator._sha(path / "curve.json")})


@pytest.fixture
def artifacts(artifact_template, tmp_path, monkeypatch):
    root = tmp_path / "fixture"
    shutil.copytree(artifact_template, root)
    monkeypatch.setattr(validator, "ROOT", root)
    output = root / "results/Q15-E005"
    mutate_json(output / "source/run_config.json", lambda value: value.update(data_dir=str(root / "raw")))
    config = fixture_config()
    freeze = {"contract_sha256": "a" * 64, "runner_sha256": "b" * 64, "execution_contract_sha256": "c" * 64}
    # Test-only patch isolates artifact validation. Placeholder receipts cannot
    # pass the real _verify_protocol function and never authorize real fitting.
    monkeypatch.setattr(validator, "_verify_protocol", lambda out: (copy.deepcopy(config), freeze, validator._sha(out / "pre_fit_freeze.json")))
    return output


def test_complete_source_artifact_validation_is_stable_non_authorizing(artifacts):
    report = validator.validate_source(artifacts)
    assert report["status"] == "source_validated_non_authorizing"
    assert report["counts"] == {"deep_inner": 8, "deep_final": 6, "shallow": 1, "predictions": 0}
    assert report["target_fits"] == 0 and report["external_prediction_authorized"] is False
    assert report["external_predictions_computed"] is False
    assert report["selected_epochs"] == {"BROAD_EEGNET": 3, "MU_BETA_SHARED": 3}
    assert json.loads((artifacts / "source_validation.json").read_text()) == report
    assert "results/Q15-E005/pre_fit_freeze.json" in report["artifact_sha256"]
    assert "results/Q15-E005/source/CSP4_LDA/all_source/model.joblib" in report["artifact_sha256"]
    assert report["execution_contract_sha256"] == "c" * 64
    assert report["csp_coordinate_rule"] == "fixed_21_to_20_helmert"
    assert report["calibration_verified"] is False
    assert len([name for name in report["artifact_sha256"] if "/final_seed_" in name and name.endswith("checkpoint.pt")]) == 6
    assert validator.validate_source(artifacts) == report


def test_rank_selection_uses_equal_fold_tie_ranks_and_earliest_epoch():
    curves = [[{"val_ce": value} for value in values] for values in ([1, 1, 2], [1, 1, 2], [2, 2, 1], [2, 2, 1])]
    assert validator.independent_rank_epoch(curves) == 1
    with pytest.raises(AssertionError, match="Four"):
        validator.independent_rank_epoch(curves[:3])


@pytest.mark.parametrize("field,value", [("train_sample_ids_sha256", "0" * 64), ("validation_sample_ids_sha256", "0" * 64), ("train_subjects", [1, 2]), ("protocol_sha256", "0" * 64), ("seed", 999)])
def test_inner_provenance_or_partition_forgery_rejected(artifacts, field, value):
    path = artifacts / "source/BROAD_EEGNET/all_source/inner_01/manifest.json"
    mutate_json(path, lambda row: row.update({field: value}))
    with pytest.raises(AssertionError, match="mismatched"):
        validator.validate_source(artifacts)


@pytest.mark.parametrize("change", ["negative_train", "missing_epoch", "target_validation"])
def test_tampered_curves_rejected_even_with_updated_manifest_hash(artifacts, change):
    job = artifacts / "source/BROAD_EEGNET/all_source" / ("final_seed_20260924" if change == "target_validation" else "inner_01")
    def mutate(value):
        if change == "negative_train":
            value["epochs"][0]["train_ce"] = -1
        elif change == "missing_epoch":
            value["epochs"].pop()
        else:
            value["epochs"][0]["val_ce"] = 0.1
    mutate_json(job / "curve.json", mutate)
    update_hash(job, "curve.json", "curve_sha256")
    with pytest.raises(AssertionError):
        validator.validate_source(artifacts)


@pytest.mark.parametrize("change", ["shape", "nonfinite", "seed", "missing_tensor"])
def test_checkpoint_forgery_rejected_after_hash_update(artifacts, change):
    job = artifacts / "source/MU_BETA_SHARED/all_source/final_seed_20260924"
    checkpoint = torch.load(job / "checkpoint.pt", map_location="cpu", weights_only=True)
    key = next(name for name, tensor in checkpoint["state_dict"].items() if tensor.dtype.is_floating_point and tensor.numel() > 1)
    if change == "shape":
        checkpoint["state_dict"][key] = checkpoint["state_dict"][key].flatten()[:1]
    elif change == "nonfinite":
        checkpoint["state_dict"][key].flatten()[0] = float("nan")
    elif change == "seed":
        checkpoint["seed"] = 999
    else:
        checkpoint["state_dict"].pop(key)
    torch.save(checkpoint, job / "checkpoint.pt")
    update_hash(job, "checkpoint.pt", "checkpoint_sha256")
    with pytest.raises(AssertionError):
        validator.validate_source(artifacts)


def test_wrong_rank_epoch_rejected(artifacts):
    path = artifacts / "source/BROAD_EEGNET/all_source/selection.json"
    mutate_json(path, lambda value: value.update(selected_epoch=4))
    with pytest.raises(AssertionError, match="rank selection"):
        validator.validate_source(artifacts)


@pytest.mark.parametrize("change", ["external_subject", "duplicate_id", "reorder", "run_missing", "false_class_balance"])
def test_source_trial_identity_or_external_contamination_rejected(artifacts, change):
    path = artifacts / "source/source_metadata.csv"
    frame = pd.read_csv(path)
    if change == "external_subject":
        frame.loc[0, "subject"] = 52
    elif change == "duplicate_id":
        frame.loc[0, "sample_id"] = frame.loc[1, "sample_id"]
    elif change == "reorder":
        frame = frame.iloc[::-1]
    elif change == "run_missing":
        frame.loc[frame["run"] == 5, "run"] = 4
    else:
        frame.loc[0, "label"] = 2
    frame.to_csv(path, index=False)
    with pytest.raises(AssertionError):
        validator.validate_source(artifacts)


def test_native_audit_window_shape_rejected(artifacts):
    path = artifacts / "source/source_audit.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "n_times_per_epoch"] = 750
    frame.to_csv(path, index=False)
    with pytest.raises(AssertionError, match="n_times_per_epoch"):
        validator.validate_source(artifacts)


@pytest.mark.parametrize("name", ["predictions.csv", "MU_BETA_SHARED/all_source/extra_fit/checkpoint.pt"])
def test_extra_fit_or_predictions_rejected(artifacts, name):
    path = artifacts / "source" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("unexpected external outcome or fit")
    with pytest.raises(AssertionError, match="Unexpected/missing"):
        validator.validate_source(artifacts)


def test_missing_fit_rejected(artifacts):
    (artifacts / "source/BROAD_EEGNET/all_source/final_seed_20260924/checkpoint.pt").unlink()
    with pytest.raises(AssertionError, match="missing"):
        validator.validate_source(artifacts)


def test_raw_bnci_change_rejected_before_checkpoint_reads(artifacts):
    (validator.ROOT / "raw/A01T.mat").write_bytes(b"changed")
    with pytest.raises(AssertionError, match="byte count"):
        validator.validate_source(artifacts)


def test_wrong_fit_counts_rejected(artifacts):
    mutate_json(artifacts / "source/source_stage_complete.json", lambda value: value.update(deep_fit_count=15))
    with pytest.raises(AssertionError, match="deep_fit_count"):
        validator.validate_source(artifacts)


def test_forged_runtime_package_rejected(artifacts):
    mutate_json(artifacts / "source/run_config.json", lambda value: value["runtime"]["packages"].update(braindecode="0.0"))
    with pytest.raises(AssertionError, match="dependency differs"):
        validator.validate_source(artifacts)


def test_csp_wrong_channel_shape_rejected_after_hash_update(artifacts):
    job = artifacts / "source/CSP4_LDA/all_source"
    pipeline = joblib.load(job / "model.joblib")
    pipeline.named_steps["csp"].filters_ = np.eye(22)
    joblib.dump(pipeline, job / "model.joblib")
    update_hash(job, "model.joblib", "model_sha256")
    with pytest.raises(AssertionError, match="CSP fitted shape"):
        validator.validate_source(artifacts)


def test_no_report_written_on_failure(artifacts):
    mutate_json(artifacts / "source/source_stage_complete.json", lambda value: value.update(external_predictions_computed=True))
    with pytest.raises(AssertionError):
        validator.validate_source(artifacts)
    assert not (artifacts / "source_validation.json").exists()


def test_uncommitted_freeze_is_rejected_before_source_artifact_reads(tmp_path):
    # Production protocol verification is not mocked here.
    with pytest.raises(FileNotFoundError):
        validator.validate_source(tmp_path)


def test_committed_byte_check_rejects_modified_protocol(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setattr(validator, "ROOT", tmp_path)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    path = tmp_path / "protocol.json"
    path.write_text('{"fixture":true}\n')
    subprocess.run(["git", "add", "protocol.json"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "test fixture"], cwd=tmp_path, check=True)
    validator._committed(path)
    path.write_text('{"fixture":false}\n')
    with pytest.raises(AssertionError, match="committed unchanged"):
        validator._committed(path)


def test_read_only_source_validation_keeps_report_absent(artifacts):
    report = validator.validate_source(artifacts, write_report=False)
    assert report["passed"] is True
    assert not (artifacts / "source_validation.json").exists()


@pytest.mark.parametrize("location", ["predictions.csv", "external/predictions.csv", "source/extra_fit", "source/target_subject_52"])
def test_extra_outputs_or_empty_fit_directories_fail_before_model_reads(artifacts, monkeypatch, location):
    path = artifacts / location
    if path.suffix:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("external outcome")
    else:
        path.mkdir(parents=True)
    monkeypatch.setattr(validator, "_state_schema", lambda *_: pytest.fail("Model construction reached before ledger rejection"))
    with pytest.raises(AssertionError, match="Unexpected/missing"):
        validator.validate_source(artifacts)


def test_symlinked_checkpoint_fails_before_model_reads(artifacts, monkeypatch, tmp_path):
    path = artifacts / "source/BROAD_EEGNET/all_source/final_seed_20260924/checkpoint.pt"
    target = tmp_path / "checkpoint.pt"
    path.replace(target)
    path.symlink_to(target)
    monkeypatch.setattr(validator, "_state_schema", lambda *_: pytest.fail("Model construction reached before symlink rejection"))
    with pytest.raises(AssertionError, match="Symlinked"):
        validator.validate_source(artifacts)


@pytest.mark.parametrize("field,value", [("reference", "native"), ("padlen", 24), ("output_n_channels", 22), ("output_n_times", 480), ("common_rate", 250), ("transform_context_relative_s", "[-1.0, 4.5]"), ("output_channel_names", '["FCz"]')])
def test_context_car_or_processed_audit_forgery_rejected(artifacts, field, value):
    path = artifacts / "source/source_audit.csv"
    frame = pd.read_csv(path)
    frame.loc[0, field] = value
    frame.to_csv(path, index=False)
    with pytest.raises(AssertionError):
        validator.validate_source(artifacts)


@pytest.mark.parametrize("field,value", [("learning_rate", 0.002), ("batch_size", 128), ("execution_reference", "native"), ("execution_csp_basis", "learned_PCA"), ("execution_contract_sha256", "0" * 64)])
def test_actual_source_run_config_must_match_independent_derivation(artifacts, field, value):
    mutate_json(artifacts / "source/run_config.json", lambda record: record["source_config"].update({field: value}))
    with pytest.raises(AssertionError, match="mismatched source_config"):
        validator.validate_source(artifacts)


@pytest.mark.parametrize("package", ["torch", "torchaudio"])
def test_training_cuda_template_runtime_is_pinned(artifacts, package):
    mutate_json(artifacts / "source/run_config.json", lambda record: record["runtime"]["packages"].update({package: "2.14.0"}))
    with pytest.raises(AssertionError, match="dependency differs"):
        validator.validate_source(artifacts)


def test_untrained_checkpoint_counter_cannot_fake_completed_fit(artifacts):
    job = artifacts / "source/BROAD_EEGNET/all_source/final_seed_20260924"
    checkpoint = torch.load(job / "checkpoint.pt", map_location="cpu", weights_only=True)
    for name, tensor in checkpoint["state_dict"].items():
        if name.endswith("num_batches_tracked"):
            tensor.fill_(1)
    torch.save(checkpoint, job / "checkpoint.pt")
    update_hash(job, "checkpoint.pt", "checkpoint_sha256")
    with pytest.raises(AssertionError, match="BatchNorm training count"):
        validator.validate_source(artifacts)


@pytest.mark.parametrize("value", [True, 14.0])
def test_fit_budget_requires_integer_count(artifacts, value):
    mutate_json(artifacts / "source/source_stage_complete.json", lambda record: record.update(deep_fit_count=value))
    with pytest.raises(AssertionError, match="deep_fit_count"):
        validator.validate_source(artifacts)


@pytest.mark.parametrize("value", [0, None, "false"])
def test_non_authorizing_flags_require_json_false(value):
    with pytest.raises(AssertionError, match="mismatched"):
        validator._fields({"external_prediction_authorized": value}, {"external_prediction_authorized": False}, "non-authorizing gate")


def test_duplicate_json_key_cannot_shadow_failed_status(tmp_path):
    path = tmp_path / "forged.json"
    path.write_text('{"passed":false,"passed":true}')
    with pytest.raises(AssertionError, match="Duplicate JSON field"):
        validator._read(path)


@pytest.mark.parametrize("change", ["basis", "missing_scaler_state", "sample_count", "class_priors", "nonfinite_lda"])
def test_csp_basis_and_complete_fitted_state_are_checked(artifacts, change):
    job = artifacts / "source/CSP4_LDA/all_source"
    pipeline = joblib.load(job / "model.joblib")
    if change == "basis":
        pipeline.named_steps["fixed_car_basis"].n_channels = 22
    elif change == "missing_scaler_state":
        del pipeline.named_steps["scaler"].var_
    elif change == "sample_count":
        pipeline.named_steps["scaler"].n_samples_seen_ = 100
    elif change == "class_priors":
        pipeline.named_steps["lda"].priors_ = np.array([0.9, 0.1])
    else:
        pipeline.named_steps["lda"].means_[0, 0] = np.nan
    joblib.dump(pipeline, job / "model.joblib")
    update_hash(job, "model.joblib", "model_sha256")
    with pytest.raises((AssertionError, AttributeError)):
        validator.validate_source(artifacts)


@pytest.fixture
def synthetic_metadata_provenance(tmp_path, monkeypatch):
    """Exercise byte-only provenance with explicitly synthetic, unusable gates."""
    import hashlib
    monkeypatch.setattr(validator, "ROOT", tmp_path)
    channels = fixture_config()["channels"]
    rows, manifest_rows, provider_rows, transport = [], [], [], []
    for subject in range(1, 53):
        file_id = f"s{subject:02d}.mat"
        path = tmp_path / "raw" / file_id
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = f"synthetic-not-MAT-{subject:02d}".encode()
        path.write_bytes(payload)
        digests = {"sha256": hashlib.sha256(payload).hexdigest(), "md5": hashlib.md5(payload).hexdigest(), "size_bytes": len(payload)}
        rows.append({"file_id": file_id, "path": str(path), **digests, "subject": subject, "session": 1, "run": "retained_labeled_MI", "channels": channels, "cue_origin": "MI_cue_onset", "task": "left_right_motor_imagery", "labeled": True, "label_map": {"left_hand": 1, "right_hand": 2}, "loader_output_unit": "V", "declared_analysis_unit": "uV", "native_numeric_calibration_verified": False, "hardware_cue_latency_verified": False, "context_bounds_verified": True, "no_outcomes_inspected": True, "execution_contract_sha256": "c" * 64, "n_labeled_trials": 240 if subject in (7, 9, 46) else 200, "sampling_rate_hz": 512, "run_role": "offline_labeled", "available_cue_window_s": [-1.5, 4.5]})
        manifest_rows.append({"file_id": file_id, "path": str(path), "sha256": digests["sha256"], "subject": subject, "session": 1, "run": "retained_labeled_MI"})
        provider_rows.append({"file_id": file_id, "size_bytes": len(payload), "provider_md5": digests["md5"]})
        transport.append({"dataset": "Cho2017", "file_id": file_id, **digests})
    ids = [row["file_id"] for row in rows]
    manifest_path = tmp_path / "synthetic_manifest.json"
    write_json(manifest_path, {"schema_version": 1, "dataset": "Cho2017", "expected_file_ids": ids, "files": manifest_rows})
    write_json(tmp_path / "research_runs/Q15-EXECUTION-20261003/evidence/cho_transfer_manifest.json", {"schema_version": 1, "dataset": "Cho2017", "expected_file_ids": ids, "files": provider_rows})
    write_json(tmp_path / "research_runs/Q15-PREPARATION/transport_inventory.json", {"schema_version": 1, "files": transport})
    receipt = {"synthetic_fixture": True, "status": "metadata_passed_non_authorizing_synthetic_fixture", "failed_files": [], "blocking_reasons": [], "provider_version": "synthetic", "loader_version": "synthetic", "license": "test-only", "provider_inventory_source": "synthetic fixture", "expected_file_ids": ids, "files": rows, "execution_contract_sha256": "c" * 64}
    return receipt, manifest_path, channels


def test_external_provenance_component_rehashes_all_test_bytes(synthetic_metadata_provenance):
    receipt, manifest_path, channels = synthetic_metadata_provenance
    validator._verify_metadata_receipt(receipt, manifest_path, "Cho2017", channels)
    # This component-level fixture still fails the real non-synthetic gate.
    with pytest.raises(AssertionError, match="mismatched synthetic_fixture"):
        validator._fields(receipt, {"synthetic_fixture": False}, "real metadata gate")


@pytest.mark.parametrize("change", ["raw_bytes", "manifest_sha", "provider_md5", "transport_sha", "canonical_subject", "short_context", "failed_files", "blocking_reasons", "false_calibration"])
def test_forged_metadata_provenance_fails_closed(synthetic_metadata_provenance, change):
    receipt, manifest_path, channels = synthetic_metadata_provenance
    if change == "raw_bytes":
        Path(receipt["files"][0]["path"]).write_bytes(b"x" * receipt["files"][0]["size_bytes"])
    elif change == "manifest_sha":
        mutate_json(manifest_path, lambda value: value["files"][0].update(sha256="0" * 64))
    elif change == "provider_md5":
        path = validator.ROOT / "research_runs/Q15-EXECUTION-20261003/evidence/cho_transfer_manifest.json"
        mutate_json(path, lambda value: value["files"][0].update(provider_md5="0" * 32))
    elif change == "transport_sha":
        path = validator.ROOT / "research_runs/Q15-PREPARATION/transport_inventory.json"
        mutate_json(path, lambda value: value["files"][0].update(sha256="0" * 64))
    elif change == "canonical_subject":
        receipt["files"][0]["subject"] = 2
        mutate_json(manifest_path, lambda value: value["files"][0].update(subject=2))
    elif change == "short_context":
        receipt["files"][0]["available_cue_window_s"] = [-1.0, 4.5]
    elif change in ("failed_files", "blocking_reasons"):
        receipt[change] = ["test_failure"]
    else:
        receipt["files"][0]["native_numeric_calibration_verified"] = True
    with pytest.raises(AssertionError):
        validator._verify_metadata_receipt(receipt, manifest_path, "Cho2017", channels)


@pytest.mark.parametrize("change", ["native_event", "balanced_label_swap"])
def test_coherent_source_identity_forgery_is_rejected_against_frozen_q8(artifacts, change):
    path = artifacts / "source/source_metadata.csv"
    meta = pd.read_csv(path)
    if change == "native_event":
        meta.loc[0, "event_sample"] += 1
    else:
        meta.loc[0, "label"], meta.loc[12, "label"] = 2, 1
    meta.to_csv(path, index=False)
    with pytest.raises(AssertionError, match="frozen Q8"):
        validator.validate_source(artifacts)


@pytest.mark.parametrize("change", ["coefficient", "runtime", "padding"])
def test_numerical_filter_freeze_is_independently_reproduced(change):
    from mi_eeg.data.q15_context import numerical_implementation
    record = numerical_implementation()
    bands = fixture_config()["bands_hz"]
    validator._verify_numerical(record, bands)
    if change == "coefficient":
        record["native_filter_sos"]["250"]["broad"][0][0] += 0.01
    elif change == "runtime":
        record["scipy_version"] = "0.0.fake"
    else:
        record["resampling"]["padtype"] = "line"
    with pytest.raises(AssertionError, match="Frozen numerical preprocessing"):
        validator._verify_numerical(record, bands)
