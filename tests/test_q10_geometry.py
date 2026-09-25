"""Small source-only and frozen-contract checks for Q10-A001."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.q10_geometry import (
    CLASSES,
    MATRIX,
    assert_q8_identity,
    fit_predict_source_only,
    logcov_features,
    q8_metadata_contract_sha256,
    read_matrix,
    read_q8_metadata,
    source_target_indices,
)


def test_frozen_geometry_matrix_and_q8_metadata() -> None:
    matrix = read_matrix(MATRIX)
    q8 = read_q8_metadata(matrix)
    assert len(matrix["conditions"]) == 4
    assert len(q8) == 5184
    assert_q8_identity(q8.copy(), q8)
    for subject in range(1, 10):
        source, target = source_target_indices(q8, subject)
        assert len(source) == 4608 and len(target) == 576
        assert set(q8.iloc[source].subject) == set(range(1, 10)) - {subject}
        assert set(q8.iloc[target].subject) == {subject}


def test_q8_metadata_contract_hash_is_cross_platform_but_not_content_blind(
    tmp_path: Path,
) -> None:
    path = tmp_path / "trial_metadata.csv"
    path.write_bytes(b"sample_id,label\r\ntrial_1,1\r\n")
    expected = q8_metadata_contract_sha256(path)
    path.write_bytes(b"sample_id,label\ntrial_1,1\n")
    assert q8_metadata_contract_sha256(path) == expected
    path.write_bytes(b"sample_id,label\ntrial_1,2\n")
    assert q8_metadata_contract_sha256(path) != expected
    path.write_bytes(b"sample_id,label\rtrial_1,1\r")
    with pytest.raises(AssertionError, match="unsupported carriage returns"):
        q8_metadata_contract_sha256(path)


def test_identity_rejects_changed_target_label() -> None:
    matrix = read_matrix(MATRIX)
    q8 = read_q8_metadata(matrix)
    mutated = q8.copy()
    mutated.loc[0, "label"] = 1 if q8.loc[0, "label"] != 1 else 2
    with pytest.raises(AssertionError, match="differs"):
        assert_q8_identity(mutated, q8)


def test_logcov_is_per_trial_and_spd() -> None:
    rng = np.random.default_rng(19)
    trials = rng.normal(size=(5, 4, 80)).astype(np.float32)
    all_features = logcov_features(trials, .01, chunk_size=2)
    assert all_features.shape == (5, 10)
    assert np.isfinite(all_features).all()
    # Adding unrelated trials or shifting channel DC offsets cannot alter
    # the log covariance of a particular trial.
    changed = np.concatenate([trials[:1], rng.normal(size=(7, 4, 80))], axis=0)
    assert np.allclose(all_features[0], logcov_features(changed, .01)[0])
    shifted = trials[:1].copy() + np.array([1, -2, 3, 4])[None, :, None]
    assert np.allclose(all_features[0], logcov_features(shifted, .01)[0])


@pytest.mark.parametrize("classifier", ["log_euclidean_nearest_class_mean", "shrinkage_lda"])
def test_target_population_does_not_change_fit_parameters(classifier: str) -> None:
    rng = np.random.default_rng(4)
    labels = np.repeat(CLASSES, 20)
    source = rng.normal(size=(80, 8)) + labels[:, None] * .3
    target = rng.normal(size=(7, 8))
    condition = {"classifier": classifier, "solver": "lsqr", "shrinkage": "auto"}
    first, _model1, receipt1 = fit_predict_source_only(source, labels, target, condition)
    second, _model2, receipt2 = fit_predict_source_only(
        source, labels, np.concatenate([target, np.full((4, 8), 10_000.0)]), condition
    )
    assert receipt1 == receipt2
    assert np.allclose(first, second[:len(target)])
    assert np.allclose(first.sum(axis=1), 1)


def test_source_target_indices_rejects_incomplete_population() -> None:
    frame = pd.DataFrame({"subject": [1, 2], "label": [1, 2]})
    with pytest.raises(AssertionError, match="LOSO"):
        source_target_indices(frame, 1)
