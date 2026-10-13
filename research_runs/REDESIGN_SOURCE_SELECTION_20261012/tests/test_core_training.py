"""Synthetic software checks, not new EEG model experiments or target scores."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
import pytest
import torch

STUDY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDY / "scripts"))
sys.path.insert(0, str(STUDY.parents[1] / "src"))
import core_source_inputs as inputs
import train_source_selection_core as core


@pytest.fixture
def config():
    return json.loads((STUDY / "config/core_experiment_v1.json").read_text())


@pytest.fixture(autouse=True)
def bounded_synthetic_cpu_threads():
    old = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(old)


def source_records():
    return [{"sample_id": f"software_s{subject}_class{label}", "subject": subject,
             "label": label, "label_index": label - 1}
            for subject in range(1, 10) for label in (1, 2)]


def authorization():
    current = datetime.now(timezone.utc)
    return {"schema_version": 1, "status": "AUTHORIZED", "scope": "core_source_training_v1",
            "authorization_kind": "explicit_author_approval", "config_sha256": core.file_hash(core.CONFIG),
            "machine_hostname": "software-test-only", "gpu_uuid": "synthetic-gpu-identity",
            "target_fits_authorized": False, "target_predictions_authorized": False,
            "optional_grouping_authorized": False, "maximum_neural_fits": 26,
            "maximum_optimizer_updates": 34440, "maximum_gpu_hours": 8,
            "maximum_total_usd": 10, "approved_hourly_rate_usd": .75, "non_gpu_reserved_usd": 2,
            "author_approval_record": "software fixture, not real authorization",
            "authorized_at_utc": (current - timedelta(minutes=1)).isoformat(),
            "expires_at_utc": (current + timedelta(hours=9)).isoformat()}


def test_default_launch_does_not_import_torch_or_read_any_eeg():
    result = subprocess.run([sys.executable, str(STUDY / "scripts/train_source_selection_core.py")],
                            capture_output=True, text=True, check=True)
    receipt = json.loads(result.stdout)
    assert receipt["status"] == "DRY_RUN_NO_EEG_READ_NO_NEURAL_FITS"
    assert receipt["new_neural_fits"] == receipt["target_fits"] == 0
    assert receipt["target_predictions_computed"] is False
    assert receipt["external_experiment_completed"] is False


@pytest.mark.parametrize("field,value", [("target_fits", 1), ("candidate_epochs", [1, 2]),
                                        ("optional_extra_grouping_enabled", True), ("source_validation_group_weight", "participant_count"),
                                        ("batch_size", 32), ("target_performance_used_for_design", True)])
def test_real_spec_rejects_unbudgeted_outcome_or_source_changes(config, field, value):
    config[field] = value
    with pytest.raises(ValueError, match="specification changed"):
        core.validate_config(config)


def test_real_source_runner_fails_before_eeg_loading_without_complete_public_freeze(config, monkeypatch):
    called = []
    monkeypatch.setattr(inputs, "load_source19", lambda *args: called.append("EEG-read"))
    with pytest.raises(ValueError, match="gate absent"):
        core.execute(Path("nonexistent-raw-data-must-not-be-read"))
    assert called == []


def test_cpu_is_not_an_authorized_real_science_gpu(config, monkeypatch):
    assert torch.cuda.is_available() is False
    monkeypatch.setattr(core, "verify_public_preanalysis", lambda config: {"protocol_commit": "a" * 40})
    monkeypatch.setattr(core, "verify_data_gate", lambda *args: {})
    monkeypatch.setattr(core, "read_json", lambda path: config if path == core.CONFIG else {})
    called = []
    monkeypatch.setattr(inputs, "load_source19", lambda *args: called.append("EEG-read"))
    with pytest.raises(ValueError, match="live CUDA GPU"):
        core.execute(Path("nonexistent-raw-data-must-not-be-read"))
    assert called == []


@pytest.mark.parametrize("field,value", [("target_predictions_authorized", True), ("maximum_total_usd", 11),
                                        ("maximum_neural_fits", 27), ("maximum_optimizer_updates", 34441),
                                        ("approved_hourly_rate_usd", 1), ("machine_hostname", "other-machine"),
                                        ("gpu_uuid", "different-gpu"), ("author_approval_record", "")])
def test_budget_receipt_rejects_target_permission_cost_or_machine_drift(field, value):
    receipt = authorization()
    receipt[field] = value
    with pytest.raises(ValueError):
        core.verify_authorization(receipt, {"machine_hostname": "software-test-only", "gpu_uuid": "synthetic-gpu-identity"})


def test_expired_authorization_and_budget_exhaustion_stop_before_optimizer_step(monkeypatch):
    receipt = authorization()
    receipt["expires_at_utc"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    with pytest.raises(ValueError, match="not currently valid"):
        core.verify_authorization(receipt, {"machine_hostname": "software-test-only", "gpu_uuid": "synthetic-gpu-identity"})
    receipt = authorization()
    budget = core.Budget(receipt)
    budget.updates = receipt["maximum_optimizer_updates"]
    with pytest.raises(RuntimeError, match="optimizer-update ceiling"):
        budget.before_step()
    budget.fits_started = 26
    with pytest.raises(RuntimeError, match="fit ceiling"):
        budget.start_fit()
    monkeypatch.setattr(core.time, "monotonic", lambda: budget.started + 8 * 3600 + 1)
    with pytest.raises(RuntimeError, match="time/cost envelope"):
        budget.guard()


def test_runtime_lock_is_not_satisfied_by_only_declared_cpu_gpu_status():
    runtime = {"packages": {"braindecode": "1.5.1", "torch": "actual"}, "runtime_cuda": "actual", "python": "actual"}
    with pytest.raises(ValueError, match="scientific packages"):
        core.verify_runtime_lock(runtime, {"status": "FROZEN_BEFORE_SOURCE_FITS", "packages": {"braindecode": "1.5.1", "torch": "other"}})


def test_data_gate_does_not_accept_a_bounded_header_audit_as_full_cohort(config):
    with pytest.raises(ValueError, match="first-use gate is incomplete"):
        core.verify_data_gate(config, {"status": "PASS", "config_sha256": core.file_hash(core.CONFIG),
                                      "author_first_use_confirmation": True, "all_retained_target_files_verified": False})


def data_gate_fixture(config, folder):
    """Explicit, temporary synthetic author/QC artifacts; never real clearance."""
    import infer_selection_core as target
    from acquire_dreyer_runs import PINNED_SHA256
    declaration = {"status": "AUTHOR_CONFIRMED", "dataset": "Dreyer2023", "provider_dataset_id": "nm000250",
                   "provider_manifest_sha256": PINNED_SHA256, "prior_proposed_decoder_results_inspected_or_used": False,
                   "prior_dataset_scientific_analysis_performed": False, "used_in_other_manuscripts_or_projects": False,
                   "acknowledged_current_metadata_annotation_and_precue_transport_preflight": True,
                   "author_name": "synthetic software fixture, not a human declaration",
                   "confirmation_record": "temporary test only; no authorization",
                   "confirmed_at_utc": datetime.now(timezone.utc).isoformat()}
    paths = {"author_prior_use": folder / "synthetic_author.json", "roster": folder / "synthetic_roster.json",
             "raw_audit": folder / "synthetic_failed_qc.json", "acquisition_receipt": folder / "synthetic_acquisition.json",
             "adapter": Path(target.__file__).resolve()}
    paths["author_prior_use"].write_text(json.dumps(declaration))
    paths["roster"].write_text("{}")
    paths["raw_audit"].write_text(json.dumps({"status": "FAILED_RAW_QC"}))
    paths["acquisition_receipt"].write_text("{}")
    gate = {"status": "PASS", "config_sha256": core.file_hash(core.CONFIG), "author_first_use_confirmation": True,
            "all_retained_target_files_verified": True, "complete_acquisition_run_coverage_verified": True,
            "native_event_semantics_verified": True, "physical_header_scale_verified": True,
            "genuine_channel_order_verified": True, "cross_version_event_conversion_verified": True,
            "raw_only_roster_frozen": True, "duplicate_identity_audit_passed": True,
            "target_predictions_computed": False, "target_fits": 0,
            "qualification": "independent_operational_derivative_cohort"}
    for key, path in paths.items():
        gate[key + "_path"] = str(path.relative_to(core.ROOT))
        gate[key + "_sha256"] = core.file_hash(path)
    gate["author_declaration_sha256"] = core.file_hash(paths["author_prior_use"])
    gate_path = folder / "synthetic_data_gate.json"
    gate_path.write_text(json.dumps(gate))
    return gate, gate_path, paths


def test_integer_one_is_not_author_confirmation(config):
    with tempfile.TemporaryDirectory(prefix="software-data-gate-only-", dir=STUDY / "results") as name:
        gate, path, _ = data_gate_fixture(config, Path(name))
        gate["author_first_use_confirmation"] = 1
        with pytest.raises(ValueError, match="first-use gate is incomplete"):
            core.verify_data_gate(config, gate)


def test_source_pass_wrapper_cannot_authorize_failed_full_cohort_qc(config, monkeypatch):
    import infer_selection_core as target
    with tempfile.TemporaryDirectory(prefix="software-data-gate-only-", dir=STUDY / "results") as name:
        gate, path, _ = data_gate_fixture(config, Path(name))
        monkeypatch.setattr(core, "DATA_GATE", path)
        monkeypatch.setattr(target, "DATA_GATE", path)
        with pytest.raises(ValueError, match="Full raw-only audit missing/failed: status"):
            core.verify_data_gate(config, gate)


def test_source_pass_wrapper_cannot_replace_actual_author_record(config, monkeypatch):
    import infer_selection_core as target
    with tempfile.TemporaryDirectory(prefix="software-data-gate-only-", dir=STUDY / "results") as name:
        gate, path, files = data_gate_fixture(config, Path(name))
        files["author_prior_use"].write_text(json.dumps({"status": "AUTHOR_CONFIRMATION_PENDING"}))
        gate["author_prior_use_sha256"] = gate["author_declaration_sha256"] = core.file_hash(files["author_prior_use"])
        path.write_text(json.dumps(gate))
        monkeypatch.setattr(core, "DATA_GATE", path)
        monkeypatch.setattr(target, "DATA_GATE", path)
        with pytest.raises(ValueError, match="author_prior_use_gate_unresolved"):
            core.verify_data_gate(config, gate)


@pytest.mark.parametrize("group", [[1, 2], [3, 4], [5, 6], [7, 8, 9]])
def test_source_validation_uses_people_and_both_sessions_without_trial_leakage(group):
    records = source_records()
    train, val = core.source_partition(records, group)
    assert not set(train) & set(val)
    assert not set(group) & {records[i]["subject"] for i in train}
    assert {records[i]["subject"] for i in val} == set(group)
    assert len(train) == 18 - 2 * len(group)


def test_source_partition_rejects_duplicate_identity_and_missing_hand():
    records = source_records()
    records[0]["sample_id"] = records[1]["sample_id"]
    with pytest.raises(ValueError, match="unique source"):
        core.source_partition(records, [1, 2])
    records = [r for r in source_records() if not (r["subject"] in [1, 2] and r["label"] == 2)]
    with pytest.raises(ValueError, match="Both source hand"):
        core.source_partition(records, [1, 2])


def test_selector_average_ties_earliest_minimum_and_fixed20_are_distinct_rules():
    flat = [{"epoch": i, "validation_cross_entropy": 1.} for i in range(1, 41)]
    result = core.select_epochs([flat] * 4, list(range(1, 41)))
    assert result["mean_loss"] == result["mean_rank"] == 1
    assert result["fixed20"] == 20
    assert result["equal_fold_mean_average_tie_rank"] == [20.5] * 40


def test_selectors_use_equal_fold_weights_not_validation_subject_counts():
    curves = []
    for losses in ([.1, .2], [.1, .2], [.1, .2], [.35, .1]):
        curves.append([{"epoch": i, "validation_cross_entropy": losses[i-1] if i <= 2 else 2.}
                       for i in range(1, 41)])
    result = core.select_epochs(curves, list(range(1, 41)))
    assert result["equal_fold_mean_loss"][:2] == pytest.approx([.1625, .175])
    assert result["mean_loss"] == result["mean_rank"] == 1
    curves[0].pop()
    with pytest.raises(ValueError, match="missing or reordered"):
        core.select_epochs(curves, list(range(1, 41)))


def test_equal_epoch_aliases_preserve_all_nominal_cells_without_fictitious_fits():
    cells = core.schedule_cells("BROAD_EEGNET", {"fixed20": 20, "mean_loss": 20, "mean_rank": 20}, [20261013, 20261014, 20261015])
    assert len(cells) == 9
    assert sum(c["alias"] for c in cells) == 6
    assert len({c["owner_cell"] for c in cells}) == 3
    mixed = core.schedule_cells("BROAD_EEGNET", {"fixed20": 20, "mean_loss": 19, "mean_rank": 20}, [20261013, 20261014, 20261015])
    assert sum(c["alias"] for c in mixed) == 3
    assert len({c["owner_cell"] for c in mixed}) == 6


def test_actual19_common_reference_excludes_extraneous_native_sensors(config):
    names = [*inputs.CHANNELS19, "P1", "P2", "POz"]
    values = np.repeat(np.arange(22)[:, None], 2000, axis=1).astype(float)
    ordered = inputs.ordered_channels19(values, names)
    assert ordered.shape == (19, 2000)
    np.testing.assert_array_equal(ordered, values[:19])
    with pytest.raises(ValueError, match="genuine required channel"):
        inputs.ordered_channels19(values[1:], names[1:])
    with pytest.raises(ValueError, match="unique"):
        inputs.ordered_channels19(values, [*names[:-1], "Fz"])


@pytest.mark.parametrize("sfreq", [250, 512])
def test_actual19_car_filter_resample_crop_is_common_mode_invariant_and_trial_local(config, sfreq):
    n = int(sfreq * 9)
    t = np.arange(n) / sfreq
    signal = np.arange(1, 20)[:, None] * np.sin(2 * np.pi * 10 * t)
    cue = int(3 * sfreq)
    first = inputs.transform_context19(signal, sfreq, cue, config)
    common_mode = np.cos(2 * np.pi * 17 * t) * 700
    second = inputs.transform_context19(signal + common_mode, sfreq, cue, config)
    for band in inputs.BANDS:
        assert first[band].shape == (19, 320) and first[band].dtype == np.float32
        np.testing.assert_allclose(first[band], second[band], rtol=1e-5, atol=2e-6)
    signal[:, :int(1.5 * sfreq)] += 1e8
    signal[:, int(7.5 * sfreq):] -= 1e8
    local = inputs.transform_context19(signal, sfreq, cue, config)
    for band in inputs.BANDS:
        np.testing.assert_array_equal(first[band], local[band])
    with pytest.raises(ValueError, match="six-second context"):
        inputs.transform_context19(signal, sfreq, cue, config, bounds=(int(2 * sfreq), n))


def test_transform_refuses_nonfinite_crop_and_changed_physiology_or_reference(config):
    signal = np.ones((19, 2000))
    signal[0, 700] = np.nan
    with pytest.raises(ValueError, match="nonfinite"):
        inputs.transform_context19(signal, 250, 750, config)
    config["reference"] = "common_average_21"
    with pytest.raises(ValueError, match="contract differs"):
        inputs.transform_context19(np.ones((19, 2000)), 250, 750, config)


def test_all18_raw_hashes_must_pass_before_native_source_parsing(config, tmp_path, monkeypatch):
    records = []
    for subject in range(1, 10):
        for session in "TE":
            path = tmp_path / f"A{subject:02d}{session}.mat"
            path.write_bytes(b"software fixture, not MATLAB EEG")
            records.append({"path": str(path), "bytes": path.stat().st_size, "sha256": inputs.file_hash(path)})
    provenance = tmp_path / "source_provenance.json"
    provenance.write_text(json.dumps(records))
    monkeypatch.setattr(inputs, "SOURCE_PROVENANCE", provenance)
    (tmp_path / "A09E.mat").write_bytes(b"changed fixture")
    import mi_eeg.data.q15_context as metadata
    called = []
    monkeypatch.setattr(metadata, "_validated_bnci_runs", lambda path: called.append(str(path)))
    with pytest.raises(ValueError, match="differs from frozen Q8"):
        inputs.load_source19(tmp_path, config)
    assert called == []


def test_real_eegnet_backbone_shared_logits_and_source_validation_state(config):
    core.seed_everything(20261013)
    model = core.build_model("MU_BETA_SHARED", config["architecture"], torch.device("cpu"))
    x = torch.randn(5, 2, 19, 320)
    y = torch.tensor([0, 1, 0, 1, 0])
    model.eval()
    before = core.state_hash(model)
    with torch.inference_mode():
        expected = model.backbone(x.reshape(10, 19, 320)).reshape(5, 2, 2).mean(dim=1)
        torch.testing.assert_close(model(x), expected)
    ce = core.evaluate_source_ce(model, x, y, torch.arange(5), batch_size=3)
    assert np.isfinite(ce) and ce > 0
    assert before == core.state_hash(model)
    accounting = core.compute_accounting(model, "MU_BETA_SHARED", torch.device("cpu"))
    broad = core.build_model("BROAD_EEGNET", config["architecture"], torch.device("cpu"))
    broad_accounting = core.compute_accounting(broad, "BROAD_EEGNET", torch.device("cpu"))
    assert accounting["parameters"] == broad_accounting["parameters"]
    assert accounting["conv_linear_macs_per_trial"] == 2 * broad_accounting["conv_linear_macs_per_trial"]
    assert accounting["input_views_per_trial"] == 2
    batchnorms = [module for module in model.modules() if isinstance(module, torch.nn.BatchNorm2d)]
    tracked_before = [module.num_batches_tracked.item() for module in batchnorms]
    assert batchnorms
    optimizer = torch.optim.Adam(model.parameters(), lr=.001)
    loss, updates = core.train_one_epoch(model, optimizer, x, y, torch.arange(5), batch_size=3)
    assert np.isfinite(loss) and updates == 2
    assert before != core.state_hash(model)
    assert [module.num_batches_tracked.item() - old for module, old in zip(batchnorms, tracked_before)] == [2] * len(batchnorms)


def test_synthetic_training_restarts_same_seed_and_keeps_remainder_batch(config):
    # A small synthetic optimization is software evidence, never a real EEG fit.
    x = torch.arange(35, dtype=torch.float32).reshape(7, 5) / 35
    y = torch.tensor([0, 1, 0, 1, 0, 1, 0])
    hashes, losses = [], []
    for _ in range(2):
        core.seed_everything(20261013)
        model = torch.nn.Sequential(torch.nn.Linear(5, 2))
        optimizer = torch.optim.Adam(model.parameters(), lr=.001)
        loss, updates = core.train_one_epoch(model, optimizer, x, y, torch.arange(7), batch_size=4)
        assert updates == 2
        hashes.append(core.state_hash(model)); losses.append(loss)
    assert hashes[0] == hashes[1] and losses[0] == losses[1]


def test_nonfinite_gradient_stops_before_any_optimizer_update():
    model = torch.nn.Linear(3, 2)
    before = core.state_hash(model)
    for parameter in model.parameters():
        parameter.register_hook(lambda grad: torch.full_like(grad, float("nan")))
    optimizer = torch.optim.Adam(model.parameters(), lr=.001)
    with pytest.raises(FloatingPointError, match="gradient"):
        core.train_one_epoch(model, optimizer, torch.ones(2, 3), torch.tensor([0, 1]), torch.arange(2), batch_size=2)
    assert before == core.state_hash(model)
