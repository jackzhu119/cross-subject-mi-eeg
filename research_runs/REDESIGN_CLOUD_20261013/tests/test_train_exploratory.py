"""Synthetic software/gate tests. No EEG fitting or target prediction."""
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import math
from pathlib import Path
import random
import sys

import numpy as np
import pytest
import torch

STUDY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDY / "scripts"))
import train_exploratory as train
import validate_source as validate
import cloud_contract as contract


@pytest.fixture
def config():
    c = json.loads((train.LEGACY / "config/core_experiment_v1.json").read_text())
    c.update(experiment="exploratory_selection_core_v2", prior_exposure_status="AUTHOR_REPORTED_UNCERTAIN",
             qualified_independent_confirmation=False)
    return c


@pytest.fixture
def runtime():
    return {"machine_hostname": "synthetic-host", "gpu_uuid": "synthetic-uuid", "python": "3.11.0",
            "runtime_cuda": "12.8", "packages": {"braindecode": "1.5.1", "torch": "2.8.0"}}


@pytest.fixture
def authorization(runtime):
    stamp = datetime.now(timezone.utc)
    return {"status": "AUTHORIZED", "machine_hostname": runtime["machine_hostname"], "gpu_uuid": runtime["gpu_uuid"],
            "target_fits_authorized": False, "optional_grouping_authorized": False,
            "maximum_neural_fits": 26, "maximum_optimizer_updates": 34440,
            "maximum_gpu_hours": 8, "maximum_total_usd": 10, "approved_hourly_rate_usd": .75,
            "non_gpu_reserved_usd": 2, "authorized_at_utc": stamp.isoformat(),
            "config_sha256": train.file_hash(train.CONFIG),
            "expires_at_utc": (stamp + timedelta(hours=8)).isoformat()}


def test_true_uncertainty_with_unchanged_numerics_accepted(config):
    assert train.validate_config(config)["qualified_independent_confirmation"] is False


@pytest.mark.parametrize("key,value", [("learning_rate", .003), ("selection_seed", 1337),
    ("final_seeds", [1337, 2025, 2026]), ("source_validation_groups", [[1], [2], [3], [4]]),
    ("candidate_epochs", list(range(1, 21))), ("optional_extra_grouping_enabled", True),
    ("qualified_independent_confirmation", True), ("prior_exposure_status", "AUTHOR_CONFIRMED_FIRST_USE"),
    ("target_fits", 1), ("batch_size", 128)])
def test_frozen_design_or_unknown_exposure_cannot_be_reinterpreted(config, key, value):
    config[key] = value
    with pytest.raises(ValueError):
        train.validate_config(config)


def test_runtime_exact_lock_required(runtime):
    train.validate_runtime(runtime, {**runtime, "status": "FROZEN_BEFORE_SOURCE_FITS"})
    altered = {**runtime, "status": "FROZEN_BEFORE_SOURCE_FITS", "gpu_uuid": "other"}
    with pytest.raises(ValueError):
        train.validate_runtime(runtime, altered)


@pytest.mark.parametrize("key,value", [("maximum_neural_fits", 27), ("maximum_optimizer_updates", 34441),
    ("maximum_gpu_hours", 9), ("maximum_total_usd", 11), ("approved_hourly_rate_usd", .76),
    ("non_gpu_reserved_usd", 2.01), ("target_fits_authorized", True), ("optional_grouping_authorized", True),
    ("maximum_neural_fits", True), ("gpu_uuid", "other-machine"), ("config_sha256", "0" * 64)])
def test_budget_bounds_cannot_be_increased(authorization, runtime, key, value):
    authorization[key] = value
    with pytest.raises(ValueError):
        train.validate_budget(authorization, runtime)


def test_budget_expiration_and_lifetime_bounded(authorization, runtime):
    assert train.validate_budget(authorization, runtime)
    authorization["expires_at_utc"] = (datetime.now(timezone.utc) + timedelta(hours=9)).isoformat()
    with pytest.raises(ValueError, match="lifetime"):
        train.validate_budget(authorization, runtime)
    authorization["expires_at_utc"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    with pytest.raises(ValueError, match="expired"):
        train.validate_budget(authorization, runtime)


def test_persistent_budget_does_not_reset_on_resume(tmp_path, authorization):
    b = train.PersistentBudget(tmp_path, authorization)
    b.start_fit()
    b.state["optimizer_updates"] = 7
    b.save()
    recovered = train.PersistentBudget(tmp_path, authorization)
    assert recovered.state["actual_neural_fits_started"] == 1
    assert recovered.state["optimizer_updates"] == 7
    recovered.state["optimizer_updates"] = 34440
    recovered.save()
    with pytest.raises(RuntimeError, match="ceiling"):
        recovered.before_update()
    recovered.state["actual_neural_fits_started"] = 26
    with pytest.raises(RuntimeError, match="ceiling"):
        recovered.start_fit()


def test_expired_budget_blocks_existing_job(tmp_path, authorization):
    authorization["expires_at_utc"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    with pytest.raises(RuntimeError, match="deadline"):
        train.PersistentBudget(tmp_path, authorization)


@pytest.mark.parametrize("key,value", [("optimizer_updates", -1), ("actual_neural_fits_started", True),
                                       ("actual_neural_fits_completed", 1), ("target_predictions_computed", True)])
def test_corrupt_ledger_is_not_a_fresh_budget(tmp_path, authorization, key, value):
    state = {"actual_neural_fits_started": 0, "actual_neural_fits_completed": 0, "optimizer_updates": 0,
             "target_fits": 0, "target_predictions_computed": False}
    state[key] = value
    train.write_json(tmp_path / "source/budget_ledger.json", state)
    with pytest.raises(ValueError):
        train.PersistentBudget(tmp_path, authorization)


def test_rng_round_trip_is_weights_only_safe(tmp_path):
    random.seed(123)
    np.random.seed(123)
    torch.manual_seed(123)
    state = train.capture_rng()
    expected = (random.random(), np.random.rand(3), torch.rand(3))
    train.atomic_torch_save(tmp_path / "state.pt", state)
    restored = torch.load(tmp_path / "state.pt", weights_only=True)
    train.restore_rng(restored)
    assert random.random() == expected[0]
    assert np.array_equal(np.random.rand(3), expected[1])
    assert torch.equal(torch.rand(3), expected[2])


def test_resume_requires_same_fit_and_committed_state(tmp_path):
    identity = {"architecture": "synthetic", "seed": 1, "epochs": 2, "cell_kind": "software_test"}
    with pytest.raises(RuntimeError, match="silent fresh restart"):
        train.recover_batch_state(tmp_path, "config", identity)
    train.atomic_torch_save(tmp_path / "resume_state.pt", {"config_sha256": "config", "fit_identity": identity, "global_updates": 3})
    assert train.recover_batch_state(tmp_path, "config", identity)["global_updates"] == 3
    with pytest.raises(ValueError, match="another"):
        train.recover_batch_state(tmp_path, "other-config", identity)


def test_ambiguous_update_crash_is_not_silently_repeated(tmp_path):
    identity = {"cell": "synthetic"}
    train.atomic_torch_save(tmp_path / "resume_state.pt", {"config_sha256": "config", "fit_identity": identity, "global_updates": 3})
    train.write_json(tmp_path / "update_intent.json", {"fit_identity": identity, "next_global_update": 4})
    with pytest.raises(RuntimeError, match="Unresolved"):
        train.recover_batch_state(tmp_path, "config", identity)
    assert (tmp_path / "update_intent.json").exists()


def test_committed_update_crash_does_not_repeat_consumed_update(tmp_path):
    identity = {"cell": "synthetic"}
    train.atomic_torch_save(tmp_path / "resume_state.pt", {"config_sha256": "config", "fit_identity": identity, "global_updates": 4})
    train.write_json(tmp_path / "update_intent.json", {"fit_identity": identity, "next_global_update": 4})
    assert train.recover_batch_state(tmp_path, "config", identity)["global_updates"] == 4
    assert not (tmp_path / "update_intent.json").exists()


def make_curves(values):
    return [[{"epoch": i + 1, "training_cross_entropy": .8, "validation_cross_entropy": v, "optimizer_updates": 32}
             for i, v in enumerate(row)] for row in values]


def test_separate_rank_selection_exact_ties_and_earliest_minimum():
    values = np.full((4, 40), 1.)
    values[:, 6:8] = .2
    curves = make_curves(values)
    expected = train.select_epochs(curves, list(range(1, 41)))
    assert validate.independent_selection(curves) == expected
    assert expected["mean_loss"] == expected["mean_rank"] == 7


def test_equal_fold_aggregation_does_not_weight_by_trial_count():
    values = np.tile(np.linspace(.2, 1., 40), (4, 1))
    values[3] = np.linspace(1., .1, 40)
    curves = make_curves(values)
    result = validate.independent_selection(curves)
    assert validate.selections_agree({"synthetic": result}, {"synthetic": train.select_epochs(curves, list(range(1, 41)))})
    assert result["equal_fold_mean_loss"][0] == pytest.approx((.2 * 3 + 1.) / 4)


@pytest.mark.parametrize("defect", ["missing_epoch", "reordered", "nan", "negative", "bad_updates", "final_has_validation"])
def test_source_curve_corruption_rejected(defect):
    curve = make_curves(np.full((1, 40), .8))[0]
    heldout = True
    if defect == "missing_epoch":
        curve.pop()
    elif defect == "reordered":
        curve[0], curve[1] = curve[1], curve[0]
    elif defect == "nan":
        curve[0]["validation_cross_entropy"] = float("nan")
    elif defect == "negative":
        curve[0]["training_cross_entropy"] = -.1
    elif defect == "bad_updates":
        curve[0]["optimizer_updates"] = 31
    else:
        heldout = False
    with pytest.raises(ValueError):
        validate.assert_curve(curve, 40, 2016, heldout)


def test_true_aliases_only_same_architecture_seed_epoch():
    selection = {"fixed20": 20, "mean_loss": 20, "mean_rank": 30}
    a = validate.expected_cells("BROAD_EEGNET", selection, [20261013, 20261014, 20261015])
    assert a == train.schedule_cells("BROAD_EEGNET", selection, [20261013, 20261014, 20261015])
    assert sum(x["alias"] for x in a) == 3
    assert {x["owner_cell"] for x in a if x["selector"] == "mean_rank"} == {x["cell"] for x in a if x["selector"] == "mean_rank"}
    b = validate.expected_cells("MU_BETA_SHARED", selection, [20261013, 20261014, 20261015])
    assert not {x["owner_cell"] for x in a} & {x["owner_cell"] for x in b}


def test_nominal_worst_case_update_budget_is_34440():
    inner = 2 * 40 * sum(math.ceil((2592 - n * 288) / 64) for n in (2, 2, 2, 3))
    final = 2 * 3 * (20 + 40 + 40) * math.ceil(2592 / 64)
    assert inner == 9840
    assert inner + final == 34440


def test_independent_array_fingerprint_matches_fixed_format():
    arrays = [np.arange(12, dtype=np.float32).reshape(3, 4), np.array([0, 1], dtype=np.int64)]
    for value in arrays:
        assert validate.array_digest(value) == train.array_hash(value)


def test_synthetic_shared_forward_preserves_parameter_and_eval_state(config):
    torch.set_num_threads(1)
    broad = train.build_model("BROAD_EEGNET", config["architecture"], "cpu")
    shared = train.build_model("MU_BETA_SHARED", config["architecture"], "cpu")
    shared.backbone.load_state_dict(broad.state_dict())
    before = train.state_hash(shared)
    x = torch.zeros((2, 19, 320))
    with torch.inference_mode():
        ordinary = broad(x)
        dual = shared(torch.stack([x, x], dim=1))
    assert torch.allclose(ordinary, dual)
    assert train.state_hash(shared) == before
    assert sum(p.numel() for p in broad.parameters()) == sum(p.numel() for p in shared.parameters())
    for name, model in (("BROAD_EEGNET", broad), ("MU_BETA_SHARED", shared)):
        separate = validate.independent_model_accounting(model, name)
        original = train.compute_accounting(model, name, "cpu")
        assert all(original[k] == v for k, v in separate.items())


def test_synthetic_source_loss_replay_separate_arithmetic_and_state_boundary():
    model = torch.nn.Linear(3, 2)
    with torch.no_grad():
        model.weight.zero_()
        model.bias.zero_()
    x = np.zeros((34, 3), dtype=np.float32)
    y = np.arange(34) % 2
    replay = validate.replay_last_source_loss(model, x, y, list(range(34)), math.log(2))
    assert replay["absolute_difference"] < 1e-14
    assert replay["model_state_unchanged"] is True
    with pytest.raises(ValueError, match="failed separate replay"):
        validate.replay_last_source_loss(model, x, y, list(range(34)), .1)


def test_duration_mismatch_is_never_hidden_by_rounding_tolerance():
    curves = make_curves(np.full((4, 40), .8))
    original = validate.independent_selection(curves)
    recorded = copy.deepcopy(original)
    recorded["mean_loss"] = 2
    assert not validate.selections_agree({"synthetic": original}, {"synthetic": recorded})
    recorded = copy.deepcopy(original)
    recorded["equal_fold_mean_loss"][0] += .001
    assert not validate.selections_agree({"synthetic": original}, {"synthetic": recorded})


def test_default_cli_dry_run_never_opens_source_or_gpu(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["train_exploratory.py"])
    monkeypatch.setattr(train, "runtime_identity", lambda: pytest.fail("GPU must not be probed"))
    monkeypatch.setattr(train, "load_source19", lambda *a: pytest.fail("EEG must not be opened"))
    train.main()
    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "DRY_RUN_NO_EEG_READ_NO_NEURAL_FITS"
    assert status["target_fits"] == 0
    assert status["target_predictions_computed"] is False


def test_no_cuda_blocks_real_execution_before_eeg_read(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(ValueError, match="CPU fits are blocked"):
        train.runtime_identity()


@pytest.mark.parametrize("defect", [None, "changed_local", "changed_commit", "changed_public", "unverified_readback", "missing_dependency"])
def test_source_protocol_freeze_binds_actual_local_and_committed_dependencies(tmp_path, monkeypatch, defect):
    code = tmp_path / "code.py"
    code.write_bytes(b"frozen numerical code\n")
    job = tmp_path / "job"
    expected_sha = train.file_hash(code)
    frozen = {"status": "PASS", "repository": "jackzhu119/cross-subject-mi-eeg", "commit_sha": "a" * 40,
              "files": {"code.py": expected_sha}, "public_readback_verified": True}
    if defect == "changed_local":
        code.write_bytes(b"outcome-driven alternative\n")
    elif defect == "unverified_readback":
        frozen["public_readback_verified"] = False
    elif defect == "missing_dependency":
        frozen["files"] = {}
    train.write_json(job / "public_freeze.json", frozen)
    monkeypatch.setattr(train, "ROOT", tmp_path)
    monkeypatch.setattr(contract, "ROOT", tmp_path)
    committed = b"altered committed code\n" if defect == "changed_commit" else b"frozen numerical code\n"
    monkeypatch.setattr(train.subprocess, "check_output", lambda *a, **k: committed)
    public = b"altered public code\n" if defect == "changed_public" else b"frozen numerical code\n"
    monkeypatch.setattr(contract, "public_bytes", lambda *a, **k: public)
    if defect is None:
        assert train.verify_freeze(job, [code])["commit_sha"] == "a" * 40
    else:
        with pytest.raises(ValueError):
            train.verify_freeze(job, [code])


def test_runtime_budget_preparation_author_and_full_raw_qc_are_mandatory_frozen_dependencies(tmp_path):
    job = tmp_path / "job"
    data = {key: str(job / "qc" / name) for key, name in
            (("roster_path", "raw_only_roster.json"), ("raw_qc_report_path", "full_raw_qc_report.json"),
             ("tensor_cache_receipt_path", "tensor_cache_receipt.json"))}
    required = set(train.required_execution_paths(job, data))
    assert {job / name for name in ("runtime_lock.json", "budget_authorization.json", "data_prepare_receipt.json")} <= required
    assert train.EXPLORATORY / "evidence/author_prior_use_uncertain.json" in required
    assert train.EXPLORATORY / "evidence/author_conditional_gpu_budget.json" in required
    assert {Path(value) for value in data.values()} <= required
    data["roster_path"] = str(tmp_path / "other-job-roster.json")
    with pytest.raises(ValueError, match="escaped"):
        train.required_execution_paths(job, data)


@pytest.mark.parametrize("key,value", [("retained_participants", 84), ("retained_events", 6799),
    ("target_file_count", 173), ("source_file_count", 17), ("qualified_independent_confirmation", True),
    ("author_prior_use", "never_used"), ("target_predictions_computed", True), ("target_fits", 1)])
def test_prepared_cohort_or_qualification_cannot_be_changed_before_source_fits(tmp_path, key, value, monkeypatch):
    # This isolated test reaches the cohort gate after a synthetic completed
    # review gate. Separate numerical-amendment tests exercise real review bytes.
    import numerical_review_gate
    monkeypatch.setattr(numerical_review_gate, "verify_review", lambda job: {"synthetic_fixture": True})
    data = {"status": "PASS_DATA_PREPARATION_EXPLORATORY", "source_raw_files_verified": 18,
        "qualified_independent_confirmation": False, "independent_confirmation_qualified": False,
        "target_fits": 0, "target_predictions_computed": False, "author_prior_use": "unknown",
        "source_file_count": 18, "target_file_count": 174, "retained_participants": 85,
        "retained_events": 6800, "exact_frozen_input_reconstruction": True,
        "numerical_execution": train.numerical_identity()}
    data[key] = value
    with pytest.raises(ValueError, match="preparation gate differs"):
        train.validate_prepared_data(tmp_path, data, tmp_path / "source")
