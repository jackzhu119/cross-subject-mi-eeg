"""Q15-E005 source-only local tests. Never fit a real model or touch cloud."""

from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from scripts import q15_source


def test_q15_derivation_changes_only_predeclared_window_and_channel_shape():
    q14 = q15_source._json(q15_source.Q14_CONFIG)
    derived = q15_source.derive_config()
    assert derived["channels"] == [name for name in q14["channels"] if name != "FCz"]
    assert derived["architecture"]["n_chans"] == 21
    assert derived["architecture"]["n_times"] == derived["n_times"] == 320
    assert (derived["source_trial_start_s"], derived["source_trial_stop_exclusive_s"]) == (2.5, 4.5)
    assert derived["q14_e002_inner_groups"] == [[1, 2], [3, 4], [5, 6], [7, 8, 9]]
    for field in ("bands_hz", "filter", "artifact_policy", "selection_seed", "final_seeds", "max_epochs", "batch_size", "learning_rate", "weight_decay", "source_subjects", "class_map"):
        assert derived[field] == q14[field]
    assert 2 * (len(derived["q14_e002_inner_groups"]) + len(derived["final_seeds"])) == 14


def test_transform_drops_only_fcz_and_preserves_320_sample_shape():
    config = q15_source.derive_config()
    original = np.zeros((2, 22, 500), dtype=np.float32)
    original[:, 3, :] = 100  # FCz must not leak into the new 21-channel model.
    indices = [idx for idx in range(22) if idx != 3]
    result = q15_source.transform_bands({"broad": original}, indices, config, 2)
    assert result["broad"].shape == (2, 21, 320)
    assert np.array_equal(result["broad"], np.zeros((2, 21, 320), dtype=np.float32))
    assert result["broad"].flags.c_contiguous
    with pytest.raises(AssertionError, match="Unexpected Q15"):
        q15_source.transform_bands({"broad": original[:, :, :499]}, indices, config, 2)


def test_real_source_execution_stops_before_any_bnci_file_read(monkeypatch, tmp_path):
    def blocked():
        raise AssertionError("pre-fit freeze missing")

    def should_not_reach(*_args, **_kwargs):
        raise AssertionError("BNCI files were read before freeze")

    monkeypatch.setattr(q15_source, "_verify_committed_freeze", blocked)
    monkeypatch.setattr(q15_source.q14_source, "source_file_receipt", should_not_reach)
    with pytest.raises(AssertionError, match="pre-fit freeze missing"):
        q15_source.run_source(tmp_path, "cpu")


def test_even_two_eligible_metadata_receipts_need_a_separately_committed_freeze(monkeypatch, tmp_path):
    monkeypatch.setattr(q15_source, "preflight_metadata", lambda: {
        "Lee2019_MI": {"status": "metadata_passed_non_authorizing"},
        "Cho2017": {"status": "metadata_passed_non_authorizing"},
    })
    monkeypatch.setattr(q15_source, "FREEZE", tmp_path / "missing_pre_fit_freeze.json")
    with pytest.raises(AssertionError, match="pre-fit freeze missing"):
        q15_source._verify_committed_freeze()


@pytest.mark.parametrize("status", [
    "blocked_raw_adapter_unverified",
    "metadata_passed_non_authorizing_synthetic_fixture",
])
def test_blocked_and_synthetic_metadata_cannot_release_source_fits(tmp_path, status):
    path = tmp_path / "metadata_audit_receipt.json"
    path.write_text(json.dumps({"schema_version": 1, "dataset": "Lee2019_MI", "status": status}), encoding="utf-8")
    with pytest.raises(AssertionError, match="raw audit has not passed"):
        q15_source._replay_metadata_receipt("Lee2019_MI", path, ["C3"])


def test_unauthenticated_provider_inventory_cannot_release_source_fits(tmp_path):
    path = tmp_path / "metadata_audit_receipt.json"
    payload = {
        "schema_version": 1, "dataset": "Lee2019_MI",
        "status": "metadata_passed_non_authorizing",
        "metadata_only": True, "raw_hashes_verified": True,
        "provider_inventory_verified": True,
        "provider_manifest_authenticated": False,
        "all_expected_files_hashed": True,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(AssertionError, match="raw provenance"):
        q15_source._replay_metadata_receipt("Lee2019_MI", path, ["C3"])
    modified = copy.deepcopy(payload)
    modified["provider_manifest_authenticated"] = True
    modified["synthetic_fixture"] = True
    path.write_text(json.dumps(modified), encoding="utf-8")
    with pytest.raises(AssertionError, match="synthetic or outcome-contaminated"):
        q15_source._replay_metadata_receipt("Lee2019_MI", path, ["C3"])


def test_shared_two_band_model_shape_only_cpu():
    import torch

    config = q15_source.derive_config()
    model = q15_source._build_model("MU_BETA_SHARED", config, torch.device("cpu"))
    with torch.inference_mode():
        output = model(torch.zeros(2, 2, 21, 320))
    assert tuple(output.shape) == (2, 2)
    with pytest.raises(ValueError, match="Expected"):
        model(torch.zeros(1, 2, 22, 320))
