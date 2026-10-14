"""Synthetic numerical-amendment checks; no EEG files, models or predictions.

Exact comparisons validate the registered implementation, not biological data
or permission to resume a blocked cloud job.
"""
import copy
import csv
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import sys

import numpy as np
import pytest
from scipy.signal import sosfilt_zi, sosfiltfilt

STUDY = Path(__file__).resolve().parents[1]
ROOT = STUDY.parents[1]
sys.path.insert(0, str(STUDY / "scripts"))
import formal_core_inputs as formal

HELPER_PATH = (ROOT / "research_runs/REDESIGN_HANDOFF_20261014"
               / "official_source_diagnostic/probe_fixed_zi_mediation.py")
spec = importlib.util.spec_from_file_location("formal_numerics_diagnostic_equations", HELPER_PATH)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


@pytest.fixture(autouse=True)
def clean_numeric_environment(monkeypatch):
    # Test fixtures explicitly remove external overrides; production rejects
    # them rather than silently modifying the caller's environment.
    monkeypatch.delenv("OPENBLAS_CORETYPE", raising=False)
    monkeypatch.delenv("NPY_DISABLE_CPU_FEATURES", raising=False)


@pytest.fixture
def config():
    return json.loads((STUDY / "config/experiment.json").read_text())


def synthetic_signal(rate, order="C"):
    n = int(8 * rate)
    signal = ((np.arange(19 * n).reshape(19, n) * 37) % 257 - 128).astype(np.float64)
    signal += np.sin(np.arange(n)[None, :] / 13.) * np.arange(1, 20)[:, None]
    return np.array(signal, order=order)


def test_policy_is_exact_explicit_and_not_training_authorization():
    assert hashlib.sha256(formal.POLICY.read_bytes()).hexdigest() == formal.POLICY_SHA256
    policy = formal.checked_policy()
    assert policy["status"] == "OPERATIONAL_AMENDMENT_FROZEN_BEFORE_RESUMPTION"
    assert policy["training_authorization"] is False
    assert policy["target_acceptance_completed"] is False
    assert policy["historical_generation_BLAS_identity_established"] is False
    assert set(policy["rates"]) == {"250", "512"}
    assert all(set(row) == {"broad", "mu", "beta"} for row in policy["rates"].values())


@pytest.mark.parametrize("rate", [250, 512])
@pytest.mark.parametrize("band", ["broad", "mu", "beta"])
def test_six_registered_profiles_are_exact_hex_and_hash_bound(rate, band):
    sos, zi = formal.coefficients(rate, band)
    entry = formal.checked_policy()["rates"][str(rate)][band]
    assert sos.shape == (4, 6) and zi.shape == (4, 2)
    assert sos.dtype == np.float64 and zi.dtype == np.float64
    assert np.isfinite(sos).all() and np.isfinite(zi).all()
    assert formal.array_hash(sos) == entry["sos_sha256"]
    assert formal.array_hash(zi) == entry["zi_sha256"]
    assert [[float(v).hex() for v in row] for row in sos] == entry["sos_hex"]
    assert [[float(v).hex() for v in row] for row in zi] == entry["zi_hex"]


@pytest.mark.parametrize("rate", [250, 512])
@pytest.mark.parametrize("band", ["broad", "mu", "beta"])
@pytest.mark.parametrize("order", ["C", "F"])
def test_explicit_filter_bitwise_matches_existing_diagnostic_equations(rate, band, order):
    context = synthetic_signal(rate, order)[:, :int(6 * rate)]
    sos, zi = formal.coefficients(rate, band)
    before = [x.copy() for x in (context, sos, zi)]
    actual = formal.explicit_filter(context, sos, zi)
    reference = helper.fixed_filter(context, sos, zi)
    assert formal.array_hash(actual) == formal.array_hash(reference)
    for actual_input, original in zip((context, sos, zi), before):
        assert np.array_equal(actual_input.view(np.uint64), original.view(np.uint64))


@pytest.mark.parametrize("rate", [250, 512])
@pytest.mark.parametrize("band", ["broad", "mu", "beta"])
def test_equation_calibration_with_native_zi_matches_original_scipy(rate, band):
    # Native zi here is only synthetic calibration. The formal loader always
    # takes the registered state, never this native fallback.
    context = synthetic_signal(rate)[:, :int(6 * rate)]
    sos, _ = formal.coefficients(rate, band)
    native = sosfilt_zi(sos)
    assert formal.array_hash(formal.explicit_filter(context, sos, native)) == formal.array_hash(
        sosfiltfilt(sos, context, axis=-1, padtype="odd", padlen=27))


@pytest.mark.parametrize("rate", [250, 512])
@pytest.mark.parametrize("cue_seconds", [2, 3])
def test_transform_uses_fixed_profiles_for_every_trial_and_band(config, monkeypatch, rate, cue_seconds):
    signal = synthetic_signal(rate)
    original = signal.copy()
    calls = []
    coefficients = formal.coefficients
    def tracked(sfreq, band):
        calls.append((sfreq, band))
        return coefficients(sfreq, band)
    monkeypatch.setattr(formal, "coefficients", tracked)
    monkeypatch.setattr(formal.legacy, "sosfiltfilt", lambda *a, **k: pytest.fail("Native fallback forbidden"))
    cue = int(cue_seconds * rate)
    arrays = formal.transform_context19(signal, rate, cue, config)
    assert calls == [(rate, band) for band in formal.BANDS]
    context = np.array(signal[:, cue - int(1.5 * rate):cue + int(4.5 * rate)], dtype=np.float64)
    context -= context.mean(axis=0, keepdims=True)
    from fractions import Fraction
    ratio = Fraction(160 / float(rate)).limit_denominator(100000)
    for band in formal.BANDS:
        sos, zi = coefficients(rate, band)
        filtered = helper.fixed_filter(context, sos, zi)
        common = formal.legacy.resample_poly(filtered, ratio.numerator, ratio.denominator, axis=-1,
                                             window=("kaiser", 5.0), padtype="constant", cval=0.0)
        expected = np.ascontiguousarray(common[:, 320:640], dtype=np.float32)
        assert formal.array_hash(arrays[band]) == formal.array_hash(expected)
        assert arrays[band].shape == (19, 320) and arrays[band].dtype == np.float32
    assert np.array_equal(signal.view(np.uint64), original.view(np.uint64))


@pytest.mark.parametrize("rate", [True, np.bool_(True), 128, 251, 250.5, 0, -250, float("nan"), "250"])
def test_unknown_rate_rejected_without_fallback(rate):
    with pytest.raises(ValueError, match="unregistered_native_rate_or_band"):
        formal.coefficients(rate, "mu")


@pytest.mark.parametrize("band", ["alpha", "MU", "", None])
def test_unknown_band_rejected_without_profile_search(band):
    with pytest.raises(ValueError, match="unregistered_native_rate_or_band"):
        formal.coefficients(250, band)


@pytest.mark.parametrize("environment,value", [("OPENBLAS_CORETYPE", "Haswell"),
    ("OPENBLAS_CORETYPE", "SkylakeX"), ("NPY_DISABLE_CPU_FEATURES", "FMA3"),
    ("NPY_DISABLE_CPU_FEATURES", "AVX2,FMA3")])
def test_external_numeric_override_is_rejected(environment, value, monkeypatch):
    monkeypatch.setenv(environment, value)
    with pytest.raises(ValueError, match="unregistered_numeric_override"):
        formal.checked_policy()


@pytest.mark.parametrize("package", ["numpy", "scipy"])
def test_unregistered_runtime_version_rejected(package, monkeypatch):
    module = formal.np if package == "numpy" else formal.scipy
    monkeypatch.setattr(module, "__version__", "unregistered-version")
    with pytest.raises(ValueError, match="explicit_numerics_runtime_changed"):
        formal.checked_policy()


def test_changed_policy_bytes_rejected(tmp_path, monkeypatch):
    changed = tmp_path / "numerical-policy.json"
    changed.write_bytes(formal.POLICY.read_bytes() + b" ")
    monkeypatch.setattr(formal, "POLICY", changed)
    with pytest.raises(ValueError, match="explicit_numerical_policy_changed"):
        formal.checked_policy()


def test_policy_symlink_rejected(tmp_path, monkeypatch):
    changed = tmp_path / "policy.json"
    changed.symlink_to(formal.POLICY)
    monkeypatch.setattr(formal, "POLICY", changed)
    with pytest.raises(ValueError, match="explicit_numerical_policy_changed"):
        formal.checked_policy()


def test_changed_legacy_implementation_rejected(tmp_path, monkeypatch):
    changed = tmp_path / "core_source_inputs.py"
    changed.write_bytes(formal.LEGACY_PATH.read_bytes() + b"\n# altered\n")
    monkeypatch.setattr(formal, "LEGACY_PATH", changed)
    with pytest.raises(ValueError, match="historical_input_implementation_changed"):
        formal.checked_policy()


@pytest.mark.parametrize("part", ["sos_hex", "zi_hex", "sos_sha256", "zi_sha256"])
def test_changed_registered_profile_rejected(part, monkeypatch):
    policy = copy.deepcopy(formal.checked_policy())
    entry = policy["rates"]["250"]["mu"]
    if part.endswith("hex"):
        entry[part][0][0] = float.fromhex(entry[part][0][0]).__add__(.001).hex()
    else:
        entry[part] = "0" * 64
    monkeypatch.setattr(formal, "checked_policy", lambda: policy)
    with pytest.raises(ValueError, match="explicit_filter_coefficient_identity_changed"):
        formal.coefficients(250, "mu")


def test_generated_sos_drift_is_not_hidden_by_fixed_profile(monkeypatch):
    butter = formal.legacy.butter
    def changed(*a, **k):
        value = butter(*a, **k)
        value[0, 0] += .0001
        return value
    monkeypatch.setattr(formal.legacy, "butter", changed)
    with pytest.raises(ValueError, match="explicit_filter_coefficient_identity_changed"):
        formal.coefficients(250, "mu")


def test_identity_keeps_legacy_provenance_and_unknown_historical_machine(config):
    identity = formal.numerical_identity()
    assert identity["historical_generation_BLAS_identity_established"] is False
    assert identity["state_application"] == "every_band_every_trial_source_and_target"
    assert identity["historical_loader_sha256"] == hashlib.sha256(formal.LEGACY_PATH.read_bytes()).hexdigest()
    assert identity["execution_module_sha256"] == hashlib.sha256(Path(formal.__file__).read_bytes()).hexdigest()
    assert formal.input_contract(config)["numerical_execution"] == identity
    assert formal.input_contract(config)["loader_sha256"] == identity["execution_module_sha256"]
    assert formal.input_contract(config)["historical_loader_sha256"] == formal.LEGACY_SHA256


def test_adapter_has_no_trial_specific_repair_or_candidate_profile_argument():
    assert list(inspect.signature(formal.transform_context19).parameters) == [
        "signal_channels_time", "sfreq", "cue_zero_based", "config", "bounds"]
    assert list(inspect.signature(formal.coefficients).parameters) == ["sfreq", "band"]
    source = inspect.getsource(formal.transform_context19)
    assert "sample_id" not in source and "expected_hash" not in source and "sosfiltfilt" not in source
    assert "counterfactual" not in source and "SELECTED" not in source


def test_actual_consumers_share_the_formal_loader_without_legacy_monkeypatch():
    import prepare_data
    import train_exploratory
    import validate_source
    assert prepare_data.source.load_source19 is formal.load_source19
    assert train_exploratory.load_source19 is formal.load_source19
    assert validate_source.load_source19 is formal.load_source19
    assert prepare_data.source.transform_context19 is formal.transform_context19
    assert formal.legacy.load_source19 is not formal.load_source19
    assert formal.legacy.transform_context19 is not formal.transform_context19
    assert hashlib.sha256(formal.LEGACY_PATH.read_bytes()).hexdigest() == formal.LEGACY_SHA256


@pytest.fixture
def synthetic_source_fingerprints(tmp_path, monkeypatch):
    """Tiny synthetic trial arrays, with real per-trial byte hashes.

    Production loader separately enforces [2592,19,320]. This gate fixture uses
    small trial shapes and substitutes only the fixed receipt identity check;
    all CSV and numerical hashes are actually calculated from fixture bytes.
    """
    folder = tmp_path / "research_runs/REDESIGN_EXPLORATORY_20261013/evidence"
    folder.mkdir(parents=True)
    rows = [{"sample_id": f"synthetic-{i:04d}"} for i in range(2592)]
    arrays = {band: (np.arange(2592 * 3, dtype=np.float32).reshape(2592, 1, 3) + offset)
              for offset, band in enumerate(formal.BANDS)}
    path = folder / "source_exact_input_fingerprints.csv"
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["source_sample_id", "broad_sha256", "mu_sha256", "beta_sha256"])
        writer.writeheader()
        for i, row in enumerate(rows):
            writer.writerow({"source_sample_id": row["sample_id"],
                             **{band + "_sha256": formal.array_hash(value[i]) for band, value in arrays.items()}})
    audit = {"array_hashes": {band: formal.array_hash(value) for band, value in arrays.items()},
             "source_labels_sha256": "synthetic-labels", "source_metadata_sha256": "synthetic-metadata",
             "source_sample_ids_sha256": "synthetic-IDs"}
    receipt = folder / "source_exact_input_fingerprints_receipt.json"
    receipt.write_text(json.dumps({"reference_sha256": formal.file_hash(path), "source_file_provenance": audit}))
    actual_hash = formal.file_hash
    def fixture_hash(file):
        if Path(file) == receipt:
            return "66c5aa472809cf29fe68b7b56401c4f0aa4b4f577156425a1f4e1fc20d45d8dd"
        return actual_hash(file)
    monkeypatch.setattr(formal, "ROOT", tmp_path)
    monkeypatch.setattr(formal, "file_hash", fixture_hash)
    return arrays, rows, audit, path


def test_full_source_gate_requires_every_trial_byte_hash(synthetic_source_fingerprints):
    arrays, rows, audit, _ = synthetic_source_fingerprints
    assert formal.verify_source_inputs(arrays, rows, audit) is True


@pytest.mark.parametrize("band", ["broad", "mu", "beta"])
def test_one_float32_ulp_change_has_no_tolerance_or_trial_exception(synthetic_source_fingerprints, band):
    arrays, rows, audit, _ = synthetic_source_fingerprints
    arrays[band][1437, 0, 1] = np.nextafter(arrays[band][1437, 0, 1], np.float32(np.inf))
    with pytest.raises(ValueError, match="frozen_source_trial_changed:" + band):
        formal.verify_source_inputs(arrays, rows, audit)


@pytest.mark.parametrize("key", ["array_hashes", "source_labels_sha256", "source_metadata_sha256", "source_sample_ids_sha256"])
def test_old_source_aggregate_and_identity_hashes_are_not_replaceable(synthetic_source_fingerprints, key):
    arrays, rows, audit, _ = synthetic_source_fingerprints
    audit[key] = {"mu": "changed"} if key == "array_hashes" else "changed"
    with pytest.raises(ValueError, match="frozen_source_input_changed:" + key):
        formal.verify_source_inputs(arrays, rows, audit)


def test_source_ID_order_cannot_be_replaced_or_reordered(synthetic_source_fingerprints):
    arrays, rows, audit, _ = synthetic_source_fingerprints
    rows[0], rows[1] = rows[1], rows[0]
    with pytest.raises(ValueError, match="source_trial_order_changed"):
        formal.verify_source_inputs(arrays, rows, audit)


def test_incomplete_source_inventory_is_blocked(synthetic_source_fingerprints):
    arrays, rows, audit, _ = synthetic_source_fingerprints
    with pytest.raises(ValueError, match="full_source_reference_inventory_required"):
        formal.verify_source_inputs(arrays, rows[:-1], audit)


def test_changed_per_trial_reference_is_blocked(synthetic_source_fingerprints):
    arrays, rows, audit, path = synthetic_source_fingerprints
    with path.open("a") as stream:
        stream.write("altered\n")
    with pytest.raises(ValueError, match="frozen_source_trial_reference_changed"):
        formal.verify_source_inputs(arrays, rows, audit)


def test_formal_module_and_policy_are_mandatory_public_freeze_dependencies(tmp_path):
    import train_exploratory as train
    job = tmp_path / "job"
    data = {key: str(job / "qc" / name) for key, name in
            (("roster_path", "raw_only_roster.json"), ("raw_qc_report_path", "full_raw_qc_report.json"),
             ("tensor_cache_receipt_path", "tensor_cache_receipt.json"))}
    required = set(train.required_execution_paths(job, data))
    assert STUDY / "scripts/formal_core_inputs.py" in required
    assert STUDY / "config/numerical_execution_v1.json" in required
    assert STUDY / "scripts/numerical_review_gate.py" in required
    assert job / "numerical_execution_review.json" in required
    assert job / "formal_source_acceptance.json" in required
    handoff = ROOT / "research_runs/REDESIGN_HANDOFF_20261014/formal_numerical_execution"
    assert {handoff / name for name in ("accept_source_numerics.py", "audit_full_diagnostic_bundle.py",
                                       "OPERATION_AMENDMENT.md")} <= required


@pytest.mark.parametrize("identity", [None, {}, {"policy_sha256": "0" * 64}])
def test_prior_preparation_receipt_does_not_authorize_new_numerical_adapter(tmp_path, identity):
    import train_exploratory as train
    with pytest.raises(ValueError, match="Prepared numerical execution identity differs"):
        train.validate_prepared_data(tmp_path, {"numerical_execution": identity}, tmp_path / "source")


@pytest.fixture
def reviewed_synthetic_acceptance(tmp_path):
    import numerical_review_gate as gate
    acceptance = {"synthetic_fixture": True,
        "status": "SOURCE_NUMERICAL_ACCEPTANCE_MATCH_TRAINING_STILL_BLOCKED",
        "numerical_execution": formal.numerical_identity(),
        "source_complete_exact_hash_gate_passed": True, "training_consumer_imports_verified": True,
        "private_full_package_independently_verified": True,
        "private_full_package_sha256": gate.FULL_PACKAGE_SHA, "training_authorization": False}
    path = tmp_path / "formal_source_acceptance.json"
    path.write_text(json.dumps(acceptance))
    review = {"synthetic_fixture": True,
        "status": "PASS_FORMAL_SOURCE_NUMERICAL_REVIEW_TARGET_GATES_REQUIRED",
        "numerical_execution": formal.numerical_identity(), "source_acceptance_sha256": gate.sha(path),
        "private_full_package_sha256": gate.FULL_PACKAGE_SHA}
    (tmp_path / "numerical_execution_review.json").write_text(json.dumps(review))
    return tmp_path, acceptance, review


def test_explicit_review_and_acceptance_are_hash_bound_but_still_not_training_authorization(reviewed_synthetic_acceptance):
    import numerical_review_gate as gate
    job, acceptance, review = reviewed_synthetic_acceptance
    original = {p.name: p.read_bytes() for p in job.iterdir()}
    assert gate.verify_review(job) == review
    assert acceptance["training_authorization"] is False
    assert {p.name: p.read_bytes() for p in job.iterdir()} == original


@pytest.mark.parametrize("key,value", [("status", "PASS"), ("numerical_execution", {}),
    ("source_acceptance_sha256", "0" * 64), ("private_full_package_sha256", "0" * 64)])
def test_review_identity_or_source_acceptance_binding_changed_is_blocked(reviewed_synthetic_acceptance, key, value):
    import numerical_review_gate as gate
    job, _, review = reviewed_synthetic_acceptance
    review[key] = value
    (job / "numerical_execution_review.json").write_text(json.dumps(review))
    with pytest.raises(ValueError, match="formal_numerical_review_absent_or_changed"):
        gate.verify_review(job)


@pytest.mark.parametrize("key,value", [("status", "FULL_DIAGNOSTIC_MATCH_TRAINING_STILL_BLOCKED"),
    ("numerical_execution", {}), ("source_complete_exact_hash_gate_passed", False),
    ("training_consumer_imports_verified", False), ("private_full_package_independently_verified", False),
    ("private_full_package_sha256", "0" * 64), ("training_authorization", True)])
def test_diagnostic_status_or_unverified_acceptance_cannot_open_review(reviewed_synthetic_acceptance, key, value):
    import numerical_review_gate as gate
    job, acceptance, review = reviewed_synthetic_acceptance
    acceptance[key] = value
    path = job / "formal_source_acceptance.json"
    path.write_text(json.dumps(acceptance))
    # Even a review bound to these changed bytes cannot make the acceptance true.
    review["source_acceptance_sha256"] = gate.sha(path)
    (job / "numerical_execution_review.json").write_text(json.dumps(review))
    with pytest.raises(ValueError, match="actual_formal_source_acceptance_required"):
        gate.verify_review(job)


@pytest.mark.parametrize("name", ["formal_source_acceptance.json", "numerical_execution_review.json"])
def test_missing_review_artifact_blocks_before_data_preparation(reviewed_synthetic_acceptance, name):
    import numerical_review_gate as gate
    job, _, _ = reviewed_synthetic_acceptance
    (job / name).unlink()
    with pytest.raises(ValueError, match="required_regular_record_absent"):
        gate.verify_review(job)


def test_absent_review_blocks_preparation_before_network_or_created_cache(tmp_path, monkeypatch):
    import prepare_data
    import r2_only
    monkeypatch.setattr(r2_only, "import_from_environment", lambda *a: pytest.fail("No network allowed before review"))
    job, data = tmp_path / "job", tmp_path / "data"
    with pytest.raises(ValueError, match="required_regular_record_absent"):
        prepare_data.prepare(job, data)
    assert not job.exists() and not data.exists()


@pytest.mark.parametrize("binding", [None, {}, {"policy_sha256": "0" * 64}])
def test_stale_source_numerics_block_inference_source_inventory(tmp_path, monkeypatch, binding):
    import test_infer_exploratory as old_tests
    import infer_exploratory as inference
    job, config = old_tests.source_fixture(tmp_path, monkeypatch)
    path = job / "source/source19_input_audit.json"
    audit = json.loads(path.read_text())
    audit["preprocessing"]["numerical_execution"] = binding
    path.write_text(json.dumps(audit))
    with pytest.raises(ValueError, match="source_actual_numerical_execution_not_bound"):
        inference.source_cells(job, config)


@pytest.fixture
def synthetic_target_metadata(tmp_path, monkeypatch):
    import infer_exploratory as inference
    import analyze_redesign_scores
    people = [f"synthetic-{i:02d}" for i in range(85)]
    events = [{"synthetic": True} for _ in range(6800)]
    monkeypatch.setattr(analyze_redesign_scores, "validate_contract", lambda *a: (people, events))
    target = tmp_path / "target"
    target.mkdir()
    roster = {"independent_confirmation_qualified": False, "evidence_class": inference.RESULT_ROLE,
              "prior_use": "unknown", "synthetic_fixture": False, "target_predictions_computed": False,
              "performance_used_for_eligibility": False, "technical_exclusions": ["A17", "A41"]}
    roster_path = target / "raw_only_roster.json"
    roster_path.write_text(json.dumps(roster))
    tensor = {"target_fits": 0, "target_predictions_computed": False,
              "numerical_execution": formal.numerical_identity(),
              "files": [{"subject_id": person} for person in people]}
    tensor_path = target / "tensor_cache_receipt.json"
    tensor_path.write_text(json.dumps(tensor))
    audit = {"status": "PASS_RAW_ONLY_FULL_COHORT_QC_EXPLORATORY_OPERATIONAL_SCOPE",
             "all_174_files_examined": True, "full_physical_signal_scan_passed": True,
             "roster_sha256": inference.sha(roster_path), "independent_confirmation_qualified": False,
             "target_fits": 0, "target_predictions_computed": False,
             "n_retained_participants": 85, "n_eligible_events": 6800,
             "tensor_cache_receipt_sha256": inference.sha(tensor_path)}
    (target / "full_raw_qc_report.json").write_text(json.dumps(audit))
    return tmp_path, tensor, audit


def test_target_metadata_requires_same_formal_numerics_identity(synthetic_target_metadata):
    import infer_exploratory as inference
    job, tensor, _ = synthetic_target_metadata
    _, accepted = inference.target_metadata(job)
    assert accepted == tensor


@pytest.mark.parametrize("binding", [None, {}, {"policy_sha256": "0" * 64}])
def test_missing_or_stale_target_numerics_cannot_be_rescued_by_matching_receipt_sha(synthetic_target_metadata, binding):
    import infer_exploratory as inference
    job, tensor, audit = synthetic_target_metadata
    tensor["numerical_execution"] = binding
    path = job / "target/tensor_cache_receipt.json"
    path.write_text(json.dumps(tensor))
    audit["tensor_cache_receipt_sha256"] = inference.sha(path)
    (job / "target/full_raw_qc_report.json").write_text(json.dumps(audit))
    with pytest.raises(ValueError, match="target_tensor_numerical_execution_not_bound"):
        inference.target_metadata(job)
