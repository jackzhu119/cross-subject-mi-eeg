"""Regression gates for the Q14-R2 aggregate CSV precision erratum."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.publish_research_run import _inside_results
from scripts.q14_r2_finalize import BATCH, ROOT
from scripts.q14_r2_numeric import assert_aggregate_matches_subjects


def _rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sample_id": ["trial_1", "trial_2"],
            "subject": [1, 1],
            "label": [1, 2],
            "model": ["BROAD_EEGNET", "BROAD_EEGNET"],
            "seed": [20260924, 20260924],
            "p_left": [0.41424790024757385, 0.07571657001972198],
            "p_right": [0.5857520699501038, 0.9242834448814392],
            "predicted_label": [2, 2],
        }
    )


def test_double_csv_serialization_precision_is_allowed() -> None:
    source = _rows()
    saved = source.copy()
    saved.loc[0, "p_left"] = 0.4142479002475738
    saved.loc[1, "p_right"] = 0.924283444881439
    assert_aggregate_matches_subjects(source, saved)


def test_material_probability_change_is_rejected() -> None:
    source = _rows()
    changed = source.copy()
    changed.loc[0, "p_left"] += 1e-8
    with pytest.raises(AssertionError):
        assert_aggregate_matches_subjects(source, changed)


@pytest.mark.parametrize("change", ["label", "predicted_label", "order"])
def test_discrete_change_or_row_shuffle_is_rejected(change: str) -> None:
    source = _rows()
    changed = source.copy()
    if change == "order":
        changed = changed.iloc[::-1].reset_index(drop=True)
    elif change == "label":
        changed.loc[0, "label"] = 2
    else:
        changed.loc[0, "predicted_label"] = 1
    with pytest.raises(AssertionError):
        assert_aggregate_matches_subjects(source, changed)


def test_published_109_subject_aggregate_matches_immutable_subject_files() -> None:
    root = Path(__file__).resolve().parents[1]
    external = root / "results" / "Q14-E002R2" / "external"
    reconstructed = pd.concat(
        [pd.read_csv(external / f"subject_{subject:03d}" / "predictions.csv")
         for subject in range(1, 110)],
        ignore_index=True,
    )
    saved = pd.read_csv(external / "predictions.csv")
    assert_aggregate_matches_subjects(reconstructed, saved)


def test_q14_validation_only_batch_is_publishable_named_results_child() -> None:
    assert _inside_results(ROOT, BATCH) == BATCH.resolve()
