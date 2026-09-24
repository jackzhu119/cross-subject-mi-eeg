"""Q11 protocol, pure scientific validator and optional CPU shape tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts import q11_batch
from scripts.validate_q11_e001 import holm_adjust, independent_epoch, validate_predictions

ROOT = Path(__file__).resolve().parents[1]


def test_q11_matrix_is_four_declared_conditions_and_252_new_fits() -> None:
    matrix = json.loads((ROOT / "research_runs/Q11-E001/MATRIX.json").read_text(encoding="utf-8"))
    names = [row["name"] for row in matrix["conditions"]]
    assert names == list(q11_batch.CONDITIONS)
    assert len(names) == len(set(names)) == 4
    assert sum(row["inner_fits"] for row in matrix["conditions"]) == 144
    assert sum(row["final_fits"] for row in matrix["conditions"]) == 108
    assert matrix["totals"]["deep_fits"] == 252
    assert matrix["target_statistics_for_fit_or_selection"] is False
    assert matrix["conditions"][0]["bands"] == {
        "b1": [8, 12], "b2": [12, 16], "b3": [16, 22], "b4": [22, 30]
    }


def test_q11_batch_has_selection_then_final_and_fixed_count(tmp_path: Path) -> None:
    from scripts import q9_batch

    matrix = ROOT / "research_runs/Q11-E001/MATRIX.json"
    templates = {"neural": ["python", "q11", "{condition}", "{phase}"],
                 "psd": ["python", "noop"]}
    manifest = q9_batch.build_manifest(matrix, templates, list(q11_batch.CONDITIONS),
                                       tmp_path, tmp_path / "results", "cuda", "python")
    assert len(manifest["jobs"]) == 8
    assert [job["phase"] for job in manifest["jobs"]] == ["selection", "final"] * 4
    assert manifest["selected_fit_counts"] == {
        "deep_inner": 144, "deep_final": 108, "shallow_source": 0
    }


def test_independent_selection_uses_within_fold_ranks_and_earliest_tie() -> None:
    curves = []
    for inner in range(4):
        values = np.arange(40, 0, -1, dtype=float)
        if inner % 2:
            values = values[::-1]
        curves.append(pd.DataFrame({"epoch": np.arange(1, 41), "val_ce": values}))
    assert independent_epoch(curves) == 1
    curves[0].loc[0, "val_ce"] = np.nan
    with pytest.raises(AssertionError, match="nonfinite"):
        independent_epoch(curves)


def test_holm_adjustment_is_step_down_within_declared_family() -> None:
    adjusted = holm_adjust({"a": 0.01, "b": 0.02, "c": 0.50, "d": 0.80})
    assert adjusted == {"a": 0.04, "b": 0.06, "c": 1.0, "d": 1.0}


def _prediction_fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    labels = np.repeat(np.arange(1, 5), 144)
    reference = pd.DataFrame({
        "sample_id": [f"trial_{i}" for i in range(576)],
        "subject": 1, "session": ["0train"] * 288 + ["1test"] * 288,
        "label": labels, "artifact_flagged": [False] * 576,
    })
    frame = reference.copy()
    frame["experiment_id"] = "Q11-E001"
    frame["condition"] = "FOUR_BAND_SHARED"
    frame["fold"] = "loso_s1"
    frame["seed"] = 20260924
    frame["selected_epochs"] = 7
    frame["selection_rule"] = "mean_rank"
    frame["y_true"] = labels
    frame["y_pred"] = labels
    for cls in range(1, 5):
        frame[f"p_class_{cls}"] = (labels == cls).astype(float)
    return frame, reference


def test_prediction_audit_recomputes_identity_probability_and_ba() -> None:
    frame, reference = _prediction_fixture()
    result = validate_predictions(frame, reference, subject=1, seed=20260924,
                                  condition="FOUR_BAND_SHARED", selected=7)
    assert result["balanced_accuracy"] == 1.0
    frame.loc[0, "p_class_1"] = 0.8
    with pytest.raises(AssertionError, match="probabilities"):
        validate_predictions(frame, reference, subject=1, seed=20260924,
                             condition="FOUR_BAND_SHARED", selected=7)


def test_architecture_counts_and_fusion_output_are_data_free() -> None:
    pytest.importorskip("torch")
    pytest.importorskip("braindecode")
    import torch

    from scripts.q11_neural import BandFusion, _capacity_plan, parameter_count

    base = json.loads((ROOT / "research_runs/Q8-E001/results/config.json").read_text(encoding="utf-8"))["architecture"]
    plan = _capacity_plan(base)
    assert plan["reference_independent_two_branch_count"] == 2 * plan["reference_single_branch_count"]
    assert plan["chosen"] == min(plan["candidates"], key=lambda row: (
        abs(row["parameter_count"] - plan["reference_independent_two_branch_count"]), row["F1"]))
    shared = BandFusion(base, 4, False, torch.device("cpu"))
    independent = BandFusion(base, 2, True, torch.device("cpu"))
    assert parameter_count(shared) == plan["reference_single_branch_count"]
    assert parameter_count(independent) == plan["reference_independent_two_branch_count"]
    with torch.inference_mode():
        assert tuple(shared(torch.zeros(2, 4, 22, 750)).shape) == (2, 4)
        assert tuple(independent(torch.zeros(2, 2, 22, 750)).shape) == (2, 4)
