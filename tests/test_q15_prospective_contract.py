"""Synthetic fail-closed checks for the prospective Q15 metadata contract."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "research_runs/PAPER_RELEASE_20260927/q15_validate_contract.py"
SPEC = importlib.util.spec_from_file_location("q15_validate_contract", MODULE)
assert SPEC is not None and SPEC.loader is not None
q15 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q15)


def _synthetic_receipt():
    channels = q15._read(q15.CONTRACT)["new_source_arm"]["channels"]
    files = []
    for subject in (1, 2):
        for session in ("1", "2"):
            file_id = f"s{subject:02d}_session{session}_offline_MI"
            files.append({
                "file_id": file_id, "subject": subject, "session": session,
                "run": "offline_MI", "sha256": "a" * 64,
                "channels": channels + ["Oz"], "sampling_rate_hz": 1000,
                "native_physical_unit": "uV", "loader_output_unit": "V",
                "unit_conversion": "multiply by 1e-6", "reference": "nasion",
                "cue_origin": "MI_cue_onset", "task": "left_right_motor_imagery",
                "labeled": True, "label_map": {"left_hand": 2, "right_hand": 1},
                "available_cue_window_s": [0.0, 4.0],
            })
    return {
        "dataset": "Lee2019_MI", "metadata_only": True,
        "predictions_computed": False, "model_predictions_computed": False,
        "performance_metrics_computed": False,
        "target_fits": 0, "provider_version": "synthetic-v1",
        "loader_version": "synthetic", "license": "test-only",
        "provider_inventory_source": "synthetic manifest", "all_expected_files_hashed": True,
        "failed_files": [], "expected_file_ids": [item["file_id"] for item in files],
        "files": files,
    }, {"dataset": "Lee2019_MI", "expected_subjects": 2, "expected_sessions_per_subject": 2}, channels


def test_static_plan_is_consistent_but_does_not_release_external_prediction():
    result = q15.validate_contract()
    assert result["new_source_deep_fits_planned"] == 14
    assert result["new_source_shallow_fits_planned"] == 1
    assert result["external_prediction_authorized"] is False


def test_synthetic_receipt_remains_non_authorizing():
    receipt, spec, channels = _synthetic_receipt()
    result = q15.validate_metadata_receipt(receipt, spec, channels)
    assert result["subjects"] == 2
    assert result["external_prediction_authorized"] is False


@pytest.mark.parametrize("mutation", [
    lambda r: r["files"][0]["channels"].remove("C3"),
    lambda r: r["files"][0].update(cue_origin="trial_start"),
    lambda r: r["files"][0].update(available_cue_window_s=[0.0, 2.0]),
    lambda r: r.update(performance_metrics_computed=True),
    lambda r: r.update(predictions_computed=True),
    lambda r: r.update(target_fits=1),
    lambda r: r["files"].pop(),
    lambda r: r.update(failed_files=["corrupt.mat"]),
    lambda r: r["files"][0].update(sha256="missing"),
    lambda r: r["files"][0].update(label_map={"left_hand": 1}),
])
def test_metadata_contract_fails_closed(mutation):
    receipt, spec, channels = _synthetic_receipt()
    bad = copy.deepcopy(receipt)
    mutation(bad)
    with pytest.raises(AssertionError):
        q15.validate_metadata_receipt(bad, spec, channels)
